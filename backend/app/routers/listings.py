from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.auth import require_auth
from app.db import get_db
from app.models import Category, Listing, Store
from app.schemas import ListingOut

router = APIRouter(dependencies=[Depends(require_auth)], tags=["listings"])


def _to_listing_out(listing: Listing) -> ListingOut:
    latest = listing.price_snapshots[-1] if listing.price_snapshots else None
    return ListingOut(
        id=listing.id,
        product_id=listing.product_id,
        store=listing.store,
        title=listing.title,
        url=listing.url,
        image_url=listing.image_url,
        latest_price=float(latest.price) if latest else None,
        latest_discount_pct=float(latest.discount_pct) if latest and latest.discount_pct else None,
    )


@router.get("/listings", response_model=list[ListingOut])
def list_listings(
    category: str | None = None,
    store: str | None = None,
    search: str | None = None,
    min_discount: float | None = None,
    sort: str = Query("discount", pattern="^(discount|price_asc|price_desc|recent)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Listing).options(joinedload(Listing.store), joinedload(Listing.product)).filter(
        Listing.is_active.is_(True)
    )

    if store:
        query = query.join(Store).filter(Store.slug == store)
    if category:
        query = query.join(Listing.product).join(Category).filter(Category.slug == category)
    if search:
        query = query.filter(Listing.title.ilike(f"%{search}%"))

    listings = query.all()
    results = [_to_listing_out(listing) for listing in listings]

    if min_discount is not None:
        results = [r for r in results if (r.latest_discount_pct or 0) >= min_discount]

    if sort == "discount":
        results.sort(key=lambda r: r.latest_discount_pct or 0, reverse=True)
    elif sort == "price_asc":
        results.sort(key=lambda r: r.latest_price or float("inf"))
    elif sort == "price_desc":
        results.sort(key=lambda r: r.latest_price or 0, reverse=True)

    start = (page - 1) * page_size
    return results[start : start + page_size]


@router.get("/listings/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    return _to_listing_out(listing)
