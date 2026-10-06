"""Entrypoint run by the Render Cron Job (python -m app.scraper.cyber_scraper).

1. Reads cyber.cl's public API for the current event: syncs the official
   category list and checks which of our supported stores participate.
2. For each participating store, walks every department (page by page, up to
   SCRAPE_MAX_PAGES) and upserts each discounted offer: matcher -> Listing ->
   new PriceSnapshot -> Telegram price-drop alerts.
3. Listings of a fully scraped store that weren't seen this run are marked
   inactive (the offer ended or dropped out of the store's top pages).

Skips entirely outside an active Cyber event window (see event_windows.py)
unless FORCE_SCRAPE=1. Limit to some stores with SCRAPE_STORES=falabella,paris
(store slugs or job groups, e.g. marcas-vtex or marcas-shopify-1).

SCRAPE_MODE=quick only reads the first QUICK_PAGES pages of each department
(where stores surface new and featured deals) and never deactivates listings,
since it doesn't see the whole catalog. It's meant to run every ~5 minutes
between full sweeps.
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import SessionLocal
from app.models import Favorite, Listing, PriceSnapshot, Store
from app.scraper import cyber_cl
from app.scraper.event_windows import is_scrape_window_active, started_event_start
from app.scraper.http import PoliteClient
from app.scraper.parser import ScrapedOffer
from app.scraper.stores import ALL_STORES, StoreScraper
from app.scraper.stores.base import MAX_PAGES_PER_DEPARTMENT
from app.services.alerts import check_price_drop, record_alert_sent
from app.services.matcher import ProductIndex, match_or_create_product
from app.services.telegram_client import format_price_drop_message, send_message
from app.utils import ensure_aware

logger = logging.getLogger(__name__)

QUICK_PAGES = int(os.environ.get("SCRAPE_QUICK_PAGES", "2"))

# How stale last_seen_at may get before a pass rewrites it. Bumping it on every
# pass rewrote ~200k rows every few minutes and exhausted the free database's
# disk I/O (Oct 5 2026), so an unchanged offer is only written about once an
# hour. Far below LISTING_STALE_AFTER (24 h), which is what reads it.
SEEN_REFRESH = timedelta(hours=1)


def is_quick_mode() -> bool:
    return os.environ.get("SCRAPE_MODE", "full").lower() == "quick"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_or_create_store(db: Session, slug: str, name: str) -> Store:
    store = db.query(Store).filter(Store.slug == slug).first()
    if store is None:
        store = Store(slug=slug, name=name)
        db.add(store)
        db.flush()
    return store


_LOOKUP = object()  # sentinel: upsert_offer looks the listing up itself


def upsert_offer(
    db: Session,
    offer: ScrapedOffer,
    category_slug: str,
    index: ProductIndex | None = None,
    *,
    store: Store | None = None,
    listing: Listing | None = _LOOKUP,  # type: ignore[assignment]
    flush: bool = True,
) -> tuple[Listing, PriceSnapshot | None]:
    """Returns the new snapshot, or None when the price didn't change: history
    is only recorded on changes, so re-scraping 40k+ offers every cycle doesn't
    grow the DB (Neon's free tier blocks writes past 1 GB).

    The scrape loop passes the store, the pre-fetched listing (None if new) and
    flush=False, so each offer costs no DB round trip of its own: the remote
    Postgres is ~50 ms away from the GitHub runners, and per-offer queries
    made a 10k-offer pass take over an hour. Everything is written when the
    caller flushes the page.
    """
    if index is None:
        index = ProductIndex(db)
    if store is None:
        store = get_or_create_store(db, offer.store_slug, offer.store_name)
    if listing is _LOOKUP:
        listing = (
            db.query(Listing)
            .filter(Listing.store_id == store.id, Listing.external_id == offer.external_id)
            .first()
        )
    if listing is None:
        product_id, product = match_or_create_product(
            db,
            title=offer.title,
            price=offer.price,
            category_slug=category_slug,
            brand=offer.brand,
            image_url=offer.image_url,
            index=index,
            flush=flush,
            exact=offer.exact_match,
        )
        listing = Listing(
            store_id=store.id,
            external_id=offer.external_id,
            title=offer.title,
            url=offer.url,
            image_url=offer.image_url,
        )
        if product is not None:
            listing.product = product
        else:
            listing.product_id = product_id
        db.add(listing)
    else:
        listing.title = offer.title
        listing.url = offer.url
        listing.image_url = offer.image_url or listing.image_url
        now = utcnow()
        if ensure_aware(listing.last_seen_at) < now - SEEN_REFRESH:
            listing.last_seen_at = now
        listing.is_active = True
        if offer.brand and not listing.product.brand:
            listing.product.brand = offer.brand
        if offer.image_url and not listing.product.image_url:
            listing.product.image_url = offer.image_url
        started = started_event_start()
        if (
            started
            and listing.pre_event_price is None
            and listing.current_price is not None
            and ensure_aware(listing.first_seen_at) < started
        ):
            # First visit since the event began: the stored price is still
            # the one from before it.
            listing.pre_event_price = listing.current_price
    if offer.details != (listing.raw_attributes or {}).get("details"):
        listing.raw_attributes = {**(listing.raw_attributes or {}), "details": offer.details}
    if offer.rating is not None:
        listing.rating = offer.rating
        listing.review_count = offer.review_count

    discount_pct = None
    if offer.original_price and offer.original_price > 0:
        discount_pct = round((offer.original_price - offer.price) / offer.original_price * 100, 2)

    unchanged = (
        listing.current_price is not None
        and float(listing.current_price) == offer.price
        and (float(listing.current_original_price) if listing.current_original_price else None)
        == offer.original_price
    )
    if unchanged:
        if flush:
            db.flush()
        return listing, None

    snapshot = PriceSnapshot(price=offer.price, original_price=offer.original_price, discount_pct=discount_pct)
    snapshot.listing = listing
    db.add(snapshot)
    listing.current_price = offer.price
    listing.current_original_price = offer.original_price
    listing.current_discount_pct = discount_pct
    if flush:
        db.flush()
    return listing, snapshot


async def dispatch_alerts(db: Session, listing: Listing, snapshot: PriceSnapshot) -> None:
    alerts = check_price_drop(db, listing, snapshot)
    for alert in alerts:
        subscriber = alert.favorite.subscriber
        if subscriber.telegram_chat_id is None:
            continue
        message = format_price_drop_message(
            product_title=listing.product.canonical_title,
            store_name=listing.store.name,
            old_price=alert.old_price,
            new_price=alert.new_price,
            url=listing.url,
        )
        sent = await send_message(subscriber.telegram_chat_id, message, parse_mode="Markdown")
        if sent:
            record_alert_sent(db, alert)


def selected_stores() -> list[StoreScraper]:
    wanted = {s.strip() for s in os.environ.get("SCRAPE_STORES", "").split(",") if s.strip()}
    return [s for s in ALL_STORES if not wanted or s.slug in wanted or s.job_group in wanted]


def sync_cyber_cl(db: Session, client: PoliteClient) -> dict[str, dict]:
    """Sync categories from cyber.cl and return its brands keyed by name.
    Failures are logged, not fatal: stores can still be scraped without it."""
    try:
        event = cyber_cl.fetch_current_event(client)
        cyber_cl.sync_categories(db, cyber_cl.fetch_event_categories(client, event["slug"]))
        brands = cyber_cl.fetch_event_brands(client, event["slug"])
        db.commit()
        logger.info("cyber.cl: event %s, %d participating brands", event["name"], len(brands))
        return {b["name"]: b for b in brands}
    except Exception:
        logger.exception("Could not read cyber.cl's API -- continuing without it")
        db.rollback()
        return {}


def prefetch_listings(db: Session, store: Store, external_ids: list[str]) -> dict[str, Listing]:
    """One query for a whole page of offers instead of one per offer."""
    if not external_ids:
        return {}
    listings = db.scalars(
        select(Listing)
        .options(selectinload(Listing.product))
        .where(Listing.store_id == store.id, Listing.external_id.in_(external_ids))
    )
    return {listing.external_id: listing for listing in listings}


async def scrape_store(db: Session, client: PoliteClient, scraper: StoreScraper, index: ProductIndex,
                       brands: dict[str, dict]) -> int:
    store = cyber_cl.sync_store_from_brand(db, scraper.slug, scraper.name, brands.get(scraper.cyber_brand_name))
    db.commit()
    # Only products someone follows can trigger a price-drop alert.
    favorited = set(db.scalars(select(Favorite.product_id)))
    run_started = utcnow()
    seen: set[str] = set()
    failed_departments = 0

    for department in scraper.departments:
        started = time.monotonic()
        count = 0
        try:
            pages = (QUICK_PAGES if is_quick_mode() else MAX_PAGES_PER_DEPARTMENT) * scraper.pages_per_step
            for offers in scraper.iter_department(client, department, max_pages=pages):
                # The same product can be listed twice on a page or under two departments.
                page_offers = {}
                for offer in offers:
                    if offer.external_id not in seen:
                        seen.add(offer.external_id)
                        page_offers.setdefault(offer.external_id, offer)
                existing = prefetch_listings(db, store, list(page_offers))
                for external_id, offer in page_offers.items():
                    previous = existing.get(external_id)
                    listing, snapshot = upsert_offer(
                        db, offer, offer.category_slug, index, store=store, listing=previous, flush=False
                    )
                    # A brand-new listing has no earlier price to drop from.
                    if snapshot is not None and previous is not None and listing.product_id in favorited:
                        db.flush()
                        await dispatch_alerts(db, listing, snapshot)
                    count += 1
                db.flush()
                index.register_pending()
                db.commit()
        except Exception:
            failed_departments += 1
            db.rollback()
            index.pending.clear()
            logger.exception("%s / %s failed after %d offers", scraper.name, department.label, count)
        logger.info("%s / %s: %d offers (%.0fs)", scraper.name, department.label, count, time.monotonic() - started)

    if seen and not failed_departments and not is_quick_mode():
        stale = (
            db.query(Listing)
            .filter(
                Listing.store_id == store.id,
                Listing.is_active.is_(True),
                Listing.last_seen_at < run_started - SEEN_REFRESH,
            )
            .update({Listing.is_active: False, Listing.updated_at: utcnow()}, synchronize_session=False)
        )
        db.commit()
        logger.info("%s: marked %d listings inactive", scraper.name, stale)
    return len(seen)


async def run_scrape() -> None:
    if not is_scrape_window_active():
        logger.info("No active Cyber event window -- skipping scrape.")
        return

    db = SessionLocal()
    try:
        with PoliteClient() as client:
            brands = sync_cyber_cl(db, client)
            index = ProductIndex(db)
            totals = {}
            for scraper in selected_stores():
                if brands and scraper.cyber_brand_name not in brands:
                    logger.info("%s is not in cyber.cl's participant list -- scraping anyway", scraper.name)
                totals[scraper.slug] = await scrape_store(db, client, scraper, index, brands)
            logger.info(
                "Scrape finished (%s mode): %s (total %d)",
                "quick" if is_quick_mode() else "full", totals, sum(totals.values()),
            )
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run_scrape())
