"""Groups scraped Listings into a canonical Product so the comparator/favorites
work across stores. Matching is intentionally simple (title similarity + same
category + rough price range) since this is a personal tool for ~2 people,
not a production entity-resolution system — false negatives (missed matches)
are an acceptable tradeoff over false positives (wrongly merged products).
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import Category, Listing, Product

TITLE_SIMILARITY_THRESHOLD = 85
MAX_PRICE_RATIO_DIFF = 0.35  # candidate prices must be within +/-35% of each other


def normalize_title(title: str) -> str:
    title = title.lower().strip()
    title = re.sub(r"[^\w\s]", " ", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


# Screen size ("55\"", "50''", "50 pulgadas") and storage/RAM ("512gb", "16 gb")
# are the most common real differentiators between otherwise near-identical
# titles (e.g. the same TV model in two sizes) -- fuzzy title similarity alone
# treats "50" vs "55" as a single differing token in a long title and happily
# scores it above the threshold, so these are checked as a hard guard.
SIZE_INCHES_RE = re.compile(r"(\d{2,3})\s*(?:\"|''|pulgadas)")
STORAGE_GB_RE = re.compile(r"(\d{2,4})\s*gb")


def extract_spec_tokens(title: str) -> set[str]:
    normalized = normalize_title(title)
    tokens = {f'{m}in' for m in SIZE_INCHES_RE.findall(title)}
    tokens |= {f"{m}gb" for m in STORAGE_GB_RE.findall(normalized)}
    return tokens


@dataclass
class _Bucket:
    product_ids: list[int] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)  # normalized, parallel to product_ids
    spec_tokens: list[set[str]] = field(default_factory=list)  # from the raw title (needs the " for inches)


class ProductIndex:
    """In-memory view of existing products for one scrape run.

    Matching used to load every product of the category from the DB and
    fuzzy-compare them in a Python loop *per offer*, which is quadratic and
    unusable at tens of thousands of offers. The index is built once, compared
    with rapidfuzz's C-level batch scorer, and updated as products are created.
    """

    def __init__(self, db: Session) -> None:
        self.buckets: dict[int | None, _Bucket] = defaultdict(_Bucket)
        self.prices: dict[int, float] = {}
        self.categories: dict[str, Category] = {c.slug: c for c in db.query(Category).all()}
        # Products created without a flush (batched scrapes) have no id yet;
        # they're indexed by register_pending() once their batch is flushed.
        self.pending: list[tuple[Product, float]] = []
        # Loading every product with its average price reads the two biggest
        # tables: 15 parallel scrape jobs doing it at once took the free
        # database down (Oct 5 2026). Each category is loaded the first time a
        # new offer of that category needs matching; a quick pass mostly sees
        # offers it already knows and loads nothing.
        self._db = db
        self._loaded: set[int | None] = set()

    def _ensure_loaded(self, category_id: int | None) -> None:
        if category_id in self._loaded:
            return
        self._loaded.add(category_id)
        in_category = Product.category_id.is_(None) if category_id is None else Product.category_id == category_id
        rows = self._db.execute(
            select(Product.id, Product.canonical_title, func.avg(Listing.current_price))
            .outerjoin(Listing, and_(Listing.product_id == Product.id, Listing.current_price.is_not(None)))
            .where(in_category)
            .group_by(Product.id)
        )
        for product_id, title, avg_price in rows:
            self._add(product_id, title, category_id)
            if avg_price is not None:
                self.prices[product_id] = float(avg_price)

    def _add(self, product_id: int, title: str, category_id: int | None) -> None:
        bucket = self.buckets[category_id]
        bucket.product_ids.append(product_id)
        bucket.titles.append(normalize_title(title))
        bucket.spec_tokens.append(extract_spec_tokens(title))

    def add(self, product: Product, price: float) -> None:
        if product.category_id not in self._loaded:
            # Already flushed, so loading the category brings it in.
            self._ensure_loaded(product.category_id)
        else:
            self._add(product.id, product.canonical_title, product.category_id)
        self.prices[product.id] = price

    def register_pending(self) -> None:
        for product, price in self.pending:
            # Categories nobody matched against yet will load them from the DB.
            if product.category_id in self._loaded:
                self.add(product, price)
        self.pending.clear()

    def get_or_create_category(self, db: Session, slug: str) -> Category:
        category = self.categories.get(slug)
        if category is None:
            category = db.query(Category).filter(Category.slug == slug).first()
        if category is None:
            category = Category(name=slug.replace("-", " ").title(), slug=slug)
            db.add(category)
            db.flush()
        self.categories[slug] = category
        return category

    def best_match(self, title: str, price: float, category_id: int | None) -> int | None:
        self._ensure_loaded(category_id)
        bucket = self.buckets.get(category_id)
        if not bucket or not bucket.titles:
            return None
        spec_tokens = extract_spec_tokens(title)
        matches = process.extract(
            normalize_title(title),
            bucket.titles,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=TITLE_SIMILARITY_THRESHOLD,
            limit=10,
        )
        for _, _score, position in matches:  # best score first
            candidate_tokens = bucket.spec_tokens[position]
            if spec_tokens and candidate_tokens and spec_tokens.isdisjoint(candidate_tokens):
                continue  # e.g. a 43" and a 55" TV with an otherwise near-identical title
            product_id = bucket.product_ids[position]
            known_price = self.prices.get(product_id)
            if known_price and abs(price - known_price) / known_price > MAX_PRICE_RATIO_DIFF:
                continue
            return product_id
        return None


def match_or_create_product(
    db: Session,
    *,
    title: str,
    price: float,
    category_slug: str | None,
    brand: str | None,
    image_url: str | None,
    index: ProductIndex,
    flush: bool = True,
    exact: bool = False,
) -> tuple[int | None, Product | None]:
    """Return (id of the matching product, None) or (None, new product).

    The matched product isn't loaded, saving a DB round trip per offer. With
    flush=False the new product is only added to the session (inserted with
    the rest of the batch) and indexed later via index.register_pending(), so
    two offers in the same batch can't match each other.
    """
    category = index.get_or_create_category(db, category_slug) if category_slug else None
    category_id = category.id if category else None

    if exact:
        pending = next(
            (p for p, _ in index.pending if p.canonical_title == title and p.category_id == category_id), None
        )
        if pending is not None:
            return None, pending
        product_id = db.scalar(
            select(Product.id).where(Product.canonical_title == title, Product.category_id == category_id).limit(1)
        )
    else:
        product_id = index.best_match(title, price, category_id)
    if product_id is not None:
        return product_id, None

    product = Product(canonical_title=title, category_id=category_id, brand=brand, image_url=image_url)
    db.add(product)
    if flush:
        db.flush()
        index.add(product, price)
    else:
        index.pending.append((product, price))
    return None, product


def find_or_create_product(
    db: Session,
    *,
    title: str,
    price: float,
    category_slug: str | None,
    brand: str | None,
    image_url: str | None,
    index: ProductIndex | None = None,
) -> Product:
    if index is None:
        index = ProductIndex(db)
    product_id, product = match_or_create_product(
        db, title=title, price=price, category_slug=category_slug, brand=brand, image_url=image_url, index=index
    )
    return product or db.get(Product, product_id)
