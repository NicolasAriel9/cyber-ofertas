from app.models import Listing, PriceSnapshot, Product, Store
from app.services.assistant import answer_question, parse_query, search_products


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


def test_search_filters_by_brand_and_sorts_cheapest_first(db_session):
    _seed_catalog(db_session)
    results = search_products(db_session, brand="Lenovo", sort="price_asc")
    assert [r["title"] for r in results] == ["Notebook Lenovo IdeaPad 3", "Notebook Lenovo Legion Pro"]
    assert results[0]["price"] == 299990


def test_search_filters_by_max_price(db_session):
    _seed_catalog(db_session)
    results = search_products(db_session, brand="Lenovo", max_price=500000)
    assert len(results) == 1
    assert results[0]["title"] == "Notebook Lenovo IdeaPad 3"


def test_search_filters_by_min_price(db_session):
    _seed_catalog(db_session)
    results = search_products(db_session, brand="Lenovo", min_price=500000)
    assert len(results) == 1
    assert results[0]["title"] == "Notebook Lenovo Legion Pro"


def test_search_filters_by_store(db_session):
    _seed_catalog(db_session)
    results = search_products(db_session, store="paris")
    assert len(results) == 1
    assert results[0]["store"] == "Paris"


def test_search_sort_by_discount_is_default(db_session):
    _seed_catalog(db_session)
    results = search_products(db_session, limit=1)
    assert results[0]["title"] == "Smart TV Samsung 55"


def test_search_tolerates_simple_plural(db_session):
    _seed_catalog(db_session)
    results = search_products(db_session, keyword_tokens=["notebooks"])
    assert len(results) == 2


def test_parse_query_detects_brand_and_cheapest_intent(db_session):
    _seed_catalog(db_session)
    parsed = parse_query(db_session, "dame el notebook más barato de Lenovo")
    assert parsed["has_signal"] is True
    assert parsed["brand"] == "Lenovo"
    assert parsed["sort"] == "price_asc"
    assert parsed["limit"] == 1


def test_parse_query_detects_store_and_price_ceiling_mil(db_session):
    _seed_catalog(db_session)
    parsed = parse_query(db_session, "ofertas en paris bajo 400 mil")
    assert parsed["store"] == "paris"
    assert parsed["max_price"] == 400000


def test_parse_query_detects_price_ceiling_millones(db_session):
    _seed_catalog(db_session)
    parsed = parse_query(db_session, "notebooks bajo 2 millones")
    assert parsed["max_price"] == 2_000_000
    assert "notebooks" in parsed["keyword_tokens"]


def test_parse_query_detects_formatted_price(db_session):
    _seed_catalog(db_session)
    parsed = parse_query(db_session, "notebook menor a 2.000.000")
    assert parsed["max_price"] == 2_000_000


def test_parse_query_detects_price_range(db_session):
    _seed_catalog(db_session)
    parsed = parse_query(db_session, "top 3 más baratos entre 200 mil y 500 mil")
    assert parsed["min_price"] == 200_000
    assert parsed["max_price"] == 500_000
    assert parsed["limit"] == 3
    assert parsed["sort"] == "price_asc"


def test_parse_query_best_discount_synonyms(db_session):
    _seed_catalog(db_session)
    for phrase in ["mejor descuento", "mejores ofertas", "recomiéndame algo"]:
        parsed = parse_query(db_session, phrase)
        assert parsed["has_signal"] is True, phrase
        assert parsed["sort"] == "discount", phrase


def test_parse_query_best_discount_in_category(db_session):
    _seed_catalog(db_session)
    parsed = parse_query(db_session, "mejor descuento en notebook")
    assert parsed["sort"] == "discount"
    assert "notebook" in parsed["keyword_tokens"]
    assert parsed["limit"] == 5  # a category-scoped ask shows options, not just one


def test_parse_query_unrecognized_message(db_session):
    _seed_catalog(db_session)
    parsed = parse_query(db_session, "hola como estas")
    assert parsed["has_signal"] is False
    assert parsed["keyword_tokens"] == []


def test_answer_question_end_to_end(db_session):
    _seed_catalog(db_session)
    answer = answer_question(db_session, "el notebook más barato de Lenovo")
    assert "Notebook Lenovo IdeaPad 3" in answer
    assert "299.990" in answer


def test_answer_question_price_range_end_to_end(db_session):
    _seed_catalog(db_session)
    answer = answer_question(db_session, "notebooks entre 200 mil y 500 mil")
    assert "Notebook Lenovo IdeaPad 3" in answer
    assert "Legion" not in answer  # outside the range


def test_answer_question_falls_back_when_unrecognized(db_session):
    _seed_catalog(db_session)
    answer = answer_question(db_session, "hola bot")
    assert "No entendí" in answer
