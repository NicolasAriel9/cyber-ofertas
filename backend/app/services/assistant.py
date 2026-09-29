"""Telegram assistant: lets subscribers ask free-text questions about the
catalog (e.g. "cual es el notebook mas barato de lenovo?") via Claude's
tool-use, backed by a single search_products tool that queries our own DB
directly -- Claude never sees or invents prices, it only calls the tool.
Stateless per message: no conversation history is kept between messages.
"""

import json

from anthropic import Anthropic
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Listing, Product, Store

MAX_RESULTS = 8
MAX_TOOL_ROUNDS = 4

SEARCH_TOOL = {
    "name": "search_products",
    "description": (
        "Busca ofertas en el catalogo real de Cyber Ofertas. Usala para responder "
        "cualquier pregunta sobre productos, precios, marcas, tiendas o descuentos "
        "disponibles ahora mismo -- nunca respondas sobre precios sin llamarla primero."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "Palabra clave a buscar en el titulo del producto, ej. 'notebook', 'smart tv'.",
            },
            "brand": {
                "type": "string",
                "description": "Marca si el usuario la menciona, ej. 'Lenovo', 'Samsung'.",
            },
            "store": {
                "type": "string",
                "enum": ["falabella", "paris"],
                "description": "Filtrar por una tienda especifica si el usuario la menciona.",
            },
            "max_price": {"type": "number", "description": "Precio maximo en pesos chilenos (CLP)."},
            "sort": {
                "type": "string",
                "enum": ["price_asc", "price_desc", "discount"],
                "description": "Como ordenar los resultados. Usa price_asc para 'el mas barato'.",
            },
            "limit": {"type": "integer", "description": "Cuantos resultados devolver (por defecto 5)."},
        },
    },
}

SYSTEM_PROMPT = (
    "Eres el asistente de Cyber Ofertas, una app personal que compara precios de "
    "Falabella y Paris durante el Cyber en Chile, para uso de Nico y Paula. "
    "Responde siempre en espanol de Chile, breve y directo, en texto plano (sin "
    "tablas ni markdown pesado) porque se envia por Telegram. Usa la herramienta "
    "search_products para consultar el catalogo real antes de responder cualquier "
    "pregunta sobre productos o precios -- nunca inventes precios ni productos. Si "
    "no encuentras nada relevante, dilo con honestidad. Cuando muestres resultados, "
    "incluye la tienda y el precio, y el link si esta disponible."
)


def _run_search(
    db: Session,
    *,
    keyword: str | None = None,
    brand: str | None = None,
    store: str | None = None,
    max_price: float | None = None,
    sort: str = "price_asc",
    limit: int = 5,
) -> list[dict]:
    query = db.query(Listing).join(Product).filter(Listing.is_active.is_(True))

    if keyword:
        query = query.filter(Listing.title.ilike(f"%{keyword}%"))
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
    elif sort == "discount":
        rows.sort(key=lambda r: r["discount_pct"] or 0, reverse=True)
    else:
        rows.sort(key=lambda r: r["price"])

    return rows[: min(limit, MAX_RESULTS)]


def answer_question(db: Session, question: str) -> str:
    if not settings.anthropic_api_key:
        return "El asistente todavía no está configurado (falta ANTHROPIC_API_KEY)."

    client = Anthropic(api_key=settings.anthropic_api_key)
    messages: list[dict] = [{"role": "user", "content": question}]

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[SEARCH_TOOL],
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            text = "".join(block.text for block in response.content if block.type == "text").strip()
            return text or "No tengo una respuesta para eso."

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            results = _run_search(db, **block.input)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(results, ensure_ascii=False),
                }
            )
        messages.append({"role": "user", "content": tool_results})

    return "No pude terminar de procesar tu pregunta, intenta de nuevo con algo más simple."
