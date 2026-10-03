from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.db import get_db
from app.models import Product
from app.routers.listings import _to_listing_out
from app.schemas import PriceHistoryPoint, ProductOut
from app.utils import ensure_aware

router = APIRouter(dependencies=[Depends(require_auth)], tags=["products"])


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductOut(
        id=product.id,
        canonical_title=product.canonical_title,
        category=product.category,
        brand=product.brand,
        image_url=product.image_url,
        listings=[_to_listing_out(listing) for listing in product.listings if listing.is_live],
    )


@router.get("/products/{product_id}/price-history", response_model=list[PriceHistoryPoint])
def get_price_history(
    product_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    points: list[PriceHistoryPoint] = []
    for listing in product.listings:
        for snapshot in listing.price_snapshots:
            if ensure_aware(snapshot.scraped_at) >= cutoff:
                points.append(
                    PriceHistoryPoint(
                        scraped_at=ensure_aware(snapshot.scraped_at),
                        price=float(snapshot.price),
                        store_slug=listing.store.slug,
                    )
                )
    points.sort(key=lambda p: p.scraped_at)
    return points
