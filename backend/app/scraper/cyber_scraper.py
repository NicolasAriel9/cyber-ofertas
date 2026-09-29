"""Entrypoint run by the Render Cron Job (python -m app.scraper.cyber_scraper).

For each known category: fetch the page, parse offers, upsert into the data
model via the matcher, record a new price snapshot per listing, and dispatch
any resulting price-drop alerts over Telegram. Skips entirely outside an
active Cyber event window (see event_windows.py) unless FORCE_SCRAPE=1.
"""

import asyncio
import logging

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Listing, PriceSnapshot, Store
from app.scraper.event_windows import is_scrape_window_active
from app.scraper.fetch import CATEGORY_SLUGS, fetch_category_page
from app.scraper.parser import ScrapedOffer, parse_category_html
from app.services.alerts import check_price_drop, record_alert_sent
from app.services.matcher import find_or_create_product
from app.services.telegram_client import format_price_drop_message, send_message

logger = logging.getLogger(__name__)


def get_or_create_store(db: Session, slug: str, name: str) -> Store:
    store = db.query(Store).filter(Store.slug == slug).first()
    if store is None:
        store = Store(slug=slug, name=name)
        db.add(store)
        db.flush()
    return store


def upsert_offer(db: Session, offer: ScrapedOffer, category_slug: str) -> tuple[Listing, PriceSnapshot]:
    store = get_or_create_store(db, offer.store_slug, offer.store_name)

    listing = (
        db.query(Listing)
        .filter(Listing.store_id == store.id, Listing.external_id == offer.external_id)
        .first()
    )
    if listing is None:
        product = find_or_create_product(
            db,
            title=offer.title,
            price=offer.price,
            category_slug=category_slug,
            brand=offer.brand,
            image_url=offer.image_url,
        )
        listing = Listing(
            product_id=product.id,
            store_id=store.id,
            external_id=offer.external_id,
            title=offer.title,
            url=offer.url,
            image_url=offer.image_url,
        )
        db.add(listing)
        db.flush()
    else:
        listing.last_seen_at = listing.last_seen_at
        listing.is_active = True
        if offer.brand and not listing.product.brand:
            listing.product.brand = offer.brand

    discount_pct = None
    if offer.original_price and offer.original_price > 0:
        discount_pct = (offer.original_price - offer.price) / offer.original_price * 100

    snapshot = PriceSnapshot(
        listing_id=listing.id,
        price=offer.price,
        original_price=offer.original_price,
        discount_pct=discount_pct,
    )
    db.add(snapshot)
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


async def run_scrape() -> None:
    if not is_scrape_window_active():
        logger.info("No active Cyber event window -- skipping scrape.")
        return

    db = SessionLocal()
    try:
        for category_slug in CATEGORY_SLUGS:
            try:
                html = fetch_category_page(category_slug)
                offers = parse_category_html(html, category_slug)
            except NotImplementedError:
                logger.warning("Parser not implemented yet for %s -- skipping.", category_slug)
                continue
            except Exception:
                logger.exception("Failed to fetch/parse category %s", category_slug)
                continue

            for offer in offers:
                listing, snapshot = upsert_offer(db, offer, category_slug)
                db.commit()
                await dispatch_alerts(db, listing, snapshot)
                db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_scrape())
