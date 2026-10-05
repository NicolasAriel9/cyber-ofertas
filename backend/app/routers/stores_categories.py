from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.cache import response_cache
from app.db import get_db
from app.models import Category, Listing, Product, Store, listing_is_live
from app.schemas import CategoryOut, StoreOut
from app.sections import SECTION_PATTERN, section_filter

router = APIRouter(dependencies=[Depends(require_auth)], tags=["catalog"])


@router.get("/stores", response_model=list[StoreOut])
def list_stores(section: str | None = Query(None, pattern=SECTION_PATTERN), db: Session = Depends(get_db)):
    return response_cache.get(("stores", section), lambda db: _stores_with_offers(db, section), db)


def _stores_with_offers(db: Session, section: str | None) -> list[StoreOut]:
    # ~200 brand stores are tracked; only offer the ones with something on sale.
    conditions = [Listing.store_id == Store.id, listing_is_live()]
    if (where := section_filter(section)) is not None:
        conditions.append(where)
    has_offers = select(Listing.id).join(Product, Listing.product_id == Product.id).where(*conditions).exists()
    return [StoreOut.model_validate(s) for s in db.query(Store).filter(has_offers).order_by(Store.name)]


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(section: str | None = Query(None, pattern=SECTION_PATTERN), db: Session = Depends(get_db)):
    return response_cache.get(("categories", section), lambda db: _categories_with_offers(db, section), db)


def _categories_with_offers(db: Session, section: str | None) -> list[CategoryOut]:
    # Categories mirror cyber.cl's full list (incl. Inmobiliarias, Seguros...);
    # only offer the ones that currently have something to show.
    has_offers = (
        select(Listing.id)
        .join(Product, Listing.product_id == Product.id)
        .where(Product.category_id == Category.id, listing_is_live())
        .exists()
    )
    query = db.query(Category).filter(has_offers)
    if (where := section_filter(section)) is not None:
        query = query.filter(Category.id.in_(select(Product.category_id).where(where)))
    return [CategoryOut.model_validate(c) for c in query.order_by(Category.name)]
