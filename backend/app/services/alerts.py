"""Price-drop detection: compares a listing's new price snapshot against its
previous one, and notifies subscribers who favorited that product — either
because the new price hits their explicit target, or because the drop exceeds
a default threshold when no target was set. Each notification is logged in
AlertEvent so the same drop is never re-sent on a later scrape cycle.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AlertEvent, Favorite, Listing, PriceSnapshot


@dataclass
class PriceDropAlert:
    favorite: Favorite
    listing: Listing
    old_price: float
    new_price: float
    pct_drop: float


def check_price_drop(db: Session, listing: Listing, new_snapshot: PriceSnapshot) -> list[PriceDropAlert]:
    previous_snapshots = [s for s in listing.price_snapshots if s.id != new_snapshot.id]
    if not previous_snapshots:
        return []

    previous = previous_snapshots[-1]
    old_price = float(previous.price)
    new_price = float(new_snapshot.price)
    if new_price >= old_price or old_price <= 0:
        return []

    pct_drop = (old_price - new_price) / old_price * 100

    favorites = db.query(Favorite).filter(Favorite.product_id == listing.product_id).all()
    alerts: list[PriceDropAlert] = []
    for favorite in favorites:
        target_met = favorite.target_price is not None and new_price <= float(favorite.target_price)
        default_threshold_met = favorite.target_price is None and pct_drop >= settings.default_drop_alert_threshold_pct
        if not (target_met or default_threshold_met):
            continue

        already_sent = (
            db.query(AlertEvent)
            .filter(
                AlertEvent.favorite_id == favorite.id,
                AlertEvent.listing_id == listing.id,
                AlertEvent.new_price == new_snapshot.price,
            )
            .first()
        )
        if already_sent:
            continue

        alerts.append(
            PriceDropAlert(
                favorite=favorite,
                listing=listing,
                old_price=old_price,
                new_price=new_price,
                pct_drop=pct_drop,
            )
        )
    return alerts


def record_alert_sent(db: Session, alert: PriceDropAlert) -> None:
    db.add(
        AlertEvent(
            favorite_id=alert.favorite.id,
            listing_id=alert.listing.id,
            old_price=alert.old_price,
            new_price=alert.new_price,
            pct_drop=alert.pct_drop,
        )
    )
