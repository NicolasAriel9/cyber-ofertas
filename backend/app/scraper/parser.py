"""The normalized offer shape every store scraper produces (see
app/scraper/stores/). Kept in its own module so scrapers, the orchestrator and
tests can share it without import cycles.
"""

from dataclasses import dataclass


@dataclass
class ScrapedOffer:
    store_slug: str
    store_name: str
    category_slug: str
    external_id: str
    title: str
    url: str
    price: float
    original_price: float | None
    image_url: str | None
    brand: str | None = None

    @property
    def is_discounted(self) -> bool:
        return bool(self.original_price and self.original_price > self.price > 0)
