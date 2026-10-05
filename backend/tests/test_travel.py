import json

from app.models import Category, Listing, Product, Store
from app.routers import listings as listings_router
from app.scraper.cyber_scraper import upsert_offer
from app.scraper.stores.travel import parse_cocha_page, parse_jetsmart_fares

JETSMART_HTML = """<script>
    let list = JSON.parse('{"SCL-LSC":{"arr":"LSC","date":"2026-10-22 17:55:00","dep":"SCL","ft":"nacional",
    "p":{"clp":10900},"pi":{"clp":18714}},"SCL-AEP":{"arr":"AEP","date":"2026-11-03 06:00:00","dep":"SCL",
    "p":{"clp":31168},"pi":{"clp":117118}}}');
</script>"""


def _cocha_html(cards):
    state = {"get-admin/ofertas": {"elements": [{"type": "cx-carousel", "deals": cards}]}}
    return f'<script id="ng-state" type="application/json">{json.dumps(state)}</script>'


def test_jetsmart_fares_include_taxes_and_route_names():
    offers = {o.external_id: o for o in parse_jetsmart_fares(JETSMART_HTML)}

    serena = offers["SCL-LSC"]
    assert serena.title == "Vuelo Santiago → La Serena · solo ida"
    assert serena.price == 18714
    assert serena.original_price is None
    assert serena.category_slug == "vuelos"
    assert serena.details == "22 oct · tarifa $10.900 + tasas"
    assert "o1=SCL" in serena.url and "d1=LSC" in serena.url and "dd1=2026-10-22" in serena.url
    assert offers["SCL-AEP"].title == "Vuelo Santiago → Buenos Aires (Aeroparque) · solo ida"


def test_cocha_cards_by_product_type():
    html = _cocha_html(
        [
            {"type": "cx-card-product", "productType": "package", "title": "Punta Cana", "price": 907751,
             "duration": 7, "allInclusive": True, "stars": 4, "discount": 0, "before": "undefined undefined",
             "deeplink": "https://www.cocha.com/paquetes/punta-cana?amenities=allin",
             "priceDescription": "Precio final por persona"},
            {"type": "cx-card-product", "productType": "flight", "title": "Vuelos a Buenos Aires",
             "price": 171803, "discount": 20, "deeplink": "https://www.cocha.com/vuelos/destinos/buenos-aires"},
            {"type": "cx-card-product", "productType": "hotel", "title": "Isla de Pascua", "price": 107413,
             "stars": 3, "deeplink": "http://www.cocha.com/hoteles/destinos/isla-de-pascua",
             "priceDescription": "Precio por noche"},
            {"type": "cx-card-product", "productType": "vuelo-hotel", "title": "Otro", "price": 1, "deeplink": "/x"},
        ]
    )
    package, flight, hotel = parse_cocha_page(html)

    assert package.title == "Paquete Punta Cana · 6 noches · todo incluido"
    assert package.category_slug == "paquetes"
    assert package.original_price is None
    assert flight.title == "Vuelo Santiago → Buenos Aires · ida y vuelta"
    assert flight.original_price == round(171803 / 0.8)
    assert hotel.category_slug == "alojamientos"
    assert hotel.url.startswith("https://")
    assert hotel.details == "Precio por noche"


def test_travel_offers_match_exact_titles_only(db_session):
    one_way, round_trip = parse_jetsmart_fares(JETSMART_HTML)[0], parse_cocha_page(
        _cocha_html([{"type": "cx-card-product", "productType": "flight", "title": "Vuelos a La Serena",
                      "price": 60000, "deeplink": "https://www.cocha.com/vuelos/destinos/la-serena"}])
    )[0]
    first, _ = upsert_offer(db_session, one_way, one_way.category_slug)
    second, _ = upsert_offer(db_session, round_trip, round_trip.category_slug)
    again, _ = upsert_offer(db_session, one_way, one_way.category_slug)

    assert first.product_id != second.product_id
    assert again.id == first.id
    assert first.raw_attributes["details"] == "22 oct · tarifa $10.900 + tasas"


def test_travel_highlights_are_cheapest_first_and_kept_apart(db_session):
    flights = Category(name="Vuelos", slug="vuelos")
    tech = Category(name="Tecnología", slug="tecnologia")
    jetsmart = Store(name="JetSMART", slug="jetsmart")
    db_session.add_all([flights, tech, jetsmart])
    db_session.flush()
    for i, price in enumerate([90_000, 20_000, 50_000, 35_000]):
        product = Product(canonical_title=f"Vuelo {i}", category_id=flights.id)
        db_session.add(product)
        db_session.flush()
        db_session.add(Listing(product_id=product.id, store_id=jetsmart.id, external_id=str(i), title=f"Vuelo {i}",
                               url="https://jetsmart.com", current_price=price))
    tv = Product(canonical_title="TV", category_id=tech.id)
    db_session.add(tv)
    db_session.flush()
    db_session.add(Listing(product_id=tv.id, store_id=jetsmart.id, external_id="tv", title="TV", url="x",
                           current_price=300_000, current_original_price=750_000, current_discount_pct=60))
    db_session.flush()

    [travel] = listings_router.list_highlights(per_category=3, section="viajes", db=db_session)
    [retail] = listings_router.list_highlights(per_category=3, section="productos", db=db_session)

    assert travel.category.slug == "vuelos"
    assert [l.latest_price for l in travel.listings] == [20_000, 35_000, 50_000]
    assert retail.category.slug == "tecnologia"
