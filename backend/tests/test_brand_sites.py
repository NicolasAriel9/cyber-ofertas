"""Brand-store and Mercado Libre parsers, fed with trimmed copies of real
payloads captured 2026-10-02."""

from app.scraper.stores.brand_sites import MagentoScraper, ShopifyScraper, VtexScraper
from app.scraper.stores.mercadolibre import parse_card


def test_shopify_picks_the_in_stock_variant_with_the_biggest_discount():
    scraper = ShopifyScraper("Columbia", "www.columbiachile.cl", "deportes-y-outdoor")
    product = {
        "id": 7012345,
        "title": "Cortaviento Hombre Glennaker",
        "handle": "cortaviento-hombre-glennaker",
        "vendor": "Columbia",
        "images": [{"src": "https://cdn.shopify.com/x.jpg"}],
        "variants": [
            {"price": "29990", "compare_at_price": "59990", "available": False},
            {"price": "39990.00", "compare_at_price": "59990.00", "available": True},
            {"price": "59990", "compare_at_price": None, "available": True},
        ],
    }
    offer = scraper.parse_product(product, "deportes-y-outdoor")
    assert offer.store_slug == "marca-columbia"
    assert offer.url == "https://www.columbiachile.cl/products/cortaviento-hombre-glennaker"
    assert (offer.price, offer.original_price) == (39990, 59990)
    assert offer.is_discounted


def test_shopify_without_compare_price_is_not_discounted():
    scraper = ShopifyScraper("Vans", "www.vans.cl", "vestuario-y-calzado")
    product = {"id": 1, "title": "Zapatilla", "handle": "z", "variants": [{"price": "49990", "compare_at_price": None}]}
    offer = scraper.parse_product(product, "vestuario-y-calzado")
    assert offer.original_price is None and not offer.is_discounted


def test_vtex_uses_list_price_and_skips_sold_out_sellers():
    scraper = VtexScraper("Reebok", "www.reebok.cl", "vestuario-y-calzado")
    product = {
        "productId": "35112",
        "productName": "Gorra Training | Rbk Aflex Cap | Hombre",
        "brand": "Reebok",
        "linkText": "gorra-training-rbk-aflex-cap-hombre-accc011",
        "link": "https://reebokcl.myvtex.com/gorra-training-rbk-aflex-cap-hombre-accc011/p",
        "items": [
            {
                "images": [{"imageUrl": "https://reebokcl.vteximg.com.br/a.jpg"}],
                "sellers": [
                    {"commertialOffer": {"Price": 1990.0, "ListPrice": 21990.0, "AvailableQuantity": 0}},
                    {"commertialOffer": {"Price": 6597.0, "ListPrice": 21990.0, "PriceWithoutDiscount": 21990.0,
                                         "AvailableQuantity": 100}},
                ],
            }
        ],
    }
    offer = scraper.parse_product(product, "vestuario-y-calzado")
    assert offer.url == "https://www.reebok.cl/gorra-training-rbk-aflex-cap-hombre-accc011/p"
    assert (offer.price, offer.original_price) == (6597, 21990)
    assert offer.image_url.endswith("a.jpg")


def test_magento_builds_the_url_on_the_brand_host():
    scraper = MagentoScraper("New Balance", "newbalance.cl", "vestuario-y-calzado", store_code="newbalance")
    item = {
        "sku": "NB-530",
        "name": "Zapatillas Urbanas Unisex New Balance 530",
        "url_key": "zapatillas-urbanas-unisex-new-balance-530",
        "url_suffix": ".html",
        "stock_status": "IN_STOCK",
        "small_image": {"url": "https://sparta.cl/media/catalog/product/a.jpg"},
        "price_range": {"minimum_price": {"regular_price": {"value": 99990}, "final_price": {"value": 69990}}},
    }
    offer = scraper.parse_item(item, "vestuario-y-calzado")
    assert offer.url == "https://newbalance.cl/zapatillas-urbanas-unisex-new-balance-530.html"
    assert (offer.price, offer.original_price) == (69990, 99990)
    assert offer.brand == "New Balance"
    assert scraper.parse_item({**item, "stock_status": "OUT_OF_STOCK"}, "vestuario-y-calzado") is None


ML_CARD = (
    ' id="_R_23j8pa_" data-andes-card="true"><div class="poly-card__portada">'
    '<img class="poly-component__picture" src="https://http2.mlstatic.com/D_Q_NP_2X_828557-MLA1.webp" alt="x"/>'
    '</div><div class="poly-card__content"><h3 class="poly-component__title-wrapper">'
    '<a href="https://www.mercadolibre.cl/camara-seguridad/p/MLC58751201?pdp_filters=deal%3AMLC1#polycard_client=offers'
    '&amp;wid=MLC3787902062&amp;sid=offers" target="_self" class="poly-component__title">'
    'C&#x27;mara De Seguridad Exterior Wifi Hd</a></h3>'
    '<div class="poly-component__price"><div class="poly-price__labels"><s class="andes-money-amount" role="img" '
    'aria-label="Antes: 129096 pesos chilenos"></s></div><div class="poly-price__current">'
    '<span class="andes-money-amount" role="img" aria-label="41708 pesos chilenos"></span></div>'
    '<span class="poly-price__installments">6 cuotas de <span aria-label="6951 pesos chilenos"></span></span>'
)


def test_mercadolibre_card():
    offer = parse_card(ML_CARD, "tecnologia")
    assert offer.external_id == "MLC3787902062"
    assert offer.title == "C'mara De Seguridad Exterior Wifi Hd"
    assert offer.url.startswith("https://www.mercadolibre.cl/camara-seguridad/p/MLC58751201")
    assert "#" not in offer.url
    assert (offer.price, offer.original_price) == (41708, 129096)
    assert offer.image_url.endswith("MLA1.webp")
