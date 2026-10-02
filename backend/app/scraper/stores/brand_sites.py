"""Brand-owned web stores taking part in the Cyber event (Under Armour, Columbia,
Levi's, New Balance...). There are hundreds of them, but most run on one of
three e-commerce platforms that each expose a public catalog endpoint, so one
scraper per platform covers them all:

- Shopify: /products.json (250 products per page, with compare_at_price as
  the list price).
- VTEX: /api/catalog_system/pub/products/search, which can sort by biggest
  discount first (50 per page, 2,500 results max).
- Magento 2: the public /graphql endpoint. Some groups run several brands on
  one Magento install; those need a `Store` header (store code), and brands
  whose /graphql answers with another site's catalog are left out by the
  discovery script.

Which brands use which platform is in brand_sites.json, generated from
cyber.cl's brand list by scripts/discover_brand_sites.py.
"""

import json
from pathlib import Path

from app.scraper.cyber_cl import slugify
from app.scraper.http import PoliteClient
from app.scraper.parser import ScrapedOffer
from app.scraper.stores.base import Department, StoreScraper

SITES_FILE = Path(__file__).with_name("brand_sites.json")


class BrandSiteScraper(StoreScraper):
    platform: str
    # Stores of one platform are spread round-robin over this many scrape
    # jobs (named marcas-<platform>-<n>), each listed in the workflow matrix.
    job_count: int = 1

    def __init__(self, name: str, host: str, category_slug: str, store_code: str | None = None) -> None:
        self.name = name
        self.cyber_brand_name = name
        self.slug = f"marca-{slugify(name)}"
        self.host = host
        self.base_url = f"https://{host}"
        self.store_code = store_code
        self.group = f"marcas-{self.platform}"
        self.departments = [Department(category_slug, "", "Catálogo")]

    def offer(self, *, external_id: str, title: str, url: str, price: float, original_price: float | None,
              image_url: str | None, brand: str | None, category_slug: str) -> ScrapedOffer:
        return ScrapedOffer(
            store_slug=self.slug,
            store_name=self.name,
            category_slug=category_slug,
            external_id=external_id,
            title=title.strip(),
            url=url,
            price=price,
            original_price=original_price if original_price and original_price > price else None,
            image_url=image_url,
            brand=brand or self.name,
        )


class ShopifyScraper(BrandSiteScraper):
    platform = "shopify"
    job_count = 3  # ~145 stores: one job would take longer than the 10-minute quick cycle
    PAGE_SIZE = 250

    def parse_product(self, product: dict, category_slug: str) -> ScrapedOffer | None:
        variants = product.get("variants") or []
        # Prefer variants in stock; some stores don't publish availability at
        # all (every variant reads False), so fall back to all of them.
        in_stock = [v for v in variants if v.get("available")]
        best = None
        for variant in in_stock or variants:
            try:
                price = float(variant.get("price") or 0)
                original = float(variant.get("compare_at_price") or 0)
            except ValueError:
                continue
            if price <= 0:
                continue
            discount = (original - price) / original if original > price else 0
            if best is None or discount > best[2]:
                best = (price, original, discount)
        if best is None or not product.get("handle"):
            return None
        images = product.get("images") or []
        return self.offer(
            external_id=str(product["id"]),
            title=product.get("title") or "",
            url=f"{self.base_url}/products/{product['handle']}",
            price=best[0],
            original_price=best[1] or None,
            image_url=images[0].get("src") if images else None,
            brand=product.get("vendor"),
            category_slug=category_slug,
        )

    def fetch_page(self, client: PoliteClient, department: Department, page: int) -> tuple[list[ScrapedOffer], bool]:
        products = client.get_json(
            f"{self.base_url}/products.json", params={"limit": self.PAGE_SIZE, "page": page}
        ).get("products") or []
        offers = [o for p in products if (o := self.parse_product(p, department.category_slug))]
        return offers, len(products) >= self.PAGE_SIZE


class VtexScraper(BrandSiteScraper):
    platform = "vtex"
    PAGE_SIZE = 50
    MAX_RESULTS = 2500  # VTEX rejects _to beyond this
    pages_per_step = 5

    def parse_product(self, product: dict, category_slug: str) -> ScrapedOffer | None:
        best = None
        image = None
        for item in product.get("items") or []:
            if image is None and item.get("images"):
                image = item["images"][0].get("imageUrl")
            for seller in item.get("sellers") or []:
                offer = seller.get("commertialOffer") or {}
                price = offer.get("Price") or 0
                if price <= 0 or not offer.get("AvailableQuantity"):
                    continue
                original = max(offer.get("ListPrice") or 0, offer.get("PriceWithoutDiscount") or 0)
                discount = (original - price) / original if original > price else 0
                if best is None or discount > best[2]:
                    best = (float(price), float(original), discount)
        if best is None or not product.get("linkText"):
            return None
        return self.offer(
            external_id=str(product["productId"]),
            title=product.get("productName") or "",
            url=f"{self.base_url}/{product['linkText']}/p",
            price=best[0],
            original_price=best[1] or None,
            image_url=image,
            brand=product.get("brand"),
            category_slug=category_slug,
        )

    def fetch_page(self, client: PoliteClient, department: Department, page: int) -> tuple[list[ScrapedOffer], bool]:
        start = (page - 1) * self.PAGE_SIZE
        if start >= self.MAX_RESULTS:
            return [], False
        products = client.get_json(
            f"{self.base_url}/api/catalog_system/pub/products/search",
            params={"_from": start, "_to": start + self.PAGE_SIZE - 1, "O": "OrderByBestDiscountDESC"},
        )
        offers = [o for p in products if (o := self.parse_product(p, department.category_slug))]
        # Sorted by discount: once a page has no discounted item, nothing after it will.
        has_more = len(products) >= self.PAGE_SIZE and any(o.is_discounted for o in offers)
        return offers, has_more


MAGENTO_QUERY = """
query ($page: Int!, $size: Int!) {
  products(filter: {price: {from: "1"}}, pageSize: $size, currentPage: $page) {
    page_info { total_pages }
    items {
      sku name url_key %s stock_status
      small_image { url }
      price_range { minimum_price { regular_price { value } final_price { value } } }
    }
  }
}
"""


class MagentoScraper(BrandSiteScraper):
    platform = "magento"
    PAGE_SIZE = 100
    pages_per_step = 3
    # Older Magento versions don't know the url_suffix field; detected on first use.
    _has_url_suffix: bool = True

    def parse_item(self, item: dict, category_slug: str) -> ScrapedOffer | None:
        prices = ((item.get("price_range") or {}).get("minimum_price")) or {}
        price = ((prices.get("final_price") or {}).get("value")) or 0
        original = ((prices.get("regular_price") or {}).get("value")) or 0
        if price <= 0 or not item.get("url_key") or item.get("stock_status") == "OUT_OF_STOCK":
            return None
        suffix = item.get("url_suffix") if self._has_url_suffix else ".html"
        return self.offer(
            external_id=str(item.get("sku") or item["url_key"]),
            title=item.get("name") or "",
            url=f"{self.base_url}/{item['url_key']}{suffix or ''}",
            price=float(price),
            original_price=float(original) or None,
            image_url=(item.get("small_image") or {}).get("url"),
            brand=None,
            category_slug=category_slug,
        )

    def query(self, client: PoliteClient, page: int) -> dict:
        headers = {"Store": self.store_code} if self.store_code else None
        while True:
            fields = "url_suffix" if self._has_url_suffix else ""
            data = client.post_json(
                f"{self.base_url}/graphql",
                {"query": MAGENTO_QUERY % fields, "variables": {"page": page, "size": self.PAGE_SIZE}},
                headers=headers,
            )
            errors = data.get("errors") or []
            if self._has_url_suffix and any("url_suffix" in (e.get("message") or "") for e in errors):
                self._has_url_suffix = False
                continue
            if not data.get("data"):
                raise RuntimeError(f"{self.host} GraphQL error: {errors[:1]}")
            return data["data"]["products"]

    def fetch_page(self, client: PoliteClient, department: Department, page: int) -> tuple[list[ScrapedOffer], bool]:
        products = self.query(client, page)
        offers = [o for i in products.get("items") or [] if (o := self.parse_item(i, department.category_slug))]
        total_pages = (products.get("page_info") or {}).get("total_pages") or 0
        return offers, page < total_pages


PLATFORMS: dict[str, type[BrandSiteScraper]] = {
    cls.platform: cls for cls in (ShopifyScraper, VtexScraper, MagentoScraper)
}


def load_brand_sites() -> list[BrandSiteScraper]:
    sites = json.loads(SITES_FILE.read_text(encoding="utf-8"))
    scrapers = [
        PLATFORMS[s["platform"]](s["name"], s["host"], s["category_slug"], s.get("store_code"))
        for s in sites
    ]
    seen: dict[str, int] = {}
    for scraper in scrapers:
        if scraper.job_count > 1:
            n = seen.get(scraper.platform, 0)
            seen[scraper.platform] = n + 1
            scraper.group = f"marcas-{scraper.platform}-{n % scraper.job_count + 1}"
    return scrapers
