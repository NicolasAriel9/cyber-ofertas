import json

from app.models import Category, Store
from app.routers import listings as listings_router
from app.scraper.stores.base import parse_rating
from app.scraper.stores.cencosud import ParisScraper
from app.scraper.stores.falabella import parse_falabella_item
from app.scraper.stores.hites import parse_hites_ratings
from app.scraper.stores.mercadolibre import parse_card
from tests.test_highlights import _listing


def test_parse_rating_treats_zero_as_unrated():
    assert parse_rating("4.5676", "296") == (4.6, 296)
    assert parse_rating(0, 0) == (None, None)
    assert parse_rating(5, 0) == (None, None)
    assert parse_rating("4.8") == (4.8, None)
    assert parse_rating("n/a", "3") == (None, None)


def test_falabella_and_paris_carry_rating():
    item = {
        "productId": "123",
        "url": "https://www.falabella.com/p/123",
        "displayName": "Notebook",
        "prices": [{"type": "internetPrice", "price": ["499.990"]}, {"type": "normalPrice", "price": ["699.990"], "crossed": True}],
        "rating": "4.5676",
        "totalReviews": "296",
    }
    offer = parse_falabella_item(item, "falabella", "Falabella", "tecnologia")
    assert (offer.rating, offer.review_count) == (4.6, 296)

    result = {"value": "TV", "data": {"id": "1", "url": "https://paris.cl/tv.html", "displayedPrice": 100,
                                      "discountPercentage": 50, "averageRating": 5, "countRating": 1}}
    offer = ParisScraper().parse_item(result, "tecnologia")
    assert (offer.rating, offer.review_count) == (5.0, 1)


def test_hites_ratings_come_from_page_item_list():
    item_list = {
        "@type": "ItemList",
        "itemListElement": [
            {"item": {"sku": "961663001", "aggregateRating": {"ratingValue": "3.4", "reviewCount": 5}}},
            {"item": {"sku": "957680001"}},
        ],
    }
    page = f'<script type="application/ld+json">{json.dumps(item_list)}</script>'
    assert parse_hites_ratings(page) == {"961663001": (3.4, 5)}


def test_mercadolibre_reads_screen_reader_rating():
    card = (
        '<a href="https://www.mercadolibre.cl/parlante/p/MLC123" class="poly-component__title">Parlante</a>'
        '<span class="andes-visually-hidden">Calificación 4.8 de 5 estrellas. Más de 1000 productos vendidos.</span>'
        '<div class="poly-price__current"><span aria-label="19990 pesos"></span></div>'
    )
    offer = parse_card(card, "tecnologia")
    assert (offer.rating, offer.review_count) == (4.8, None)


def test_rating_sort_puts_well_reviewed_first(db_session):
    tech = Category(name="Tecnología", slug="tecnologia")
    paris = Store(name="Paris", slug="paris")
    db_session.add_all([tech, paris])
    db_session.flush()
    lucky = _listing(db_session, paris, tech, "Una reseña", 100, 200)
    lucky.rating, lucky.review_count = 5.0, 1
    solid = _listing(db_session, paris, tech, "Muchas reseñas", 100, 200)
    solid.rating, solid.review_count = 4.7, 250
    _listing(db_session, paris, tech, "Sin reseñas", 100, 200)
    db_session.flush()

    class FakeResponse:
        headers: dict = {}

    listings = listings_router.list_listings(
        category=None, store=None, search=None, min_discount=None, section=None, sort="rating",
        page=1, page_size=30, response=FakeResponse(), db=db_session,
    )
    assert [l.title for l in listings] == ["Muchas reseñas", "Una reseña", "Sin reseñas"]
    assert (listings[0].rating, listings[0].review_count) == (4.7, 250)
