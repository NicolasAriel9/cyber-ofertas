"""One-off dev helper to seed a couple of stores/products/listings/prices so
the API and frontend have something real to render locally. Not part of the
production scraper -- purely for local development/testing.

Run `alembic upgrade head` first to create the schema.
"""

from app.db import SessionLocal
from app.models import Category, Listing, PriceSnapshot, Product, Store, Subscriber

db = SessionLocal()

tecnologia = Category(name="Tecnología", slug="tecnologia")
falabella = Store(name="Falabella", slug="falabella")
paris = Store(name="Paris", slug="paris")
db.add_all([tecnologia, falabella, paris])
db.flush()

notebook = Product(canonical_title="Notebook Lenovo IdeaPad 3 15.6\" 8GB RAM", category_id=tecnologia.id, brand="Lenovo")
db.add(notebook)
db.flush()

listing_falabella = Listing(
    product_id=notebook.id,
    store_id=falabella.id,
    external_id="falabella-123",
    title="Notebook Lenovo IdeaPad 3 15.6\" 8GB RAM 256GB SSD",
    url="https://falabella.com/p/123",
)
listing_paris = Listing(
    product_id=notebook.id,
    store_id=paris.id,
    external_id="paris-456",
    title="Notebook Lenovo IdeaPad 3 15.6 pulgadas 8GB",
    url="https://paris.cl/p/456",
)
db.add_all([listing_falabella, listing_paris])
db.flush()

db.add_all(
    [
        PriceSnapshot(listing_id=listing_falabella.id, price=399990, original_price=499990, discount_pct=20),
        PriceSnapshot(listing_id=listing_falabella.id, price=349990, original_price=499990, discount_pct=30),
        PriceSnapshot(listing_id=listing_paris.id, price=359990, original_price=459990, discount_pct=21.7),
    ]
)

nico = Subscriber(name="Nico")
paula = Subscriber(name="Paula")
db.add_all([nico, paula])
db.commit()

print(f"Seeded product_id={notebook.id}, subscriber_ids=({nico.id}, {paula.id})")
db.close()
