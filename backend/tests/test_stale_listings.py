from datetime import timedelta

from app.models import Category, Store, utcnow
from app.routers import listings as listings_router
from app.routers.products import get_product
from app.routers.stores_categories import list_stores
from tests.test_highlights import _listing


class FakeResponse:
    headers: dict = {}


def test_offers_not_seen_for_a_day_are_hidden(db_session):
    tech = Category(name="Tecnología", slug="tecnologia")
    paris, ripley = Store(name="Paris", slug="paris"), Store(name="Ripley", slug="ripley")
    db_session.add_all([tech, paris, ripley])
    db_session.flush()
    fresh = _listing(db_session, paris, tech, "Notebook", 400_000, 800_000)
    # Same product at a store the scraper hasn't been able to read since yesterday.
    stale = _listing(db_session, ripley, tech, "Notebook Ripley", 350_000, 800_000, product=fresh.product)
    stale.last_seen_at = utcnow() - timedelta(hours=25)
    db_session.flush()

    listings = listings_router.list_listings(
        category=None, store=None, search=None, min_discount=None, section=None, sort="discount",
        page=1, page_size=30, response=FakeResponse(), db=db_session,
    )
    assert [l.title for l in listings] == ["Notebook"]
    assert [s.slug for s in list_stores(section=None, db=db_session)] == ["paris"]
    assert [l.store.slug for l in get_product(fresh.product_id, db=db_session).listings] == ["paris"]
