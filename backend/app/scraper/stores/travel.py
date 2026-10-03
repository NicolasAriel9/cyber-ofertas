"""Travel offers (flights, packages, hotels) for the "Cyber Viajes" section.

Checked 2026-10-03, two days before the event. The Cyber landings of the
travel sites (LATAM, Despegar, Viajes Falabella, Cocha...) only showed a
countdown; offers go live on Oct 5. So these scrapers read the sites' regular
deal pages, which are fed by the same data as their Cyber landings.

Covered:
- JetSMART: its home page embeds the lowest fare of every route it flies
  (`let list = JSON.parse('...')`, keyed by "ORIGIN-DESTINATION").
- Cocha: an Angular app whose server-rendered pages carry their CMS content in
  `<script id="ng-state">`, including every offer card. /promociones/cybermonday
  uses the same structure (empty until the event starts).

Not covered: LATAM, Despegar / Viajes Falabella, Iberia and Turismocity sit
behind bot protection (requests hang or get 403 after a few calls), same as
Lider and Tottus on the retail side.
"""

import html
import json
import logging
import re
from datetime import date
from urllib.parse import urlencode, urlparse

from app.scraper.http import PoliteClient
from app.scraper.parser import ScrapedOffer
from app.scraper.stores.base import Department, StoreScraper, parse_clp
from app.sections import FLIGHTS, HOTELS, PACKAGES

logger = logging.getLogger(__name__)


MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"]

# Airports JetSMART flies to, by IATA code.
AIRPORTS = {
    "AEP": "Buenos Aires (Aeroparque)",
    "ANF": "Antofagasta",
    "ARI": "Arica",
    "BOG": "Bogotá",
    "CCP": "Concepción",
    "CJC": "Calama",
    "CLO": "Cali",
    "COR": "Córdoba",
    "CPO": "Copiapó",
    "CUZ": "Cusco",
    "EZE": "Buenos Aires (Ezeiza)",
    "FLN": "Florianópolis",
    "GIG": "Río de Janeiro",
    "GRU": "São Paulo",
    "IGU": "Foz de Iguazú",
    "IQQ": "Iquique",
    "LIM": "Lima",
    "LSC": "La Serena",
    "MDE": "Medellín",
    "MDZ": "Mendoza",
    "MVD": "Montevideo",
    "PMC": "Puerto Montt",
    "PUQ": "Punta Arenas",
    "SCL": "Santiago",
    "TRU": "Trujillo",
    "ZAL": "Valdivia",
    "ZCO": "Temuco",
    "ZOS": "Osorno",
}


def short_date(iso: str) -> str:
    day = date.fromisoformat(iso[:10])
    return f"{day.day} {MONTHS[day.month - 1]}"


# --- JetSMART -----------------------------------------------------------------

JETSMART_URL = "https://jetsmart.com/cl/es/"
JETSMART_BOOKING = "https://booking.jetsmart.com/Flight/InternalSelect"
JETSMART_ATTEMPTS = 6
JETSMART_FARES_RE = re.compile(r"let list = JSON\.parse\('(.*?)'\);", re.S)


def parse_jetsmart_fares(page_html: str) -> list[ScrapedOffer]:
    match = JETSMART_FARES_RE.search(page_html)
    if not match:
        return []
    fares = json.loads(match.group(1).replace("\\'", "'"))
    offers = []
    for route, fare in fares.items():
        origin, destination = fare.get("dep"), fare.get("arr")
        base = (fare.get("p") or {}).get("clp")
        total = (fare.get("pi") or {}).get("clp")
        if not origin or not destination or not total:
            continue
        origin_name = AIRPORTS.get(origin, origin)
        destination_name = AIRPORTS.get(destination, destination)
        flight_date = fare["date"][:10]
        query = {"c": "true", "mon": "true", "r": "false", "cur": "CLP", "culture": "es-CL",
                 "dd1": flight_date, "o1": origin, "d1": destination}
        offers.append(
            ScrapedOffer(
                store_slug="jetsmart",
                store_name="JetSMART",
                category_slug=FLIGHTS,
                external_id=f"{origin}-{destination}",
                title=f"Vuelo {origin_name} → {destination_name} · solo ida",
                url=f"{JETSMART_BOOKING}?{urlencode(query)}",
                # The site advertises the fare without airport taxes ("precio no
                # incluye tasas"); the total is what's actually paid.
                price=float(round(total)),
                original_price=None,
                image_url=None,
                details=f"{short_date(flight_date)} · tarifa ${round(base):,} + tasas".replace(",", ".")
                if base else short_date(flight_date),
                exact_match=True,
            )
        )
    return offers


class JetSmartScraper(StoreScraper):
    slug = "jetsmart"
    name = "JetSMART"
    cyber_brand_name = "JetSMART"
    discounted_only = False
    departments = [Department(FLIGHTS, JETSMART_URL, "Tarifas por ruta")]

    def fetch_page(self, client: PoliteClient, department: Department, page: int) -> tuple[list[ScrapedOffer], bool]:
        # The home page is A/B tested per visitor, and one variant leaves the
        # fare list out (checked 2026-10-03: about 1 visit in 3). Come back as
        # a new visitor until the list shows up.
        for _ in range(JETSMART_ATTEMPTS):
            client.clear_cookies()
            offers = parse_jetsmart_fares(client.get(department.ref).text)
            if offers:
                return offers, False
        logger.warning("JetSMART: no fare list on %s after %d visits", department.ref, JETSMART_ATTEMPTS)
        return [], False


# --- Cocha --------------------------------------------------------------------

COCHA_BASE = "https://www.cocha.com"
COCHA_STATE_RE = re.compile(r'<script id="ng-state" type="application/json">(.*?)</script>', re.S)
COCHA_TYPES = {"flight": FLIGHTS, "multiflight": FLIGHTS, "package": PACKAGES, "hotel": HOTELS}


def _cocha_cards(state: object) -> list[dict]:
    cards = []
    if isinstance(state, dict):
        if state.get("type") == "cx-card-product":
            cards.append(state)
        for value in state.values():
            cards.extend(_cocha_cards(value))
    elif isinstance(state, list):
        for value in state:
            cards.extend(_cocha_cards(value))
    return cards


def _cocha_original_price(card: dict, price: float) -> float | None:
    # Cards have a "before" (crossed-out price text) and a "discount" (%) that
    # are empty outside sales; use whichever the event fills in.
    before = parse_clp(card.get("before")) if re.search(r"\d", str(card.get("before") or "")) else None
    if before and before > price:
        return before
    discount = card.get("discount")
    if isinstance(discount, (int, float)) and 0 < discount < 100:
        return float(round(price / (1 - discount / 100)))
    return None


def parse_cocha_card(card: dict) -> ScrapedOffer | None:
    category = COCHA_TYPES.get(card.get("productType") or "")
    price = parse_clp(card.get("price"))
    link = card.get("deeplink") or ""
    name = html.unescape(card.get("title") or "").strip()
    if not category or not price or not link or not name:
        return None
    url = link if link.startswith("http") else f"{COCHA_BASE}{link}"
    url = url.replace("http://", "https://", 1)
    parsed = urlparse(url)
    stars = card.get("stars") or (card.get("info") or {}).get("stars")
    # "duration" counts days; the site shows it as nights (7 -> "6 noches").
    days = card.get("duration")
    nights = days - 1 if isinstance(days, int) and days > 1 else None

    if category == FLIGHTS:
        destination = re.sub(r"^vuelos? (a|al|hacia) ", "", name, flags=re.I)
        title = f"Vuelo Santiago → {destination} · ida y vuelta"
        details = card.get("priceDescription") or "Ida y vuelta por persona"
    elif category == PACKAGES:
        extras = [f"{nights} noches" if nights else None, "todo incluido" if card.get("allInclusive") else None]
        title = " · ".join(filter(None, [f"Paquete {name}", *extras]))
        details = " · ".join(filter(None, [f"Hotel {stars}★" if stars else None,
                                           card.get("priceDescription") or "Por persona"]))
    else:
        title = f"Hoteles en {name}" + (f" · {stars}★" if stars else "")
        details = card.get("priceDescription") or "Precio por noche"

    return ScrapedOffer(
        store_slug="cocha",
        store_name="Cocha",
        category_slug=category,
        external_id=f"{card.get('productType')}:{parsed.path}?{parsed.query}",
        title=title,
        url=url,
        price=price,
        original_price=_cocha_original_price(card, price),
        image_url=card.get("image") or None,
        details=details,
        exact_match=True,
    )


def parse_cocha_page(page_html: str) -> list[ScrapedOffer]:
    match = COCHA_STATE_RE.search(page_html)
    if not match:
        return []
    offers = [parse_cocha_card(card) for card in _cocha_cards(json.loads(match.group(1)))]
    return [offer for offer in offers if offer is not None]


class CochaScraper(StoreScraper):
    slug = "cocha"
    name = "Cocha"
    cyber_brand_name = "Cocha"
    discounted_only = False
    # Same card format on every page; the orchestrator drops repeats.
    departments = [
        Department(PACKAGES, "/promociones/cybermonday", "Cyber Monday"),
        Department(PACKAGES, "/ofertas", "Ofertas hit"),
        Department(FLIGHTS, "/vuelos", "Vuelos"),
        Department(PACKAGES, "/paquetes", "Paquetes"),
        Department(HOTELS, "/hoteles", "Hoteles"),
        Department(PACKAGES, "/", "Portada"),
    ]

    def fetch_page(self, client: PoliteClient, department: Department, page: int) -> tuple[list[ScrapedOffer], bool]:
        return parse_cocha_page(client.get(f"{COCHA_BASE}{department.ref}").text), False
