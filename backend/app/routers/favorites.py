from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.db import get_db
from app.models import Favorite, Product, Subscriber
from app.schemas import FavoriteCreate, FavoriteOut, FavoriteUpdate, ProductSummaryOut, SubscriberOut
from app.utils import ensure_aware

router = APIRouter(dependencies=[Depends(require_auth)], tags=["favorites"])


@router.get("/subscribers", response_model=list[SubscriberOut])
def list_subscribers(db: Session = Depends(get_db)):
    subscribers = db.query(Subscriber).order_by(Subscriber.id).all()
    return [
        SubscriberOut(id=s.id, name=s.name, telegram_linked=s.telegram_chat_id is not None)
        for s in subscribers
    ]


def _product_summary(product: Product) -> ProductSummaryOut:
    active = [x for x in product.listings if x.is_active and x.current_price is not None]
    best = min(active, key=lambda x: x.current_price, default=None)
    discounts = [float(x.current_discount_pct) for x in active if x.current_discount_pct]
    seen_prices = [float(s.price) for x in active for s in x.price_snapshots]
    seen_prices += [float(x.current_price) for x in active]

    return ProductSummaryOut(
        id=product.id,
        canonical_title=product.canonical_title,
        image_url=product.image_url,
        brand=product.brand,
        category=product.category,
        best_price=float(best.current_price) if best else None,
        best_original_price=float(best.current_original_price) if best and best.current_original_price else None,
        best_discount_pct=float(best.current_discount_pct) if best and best.current_discount_pct else None,
        best_store=best.store.name if best else None,
        best_url=best.url if best else None,
        max_discount_pct=max(discounts, default=None),
        store_count=len(active),
        lowest_price=min(seen_prices, default=None),
    )


def _price_when_added(favorite: Favorite) -> float | None:
    # Snapshots are only stored when a price changes, so the price at a given
    # moment is the last snapshot taken before it.
    added_at = ensure_aware(favorite.created_at)
    prices = []
    for listing in favorite.product.listings:
        before = [s for s in listing.price_snapshots if ensure_aware(s.scraped_at) <= added_at]
        if before:
            prices.append(float(max(before, key=lambda s: ensure_aware(s.scraped_at)).price))
    return min(prices, default=None)


def _favorite_out(favorite: Favorite) -> FavoriteOut:
    return FavoriteOut(
        id=favorite.id,
        product=_product_summary(favorite.product),
        target_price=favorite.target_price,
        created_at=favorite.created_at,
        price_when_added=_price_when_added(favorite),
    )


@router.get("/favorites", response_model=list[FavoriteOut])
def list_favorites(subscriber_id: int, db: Session = Depends(get_db)):
    favorites = (
        db.query(Favorite)
        .filter(Favorite.subscriber_id == subscriber_id)
        .order_by(Favorite.created_at.desc())
        .all()
    )
    return [_favorite_out(f) for f in favorites]


@router.post("/favorites", response_model=FavoriteOut, status_code=201)
def create_favorite(subscriber_id: int, payload: FavoriteCreate, db: Session = Depends(get_db)):
    if db.get(Subscriber, subscriber_id) is None:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    if db.get(Product, payload.product_id) is None:
        raise HTTPException(status_code=404, detail="Product not found")

    favorite = Favorite(
        subscriber_id=subscriber_id,
        product_id=payload.product_id,
        target_price=payload.target_price,
    )
    db.add(favorite)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Product already favorited")
    db.refresh(favorite)
    return _favorite_out(favorite)


@router.patch("/favorites/{favorite_id}", response_model=FavoriteOut)
def update_favorite(favorite_id: int, subscriber_id: int, payload: FavoriteUpdate, db: Session = Depends(get_db)):
    favorite = db.get(Favorite, favorite_id)
    if favorite is None or favorite.subscriber_id != subscriber_id:
        raise HTTPException(status_code=404, detail="Favorite not found")
    favorite.target_price = payload.target_price
    db.commit()
    db.refresh(favorite)
    return _favorite_out(favorite)


@router.delete("/favorites/{favorite_id}", status_code=204)
def delete_favorite(favorite_id: int, subscriber_id: int, db: Session = Depends(get_db)):
    favorite = db.get(Favorite, favorite_id)
    if favorite is None or favorite.subscriber_id != subscriber_id:
        raise HTTPException(status_code=404, detail="Favorite not found")
    db.delete(favorite)
    db.commit()
