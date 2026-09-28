"""Known Cyber event date ranges in Chile, so the scraper cron job can run on a
fixed schedule (e.g. every 20 min, always) and simply no-op outside an active
window instead of requiring the Render cron schedule itself to be edited
before/after every event.
"""

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

BUFFER = timedelta(hours=6)


@dataclass(frozen=True)
class EventWindow:
    name: str
    start: date
    end: date


KNOWN_EVENTS: list[EventWindow] = [
    EventWindow(name="CyberMonday 2026", start=date(2026, 10, 5), end=date(2026, 10, 7)),
]


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
