from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


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
    category_id: Mapped[int | None] = mapped_column(ForeignKey("category.id"), default=None)
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
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"))
    store_id: Mapped[int] = mapped_column(ForeignKey("store.id"))
    external_id: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(1000))
    image_url: Mapped[str | None] = mapped_column(String(500), default=None)
    raw_attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    product: Mapped[Product] = relationship(back_populates="listings")
    store: Mapped[Store] = relationship(back_populates="listings")
    price_snapshots: Mapped[list["PriceSnapshot"]] = relationship(
        back_populates="listing", order_by="PriceSnapshot.scraped_at"
    )


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
    telegram_chat_id: Mapped[int | None] = mapped_column(unique=True, default=None)
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
