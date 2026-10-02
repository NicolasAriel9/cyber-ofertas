"""Per-store scrapers for the biggest participating retailers.

Not covered (checked 2026-10-01): Lider.cl answers bots with a "Robot or
human?" challenge, Tottus's site returned Cloudflare 526, and Mercado Libre's
listing API now requires OAuth -- none reachable without a headless browser
or credentials.
"""

from app.scraper.stores.base import Department, StoreScraper
from app.scraper.stores.cencosud import EasyScraper, JumboScraper, ParisScraper
from app.scraper.stores.falabella import FalabellaScraper, SodimacScraper
from app.scraper.stores.hites import HitesScraper
from app.scraper.stores.ripley import RipleyScraper

ALL_STORES: list[StoreScraper] = [
    FalabellaScraper(),
    ParisScraper(),
    RipleyScraper(),
    HitesScraper(),
    SodimacScraper(),
    EasyScraper(),
    JumboScraper(),
]

__all__ = ["ALL_STORES", "Department", "StoreScraper"]
