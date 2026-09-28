from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.db import get_db
from app.models import Favorite, Product, Subscriber
from app.schemas import FavoriteCreate, FavoriteOut, ProductSummaryOut, SubscriberOut

router = APIRouter(dependencies=[Depends(require_auth)], tags=["favorites"])


@router.get("/subscribers", response_model=list[SubscriberOut])
def list_subscribers(db: Session = Depends(get_db)):
    subscribers = db.query(Subscriber).order_by(Subscriber.id).all()
    return [
        SubscriberOut(id=s.id, name=s.name, telegram_linked=s.telegram_chat_id is not None)
        for s in subscribers
    ]


def _product_summary(product: Product) -> ProductSummaryOut:
    best_price = None
    best_store = None
    max_discount_pct = None
    for listing in product.listings:
        if not listing.is_active or not listing.price_snapshots:
            continue
        latest = listing.price_snapshots[-1]
        price = float(latest.price)
        if best_price is None or price < best_price:
            best_price = price
            best_store = listing.store.name
        if latest.discount_pct and (max_discount_pct is None or float(latest.discount_pct) > max_discount_pct):
            max_discount_pct = float(latest.discount_pct)

    return ProductSummaryOut(
        id=product.id,
        canonical_title=product.canonical_title,
        image_url=product.image_url,
        best_price=best_price,
        best_store=best_store,
        max_discount_pct=max_discount_pct,
    )


@router.get("/favorites", response_model=list[FavoriteOut])
def list_favorites(subscriber_id: int, db: Session = Depends(get_db)):
    favorites = db.query(Favorite).filter(Favorite.subscriber_id == subscriber_id).all()
    return [
        FavoriteOut(id=f.id, product=_product_summary(f.product), target_price=f.target_price)
        for f in favorites
    ]


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
    return FavoriteOut(id=favorite.id, product=_product_summary(favorite.product), target_price=favorite.target_price)


@router.delete("/favorites/{favorite_id}", status_code=204)
def delete_favorite(favorite_id: int, subscriber_id: int, db: Session = Depends(get_db)):
    favorite = db.get(Favorite, favorite_id)
    if favorite is None or favorite.subscriber_id != subscriber_id:
        raise HTTPException(status_code=404, detail="Favorite not found")
    db.delete(favorite)
    db.commit()
