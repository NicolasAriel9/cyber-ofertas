"""The scrape loop writes a page of offers in a few batched statements and
still sends price-drop alerts for followed products."""

import asyncio

from sqlalchemy import event

from app.models import Favorite, Listing, PriceSnapshot, Subscriber
from app.scraper import cyber_scraper
from app.scraper.parser import ScrapedOffer
from app.scraper.stores.base import Department, StoreScraper
from app.services.matcher import ProductIndex


class FakeStore(StoreScraper):
    slug = "fake"
    name = "Fake"
    cyber_brand_name = "Fake"
    departments = [Department("tecnologia", "", "Todo")]

    def __init__(self, prices: dict[str, float]) -> None:
        self.prices = prices

    def fetch_page(self, client, department, page):
        offers = [
            ScrapedOffer(
                store_slug=self.slug,
                store_name=self.name,
                category_slug="tecnologia",
                external_id=external_id,
                title=f"Producto distinto numero {external_id} modelo {external_id}x",
                url=f"https://fake.cl/p/{external_id}",
                price=price,
                original_price=price * 2,
                image_url=None,
            )
            for external_id, price in self.prices.items()
        ]
        return offers, False


def scrape(db, store: FakeStore) -> int:
    return asyncio.run(cyber_scraper.scrape_store(db, None, store, ProductIndex(db), {}))


def count_selects(db, n_offers: int) -> int:
    statements = []
    listener = lambda *args: statements.append(args[2])  # noqa: E731
    event.listen(db.get_bind(), "before_cursor_execute", listener)
    try:
        assert scrape(db, FakeStore({f"{n_offers}-{i}": 1000.0 + i for i in range(n_offers)})) == n_offers
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", listener)
    # SQLite runs batched INSERTs as one statement per row, so count the
    # SELECTs: per-offer lookups are the round trips that used to scale.
    return sum(1 for s in statements if s.lstrip().upper().startswith("SELECT"))


def test_db_lookups_dont_grow_with_the_page_size(db_session):
    assert count_selects(db_session, 5) == count_selects(db_session, 50)
    assert db_session.query(Listing).count() == 55
    assert db_session.query(PriceSnapshot).count() == 55


def test_price_drop_on_a_followed_product_dispatches_an_alert(db_session, monkeypatch):
    scrape(db_session, FakeStore({"a": 1000.0, "b": 2000.0}))
    followed = db_session.query(Listing).filter(Listing.external_id == "a").one()
    subscriber = Subscriber(name="Nico")
    db_session.add(subscriber)
    db_session.flush()
    db_session.add(Favorite(subscriber_id=subscriber.id, product_id=followed.product_id))
    db_session.commit()

    dispatched = []

    async def fake_dispatch(db, listing, snapshot):
        assert snapshot.id is not None and len(listing.price_snapshots) == 2
        dispatched.append((listing.external_id, float(snapshot.price)))

    monkeypatch.setattr(cyber_scraper, "dispatch_alerts", fake_dispatch)
    scrape(db_session, FakeStore({"a": 800.0, "b": 1500.0, "c": 500.0}))

    # "b" dropped too but nobody follows it; "c" is new.
    assert dispatched == [("a", 800.0)]
    assert db_session.query(Listing).count() == 3


def test_an_unchanged_pass_writes_nothing(db_session):
    # Rewriting every offer on every pass exhausted the free database's I/O.
    prices = {f"same-{i}": 5000.0 + i for i in range(20)}
    scrape(db_session, FakeStore(prices))
    statements = []
    listener = lambda *args: statements.append(args[2])  # noqa: E731
    event.listen(db_session.get_bind(), "before_cursor_execute", listener)
    try:
        scrape(db_session, FakeStore(prices))
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", listener)
    # The full-sweep cleanup is one statement for the whole store, not per offer.
    writes = [s for s in statements if s.lstrip().upper().startswith(("UPDATE", "INSERT")) and "last_seen_at <" not in s]
    assert writes == []
