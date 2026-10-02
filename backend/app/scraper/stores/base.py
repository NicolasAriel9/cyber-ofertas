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


class StoreScraper:
    slug: str
    name: str
    # How the store is named in cyber.cl's brand list, to pick up its logo and
    # check that it is participating in the current event.
    cyber_brand_name: str
    departments: list[Department]

    def fetch_page(self, client: PoliteClient, department: Department, page: int) -> tuple[list[ScrapedOffer], bool]:
        """Return (offers on this page, whether a next page exists). Pages start at 1."""
        raise NotImplementedError

    def iter_department(
        self, client: PoliteClient, department: Department, max_pages: int = MAX_PAGES_PER_DEPARTMENT
    ) -> Iterator[list[ScrapedOffer]]:
        """Yield one list of discounted offers per page."""
        for page in range(1, max_pages + 1):
            offers, has_more = self.fetch_page(client, department, page)
            yield [offer for offer in offers if offer.is_discounted]
            if not has_more or not offers:
                return
