"""Known Cyber event date ranges in Chile, so the scraper cron job can run on a
fixed schedule (e.g. every 20 min, always) and simply no-op outside an active
window instead of requiring the Render cron schedule itself to be edited
before/after every event.
"""

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

BUFFER = timedelta(hours=6)
# Events start at midnight in Chile; October is daylight-saving time (UTC-3).
CHILE = timezone(timedelta(hours=-3))


@dataclass(frozen=True)
class EventWindow:
    name: str
    start: date
    end: date


KNOWN_EVENTS: list[EventWindow] = [
    EventWindow(name="CyberMonday 2026", start=date(2026, 10, 5), end=date(2026, 10, 7)),
]


# Stores don't wait for the official start: in Oct 2026 Cyber prices went up
# through the afternoon before (13k+ drops per scrape vs. a few hundred the
# days before). Event prices are compared against the day before the event.
DEALS_EARLY = timedelta(days=1)


def event_start(event: EventWindow) -> datetime:
    """When Cyber prices start: midnight in Chile, the day before the event."""
    return datetime.combine(event.start - DEALS_EARLY, datetime.min.time(), tzinfo=CHILE)


def started_event_start(now: datetime | None = None) -> datetime | None:
    """When the latest event that has already begun started, or None before
    the first one. Offers are compared against their price at that moment."""
    now = now or datetime.now(timezone.utc)
    starts = [event_start(e) for e in KNOWN_EVENTS if event_start(e) <= now]
    return max(starts, default=None)


def is_scrape_window_active(now: datetime | None = None) -> bool:
    if os.environ.get("FORCE_SCRAPE") == "1":
        return True

    now = now or datetime.now(timezone.utc)
    for event in KNOWN_EVENTS:
        start = datetime.combine(event.start, datetime.min.time(), tzinfo=timezone.utc) - BUFFER
        end = datetime.combine(event.end, datetime.max.time(), tzinfo=timezone.utc) + BUFFER
        if start <= now <= end:
            return True
    return False
