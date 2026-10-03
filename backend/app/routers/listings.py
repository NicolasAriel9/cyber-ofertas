import math
import time

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.auth import require_auth
from app.db import get_db
from app.models import Category, Listing, Product, Store
from app.schemas import CategoryHighlightsOut, ListingOut

router = APIRouter(dependencies=[Depends(require_auth)], tags=["listings"])


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
    )


SORTS = {
    "discount": (Listing.current_discount_pct.desc().nulls_last(), Listing.id),
    "price_asc": (Listing.current_price.asc().nulls_last(), Listing.id),
    "price_desc": (Listing.current_price.desc().nulls_last(), Listing.id),
    "recent": (Listing.first_seen_at.desc(), Listing.id.desc()),
}


@router.get("/listings", response_model=list[ListingOut])
def list_listings(
    category: str | None = None,
    store: str | None = None,
    search: str | None = None,
    min_discount: float | None = None,
    sort: str = Query("discount", pattern="^(discount|price_asc|price_desc|recent)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    response: Response = None,
    db: Session = Depends(get_db),
):
    query = (
        db.query(Listing)
        .join(Listing.product)
        .options(joinedload(Listing.store))
        .filter(Listing.is_active.is_(True))
    )

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


# The scraper writes every ~10 min; recomputing highlights on every page load
# would scan all active listings for nothing.
HIGHLIGHTS_TTL_SECONDS = 300
_highlights_cache: dict[int, tuple[float, list[CategoryHighlightsOut]]] = {}


@router.get("/highlights", response_model=list[CategoryHighlightsOut])
def list_highlights(per_category: int = Query(3, ge=1, le=10), db: Session = Depends(get_db)):
    """Best few offers of every category, for the top of the home page."""
    cached = _highlights_cache.get(per_category)
    if cached and time.monotonic() - cached[0] < HIGHLIGHTS_TTL_SECONDS:
        return cached[1]

    rank = (
        func.row_number()
        .over(partition_by=Product.category_id, order_by=(Listing.current_discount_pct.desc(), Listing.id))
        .label("rank")
    )
    candidates = (
        select(Listing.id.label("listing_id"), rank)
        .join(Listing.product)
        .where(
            Listing.is_active.is_(True),
            Product.category_id.is_not(None),
            Listing.current_discount_pct.between(HIGHLIGHT_MIN_DISCOUNT, HIGHLIGHT_MAX_DISCOUNT),
            Listing.current_original_price - Listing.current_price >= HIGHLIGHT_MIN_SAVINGS,
        )
        .subquery()
    )
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
        .filter(Listing.is_active.is_(True))
        .group_by(Product.category_id)
        .all()
    )

    highlights = []
    for category_listings in by_category.values():
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
    # Biggest categories first: that's where most of the action is.
    highlights.sort(key=lambda h: h.total, reverse=True)
    _highlights_cache[per_category] = (time.monotonic(), highlights)
    return highlights


@router.get("/listings/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    return _to_listing_out(listing)
