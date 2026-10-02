"""Regenerate app/scraper/stores/brand_sites.json from cyber.cl's brand list.

For every participating brand, checks whether its web store runs on a platform
we can read (Shopify, VTEX, Magento 2), then validates it by actually scraping
its first page with the real scraper class. Brands that fail, sell services
rather than products, or whose Magento endpoint answers with another site's
catalog (several brands share one install) are left out.

Run before each event, from backend/:  python scripts/discover_brand_sites.py
"""

import concurrent.futures as cf
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.scraper import cyber_cl  # noqa: E402
from app.scraper.http import PoliteClient  # noqa: E402
from app.scraper.stores import RETAILERS  # noqa: E402
from app.scraper.stores.brand_sites import PLATFORMS, SITES_FILE  # noqa: E402

# cyber.cl categories that aren't product stores.
SKIP_CATEGORIES = {
    "Inmobiliarias", "Instituciones Benéficas", "Seguros y Servicios", "Viajes y Turismo",
    "Cuponeras", "Automóviles",
}
# Aesthetic clinics (services) and adult stores.
SKIP_BRANDS = {
    "Clinica Belenus", "Clinica Altos del Desierto", "Lasertam", "UltraEstetica",
    "Starsex", "Dominame.cl SexShop", "Japi Jane",
}
# Brands sharing a Magento install with another site, reachable with a store code.
MAGENTO_STORE_CODES = {"New Balance": "newbalance"}

MAGENTO_CONFIG_QUERY = "{storeConfig{base_url}}"


def bare_host(host: str) -> str:
    return host.lower().removeprefix("www.")


def detect_platform(client: PoliteClient, brand: dict) -> tuple[str, str | None] | None:
    host = urlparse(brand["url"]).netloc
    base = f"https://{host}"
    try:
        response = client.get(f"{base}/products.json", params={"limit": 1})
        if response.json().get("products"):
            return "shopify", None
    except Exception:
        pass
    try:
        response = client.get(f"{base}/api/catalog_system/pub/products/search", params={"_from": 0, "_to": 0})
        if response.text.startswith("[") and '"productName"' in response.text:
            return "vtex", None
    except Exception:
        pass
    try:
        store_code = MAGENTO_STORE_CODES.get(brand["name"])
        headers = {"Store": store_code} if store_code else None
        data = client.post_json(f"{base}/graphql", {"query": MAGENTO_CONFIG_QUERY}, headers=headers)
        served = urlparse(data["data"]["storeConfig"]["base_url"]).netloc
        if bare_host(served) == bare_host(host):
            return "magento", store_code
    except Exception:
        pass
    return None


def check_brand(brand: dict) -> dict | None:
    if brand["name"] in SKIP_BRANDS or brand["category"]["name"] in SKIP_CATEGORIES:
        return None
    with PoliteClient(delay=0.5) as client:
        found = detect_platform(client, brand)
        if not found:
            return None
        platform, store_code = found
        site = {
            "name": brand["name"].strip(),
            "host": urlparse(brand["url"]).netloc,
            "platform": platform,
            "category_slug": cyber_cl.slugify(brand["category"]["name"]),
        }
        if store_code:
            site["store_code"] = store_code
        scraper = PLATFORMS[platform](site["name"], site["host"], site["category_slug"], store_code)
        try:
            offers, _ = scraper.fetch_page(client, scraper.departments[0], 1)
        except Exception as exc:
            print(f"  {brand['name']} ({platform}): first page failed: {exc}", file=sys.stderr)
            return None
        if not offers:
            print(f"  {brand['name']} ({platform}): no products parsed", file=sys.stderr)
            return None
        site["sample_products"] = len(offers)
        return site


def main() -> None:
    with PoliteClient() as client:
        event = cyber_cl.fetch_current_event(client)
        brands = cyber_cl.fetch_event_brands(client, event["slug"])
    print(f"cyber.cl event {event['name']}: {len(brands)} brands", file=sys.stderr)

    retailer_names = {s.cyber_brand_name for s in RETAILERS}
    brands = [b for b in brands if b["name"] not in retailer_names]
    with cf.ThreadPoolExecutor(16) as pool:
        sites = [s for s in pool.map(check_brand, brands) if s]

    unique: dict[str, dict] = {}
    for site in sites:
        key = cyber_cl.slugify(site["name"])
        unique.setdefault(key, site)
    result = sorted(unique.values(), key=lambda s: s["name"].lower())
    for site in result:
        site.pop("sample_products", None)
    SITES_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    counts: dict[str, int] = {}
    for site in result:
        counts[site["platform"]] = counts.get(site["platform"], 0) + 1
    print(f"Wrote {len(result)} brand sites to {SITES_FILE.name}: {counts}", file=sys.stderr)


if __name__ == "__main__":
    main()
