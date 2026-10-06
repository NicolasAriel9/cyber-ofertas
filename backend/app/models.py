from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    and_,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.utils import ensure_aware


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Store(Base):
    __tablename__ = "store"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), default=None)

    listings: Mapped[list["Listing"]] = relationship(back_populates="store")


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), unique=True)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "product"

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_title: Mapped[str] = mapped_column(String(300))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("category.id"), default=None, index=True)
    brand: Mapped[str | None] = mapped_column(String(120), default=None)
    image_url: Mapped[str | None] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    category: Mapped[Category | None] = relationship(back_populates="products")
    listings: Mapped[list["Listing"]] = relationship(back_populates="product")
    favorites: Mapped[list["Favorite"]] = relationship(back_populates="product")


class Listing(Base):
    __tablename__ = "listing"
    __table_args__ = (UniqueConstraint("store_id", "external_id", name="uq_listing_store_external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("store.id"))
    external_id: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(1000))
    image_url: Mapped[str | None] = mapped_column(String(500), default=None)
    raw_attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Set on every write, so the API's in-memory catalog (app/catalog.py) can
    # fetch just what changed instead of re-reading ~250k rows.
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, index=True
    )
    # Denormalized copy of the latest PriceSnapshot so the listings endpoint can
    # filter/sort/paginate in SQL instead of loading every snapshot -- with
    # tens of thousands of scraped offers, doing that in Python doesn't scale.
    current_price: Mapped[float | None] = mapped_column(Numeric(12, 2), default=None, index=True)
    current_original_price: Mapped[float | None] = mapped_column(Numeric(12, 2), default=None)
    current_discount_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), default=None, index=True)
    rating: Mapped[float | None] = mapped_column(Float, default=None)
    review_count: Mapped[int | None] = mapped_column(Integer, default=None)
    # The price right before the current Cyber event began, captured the first
    # time the scraper sees the offer after the start (see upsert_offer). Lets
    # the API tell real Cyber drops from prices that were already there.
    pre_event_price: Mapped[float | None] = mapped_column(Numeric(12, 2), default=None)

    product: Mapped[Product] = relationship(back_populates="listings")
    store: Mapped[Store] = relationship(back_populates="listings")
    price_snapshots: Mapped[list["PriceSnapshot"]] = relationship(
        back_populates="listing", order_by="PriceSnapshot.scraped_at"
    )

    @property
    def is_live(self) -> bool:
        return self.is_active and ensure_aware(self.last_seen_at) >= utcnow() - LISTING_STALE_AFTER


# A full sweep deactivates offers that disappeared, but only when it read the
# whole store: a store that starts blocking the scraper (Ripley, Oct 2026)
# would otherwise keep showing its last prices forever. Offers not seen for a
# day are hidden instead; during the event full sweeps run every 3 hours.
LISTING_STALE_AFTER = timedelta(hours=24)


def listing_is_live():
    """SQL counterpart of Listing.is_live."""
    return and_(Listing.is_active.is_(True), Listing.last_seen_at >= utcnow() - LISTING_STALE_AFTER)


class PriceSnapshot(Base):
    __tablename__ = "price_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.id"))
    price: Mapped[float] = mapped_column(Numeric(12, 2))
    original_price: Mapped[float | None] = mapped_column(Numeric(12, 2), default=None)
    discount_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), default=None)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    listing: Mapped[Listing] = relationship(back_populates="price_snapshots")


class Subscriber(Base):
    __tablename__ = "subscriber"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    # BigInteger: Telegram chat ids can exceed a 32-bit INTEGER (> 2,147,483,647).
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, default=None)
    link_code: Mapped[str | None] = mapped_column(String(20), default=None)
    link_code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    favorites: Mapped[list["Favorite"]] = relationship(back_populates="subscriber")


class Favorite(Base):
    __tablename__ = "favorite"
    __table_args__ = (UniqueConstraint("subscriber_id", "product_id", name="uq_favorite_subscriber_product"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    subscriber_id: Mapped[int] = mapped_column(ForeignKey("subscriber.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"))
    target_price: Mapped[float | None] = mapped_column(Numeric(12, 2), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    subscriber: Mapped[Subscriber] = relationship(back_populates="favorites")
    product: Mapped[Product] = relationship(back_populates="favorites")


class AlertEvent(Base):
    __tablename__ = "alert_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    favorite_id: Mapped[int] = mapped_column(ForeignKey("favorite.id"))
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.id"))
    old_price: Mapped[float] = mapped_column(Numeric(12, 2))
    new_price: Mapped[float] = mapped_column(Numeric(12, 2))
    pct_drop: Mapped[float] = mapped_column(Numeric(5, 2))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
