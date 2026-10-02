"""Hites (Salesforce Commerce Cloud): server-rendered HTML grid, paginated with
?start=&sz=. Each product tile carries a `data-gtmselectitem` attribute with a
JSON analytics payload (name, brand, price and discount amount), which is far
sturdier to parse than the visual price markup.
"""

import html
import json
import re

from app.scraper.http import PoliteClient
from app.scraper.parser import ScrapedOffer
from app.scraper.stores.base import Department, StoreScraper, parse_clp

BASE_URL = "https://www.hites.com"
PAGE_SIZE = 48
TILE_SPLIT = 'class="h-100 plp-grid-tile"'
GTM_RE = re.compile(r'data-gtmselectitem="([^"]+)"')
HREF_RE = re.compile(r'<a class="image-item[^"]*" href="([^"]+)"')
IMG_RE = re.compile(r'<img class="img-fluid w-100 tile-image js-image1"\s+src="([^"]+)"')


def parse_hites_tile(tile_html: str, category_slug: str) -> ScrapedOffer | None:
    gtm = GTM_RE.search(tile_html)
    if not gtm:
        return None
    payload = json.loads(html.unescape(gtm.group(1)))
    item = payload.get("item") or {}
    price = parse_clp(item.get("price") or payload.get("value"))
    href = HREF_RE.search(tile_html)
    if not price or not item.get("item_id") or not href:
        return None
    discount = parse_clp(item.get("discount")) or 0
    image = IMG_RE.search(tile_html)
    return ScrapedOffer(
        store_slug="hites",
        store_name="Hites",
        category_slug=category_slug,
        external_id=str(item["item_id"]),
        title=html.unescape(item.get("item_name") or "").strip(),
        url=BASE_URL + html.unescape(href.group(1)),
        price=price,
        original_price=price + discount if discount > 0 else None,
        image_url=html.unescape(image.group(1)) if image else None,
        brand=item.get("item_brand"),
    )


class HitesScraper(StoreScraper):
    slug = "hites"
    name = "Hites"
    cyber_brand_name = "Hites"
    departments = [
        Department("tecnologia", "tecnologia", "Tecnología"),
        Department("tecnologia", "celulares", "Celulares"),
        Department("hogar", "electro-hogar", "Electrohogar"),
        Department("hogar", "hogar", "Hogar"),
        Department("hogar", "dormitorio", "Dormitorio"),
        Department("muebles", "muebles", "Muebles"),
        Department("vestuario-y-calzado", "mujer", "Mujer"),
        Department("vestuario-y-calzado", "hombre", "Hombre"),
        Department("vestuario-y-calzado", "zapatillas", "Zapatillas"),
        Department("vestuario-y-calzado", "zapatos", "Zapatos"),
        Department("accesorios-moda", "accesorios", "Accesorios"),
        Department("infantil", "ninos-y-jugueteria", "Niños y juguetería"),
        Department("infantil", "bebes", "Bebés"),
        Department("salud-y-belleza", "belleza", "Belleza"),
        Department("deportes-y-outdoor", "deportes", "Deportes"),
        Department("ferreteria-y-construccion", "construccion", "Construcción"),
    ]

    def fetch_page(self, client: PoliteClient, department: Department, page: int) -> tuple[list[ScrapedOffer], bool]:
        response = client.get(
            f"{BASE_URL}/{department.ref}/", params={"start": (page - 1) * PAGE_SIZE, "sz": PAGE_SIZE}
        )
        tiles = response.text.split(TILE_SPLIT)[1:]
        offers = [
            offer for tile_html in tiles if (offer := parse_hites_tile(tile_html, department.category_slug))
        ]
        return offers, len(tiles) >= PAGE_SIZE
