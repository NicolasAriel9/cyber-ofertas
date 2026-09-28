from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    logo_url: str | None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str


class ListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    store: StoreOut
    title: str
    url: str
    image_url: str | None
    latest_price: float | None
    latest_original_price: float | None
    latest_discount_pct: float | None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    canonical_title: str
    category: CategoryOut | None
    brand: str | None
    image_url: str | None
    listings: list[ListingOut]


class ProductSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    canonical_title: str
    image_url: str | None
    best_price: float | None
    best_store: str | None
    max_discount_pct: float | None


class PriceHistoryPoint(BaseModel):
    scraped_at: datetime
    price: float
    store_slug: str


class FavoriteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product: ProductSummaryOut
    target_price: float | None


class SubscriberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    telegram_linked: bool


class FavoriteCreate(BaseModel):
    product_id: int
    target_price: float | None = None


class TelegramLinkCodeOut(BaseModel):
    code: str
    deep_link: str
    expires_at: datetime
