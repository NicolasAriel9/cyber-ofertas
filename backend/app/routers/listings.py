import math
import time

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import and_, case, false, func, or_, select
from sqlalchemy.orm import Session, contains_eager, joinedload

from app.auth import require_auth
from app.db import get_db
from app.models import Category, Listing, Product, Store, listing_is_live
from app.scraper.event_windows import started_event_start
from app.schemas import CategoryHighlightsOut, ListingOut
from app.sections import SECTION_PATTERN, TRAVEL_CATEGORY_SLUGS, section_filter

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


MIN_REVIEWS = 3
# A rating backed by enough reviews to trust (see the "rating" sort).
WELL_RATED = and_(Listing.rating.is_not(None), func.coalesce(Listing.review_count, MIN_REVIEWS) >= MIN_REVIEWS)
SAVINGS = Listing.current_original_price - Listing.current_price

# Same idea as the highlights score (_highlight_score): the discount weighted
# by the money it saves, with implausible discounts sent to the bottom.
BELIEVABLE_DEAL = and_(
    Listing.current_discount_pct.between(20, 85),
    SAVINGS >= 5000,
)

SORTS = {
    "top": (
        case((BELIEVABLE_DEAL, 0), else_=1),
        (Listing.current_discount_pct * func.ln(case((SAVINGS > 1, SAVINGS), else_=1))).desc().nulls_last(),
        Listing.id,
    ),
    "discount": (Listing.current_discount_pct.desc().nulls_last(), Listing.id),
    "price_asc": (Listing.current_price.asc().nulls_last(), Listing.id),
    "price_desc": (Listing.current_price.desc().nulls_last(), Listing.id),
    "recent": (Listing.first_seen_at.desc(), Listing.id.desc()),
    "savings": (SAVINGS.desc().nulls_last(), Listing.id),
    # A 5-star product with one review shouldn't outrank a 4.8 with hundreds:
    # ratings backed by fewer than MIN_REVIEWS reviews go after the rest.
    # Mercado Libre doesn't publish the count, so its ratings count as backed.
    "rating": (
        case((WELL_RATED, 0), else_=1),
        Listing.rating.desc().nulls_last(),
        Listing.review_count.desc().nulls_last(),
        Listing.current_discount_pct.desc().nulls_last(),
        Listing.id,
    ),
}


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
    query = (
        db.query(Listing)
        .join(Listing.product)
        .options(joinedload(Listing.store), contains_eager(Listing.product).joinedload(Product.category))
        .filter(listing_is_live())
    )

    if (where := section_filter(section)) is not None:
        query = query.filter(where)
    if store:
        query = query.join(Store).filter(Store.slug == store)
    if category:
        query = query.join(Category, Product.category_id == Category.id).filter(Category.slug == category)
    if search:
        # Every word must appear in the title or the brand: stores often leave
        # the brand out of the title ("Notebook IdeaPad Slim 3...").
        for word in search.split():
            query = query.filter(or_(Listing.title.ilike(f"%{word}%"), Product.brand.ilike(f"%{word}%")))
    if min_discount is not None:
        query = query.filter(Listing.current_discount_pct >= min_discount)
    if cyber:
        # Cheaper than right before the event, or first seen since it began.
        # "New" only counts at stores we were already reading before the start:
        # a store first scraped mid-event (or a database rebuilt mid-event)
        # would otherwise list its whole catalog as Cyber offers.
        started = started_event_start()
        if started:
            tracked_before = select(Listing.store_id).where(Listing.first_seen_at < started).distinct()
            query = query.filter(
                or_(
                    Listing.current_price <= Listing.pre_event_price * CYBER_MIN_DROP,
                    and_(Listing.first_seen_at >= started, Listing.store_id.in_(tracked_before)),
                )
            )
        else:
            query = query.filter(false())
    if min_rating is not None:
        query = query.filter(WELL_RATED, Listing.rating >= min_rating)
    if min_price is not None:
        query = query.filter(Listing.current_price >= min_price)
    if max_price is not None:
        query = query.filter(Listing.current_price <= max_price)

    response.headers["X-Total-Count"] = str(query.order_by(None).count())
    listings = query.order_by(*SORTS[sort]).offset((page - 1) * page_size).limit(page_size).all()
    return [_to_listing_out(listing) for listing in listings]


# Highlights skip discounts that are usually bogus (a "-95%" on a crossed-out
# price nobody ever charged) and tiny savings on cheap items.
HIGHLIGHT_MIN_DISCOUNT = 20
HIGHLIGHT_MAX_DISCOUNT = 85
HIGHLIGHT_MIN_SAVINGS = 5000
HIGHLIGHT_CANDIDATES = 40


def _highlight_score(listing: Listing) -> float:
    # A -60% on a $400.000 TV beats a -70% on a $3.000 cable: weigh the
    # discount by how much money it actually saves.
    savings = float(listing.current_original_price) - float(listing.current_price)
    return float(listing.current_discount_pct) * math.log10(savings)


def _pick_varied(listings: list[Listing], count: int) -> list[Listing]:
    """Top `count` listings by score, one per product, spreading across stores
    when the category has enough of them."""
    picked: list[Listing] = []
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


# The scraper writes every ~5 min and the page polls every minute; recomputing
# highlights on every request would scan all active listings for nothing.
HIGHLIGHTS_TTL_SECONDS = 60
_highlights_cache: dict[tuple[str, int], tuple[float, list[CategoryHighlightsOut]]] = {}


def _travel_sort_key(listing: Listing) -> tuple[float, float]:
    # Fares usually come as "desde $X" with no crossed-out price: the best deal
    # is the cheapest. Real discounts (during the event) still go first.
    return (-float(listing.current_discount_pct or 0), float(listing.current_price))


@router.get("/highlights", response_model=list[CategoryHighlightsOut])
def list_highlights(
    per_category: int = Query(3, ge=1, le=10),
    section: str = Query("productos", pattern=SECTION_PATTERN),
    db: Session = Depends(get_db),
):
    """Best few offers of every category of a section, for the top of its page."""
    cached = _highlights_cache.get((section, per_category))
    if cached and time.monotonic() - cached[0] < HIGHLIGHTS_TTL_SECONDS:
        return cached[1]

    travel = section == "viajes"
    order = (
        (Listing.current_discount_pct.desc().nulls_last(), Listing.current_price, Listing.id)
        if travel
        else (Listing.current_discount_pct.desc(), Listing.id)
    )
    rank = func.row_number().over(partition_by=Product.category_id, order_by=order).label("rank")
    conditions = [listing_is_live(), Product.category_id.is_not(None), section_filter(section)]
    if not travel:
        conditions += [
            Listing.current_discount_pct.between(HIGHLIGHT_MIN_DISCOUNT, HIGHLIGHT_MAX_DISCOUNT),
            Listing.current_original_price - Listing.current_price >= HIGHLIGHT_MIN_SAVINGS,
        ]
    else:
        conditions.append(Listing.current_price.is_not(None))
    candidates = select(Listing.id.label("listing_id"), rank).join(Listing.product).where(*conditions).subquery()
    listings = (
        db.query(Listing)
        .join(candidates, candidates.c.listing_id == Listing.id)
        .filter(candidates.c.rank <= HIGHLIGHT_CANDIDATES)
        .options(joinedload(Listing.store), joinedload(Listing.product).joinedload(Product.category))
        .all()
    )

    by_category: dict[int, list[Listing]] = {}
    for listing in listings:
        by_category.setdefault(listing.product.category_id, []).append(listing)

    totals = dict(
        db.query(Product.category_id, func.count(Listing.id))
        .join(Listing.product)
        .filter(listing_is_live())
        .group_by(Product.category_id)
        .all()
    )

    highlights = []
    for category_listings in by_category.values():
        if travel:
            category_listings.sort(key=_travel_sort_key)
        else:
            category_listings.sort(key=_highlight_score, reverse=True)
        best = _pick_varied(category_listings, per_category)
        category = category_listings[0].product.category
        highlights.append(
            CategoryHighlightsOut(
                category=category,
                total=totals.get(category.id, 0),
                listings=[_to_listing_out(listing) for listing in best],
            )
        )
    if travel:
        highlights.sort(key=lambda h: TRAVEL_CATEGORY_SLUGS.index(h.category.slug))
    else:
        # Biggest categories first: that's where most of the action is.
        highlights.sort(key=lambda h: h.total, reverse=True)
    _highlights_cache[(section, per_category)] = (time.monotonic(), highlights)
    return highlights


@router.get("/listings/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    return _to_listing_out(listing)
