"""Per-store scrapers: the biggest participating retailers, each with its own
scraper, plus ~200 brand-owned stores read through their platform's public
catalog (see brand_sites.py).

Not covered (checked 2026-10-02): Lider.cl answers bots with a "Robot or
human?" challenge, Tottus's site returned Cloudflare 526, and Adidas, Nike,
The North Face and Mammut block automated requests (403).
"""

from app.scraper.stores.base import Department, StoreScraper
from app.scraper.stores.brand_sites import load_brand_sites
from app.scraper.stores.cencosud import EasyScraper, JumboScraper, ParisScraper
from app.scraper.stores.falabella import FalabellaScraper, SodimacScraper
from app.scraper.stores.hites import HitesScraper
from app.scraper.stores.mercadolibre import MercadoLibreScraper
from app.scraper.stores.ripley import RipleyScraper

RETAILERS: list[StoreScraper] = [
    FalabellaScraper(),
    ParisScraper(),
    RipleyScraper(),
    HitesScraper(),
    SodimacScraper(),
    EasyScraper(),
    JumboScraper(),
    MercadoLibreScraper(),
]

ALL_STORES: list[StoreScraper] = RETAILERS + load_brand_sites()

__all__ = ["ALL_STORES", "RETAILERS", "Department", "StoreScraper"]
