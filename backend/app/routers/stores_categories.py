from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.db import get_db
from app.models import Category, Store
from app.schemas import CategoryOut, StoreOut

router = APIRouter(dependencies=[Depends(require_auth)], tags=["catalog"])


@router.get("/stores", response_model=list[StoreOut])
def list_stores(db: Session = Depends(get_db)):
    return db.query(Store).order_by(Store.name).all()


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.name).all()
