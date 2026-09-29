"""Manual end-to-end test: scrape REAL Falabella.com search results and run
them through the production pipeline (store/category upsert, matcher,
price-snapshot insert) to verify everything works with real data before
pointing the real scraper at cyber.cl once its event catalog goes live.

NOT part of the production scraper. Falabella.com happens to be a clean case
(Next.js Pages Router, product data embedded as JSON in a `__NEXT_DATA__`
script tag -- no headless browser needed), which made it a good target for
this smoke test. Per the locked project scope, the real v1 data source is
cyber.cl's aggregator, not per-retailer scraping -- this script is here only
to validate the pipeline, not as a permanent scraper.

Usage: .venv\\Scripts\\python.exe scripts\\test_scrape_falabella.py
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
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


def parse_clp(raw: str) -> float:
    return float(re.sub(r"[^\d]", "", raw))


def fetch_search_results(query: str) -> list[dict]:
    url = f"https://www.falabella.com/falabella-cl/search?Ntt={query.replace(' ', '%20')}"
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=20.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()

    match = NEXT_DATA_RE.search(response.text)
    if not match:
        raise RuntimeError("__NEXT_DATA__ not found -- Falabella may have changed its page structure")
    data = json.loads(match.group(1))
    return data["props"]["pageProps"].get("results", [])


def to_offer(item: dict) -> ScrapedOffer | None:
    prices_by_type = {p["type"]: p for p in item.get("prices", []) if p.get("price")}
    current = prices_by_type.get("cmrPrice") or prices_by_type.get("eventPrice") or next(
        iter(prices_by_type.values()), None
    )
    if current is None or not item.get("productId"):
        return None

    original = next((p for p in item.get("prices", []) if p.get("crossed") and p.get("price")), None)
    image_urls = item.get("mediaUrls") or []

    return ScrapedOffer(
        store_slug="falabella",
        store_name="Falabella",
        category_slug=CATEGORY_SLUG,
        external_id=str(item["productId"]),
        title=item["displayName"],
        url=item["url"],
        price=parse_clp(current["price"][0]),
        original_price=parse_clp(original["price"][0]) if original else None,
        image_url=image_urls[0] if image_urls else None,
        brand=item.get("brand"),
    )


def main() -> None:
    db = SessionLocal()
    total = 0
    try:
        for query in SEARCH_QUERIES:
            print(f"Fetching '{query}'...")
            results = fetch_search_results(query)
            print(f"  {len(results)} raw results")
            for item in results:
                offer = to_offer(item)
                if offer is None:
                    continue
                upsert_offer(db, offer, category_slug=CATEGORY_SLUG)
                total += 1
            db.commit()
            time.sleep(2)  # be a polite scraper, don't hammer the site
    finally:
        db.close()
    print(f"Done -- upserted {total} real Falabella listings")


if __name__ == "__main__":
    main()
