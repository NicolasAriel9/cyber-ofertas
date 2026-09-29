"""Manual end-to-end test: scrape REAL Paris.cl search results (same purpose
as test_scrape_falabella.py -- see that file's docstring). Paris.cl embeds
its search results as a standard schema.org JSON-LD block
(`<script id="jsonld-webpage-plp-root-search-...">`), which only exposes the
current price (no original/crossed price), so discount_pct will be None here
unlike the Falabella script.

NOT part of the production scraper -- see test_scrape_falabella.py.

Usage: .venv\\Scripts\\python.exe scripts\\test_scrape_paris.py
"""

import json
import re
import time

import httpx

from app.db import SessionLocal
from app.scraper.cyber_scraper import upsert_offer
from app.scraper.fetch import USER_AGENT
from app.scraper.parser import ScrapedOffer

SEARCH_QUERIES = ["notebook", "smart tv"]
CATEGORY_SLUG = "tecnologia"
JSONLD_RE = re.compile(
    r'<script id="jsonld-webpage-plp-root-search-[^"]*" type="application/ld\+json">(.*?)</script>',
    re.S,
)


def fetch_search_results(query: str) -> list[dict]:
    url = f"https://www.paris.cl/search/?q={query.replace(' ', '%20')}"
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=20.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()

    match = JSONLD_RE.search(response.text)
    if not match:
        raise RuntimeError("JSON-LD product list not found -- Paris.cl may have changed its page structure")
    data = json.loads(match.group(1))
    return data["mainEntity"]["itemListElement"]


def to_offer(list_item: dict) -> ScrapedOffer | None:
    item = list_item.get("item", {})
    offers = item.get("offers", {})
    price = offers.get("price")
    if price is None or not item.get("sku"):
        return None

    return ScrapedOffer(
        store_slug="paris",
        store_name="Paris",
        category_slug=CATEGORY_SLUG,
        external_id=str(item["sku"]),
        title=item["name"],
        url=item.get("url") or offers.get("url"),
        price=float(price),
        original_price=None,  # Paris's JSON-LD doesn't expose a crossed/original price
        image_url=item.get("image"),
    )


def main() -> None:
    db = SessionLocal()
    total = 0
    try:
        for query in SEARCH_QUERIES:
            print(f"Fetching '{query}'...")
            results = fetch_search_results(query)
            print(f"  {len(results)} raw results")
            for list_item in results:
                offer = to_offer(list_item)
                if offer is None:
                    continue
                upsert_offer(db, offer, category_slug=CATEGORY_SLUG)
                total += 1
            db.commit()
            time.sleep(2)  # be a polite scraper, don't hammer the site
    finally:
        db.close()
    print(f"Done -- upserted {total} real Paris listings")


if __name__ == "__main__":
    main()
