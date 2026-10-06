from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.cache import response_cache
from app.catalog import catalog
from app.db import get_db
from app.models import Category, Store
from app.schemas import CategoryOut, StoreOut
from app.sections import SECTION_PATTERN

router = APIRouter(dependencies=[Depends(require_auth)], tags=["catalog"])


@router.get("/stores", response_model=list[StoreOut])
def list_stores(section: str | None = Query(None, pattern=SECTION_PATTERN), db: Session = Depends(get_db)):
    return response_cache.get(("stores", section), lambda db: _stores_with_offers(db, section), db)


def _stores_with_offers(db: Session, section: str | None) -> list[StoreOut]:
    # ~200 brand stores are tracked; only offer the ones with something on sale.
    snapshot = catalog.get(db)
    ids = {r.store_id for r in snapshot.live(section)}
    return [StoreOut.model_validate(s) for s in db.query(Store).filter(Store.id.in_(ids)).order_by(Store.name)]


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(section: str | None = Query(None, pattern=SECTION_PATTERN), db: Session = Depends(get_db)):
    return response_cache.get(("categories", section), lambda db: _categories_with_offers(db, section), db)


def _categories_with_offers(db: Session, section: str | None) -> list[CategoryOut]:
    # Categories mirror cyber.cl's full list (incl. Inmobiliarias, Seguros...);
    # only offer the ones that currently have something to show.
    snapshot = catalog.get(db)
    ids = {r.category_id for r in snapshot.live(section) if r.category_id is not None}
    return [
        CategoryOut.model_validate(c)
        for c in db.query(Category).filter(Category.id.in_(ids)).order_by(Category.name)
    ]
