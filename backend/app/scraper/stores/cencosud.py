"""Cencosud stores (Paris, Easy, Jumbo): their product listings are served by
Constructor.io, whose public browse API returns clean JSON. The per-store
"prod" keys are public -- they ship in Cencosud's own client bundle
(https://cnstrc.com/js/cust/cencosud_*.js) and are sent by every visitor's
browser. Paris's own pages paginate client-side through this same API, so
scraping its HTML would only ever see page 1.

Results are capped by Constructor at 10,000 per group.
"""

from app.scraper.http import PoliteClient
from app.scraper.parser import ScrapedOffer
from app.scraper.stores.base import Department, StoreScraper

BROWSE_URL = "https://ac.cnstrc.com/browse/group_id/{group_id}"
PAGE_SIZE = 100


class ConstructorStoreScraper(StoreScraper):
    api_key: str

    def parse_item(self, result: dict, category_slug: str) -> ScrapedOffer | None:
        raise NotImplementedError

    def fetch_page(self, client: PoliteClient, department: Department, page: int) -> tuple[list[ScrapedOffer], bool]:
        data = client.get_json(
            BROWSE_URL.format(group_id=department.ref),
            params={"key": self.api_key, "page": page, "num_results_per_page": PAGE_SIZE, "sort_by": "relevance"},
        )["response"]
        offers = [
            offer
            for result in data.get("results") or []
            if (offer := self.parse_item(result, department.category_slug))
        ]
        has_more = page * PAGE_SIZE < (data.get("total_num_results") or 0)
        return offers, has_more


class ParisScraper(ConstructorStoreScraper):
    slug = "paris"
    name = "Paris"
    cyber_brand_name = "Paris.cl"
    api_key = "key_8pjkPsSkEsJHKgxR"
    departments = [
        Department("tecnologia", "tecnologia", "Tecno"),
        Department("tecnologia", "electro", "TV y audio"),
        Department("hogar", "lineablanca", "Electro y línea blanca"),
        Department("hogar", "decohogar", "Deco"),
        Department("hogar", "dormitorio", "Dormitorio"),
        Department("muebles", "muebles", "Muebles"),
        Department("vestuario-y-calzado", "modamujer", "Mujer"),
        Department("vestuario-y-calzado", "modahombre", "Hombre"),
        Department("vestuario-y-calzado", "zapatos", "Zapatos"),
        Department("infantil", "ninos", "Niños"),
        Department("infantil", "jugueteria", "Juguetes"),
        Department("salud-y-belleza", "belleza", "Belleza"),
        Department("deportes-y-outdoor", "deportes", "Deportes"),
        Department("neumaticos-y-accesorios", "Automotriz", "Automotriz"),
        Department("ferreteria-y-construccion", "Herramientas", "Herramientas"),
        Department("mascotas", "Mascotas", "Mascotas"),
    ]

    def parse_item(self, result: dict, category_slug: str) -> ScrapedOffer | None:
        data = result.get("data") or {}
        price = data.get("displayedPrice")
        if not price or not data.get("id") or not data.get("url"):
            return None
        # Paris's index only has the final price and the discount percentage;
        # the list price is reconstructed from them (rounded to the peso).
        pct = data.get("discountPercentage") or 0
        original = round(price / (1 - pct / 100)) if 0 < pct < 100 else None
        return ScrapedOffer(
            store_slug=self.slug,
            store_name=self.name,
            category_slug=category_slug,
            external_id=str(data["id"]),
            title=(result.get("value") or "").strip(),
            url=data["url"],
            price=float(price),
            original_price=float(original) if original else None,
            image_url=data.get("image_url"),
            brand=data.get("brand"),
        )


class VtexConstructorScraper(ConstructorStoreScraper):
    """Easy and Jumbo index their VTEX catalog: sellingPrice is what you pay,
    listPrice the regular price."""

    def parse_item(self, result: dict, category_slug: str) -> ScrapedOffer | None:
        data = result.get("data") or {}
        variation = ((result.get("variations") or [{}])[0]).get("data") or {}
        price = variation.get("sellingPrice") or data.get("sellingPrice")
        original = variation.get("listPrice") or data.get("listPrice")
        if not price or not data.get("id") or not data.get("url"):
            return None
        return ScrapedOffer(
            store_slug=self.slug,
            store_name=self.name,
            category_slug=category_slug,
            external_id=str(data["id"]),
            title=(result.get("value") or "").strip(),
            url=data["url"],
            price=float(price),
            original_price=float(original) if original and original > price else None,
            image_url=data.get("image_url"),
            brand=data.get("BrandName"),
        )


class EasyScraper(VtexConstructorScraper):
    slug = "easy"
    name = "Easy"
    cyber_brand_name = "Easy"
    api_key = "key_AimxrTjorsjiKQPy"
    departments = [
        Department("ferreteria-y-construccion", "23", "Herramientas"),
        Department("ferreteria-y-construccion", "25", "Electricidad y seguridad"),
        Department("ferreteria-y-construccion", "26", "Ferretería y gasfitería"),
        Department("hogar", "11", "Electrohogar y climatización"),
        Department("hogar", "16", "Decoración e iluminación"),
        Department("hogar", "14", "Dormitorio"),
        Department("hogar", "13", "Jardín y aire libre"),
        Department("hogar", "15", "Organización y limpieza"),
        Department("hogar", "18", "Baño"),
        Department("muebles", "12", "Muebles"),
        Department("neumaticos-y-accesorios", "24", "Automóvil"),
        Department("mascotas", "19", "Mascotas"),
        Department("hogar", "1809040734", "Ofertas"),
    ]


class JumboScraper(VtexConstructorScraper):
    slug = "jumbo"
    name = "Jumbo"
    cyber_brand_name = "Jumbo"
    api_key = "key_JopvNXKS61kwGkBe"
    departments = [
        Department("tecnologia", "298", "Electro y tecnología"),
        Department("hogar", "354", "Hogar"),
        Department("deportes-y-outdoor", "338", "Deportes"),
        Department("ferreteria-y-construccion", "361", "Automóvil, ferretería y jardín"),
        Department("infantil", "1163", "Juguetería"),
        Department("salud-y-belleza", "230", "Cuidado personal"),
        Department("alimentos-y-bebidas", "204", "Botillería"),
        Department("alimentos-y-bebidas", "27", "Despensa"),
        Department("mascotas", "400", "Mascotas"),
    ]
