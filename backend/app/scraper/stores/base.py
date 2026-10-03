import logging
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass

from app.scraper.http import PoliteClient
from app.scraper.parser import ScrapedOffer

logger = logging.getLogger(__name__)

# Each department of a big retailer has tens of thousands of discounted items
# (e.g. ~80k in Falabella's Tecnología alone), far more than this tool needs
# or a free-tier Postgres should hold. Pages are walked in the store's own
# relevance order, so the cap keeps the offers the store itself ranks first.
MAX_PAGES_PER_DEPARTMENT = int(os.environ.get("SCRAPE_MAX_PAGES", "10"))


@dataclass(frozen=True)
class Department:
    category_slug: str  # one of cyber.cl's categories, slugified (see cyber_cl.slugify)
    ref: str  # store-specific id: URL path, category id, Constructor group id...
    label: str


def parse_clp(raw: str | int | float | None) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw) or None
    digits = re.sub(r"[^\d]", "", raw)
    return float(digits) if digits else None


def parse_rating(rating: str | int | float | None, count: str | int | None = None) -> tuple[float | None, int | None]:
    """(rating out of 5, review count), or (None, None) when there are no
    reviews -- stores report unrated products as 0 stars."""
    try:
        value = float(rating) if rating not in (None, "") else 0.0
        reviews = int(count) if count not in (None, "") else None
    except (TypeError, ValueError):
        return None, None
    if not 0 < value <= 5 or reviews == 0:
        return None, None
    return round(value, 1), reviews


class StoreScraper:
    slug: str
    name: str
    # How the store is named in cyber.cl's brand list, to pick up its logo and
    # check that it is participating in the current event.
    cyber_brand_name: str
    departments: list[Department]
    # Which scrape job runs this store (SCRAPE_STORES matches slugs and
    # groups). The big retailers each get their own; the ~200 brand sites are
    # batched per platform. Defaults to the slug.
    group: str | None = None
    # Stores with small pages (VTEX caps a page at 50 items) get proportionally
    # more of them, so SCRAPE_MAX_PAGES means roughly the same number of
    # products everywhere.
    pages_per_step: int = 1
    # Retail offers without a crossed-out price aren't deals, so they're
    # dropped. Travel sites publish "desde $X" fares with no "before" price:
    # those are the offer, so travel scrapers keep everything.
    discounted_only: bool = True

    @property
    def job_group(self) -> str:
        return self.group or self.slug

    def fetch_page(self, client: PoliteClient, department: Department, page: int) -> tuple[list[ScrapedOffer], bool]:
        """Return (offers on this page, whether a next page exists). Pages start at 1."""
        raise NotImplementedError

    def iter_department(
        self, client: PoliteClient, department: Department, max_pages: int = MAX_PAGES_PER_DEPARTMENT
    ) -> Iterator[list[ScrapedOffer]]:
        """Yield one list of discounted offers per page."""
        for page in range(1, max_pages + 1):
            offers, has_more = self.fetch_page(client, department, page)
            yield [offer for offer in offers if offer.is_discounted or not self.discounted_only]
            if not has_more or not offers:
                return
