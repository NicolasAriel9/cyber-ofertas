"""Ripley (simple.ripley.cl): Next.js Pages Router; each department page embeds
its products in __NEXT_DATA__ at props.pageProps.findabilityProps.data, with
numeric prices already parsed (priceNumber / masterPriceNumber /
ripleyPriceNumber -- the last one is the Ripley-card-only price).
"""

import json
import re
import unicodedata

from app.scraper.http import PoliteClient
from app.scraper.parser import ScrapedOffer
from app.scraper.stores.base import Department, StoreScraper

NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
BASE_URL = "https://simple.ripley.cl"


def product_url(item: dict) -> str:
    """The listing JSON has no URL; Ripley's product pages are
    /<slugified name, dots dropped>-<parentProductID lowercased>, e.g.
    /notebook-hp-15-fc0252la-amd-ryzen-5-8gb-ram-512gb-ssd-156-2000409675203p
    """
    name = unicodedata.normalize("NFKD", item.get("name") or "").encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().replace(".", "")).strip("-")
    product_id = (item.get("parentProductID") or f"{item['sku']}p").lower()
    return f"{BASE_URL}/{slug}-{product_id}"


def parse_ripley_item(item: dict, category_slug: str) -> ScrapedOffer | None:
    price = item.get("priceNumber") or item.get("ripleyPriceNumber")
    if not price or not item.get("sku"):
        return None
    original = item.get("masterPriceNumber")
    image = item.get("primaryImage")
    if image and image.startswith("//"):
        image = "https:" + image
    return ScrapedOffer(
        store_slug="ripley",
        store_name="Ripley",
        category_slug=category_slug,
        external_id=str(item["sku"]),
        title=(item.get("name") or "").strip(),
        url=product_url(item),
        price=float(price),
        original_price=float(original) if original and original > price else None,
        image_url=image,
        brand=item.get("brand"),
    )


class RipleyScraper(StoreScraper):
    slug = "ripley"
    name = "Ripley"
    cyber_brand_name = "Ripley"
    departments = [
        Department("tecnologia", "tecno", "Tecno"),
        Department("tecnologia", "electro", "Electro"),
        Department("hogar", "decoracion", "Decoración"),
        Department("hogar", "dormitorio", "Dormitorio"),
        Department("muebles", "muebles", "Muebles"),
        Department("vestuario-y-calzado", "moda-mujer", "Moda mujer"),
        Department("vestuario-y-calzado", "moda-hombre", "Moda hombre"),
        Department("vestuario-y-calzado", "zapatos-y-zapatillas", "Zapatos y zapatillas"),
        Department("accesorios-moda", "accesorios-y-complementos", "Accesorios"),
        Department("infantil", "moda-infantil", "Moda infantil"),
        Department("infantil", "jugueteria-y-ninos", "Juguetería y niños"),
        Department("salud-y-belleza", "belleza", "Belleza"),
        Department("deportes-y-outdoor", "deporte-y-aventura", "Deporte y aventura"),
        Department("mascotas", "mascotas", "Mascotas"),
        Department("neumaticos-y-accesorios", "automotriz", "Automotriz"),
        Department("ferreteria-y-construccion", "ferreteria", "Ferretería"),
    ]

    def fetch_page(self, client: PoliteClient, department: Department, page: int) -> tuple[list[ScrapedOffer], bool]:
        response = client.get(f"{BASE_URL}/{department.ref}", params={"page": page})
        match = NEXT_DATA_RE.search(response.text)
        if not match:
            raise RuntimeError(f"Ripley: __NEXT_DATA__ not found for {department.label} page {page}")
        page_props = json.loads(match.group(1))["props"]["pageProps"]
        data = (page_props.get("findabilityProps") or {}).get("data") or {}

        offers = [
            offer
            for item in data.get("products") or []
            if (offer := parse_ripley_item(item, department.category_slug))
        ]
        has_more = (data.get("offset") or 0) + (data.get("limit") or 48) < (data.get("total") or 0)
        return offers, has_more
