from datetime import datetime, timedelta, timezone

from app.models import Category, Store
from app.routers import listings as listings_router
from app.scraper import cyber_scraper
from app.scraper.event_windows import CHILE, started_event_start
from app.scraper.parser import ScrapedOffer
from tests.test_highlights import _listing

START = datetime(2026, 10, 4, tzinfo=CHILE)


class FakeResponse:
    headers: dict = {}


def _titles(db, **filters):
    params = dict(category=None, store=None, search=None, min_discount=None, section=None, sort="discount",
                  page=1, page_size=30, response=FakeResponse(), db=db)
    return [l.title for l in listings_router.list_listings(**{**params, **filters})]


def test_cyber_prices_count_from_midnight_the_day_before():
    assert started_event_start(datetime(2026, 10, 4, 2, 59, tzinfo=timezone.utc)) is None
    assert started_event_start(datetime(2026, 10, 4, 3, 0, tzinfo=timezone.utc)) == START


def test_first_scrape_after_the_start_keeps_the_price_from_before(db_session, monkeypatch):
    def offer(price):
        return ScrapedOffer(store_slug="paris", store_name="Paris", category_slug="tecnologia", external_id="tv",
                            title="Smart TV 55", url="https://paris.cl/tv", price=price,
                            original_price=600_000, image_url=None)

    monkeypatch.setattr(cyber_scraper, "started_event_start", lambda: None)
    listing, _ = cyber_scraper.upsert_offer(db_session, offer(400_000), "tecnologia")
    listing.first_seen_at = START - timedelta(days=2)
    monkeypatch.setattr(cyber_scraper, "started_event_start", lambda: START)
    cyber_scraper.upsert_offer(db_session, offer(300_000), "tecnologia")
    cyber_scraper.upsert_offer(db_session, offer(280_000), "tecnologia")

    db_session.flush()
    db_session.refresh(listing)  # read back as Decimal, like from the database
    assert listing.pre_event_price == 400_000  # not overwritten by later Cyber prices
    assert listings_router._cyber_drop_pct(listing) == 30.0


def test_cyber_filter_keeps_drops_and_new_offers(db_session, monkeypatch):
    monkeypatch.setattr(listings_router, "started_event_start", lambda: START)
    tech = Category(name="Tecnología", slug="tecnologia")
    paris = Store(name="Paris", slug="paris")
    db_session.add_all([tech, paris])
    db_session.flush()
    before = START - timedelta(days=1)
    dropped = _listing(db_session, paris, tech, "Bajó en el Cyber", 300_000, 600_000)
    dropped.pre_event_price, dropped.first_seen_at = 400_000, before
    same = _listing(db_session, paris, tech, "Mismo precio", 300_000, 600_000)
    same.pre_event_price, same.first_seen_at = 300_000, before
    _listing(db_session, paris, tech, "Nueva en el Cyber", 100_000, 200_000).first_seen_at = START + timedelta(hours=1)
    db_session.flush()

    assert sorted(_titles(db_session, cyber=True)) == ["Bajó en el Cyber", "Nueva en el Cyber"]

    monkeypatch.setattr(listings_router, "started_event_start", lambda: None)
    assert _titles(db_session, cyber=True) == []


def test_top_sort_weighs_savings_and_buries_bogus_discounts(db_session):
    tech = Category(name="Tecnología", slug="tecnologia")
    paris = Store(name="Paris", slug="paris")
    db_session.add_all([tech, paris])
    db_session.flush()
    _listing(db_session, paris, tech, "Mouse -98%", 1_000, 50_000)  # bogus
    _listing(db_session, paris, tech, "Cable -78%", 2_000, 9_000)  # big discount, small savings
    _listing(db_session, paris, tech, "TV -60%", 300_000, 750_000)
    _listing(db_session, paris, tech, "Notebook -50%", 400_000, 800_000)
    db_session.flush()

    assert _titles(db_session, sort="top") == ["TV -60%", "Cable -78%", "Notebook -50%", "Mouse -98%"]
