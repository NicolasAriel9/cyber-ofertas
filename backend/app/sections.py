"""The app has two sections: retail offers ("productos") and travel deals
("viajes", the Cyber Viajes page). Travel is told apart by its categories,
which the travel scrapers create (app/scraper/stores/travel.py)."""

from sqlalchemy import ColumnElement, or_, select

from app.models import Category, Product

FLIGHTS = "vuelos"
PACKAGES = "paquetes"
HOTELS = "alojamientos"
TRAVEL_CATEGORY_SLUGS = (FLIGHTS, PACKAGES, HOTELS)

SECTION_PATTERN = "^(productos|viajes)$"


def section_filter(section: str | None) -> ColumnElement[bool] | None:
    """WHERE clause on Product for a section; None means both."""
    travel_ids = select(Category.id).where(Category.slug.in_(TRAVEL_CATEGORY_SLUGS)).scalar_subquery()
    if section == "viajes":
        return Product.category_id.in_(travel_ids)
    if section == "productos":
        return or_(Product.category_id.is_(None), Product.category_id.not_in(travel_ids))
    return None
