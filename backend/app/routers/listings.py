from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.auth import require_auth
from app.db import get_db
from app.models import Category, Listing, Product, Store
from app.schemas import ListingOut

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


@router.get("/listings/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    return _to_listing_out(listing)
