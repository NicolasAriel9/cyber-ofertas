"""Store parsers, fed with trimmed copies of real payloads captured 2026-10-01."""

import html
import json

from app.scraper.cyber_cl import slugify
from app.scraper.stores.base import parse_clp
from app.scraper.stores.cencosud import EasyScraper, ParisScraper
from app.scraper.stores.falabella import parse_falabella_item
from app.scraper.stores.hites import parse_hites_tile
from app.scraper.stores.ripley import parse_ripley_item


def test_slugify_matches_cyber_cl_category_names():
    assert slugify("Tecnología") == "tecnologia"
    assert slugify("Ferretería y Construcción") == "ferreteria-y-construccion"


def test_parse_clp():
    assert parse_clp("$ 1.299.990") == 1299990
    assert parse_clp("") is None


def test_falabella_prefers_regular_price_over_cmr_card_price():
    item = {
        "productId": "17482518",
        "skuId": "17482518",
        "displayName": "Notebook Gamer Victus 15",
        "url": "https://www.falabella.com/falabella-cl/product/17482518/x",
        "brand": "HP",
        "mediaUrls": ["https://media.falabella.com/falabellaCL/17482518_1/public"],
        "prices": [
            {"type": "cmrPrice", "crossed": False, "price": ["799.990"]},
            {"type": "eventPrice", "crossed": False, "price": ["849.990"]},
            {"type": "normalPrice", "crossed": True, "price": ["989.990"]},
        ],
    }
    offer = parse_falabella_item(item, "falabella", "Falabella", "tecnologia")
    assert offer.price == 849990
    assert offer.original_price == 989990
    assert offer.is_discounted


def test_ripley_builds_product_url_and_ignores_card_price():
    item = {
        "sku": "2000409675203",
        "parentProductID": "2000409675203P",
        "brand": "HP",
        "name": "NOTEBOOK HP 15-FC0252LA AMD RYZEN 5 8GB RAM 512GB SSD 15.6",
        "primaryImage": "https://rimage.ripley.cl/x",
        "priceNumber": 529990,
        "masterPriceNumber": 639990,
        "ripleyPriceNumber": 499990,
    }
    offer = parse_ripley_item(item, "tecnologia")
    assert offer.price == 529990
    assert offer.original_price == 639990
    assert offer.url == (
        "https://simple.ripley.cl/notebook-hp-15-fc0252la-amd-ryzen-5-8gb-ram-512gb-ssd-156-2000409675203p"
    )


def test_hites_tile_uses_gtm_payload():
    payload = {
        "item": {
            "item_id": "961663001",
            "item_name": 'Tablet 10.9" Samsung Galaxy Tab S10 Lite',
            "item_brand": "Samsung",
            "price": 339990,
            "discount": 60000,
        },
        "value": 339990,
    }
    tile = (
        f'<div class="product-tile h-100" data-gtmselectitem="{html.escape(json.dumps(payload))}">'
        '<a class="image-item js-tile-image-container" href="/tablet-samsung-961663001.html">'
        '<img class="img-fluid w-100 tile-image js-image1"\n src="https://www.hites.com/img.jpg?sw=306&amp;sh=306"'
    )
    offer = parse_hites_tile(tile, "tecnologia")
    assert offer.price == 339990
    assert offer.original_price == 399990
    assert offer.url == "https://www.hites.com/tablet-samsung-961663001.html"
    assert offer.image_url == "https://www.hites.com/img.jpg?sw=306&sh=306"


def test_paris_reconstructs_list_price_from_discount_percentage():
    result = {
        "value": "iPhone 15 128GB Azul",
        "data": {
            "id": "549956999",
            "url": "https://paris.cl/iphone-15-128gb-azul-549956999.html",
            "brand": "Apple",
            "displayedPrice": 669990,
            "discountPercentage": 32,
        },
    }
    offer = ParisScraper().parse_item(result, "tecnologia")
    assert offer.price == 669990
    assert offer.original_price == 985279


def test_easy_uses_selling_and_list_price():
    result = {
        "value": "Set Cortina Blackout",
        "data": {"id": "487615", "url": "https://www.easy.cl/set-cortina/p", "BrandName": "Mashini",
                 "sellingPrice": 25990, "listPrice": 53990},
        "variations": [{"data": {"sellingPrice": 25990, "listPrice": 53990}}],
    }
    offer = EasyScraper().parse_item(result, "hogar")
    assert (offer.price, offer.original_price, offer.brand) == (25990, 53990, "Mashini")
