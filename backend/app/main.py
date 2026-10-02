from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import admin, favorites, health, listings, products, stores_categories, telegram

app = FastAPI(title="Cyber Ofertas API")

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
