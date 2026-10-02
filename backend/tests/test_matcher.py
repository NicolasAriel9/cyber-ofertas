from app.models import Listing, PriceSnapshot
from app.services.matcher import find_or_create_product, normalize_title


def test_normalize_title_strips_punctuation_and_case():
    assert normalize_title("Notebook Lenovo  IdeaPad-3 (2024)!") == "notebook lenovo ideapad 3 2024"


def test_same_product_different_stores_is_matched(db_session):
    product_a = find_or_create_product(
        db_session,
        title="Notebook Lenovo IdeaPad 3 15.6\" 8GB RAM",
        price=349990,
        category_slug="tecnologia",
        brand="Lenovo",
        image_url=None,
    )
    listing = Listing(
        product_id=product_a.id,
        store_id=1,
        external_id="falabella-123",
        title="Notebook Lenovo IdeaPad 3 15.6\" 8GB RAM",
        url="https://falabella.com/p/123",
    )
    db_session.add(listing)
    db_session.flush()
    db_session.add(PriceSnapshot(listing_id=listing.id, price=349990))
    listing.current_price = 349990
    db_session.flush()

    product_b = find_or_create_product(
        db_session,
        title="Notebook Lenovo IdeaPad 3 15.6 8GB RAM",
        price=359990,
        category_slug="tecnologia",
        brand="Lenovo",
        image_url=None,
    )

    assert product_b.id == product_a.id


def test_different_products_are_not_matched(db_session):
    product_a = find_or_create_product(
        db_session,
        title="Notebook Lenovo IdeaPad 3",
        price=349990,
        category_slug="tecnologia",
        brand="Lenovo",
        image_url=None,
    )
    product_b = find_or_create_product(
        db_session,
        title="Refrigerador Samsung No Frost 400L",
        price=549990,
        category_slug="hogar",
        brand="Samsung",
        image_url=None,
    )

    assert product_a.id != product_b.id


def test_similar_title_but_very_different_price_is_not_matched(db_session):
    product_a = find_or_create_product(
        db_session,
        title="Smartphone Galaxy A15 128GB",
        price=129990,
        category_slug="tecnologia",
        brand="Samsung",
        image_url=None,
    )
    listing = Listing(
        product_id=product_a.id,
        store_id=1,
        external_id="paris-999",
        title="Smartphone Galaxy A15 128GB",
        url="https://paris.cl/p/999",
    )
    db_session.add(listing)
    db_session.flush()
    db_session.add(PriceSnapshot(listing_id=listing.id, price=129990))
    listing.current_price = 129990
    db_session.flush()

    # Same title but wildly different price -- likely a different storage
    # variant or a data error, shouldn't be silently merged.
    product_b = find_or_create_product(
        db_session,
        title="Smartphone Galaxy A15 128GB",
        price=899990,
        category_slug="tecnologia",
        brand="Samsung",
        image_url=None,
    )

    assert product_b.id != product_a.id


def test_same_model_different_screen_size_is_not_matched(db_session):
    product_a = find_or_create_product(
        db_session,
        title='55" Mini LED M70H 4K Vision AI Smart TV (2026)',
        price=399990,
        category_slug="tecnologia",
        brand="Samsung",
        image_url=None,
    )
    product_b = find_or_create_product(
        db_session,
        title='50" Mini LED M70H 4K Vision AI Smart TV (2026)',
        price=349990,
        category_slug="tecnologia",
        brand="Samsung",
        image_url=None,
    )

    assert product_a.id != product_b.id


def test_upsert_records_snapshot_only_when_price_changes(db_session):
    from app.models import PriceSnapshot
    from app.scraper.cyber_scraper import upsert_offer
    from app.scraper.parser import ScrapedOffer

    def offer(price):
        return ScrapedOffer("falabella", "Falabella", "tecnologia", "123", "Notebook X", "https://x", price, 500000, None)

    _, first = upsert_offer(db_session, offer(400000), "tecnologia")
    _, same = upsert_offer(db_session, offer(400000), "tecnologia")
    listing, dropped = upsert_offer(db_session, offer(350000), "tecnologia")

    assert first is not None and same is None and dropped is not None
    assert db_session.query(PriceSnapshot).count() == 2
    assert float(listing.current_price) == 350000
