"""Mercado Libre: its search API now requires OAuth, but the public deals page
(mercadolibre.cl/ofertas) is server-rendered: 48 product cards per page, up to
~20 pages per category (?category=MLC...&page=N). Each card's prices carry an
aria-label with the plain amount ("Antes: 129096 pesos chilenos" for the list
price), sturdier than the formatted visual markup.

Mercado Libre sometimes blocks datacenter IPs (like GitHub Actions runners);
a blocked department just logs an error and the other stores carry on.
"""

import html
import re

from app.scraper.http import PoliteClient
from app.scraper.parser import ScrapedOffer
from app.scraper.stores.base import Department, StoreScraper, parse_rating

DEALS_URL = "https://www.mercadolibre.cl/ofertas"
CARD_SPLIT = re.compile(r'<div class="andes-card poly-card[^"]*"')
TITLE_RE = re.compile(r'<a href="([^"]+)"[^>]*class="poly-component__title"[^>]*>([^<]+)</a>')
PREVIOUS_RE = re.compile(r'aria-label="Antes: (\d+) pesos')
# The current price is the first amount inside poly-price__current.
CURRENT_RE = re.compile(r'class="poly-price__current".*?aria-label="(\d+) pesos', re.S)
IMG_RE = re.compile(r'<img class="poly-component__picture"[^>]*?(?:data-src|src)="(https://[^"]+)"')
# The listing id: the wid= tracking param when present (catalog product pages,
# /p/MLC123, are shared by several sellers), else the id in the path.
WID_RE = re.compile(r"wid=(MLC\d+)")
PATH_ID_RE = re.compile(r"/p/(MLC\d+)|/MLC-?(\d+)")
# Screen-reader text of the stars: "Calificación 4.8 de 5 estrellas". The deals
# page shows units sold next to it, not how many reviews there are.
RATING_RE = re.compile(r"Calificaci\S+ ([\d.]+) de 5")


def parse_card(card_html: str, category_slug: str) -> ScrapedOffer | None:
    title = TITLE_RE.search(card_html)
    current = CURRENT_RE.search(card_html)
    if not title or not current:
        return None
    url = html.unescape(title.group(1))
    wid = WID_RE.search(url)
    path_id = PATH_ID_RE.search(url)
    if wid:
        external_id = wid.group(1)
    elif path_id:
        external_id = path_id.group(1) or f"MLC{path_id.group(2)}"
    else:
        return None
    previous = PREVIOUS_RE.search(card_html)
    image = IMG_RE.search(card_html)
    rating = RATING_RE.search(card_html)
    price = float(current.group(1))
    original = float(previous.group(1)) if previous else None
    return ScrapedOffer(
        store_slug="mercadolibre",
        store_name="Mercado Libre",
        category_slug=category_slug,
        external_id=external_id,
        title=html.unescape(title.group(2)).strip(),
        url=url.split("#")[0],
        price=price,
        original_price=original if original and original > price else None,
        image_url=image.group(1) if image else None,
        rating=parse_rating(rating.group(1))[0] if rating else None,
    )


class MercadoLibreScraper(StoreScraper):
    slug = "mercadolibre"
    name = "Mercado Libre"
    cyber_brand_name = "Mercado Libre"
    departments = [
        Department("tecnologia", "MLC1648", "Computación"),
        Department("tecnologia", "MLC1051", "Celulares y telefonía"),
        Department("tecnologia", "MLC1000", "Electrónica, audio y video"),
        Department("tecnologia", "MLC1144", "Consolas y videojuegos"),
        Department("tecnologia", "MLC1039", "Cámaras"),
        Department("hogar", "MLC1574", "Hogar y muebles"),
        Department("hogar", "MLC5726", "Electrodomésticos"),
        Department("deportes-y-outdoor", "MLC1276", "Deportes y fitness"),
        Department("vestuario-y-calzado", "MLC1430", "Vestuario y calzado"),
        Department("salud-y-belleza", "MLC1246", "Belleza y cuidado personal"),
        Department("infantil", "MLC1132", "Juegos y juguetes"),
        Department("infantil", "MLC1384", "Bebés"),
        Department("ferreteria-y-construccion", "MLC1500", "Construcción"),
        Department("mascotas", "MLC1071", "Animales y mascotas"),
        Department("neumaticos-y-accesorios", "MLC1747", "Accesorios para vehículos"),
    ]

    def fetch_page(self, client: PoliteClient, department: Department, page: int) -> tuple[list[ScrapedOffer], bool]:
        params = {"category": department.ref}
        if page > 1:
            params["page"] = page
        text = client.get(DEALS_URL, params=params).text
        cards = CARD_SPLIT.split(text)[1:]
        offers = [o for card in cards if (o := parse_card(card, department.category_slug))]
        has_more = re.search(rf"[?&;]page={page + 1}(?!\d)", text) is not None  # a link to the next page
        return offers, has_more
