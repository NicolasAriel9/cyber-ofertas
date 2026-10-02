from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.db import get_db
from app.models import Category, Listing, Product, Store
from app.schemas import CategoryOut, StoreOut

router = APIRouter(dependencies=[Depends(require_auth)], tags=["catalog"])


@router.get("/stores", response_model=list[StoreOut])
def list_stores(db: Session = Depends(get_db)):
    return db.query(Store).order_by(Store.name).all()


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    # Categories mirror cyber.cl's full list (incl. Inmobiliarias, Seguros...);
    # only offer the ones that currently have something to show.
    has_offers = (
        select(Listing.id)
        .join(Product, Listing.product_id == Product.id)
        .where(Product.category_id == Category.id, Listing.is_active.is_(True))
        .exists()
    )
    return db.query(Category).filter(has_offers).order_by(Category.name).all()
