"""Client for cyber.cl's public JSON API (the backend behind the official
event site, at app.cyber.cl/api/).

cyber.cl itself does NOT publish products or prices -- it is a directory of
participating brands that links out to each store (re-inspected 2026-10-01,
see docs/cyber_cl_inspection_notes.md). So it's used here for what it does
have: the official category list (our Category rows mirror it) and which
stores are participating in the current event, plus their logos. Offers come
from the per-store scrapers in app/scraper/stores/.
"""

import logging
import re
import unicodedata

from sqlalchemy.orm import Session

from app.models import Category, Store
from app.scraper.http import PoliteClient

logger = logging.getLogger(__name__)

API_BASE = "https://app.cyber.cl/api"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def fetch_current_event(client: PoliteClient) -> dict:
    return client.get_json(f"{API_BASE}/events/current/")


def fetch_event_brands(client: PoliteClient, event_slug: str) -> list[dict]:
    return client.get_json(f"{API_BASE}/events/{event_slug}/brands/")


def fetch_event_categories(client: PoliteClient, event_slug: str) -> list[dict]:
    return client.get_json(f"{API_BASE}/events/{event_slug}/categories/")


def sync_categories(db: Session, categories: list[dict]) -> None:
    for item in categories:
        slug = slugify(item["name"])
        category = db.query(Category).filter(Category.slug == slug).first()
        if category is None:
            db.add(Category(name=item["name"], slug=slug))
        else:
            category.name = item["name"]
    db.flush()


def sync_store_from_brand(db: Session, store_slug: str, store_name: str, brand: dict | None) -> Store:
    store = db.query(Store).filter(Store.slug == store_slug).first()
    if store is None:
        store = Store(slug=store_slug, name=store_name)
        db.add(store)
    store.name = store_name
    if brand and brand.get("logo"):
        store.logo_url = brand["logo"]
    db.flush()
    return store
