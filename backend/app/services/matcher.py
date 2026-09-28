"""Groups scraped Listings into a canonical Product so the comparator/favorites
work across stores. Matching is intentionally simple (title similarity + same
category + rough price range) since this is a personal tool for ~2 people,
not a production entity-resolution system — false negatives (missed matches)
are an acceptable tradeoff over false positives (wrongly merged products).
"""

import re

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.models import Category, Product

TITLE_SIMILARITY_THRESHOLD = 85
MAX_PRICE_RATIO_DIFF = 0.35  # candidate prices must be within +/-35% of each other


def normalize_title(title: str) -> str:
    title = title.lower().strip()
    title = re.sub(r"[^\w\s]", " ", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def find_or_create_product(
    db: Session,
    *,
    title: str,
    price: float,
    category_slug: str | None,
    brand: str | None,
    image_url: str | None,
) -> Product:
    category = None
    if category_slug:
        category = db.query(Category).filter(Category.slug == category_slug).first()
        if category is None:
            category = Category(name=category_slug.replace("-", " ").title(), slug=category_slug)
            db.add(category)
            db.flush()

    normalized = normalize_title(title)

    query = db.query(Product)
    if category is not None:
        query = query.filter(Product.category_id == category.id)
    candidates = query.all()

    best_match: Product | None = None
    best_score = 0.0
    for candidate in candidates:
        score = fuzz.token_sort_ratio(normalized, normalize_title(candidate.canonical_title))
        if score < TITLE_SIMILARITY_THRESHOLD:
            continue
        existing_prices = [
            float(snap.price)
            for listing in candidate.listings
            for snap in listing.price_snapshots[-1:]
        ]
        if existing_prices:
            avg_price = sum(existing_prices) / len(existing_prices)
            if avg_price > 0 and abs(price - avg_price) / avg_price > MAX_PRICE_RATIO_DIFF:
                continue
        if score > best_score:
            best_score = score
            best_match = candidate

    if best_match is not None:
        return best_match

    product = Product(
        canonical_title=title,
        category_id=category.id if category else None,
        brand=brand,
        image_url=image_url,
    )
    db.add(product)
    db.flush()
    return product
