"""Telegram assistant: answers free-text catalog questions using pattern
matching (brand/store/price/sort/limit detection) against known DB values,
not an LLM -- free, no external API/account needed. Covers a wide range of
common Spanish phrasings (see HELP examples in app/routers/telegram.py) by
design, but it's still pattern matching, not true open-ended understanding.
"""

import re

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Listing, Product, Store

MAX_RESULTS = 8
DEFAULT_LIMIT = 5

# --- sort / superlative intent -------------------------------------------------

SORT_EXPENSIVE_RE = re.compile(r"m[aá]s car[oa]s?")
SORT_DISCOUNT_RE = re.compile(
    r"m[aá]s descuento|mayor descuento|mejor descuento|m[aá]s rebajad[oa]s?|"
    r"mejor oferta|mejores ofertas|top ofertas|recomi[eé]ndame|"
    r"qu[eé] me recomiendas|algo bueno"
)
SORT_CHEAP_RE = re.compile(
    r"m[aá]s barat[oa]s?|m[aá]s econ[oó]mic[oa]s?|menor precio|mejor precio|"
    r"m[aá]s conveniente[s]?"
)

# --- price parsing --------------------------------------------------------------

_NUM = r"\$?\s*(\d{1,3}(?:[.,]\d{3})+|\d+)"
_UNIT = r"\s*(mill[oó]n(?:es)?|palo[s]?|mil|k|lucas)?"

PRICE_RANGE_RE = re.compile(rf"entre\s*{_NUM}{_UNIT}\s*(?:y|a)\s*{_NUM}{_UNIT}", re.IGNORECASE)
PRICE_MAX_RE = re.compile(
    rf"(?:bajo|menos de|por debajo de|m[aá]ximo|hasta|menor a|inferior a)\s*{_NUM}{_UNIT}",
    re.IGNORECASE,
)
PRICE_MIN_RE = re.compile(
    rf"(?:sobre|arriba de|mayor a|m[aá]s de|desde|superior a)\s*{_NUM}{_UNIT}",
    re.IGNORECASE,
)

# --- result-count requests -------------------------------------------------------

LIMIT_RE = re.compile(
    r"\btop\s*(\d{1,2})\b|\b(\d{1,2})\s*(?:opciones|resultados|productos|alternativas)\b",
    re.IGNORECASE,
)

STOPWORDS = {
    "el", "la", "los", "las", "de", "del", "un", "una", "unos", "unas", "por", "para",
    "me", "mi", "dame", "cual", "cuál", "es", "son", "que", "qué", "hay", "ofertas",
    "oferta", "producto", "productos", "favor", "porfa", "porfavor", "y", "en", "con",
    "quiero", "busco", "muestrame", "muéstrame", "dime", "cuáles", "cuales", "algo",
    "hola", "buenas", "gracias", "bot", "oye", "chao", "adios", "adiós", "ok", "vale",
    "bueno", "buena", "tienes", "tienen", "hazme", "dale", "como", "estas", "estás",
    "tal", "todo", "bien",
}


def _to_number(raw: str, unit: str | None) -> float:
    value = float(raw.replace(".", "").replace(",", ""))
    if not unit:
        return value
    unit = unit.lower()
    if unit in ("mil", "k", "lucas"):
        return value * 1_000
    if unit.startswith("mill") or unit.startswith("palo"):
        return value * 1_000_000
    return value


def parse_query(db: Session, text: str) -> dict:
    lowered = text.lower().strip()
    remaining = lowered

    min_price = None
    max_price = None

    range_match = PRICE_RANGE_RE.search(remaining)
    if range_match:
        a = _to_number(range_match.group(1), range_match.group(2))
        b = _to_number(range_match.group(3), range_match.group(4))
        min_price, max_price = min(a, b), max(a, b)
        remaining = remaining[: range_match.start()] + " " + remaining[range_match.end() :]
    else:
        max_match = PRICE_MAX_RE.search(remaining)
        if max_match:
            max_price = _to_number(max_match.group(1), max_match.group(2))
            remaining = remaining[: max_match.start()] + " " + remaining[max_match.end() :]

        min_match = PRICE_MIN_RE.search(remaining)
        if min_match:
            min_price = _to_number(min_match.group(1), min_match.group(2))
            remaining = remaining[: min_match.start()] + " " + remaining[min_match.end() :]

    requested_limit = None
    limit_match = LIMIT_RE.search(remaining)
    if limit_match:
        requested_limit = int(limit_match.group(1) or limit_match.group(2))
        remaining = remaining[: limit_match.start()] + " " + remaining[limit_match.end() :]

    sort = "discount"
    superlative = False
    if SORT_EXPENSIVE_RE.search(remaining):
        sort = "price_desc"
        superlative = True
        remaining = SORT_EXPENSIVE_RE.sub(" ", remaining)
    elif SORT_DISCOUNT_RE.search(remaining):
        sort = "discount"
        superlative = True
        remaining = SORT_DISCOUNT_RE.sub(" ", remaining)
    elif SORT_CHEAP_RE.search(remaining):
        sort = "price_asc"
        superlative = True
        remaining = SORT_CHEAP_RE.sub(" ", remaining)

    store = None
    for slug, name in db.query(Store.slug, Store.name).all():
        if re.search(rf"\b{slug}\b", remaining) or name.lower() in remaining:
            store = slug
            remaining = re.sub(rf"\b{slug}\b", " ", remaining).replace(name.lower(), " ")
            break

    brand = None
    brands = [b for (b,) in db.query(Product.brand).distinct().all() if b]
    for candidate in sorted(brands, key=len, reverse=True):
        if re.search(rf"\b{re.escape(candidate.lower())}\b", remaining):
            brand = candidate
            remaining = re.sub(rf"\b{re.escape(candidate.lower())}\b", " ", remaining)
            break

    keyword_tokens = [
        word
        for word in re.findall(r"[a-záéíóúñ0-9]+", remaining)
        if word not in STOPWORDS and len(word) > 1
    ]

    has_signal = bool(brand or store or max_price is not None or min_price is not None or superlative)

    # "el <categoria> más barato de <marca>" narrows down to one specific
    # item (brand + a ranking) so answer with just the best match; a bare
    # superlative or a category/store-only ask ("mejor descuento en
    # notebook") reads as "show me some options to compare".
    if requested_limit is not None:
        limit = requested_limit
    elif superlative and brand:
        limit = 1
    else:
        limit = DEFAULT_LIMIT

    return {
        "has_signal": has_signal,
        "keyword_tokens": keyword_tokens,
        "brand": brand,
        "store": store,
        "min_price": min_price,
        "max_price": max_price,
        "sort": sort,
        "limit": min(limit, MAX_RESULTS),
    }


def search_products(
    db: Session,
    *,
    keyword_tokens: list[str] | None = None,
    brand: str | None = None,
    store: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    sort: str = "discount",
    limit: int = DEFAULT_LIMIT,
) -> list[dict]:
    query = db.query(Listing).join(Product).filter(Listing.is_active.is_(True))

    for token in keyword_tokens or []:
        # Tolerate simple Spanish plurals (notebooks -> notebook) by accepting
        # either form rather than requiring an exact contiguous phrase match.
        forms = {token}
        if token.endswith("es") and len(token) > 4:
            forms.add(token[:-2])
        elif token.endswith("s") and len(token) > 3:
            forms.add(token[:-1])
        query = query.filter(or_(*[Listing.title.ilike(f"%{form}%") for form in forms]))

    if brand:
        query = query.filter(Product.brand.ilike(f"%{brand}%"))
    if store:
        query = query.join(Store).filter(Store.slug == store)

    rows = []
    for listing in query.limit(300).all():  # cap before Python-side price filter/sort
        snapshot = listing.price_snapshots[-1] if listing.price_snapshots else None
        if snapshot is None:
            continue
        price = float(snapshot.price)
        if max_price is not None and price > max_price:
            continue
        if min_price is not None and price < min_price:
            continue
        rows.append(
            {
                "title": listing.title,
                "store": listing.store.name,
                "price": price,
                "discount_pct": float(snapshot.discount_pct) if snapshot.discount_pct else None,
                "url": listing.url,
            }
        )

    if sort == "price_desc":
        rows.sort(key=lambda r: r["price"], reverse=True)
    elif sort == "price_asc":
        rows.sort(key=lambda r: r["price"])
    else:
        rows.sort(key=lambda r: r["discount_pct"] or 0, reverse=True)

    return rows[: min(limit, MAX_RESULTS)]


def format_clp(value: float) -> str:
    return f"${value:,.0f}".replace(",", ".")


def format_results(results: list[dict], *, singular: bool) -> str:
    if not results:
        return "No encontré ofertas que calcen con lo que pediste 😕 Prueba con otra marca, tienda o rango de precio."

    if singular:
        r = results[0]
        discount = f" (-{r['discount_pct']:.0f}%)" if r["discount_pct"] else ""
        return f"{r['title']}\n{r['store']}: {format_clp(r['price'])}{discount}\n{r['url']}"

    lines = []
    for i, r in enumerate(results, start=1):
        discount = f" (-{r['discount_pct']:.0f}%)" if r["discount_pct"] else ""
        lines.append(f"{i}. {r['title']}\n   {r['store']}: {format_clp(r['price'])}{discount}\n   {r['url']}")
    return "\n\n".join(lines)


NOT_RECOGNIZED_TEXT = (
    "No entendí bien esa pregunta 🤔 Puedo buscar por marca, tienda, precio o descuento, por ejemplo:\n\n"
    '• "el notebook más barato de Lenovo"\n'
    '• "ofertas de Samsung bajo 300 mil"\n'
    '• "notebooks bajo 2 millones"\n'
    '• "qué hay con mejor descuento en Falabella"\n'
    '• "top 3 más baratos entre 200 mil y 500 mil"'
)


def answer_question(db: Session, question: str) -> str:
    parsed = parse_query(db, question)

    if not parsed["has_signal"] and not parsed["keyword_tokens"]:
        return NOT_RECOGNIZED_TEXT

    results = search_products(
        db,
        keyword_tokens=parsed["keyword_tokens"],
        brand=parsed["brand"],
        store=parsed["store"],
        min_price=parsed["min_price"],
        max_price=parsed["max_price"],
        sort=parsed["sort"],
        limit=parsed["limit"],
    )
    return format_results(results, singular=parsed["limit"] == 1)
