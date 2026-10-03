"""Falabella and Sodimac (same Falabella-group Next.js platform): each listing
page embeds its results as JSON in `<script id="__NEXT_DATA__">` under
props.pageProps.results, with pagination in props.pageProps.pagination. The
"20% dcto y más" facet is applied server-side so pages contain only offers.
"""

import json
import re

from app.scraper.http import PoliteClient
from app.scraper.parser import ScrapedOffer
from app.scraper.stores.base import Department, StoreScraper, parse_clp, parse_rating

NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
DISCOUNT_FACET = {"f.range.derived.variant.discount": "20% dcto y más"}
# Price types in preference order. CMR is Falabella's own credit card, so the
# card-only price is used only when there is no regular one.
PRICE_TYPES = ("eventPrice", "internetPrice", "normalPrice", "cmrPrice")


def parse_falabella_item(item: dict, store_slug: str, store_name: str, category_slug: str) -> ScrapedOffer | None:
    prices = [p for p in item.get("prices", []) if p.get("price")]
    current_by_type = {p["type"]: p for p in prices if not p.get("crossed")}
    current = next((current_by_type[t] for t in PRICE_TYPES if t in current_by_type), None)
    original = next((p for p in prices if p.get("crossed")), None)
    if current is None or not item.get("productId") or not item.get("url"):
        return None

    media = item.get("mediaUrls") or []
    rating, review_count = parse_rating(item.get("rating"), item.get("totalReviews"))
    return ScrapedOffer(
        store_slug=store_slug,
        store_name=store_name,
        category_slug=category_slug,
        external_id=str(item["productId"]),  # not skuId: color variants share one productId
        title=item.get("displayName", "").strip(),
        url=item["url"],
        price=parse_clp(current["price"][0]),
        original_price=parse_clp(original["price"][0]) if original else None,
        image_url=media[0] if media else None,
        brand=item.get("brand"),
        rating=rating,
        review_count=review_count,
    )


class FalabellaPlatformScraper(StoreScraper):
    listing_url: str  # formatted with the department ref

    def fetch_page(self, client: PoliteClient, department: Department, page: int) -> tuple[list[ScrapedOffer], bool]:
        response = client.get(self.listing_url.format(ref=department.ref), params={**DISCOUNT_FACET, "page": page})
        match = NEXT_DATA_RE.search(response.text)
        if not match:
            raise RuntimeError(f"{self.name}: __NEXT_DATA__ not found for {department.label} page {page}")
        page_props = json.loads(match.group(1))["props"]["pageProps"]

        offers = [
            offer
            for item in page_props.get("results") or []
            if (offer := parse_falabella_item(item, self.slug, self.name, department.category_slug))
        ]
        pagination = page_props.get("pagination") or {}
        has_more = page * (pagination.get("perPage") or 48) < (pagination.get("count") or 0)
        return offers, has_more


class FalabellaScraper(FalabellaPlatformScraper):
    slug = "falabella"
    name = "Falabella"
    cyber_brand_name = "Falabella.com"
    listing_url = "https://www.falabella.com/falabella-cl/category/{ref}"
    departments = [
        Department("tecnologia", "cat7090034", "Tecnología"),
        Department("hogar", "cat16510006", "Electrohogar"),
        Department("hogar", "cat1005", "Dormitorio"),
        Department("hogar", "cat2026", "Decoración e iluminación"),
        Department("hogar", "cat01", "Cocina y baño"),
        Department("muebles", "cat1008", "Muebles"),
        Department("vestuario-y-calzado", "cat7330051", "Mujer"),
        Department("vestuario-y-calzado", "cat7450065", "Hombre"),
        Department("vestuario-y-calzado", "cat2083", "Zapatillas"),
        Department("infantil", "cat5620004", "Moda infantil"),
        Department("infantil", "cat14680031", "Juguetería"),
        Department("salud-y-belleza", "cat7660002", "Belleza"),
        Department("deportes-y-outdoor", "cat6930002", "Deportes y aire libre"),
        Department("mascotas", "cat9360001", "Mascotas"),
        Department("neumaticos-y-accesorios", "CATG10006", "Automotriz"),
    ]


class SodimacScraper(FalabellaPlatformScraper):
    slug = "sodimac"
    name = "Sodimac"
    cyber_brand_name = "Sodimac"
    listing_url = "https://www.sodimac.cl/sodimac-cl/lista/{ref}"
    departments = [
        Department("ferreteria-y-construccion", "cat14080023", "Taladros"),
        Department("ferreteria-y-construccion", "cat14090005", "Sierras eléctricas"),
        Department("ferreteria-y-construccion", "cat20791939", "Herramientas manuales"),
        Department("ferreteria-y-construccion", "CATG10737", "Electricidad"),
        Department("ferreteria-y-construccion", "CATG10741", "Pisos y revestimientos"),
        Department("ferreteria-y-construccion", "CATG36265", "Pinturas"),
        Department("hogar", "cat3065", "Cocina"),
        Department("hogar", "cat2034", "Electrodomésticos cocina"),
        Department("hogar", "cat3136", "Lavado"),
        Department("hogar", "CATG12097", "Climatización"),
        Department("hogar", "CATG36066", "Iluminación"),
        Department("hogar", "cat1005", "Dormitorio"),
        Department("hogar", "CATG10503", "Terrazas"),
        Department("hogar", "cat18320015", "Maquinaria de jardín"),
        Department("deportes-y-outdoor", "cat6930002", "Deportes y aire libre"),
        Department("mascotas", "CATG11652", "Alimento para perros"),
    ]
