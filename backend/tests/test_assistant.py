from app.models import Listing, PriceSnapshot, Product, Store
from app.services.assistant import _run_search


def _seed_catalog(db_session):
    falabella = Store(name="Falabella", slug="falabella")
    paris = Store(name="Paris", slug="paris")
    db_session.add_all([falabella, paris])
    db_session.flush()

    cheap_lenovo = Product(canonical_title="Notebook Lenovo IdeaPad 3", brand="Lenovo")
    pricey_lenovo = Product(canonical_title="Notebook Lenovo Legion Pro", brand="Lenovo")
    samsung_tv = Product(canonical_title="Smart TV Samsung 55", brand="Samsung")
    db_session.add_all([cheap_lenovo, pricey_lenovo, samsung_tv])
    db_session.flush()

    def add_listing(product, store, price, discount=None):
        listing = Listing(
            product_id=product.id,
            store_id=store.id,
            external_id=f"{store.slug}-{product.id}",
            title=product.canonical_title,
            url=f"https://{store.slug}.cl/p/{product.id}",
        )
        db_session.add(listing)
        db_session.flush()
        db_session.add(PriceSnapshot(listing_id=listing.id, price=price, discount_pct=discount))
        db_session.flush()

    add_listing(cheap_lenovo, falabella, 299990, discount=20)
    add_listing(pricey_lenovo, falabella, 1299990, discount=5)
    add_listing(samsung_tv, paris, 399990, discount=30)


def test_filters_by_brand_and_sorts_cheapest_first(db_session):
    _seed_catalog(db_session)
    results = _run_search(db_session, brand="Lenovo", sort="price_asc")
    assert [r["title"] for r in results] == ["Notebook Lenovo IdeaPad 3", "Notebook Lenovo Legion Pro"]
    assert results[0]["price"] == 299990


def test_filters_by_max_price(db_session):
    _seed_catalog(db_session)
    results = _run_search(db_session, brand="Lenovo", max_price=500000)
    assert len(results) == 1
    assert results[0]["title"] == "Notebook Lenovo IdeaPad 3"


def test_filters_by_store(db_session):
    _seed_catalog(db_session)
    results = _run_search(db_session, store="paris")
    assert len(results) == 1
    assert results[0]["store"] == "Paris"


def test_sort_by_discount(db_session):
    _seed_catalog(db_session)
    results = _run_search(db_session, sort="discount", limit=1)
    assert results[0]["title"] == "Smart TV Samsung 55"
