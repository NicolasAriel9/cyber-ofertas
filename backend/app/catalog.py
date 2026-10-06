"""Compact in-memory copy of every listing's filter and sort columns.

The browse queries (lists, highlights, stores, categories) used to scan the
listing table (~250k rows, 165 MB) on every request and every cache refresh.
On Supabase's free plan, once the day's I/O burst is spent, such a scan takes
minutes, and the app stopped loading (Oct 5 2026). Now the table is read once
when the API starts; after that, every REFRESH seconds, only the rows written
since (listing.updated_at, indexed). Requests filter and sort this copy in
Python and only fetch the ~30 rows they show, by primary key.

Disabled unless the app enables it at startup: tests (and anything else
calling the endpoint functions directly) get a fresh copy from their session.
"""
import logging
import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import LISTING_STALE_AFTER, Category, Listing, Product, Store, utcnow
from app.sections import TRAVEL_CATEGORY_SLUGS
from app.utils import ensure_aware

log = logging.getLogger(__name__)

# The scraper refreshes each store every ~10 minutes; fetching what changed
# is a small indexed read.
REFRESH = 60
# Rows are stamped when the scraper flushes them but become visible when it
# commits, a little later: re-read a margin, re-applying a row is harmless.
OVERLAP = timedelta(minutes=5)
# A full re-read now and then (in the background, requests keep the current
# copy) catches writes that didn't stamp updated_at -- a scrape job started
# before this code was deployed -- and product category/brand changes.
FULL_EVERY = 30 * 60


def _num(value) -> float | None:
    return float(value) if value is not None else None  # Numeric -> Decimal


@dataclass(slots=True)
class Row:
    """~250k of these live in memory: times are POSIX timestamps, not
    datetimes, and only active listings are kept."""
    id: int
    product_id: int
    store_id: int
    category_id: int | None
    title: str  # lowercased, for search
    brand: str  # lowercased, for search; shared between a brand's rows
    price: float | None
    original_price: float | None
    discount_pct: float | None
    rating: float | None
    review_count: int | None
    first_seen: float
    last_seen: float
    pre_event_price: float | None
    savings: float | None = None
    top_score: float | None = None  # see the "top" sort

    def __post_init__(self) -> None:
        if self.original_price is not None and self.price is not None:
            self.savings = self.original_price - self.price
        if self.discount_pct is not None and self.savings is not None:
            self.top_score = self.discount_pct * math.log(self.savings if self.savings > 1 else 1)


@dataclass
class Snapshot:
    by_section: dict[str | None, list[Row]]  # live rows; None = every section
    store_slugs: dict[int, str]
    category_slugs: dict[int, str]
    # Earliest first_seen of each store, inactive listings included.
    store_first_seen: dict[int, float]

    def live(self, section: str | None = None) -> list[Row]:
        return self.by_section[section]

    def stores_tracked_before(self, moment: datetime) -> set[int]:
        ts = moment.timestamp()
        return {store_id for store_id, first in self.store_first_seen.items() if first < ts}


_COLUMNS = (
    Listing.id, Listing.product_id, Listing.store_id, Product.category_id, Listing.title, Product.brand,
    Listing.current_price, Listing.current_original_price, Listing.current_discount_pct,
    Listing.rating, Listing.review_count, Listing.first_seen_at, Listing.last_seen_at,
    Listing.is_active, Listing.pre_event_price,
)


class Catalog:
    def __init__(self) -> None:
        self.enabled = False
        self._rows: dict[int, Row] = {}
        self._store_first_seen: dict[int, float] = {}
        self._brands: dict[str, str] = {}
        self._since: datetime | None = None
        self._full_at = 0.0
        self._snapshot: Snapshot | None = None
        self._lock = threading.Lock()

    def get(self, db: Session) -> Snapshot:
        if not self.enabled:
            fresh = Catalog()
            fresh._load(db)
            return fresh._snapshot
        if self._snapshot is None:
            with self._lock:  # one load at startup, not one per waiting request
                if self._snapshot is None:
                    self._load(db)
        return self._snapshot

    def start(self) -> None:
        self.enabled = True
        threading.Thread(target=self._refresh_forever, name="catalog", daemon=True).start()

    def _refresh_forever(self) -> None:
        # The first, full load is made by the first request (the startup warm-up).
        while True:
            time.sleep(REFRESH)
            if self._snapshot is None:
                continue
            if time.monotonic() - self._full_at > FULL_EVERY:
                self._since = None
            try:
                with self._lock, SessionLocal() as db:
                    self._load(db)
            except Exception:
                log.exception("catalog refresh failed; serving the previous copy")

    def _load(self, db: Session) -> None:
        started = time.monotonic()
        since, next_since = self._since, utcnow()
        query = select(*_COLUMNS).join(Product, Listing.product_id == Product.id)
        if since is not None:
            query = query.where(Listing.updated_at >= since - OVERLAP)
        elif db.get_bind().dialect.name == "postgresql":
            # Supabase cancels statements after ~2 minutes; on its throttled
            # disk a full read can take longer. SET LOCAL lasts until this
            # transaction ends, on the session the pooler gave it.
            db.execute(text("SET LOCAL statement_timeout = 0"))
        count = 0
        for r in db.execute(query.execution_options(yield_per=5000)):
            count += 1
            self._apply(r)
        self._since = next_since
        if since is None:
            self._full_at = time.monotonic()
        self._publish(db)
        if since is None or count:
            log.info("catalog: %s %d rows in %.1fs (%d live)", "read" if since is None else "updated", count,
                     time.monotonic() - started, len(self._snapshot.by_section[None]))

    def _apply(self, r) -> None:
        first_seen = ensure_aware(r.first_seen_at).timestamp()
        if first_seen < self._store_first_seen.get(r.store_id, math.inf):
            self._store_first_seen[r.store_id] = first_seen
        last_seen = ensure_aware(r.last_seen_at).timestamp()
        if not r.is_active or last_seen < (utcnow() - LISTING_STALE_AFTER).timestamp():
            # Hidden anyway (see listing_is_live); if seen again, the write
            # brings it back in.
            self._rows.pop(r.id, None)
            return
        brand = (r.brand or "").lower()
        self._rows[r.id] = Row(
            id=r.id,
            product_id=r.product_id,
            store_id=r.store_id,
            category_id=r.category_id,
            title=(r.title or "").lower(),
            brand=self._brands.setdefault(brand, brand),
            price=_num(r.current_price),
            original_price=_num(r.current_original_price),
            discount_pct=_num(r.current_discount_pct),
            rating=r.rating,
            review_count=r.review_count,
            first_seen=first_seen,
            last_seen=last_seen,
            pre_event_price=_num(r.pre_event_price),
        )

    def _publish(self, db: Session) -> None:
        categories = dict(db.execute(select(Category.id, Category.slug)).all())
        travel = {cid for cid, slug in categories.items() if slug in TRAVEL_CATEGORY_SLUGS}
        cutoff = (utcnow() - LISTING_STALE_AFTER).timestamp()
        live = [r for r in self._rows.values() if r.last_seen >= cutoff]
        self._snapshot = Snapshot(
            by_section={
                None: live,
                "productos": [r for r in live if r.category_id not in travel],
                "viajes": [r for r in live if r.category_id in travel],
            },
            store_slugs=dict(db.execute(select(Store.id, Store.slug)).all()),
            category_slugs=categories,
            store_first_seen=dict(self._store_first_seen),
        )


catalog = Catalog()


# --- sort keys, matching what the SQL version did (NULLs last) ---

MIN_REVIEWS = 3


def well_rated(row: Row) -> bool:
    """A rating backed by enough reviews to trust. Mercado Libre doesn't
    publish the count, so its ratings count as backed."""
    return row.rating is not None and (row.review_count if row.review_count is not None else MIN_REVIEWS) >= MIN_REVIEWS


def believable_deal(row: Row) -> bool:
    return (row.discount_pct is not None and 20 <= row.discount_pct <= 85
            and row.savings is not None and row.savings >= 5000)


def _desc(value: float | None) -> tuple[int, float]:
    return (1, 0.0) if value is None else (0, -value)


def _asc(value: float | None) -> tuple[int, float]:
    return (1, 0.0) if value is None else (0, value)


SORT_KEYS = {
    "top": lambda r: (0 if believable_deal(r) else 1, _desc(r.top_score), r.id),
    "discount": lambda r: (_desc(r.discount_pct), r.id),
    "price_asc": lambda r: (_asc(r.price), r.id),
    "price_desc": lambda r: (_desc(r.price), r.id),
    "recent": lambda r: (-r.first_seen, -r.id),
    "savings": lambda r: (_desc(r.savings), r.id),
    # A 5-star product with one review shouldn't outrank a 4.8 with hundreds.
    "rating": lambda r: (
        0 if well_rated(r) else 1,
        _desc(r.rating),
        _desc(r.review_count),
        _desc(r.discount_pct),
        r.id,
    ),
}
