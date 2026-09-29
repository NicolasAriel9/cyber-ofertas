"""Parses cyber.cl's brand/offer listings into ScrapedOffer records.

NOT YET IMPLEMENTED against the real site: as of the Phase 0 inspection
(2026-09-28, see docs/cyber_cl_inspection_notes.md) the category pages had no
live catalog to parse yet -- the real event starts 2026-10-05. This module
defines the target shape (ScrapedOffer) and a `parse_category_html` entrypoint
to fill in once real markup/JSON is available, closer to the event.
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


def parse_category_html(html: str, category_slug: str) -> list[ScrapedOffer]:
    """Placeholder -- implement once cyber.cl's real catalog markup is known."""
    raise NotImplementedError(
        "cyber.cl's category catalog wasn't populated during Phase 0 inspection. "
        "Re-inspect closer to the event (see docs/cyber_cl_inspection_notes.md) "
        "before implementing this."
    )
