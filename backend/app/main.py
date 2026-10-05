import logging
import threading

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.cache import response_cache
from app.db import SessionLocal
from app.routers import admin, favorites, health, listings, products, stores_categories, telegram

log = logging.getLogger(__name__)

app = FastAPI(title="Cyber Ofertas API")


@app.on_event("startup")
def start_response_cache() -> None:
    response_cache.start()
    # Fill the cache with what the home pages ask for, so the first visit
    # after a deploy or a restart doesn't wait for the database either.
    threading.Thread(target=_warm_home_pages, name="warm-cache", daemon=True).start()


def _warm_home_pages() -> None:
    with SessionLocal() as db:
        for section, sort in (("productos", "top"), ("viajes", "price_asc")):
            try:
                stores_categories.list_stores(section=section, db=db)
                stores_categories.list_categories(section=section, db=db)
                listings.list_highlights(per_category=3, section=section, db=db)
                for cyber in (False, True):
                    listings.list_listings(
                        category=None, store=None, search=None, min_discount=None, cyber=cyber, min_rating=None,
                        min_price=None, max_price=None, section=section, sort=sort, page=1, page_size=30,
                        response=Response(), db=db,
                    )
            except Exception:
                log.exception("could not warm the %s page", section)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)

app.include_router(health.router)
app.include_router(stores_categories.router)
app.include_router(listings.router)
app.include_router(products.router)
app.include_router(favorites.router)
app.include_router(telegram.router)
app.include_router(admin.router)
