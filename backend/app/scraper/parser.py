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
    # Travel offers: a short line shown under the title ("Solo ida · 22 oct"),
    # and exact-title product matching. Fuzzy matching would merge "Santiago ->
    # Lima, solo ida" with "Santiago -> Lima, ida y vuelta".
    details: str | None = None
    exact_match: bool = False

    @property
    def is_discounted(self) -> bool:
        return bool(self.original_price and self.original_price > self.price > 0)
