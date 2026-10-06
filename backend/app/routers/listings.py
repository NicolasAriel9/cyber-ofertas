import heapq
import math
from collections import Counter

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session, joinedload

from app.auth import require_auth
from app.cache import response_cache
from app.catalog import SORT_KEYS, Row, catalog, well_rated
from app.db import get_db
from app.models import Category, Listing, Product
from app.scraper.event_windows import started_event_start
from app.schemas import CategoryHighlightsOut, ListingOut
from app.sections import SECTION_PATTERN, TRAVEL_CATEGORY_SLUGS

router = APIRouter(dependencies=[Depends(require_auth)], tags=["listings"])


# A drop smaller than this since the event began is rounding noise, not a deal.
CYBER_MIN_DROP = 0.99


def _cyber_drop_pct(listing: Listing) -> float | None:
    if listing.pre_event_price is None or listing.current_price is None:
        return None
    before, now = float(listing.pre_event_price), float(listing.current_price)  # Numeric -> Decimal
    if now > before * CYBER_MIN_DROP:
        return None
    return round((before - now) / before * 100, 1)


def _to_listing_out(listing: Listing) -> ListingOut:
    return ListingOut(
        id=listing.id,
        product_id=listing.product_id,
        store=listing.store,
        title=listing.title,
        url=listing.url,
        image_url=listing.image_url,
        latest_price=float(listing.current_price) if listing.current_price is not None else None,
        latest_original_price=float(listing.current_original_price) if listing.current_original_price else None,
        latest_discount_pct=float(listing.current_discount_pct) if listing.current_discount_pct else None,
        details=(listing.raw_attributes or {}).get("details"),
        category_slug=listing.product.category.slug if listing.product.category else None,
        rating=listing.rating,
        review_count=listing.review_count,
        first_seen_at=listing.first_seen_at,
        cyber_drop_pct=_cyber_drop_pct(listing),
    )


@router.get("/listings", response_model=list[ListingOut])
def list_listings(
    category: str | None = None,
    store: str | None = None,
    search: str | None = None,
    min_discount: float | None = None,
    cyber: bool = False,
    min_rating: float | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    section: str | None = Query(None, pattern=SECTION_PATTERN),
    sort: str = Query("discount", pattern="^(top|discount|savings|price_asc|price_desc|recent|rating)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    response: Response = None,
    db: Session = Depends(get_db),
):
    key = ("listings", category, store, search, min_discount, cyber, min_rating, min_price, max_price,
           section, sort, page, page_size)

    def compute(db: Session) -> tuple[int, list[ListingOut]]:
        return _query_listings(db, category, store, search, min_discount, cyber, min_rating, min_price, max_price,
                               section, sort, page, page_size)

    total, listings = response_cache.get(key, compute, db)
    response.headers["X-Total-Count"] = str(total)
    return listings


def _query_listings(db, category, store, search, min_discount, cyber, min_rating, min_price, max_price,
                    section, sort, page, page_size) -> tuple[int, list[ListingOut]]:
    snapshot = catalog.get(db)
    rows = snapshot.live(section)

    if store:
        rows = [r for r in rows if snapshot.store_slugs.get(r.store_id) == store]
    if category:
        rows = [r for r in rows if snapshot.category_slugs.get(r.category_id) == category]
    if search:
        # Every word must appear in the title or the brand: stores often leave
        # the brand out of the title ("Notebook IdeaPad Slim 3...").
        for word in search.lower().split():
            rows = [r for r in rows if word in r.title or word in r.brand]
    if min_discount is not None:
        rows = [r for r in rows if r.discount_pct is not None and r.discount_pct >= min_discount]
    if cyber:
        # Cheaper than right before the event, or first seen since it began.
        # "New" only counts at stores we were already reading before the start:
        # a store first scraped mid-event (or a database rebuilt mid-event)
        # would otherwise list its whole catalog as Cyber offers.
        started = started_event_start()
        if started:
            tracked_before = snapshot.stores_tracked_before(started)
            started_ts = started.timestamp()
            rows = [
                r for r in rows
                if (r.pre_event_price is not None and r.price is not None
                    and r.price <= r.pre_event_price * CYBER_MIN_DROP)
                or (r.first_seen >= started_ts and r.store_id in tracked_before)
            ]
        else:
            rows = []
    if min_rating is not None:
        rows = [r for r in rows if well_rated(r) and r.rating >= min_rating]
    if min_price is not None:
        rows = [r for r in rows if r.price is not None and r.price >= min_price]
    if max_price is not None:
        rows = [r for r in rows if r.price is not None and r.price <= max_price]

    page_rows = heapq.nsmallest(page * page_size, rows, key=SORT_KEYS[sort])[(page - 1) * page_size:]
    return len(rows), _listings_out(db, [r.id for r in page_rows])


def _listings_out(db: Session, ids: list[int]) -> list[ListingOut]:
    """The rows to show, by primary key, in the given order."""
    if not ids:
        return []
    by_id = {
        listing.id: listing
        for listing in db.query(Listing)
        .filter(Listing.id.in_(ids))
        .options(joinedload(Listing.store), joinedload(Listing.product).joinedload(Product.category))
    }
    return [_to_listing_out(by_id[i]) for i in ids if i in by_id]


# Highlights skip discounts that are usually bogus (a "-95%" on a crossed-out
# price nobody ever charged) and tiny savings on cheap items.
HIGHLIGHT_MIN_DISCOUNT = 20
HIGHLIGHT_MAX_DISCOUNT = 85
HIGHLIGHT_MIN_SAVINGS = 5000
HIGHLIGHT_CANDIDATES = 40


def _highlight_score(row: Row) -> float:
    # A -60% on a $400.000 TV beats a -70% on a $3.000 cable: weigh the
    # discount by how much money it actually saves.
    return row.discount_pct * math.log10(row.savings)


def _pick_varied(listings: list, count: int) -> list:
    """Top `count` listings by score, one per product, spreading across stores
    when the category has enough of them."""
    picked: list = []
    for one_per_store in (True, False):
        for listing in listings:
            if len(picked) == count:
                return picked
            if any(p.product_id == listing.product_id or p.id == listing.id for p in picked):
                continue
            if one_per_store and any(p.store_id == listing.store_id for p in picked):
                continue
            picked.append(listing)
    return picked


def _travel_sort_key(row: Row) -> tuple[float, float]:
    # Fares usually come as "desde $X" with no crossed-out price: the best deal
    # is the cheapest. Real discounts (during the event) still go first.
    return (-(row.discount_pct or 0), row.price)


@router.get("/highlights", response_model=list[CategoryHighlightsOut])
def list_highlights(
    per_category: int = Query(3, ge=1, le=10),
    section: str = Query("productos", pattern=SECTION_PATTERN),
    db: Session = Depends(get_db),
):
    """Best few offers of every category of a section, for the top of its page."""
    return response_cache.get(("highlights", section, per_category),
                              lambda db: _compute_highlights(db, section, per_category), db)


def _travel_candidate_order(row: Row):
    return ((1, 0.0) if row.discount_pct is None else (0, -row.discount_pct), row.price, row.id)


def _deal_candidate_order(row: Row):
    return (-row.discount_pct, row.id)


def _compute_highlights(db: Session, section: str, per_category: int) -> list[CategoryHighlightsOut]:
    travel = section == "viajes"
    snapshot = catalog.get(db)
    totals = Counter(r.category_id for r in snapshot.live())

    by_category: dict[int, list[Row]] = {}
    for r in snapshot.live(section):
        if r.category_id is None:
            continue
        if travel:
            if r.price is None:
                continue
        elif not (r.discount_pct is not None and HIGHLIGHT_MIN_DISCOUNT <= r.discount_pct <= HIGHLIGHT_MAX_DISCOUNT
                  and r.savings is not None and r.savings >= HIGHLIGHT_MIN_SAVINGS):
            continue
        by_category.setdefault(r.category_id, []).append(r)

    picks: dict[int, list[Row]] = {}
    for category_id, rows in by_category.items():
        # The best few by discount are the candidates, then the score decides.
        if travel:
            candidates = heapq.nsmallest(HIGHLIGHT_CANDIDATES, rows, key=_travel_candidate_order)
            candidates.sort(key=_travel_sort_key)
        else:
            candidates = heapq.nsmallest(HIGHLIGHT_CANDIDATES, rows, key=_deal_candidate_order)
            candidates.sort(key=_highlight_score, reverse=True)
        picks[category_id] = _pick_varied(candidates, per_category)

    shown = {listing.id: listing for listing in _listings_out(db, [r.id for rows in picks.values() for r in rows])}
    categories = {c.id: c for c in db.query(Category).filter(Category.id.in_(list(picks)))}
    highlights = [
        CategoryHighlightsOut(
            category=categories[category_id],
            total=totals.get(category_id, 0),
            listings=[shown[r.id] for r in rows if r.id in shown],
        )
        for category_id, rows in picks.items()
    ]
    if travel:
        highlights.sort(key=lambda h: TRAVEL_CATEGORY_SLUGS.index(h.category.slug))
    else:
        # Biggest categories first: that's where most of the action is.
        highlights.sort(key=lambda h: h.total, reverse=True)
    return highlights


@router.get("/listings/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    return _to_listing_out(listing)
