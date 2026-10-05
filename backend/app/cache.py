"""In-memory cache for the browsing endpoints, refreshed in the background.

The listing queries scan every live offer (~200k during the Cyber) and the
database also takes the scraper's writes, so a single page could take from a
few seconds to over a minute. Results are kept per query: a request gets the
stored copy right away, and a background thread recomputes every query used
in the last KEEP_FOR seconds once it's older than TTL. Only the first request
for a new combination of filters waits for the database.

Disabled unless the app enables it at startup, so tests calling the endpoint
functions directly always hit the database.
"""
import logging
import threading
import time
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db import SessionLocal

log = logging.getLogger(__name__)

# The scraper refreshes a store every ~10 minutes; a minute behind is free.
TTL = 60
# Queries nobody asked for in this long stop being refreshed and are dropped.
KEEP_FOR = 15 * 60


@dataclass
class _Entry:
    value: Any
    compute: Callable[[Session], Any]
    computed_at: float
    used_at: float


class ResponseCache:
    def __init__(self) -> None:
        self.enabled = False
        self._entries: dict[Hashable, _Entry] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def get(self, key: Hashable, compute: Callable[[Session], Any], db: Session) -> Any:
        if not self.enabled:
            return compute(db)
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry:
                entry.used_at = now
                return entry.value
        value = compute(db)
        with self._lock:
            self._entries[key] = _Entry(value, compute, now, now)
        return value

    def start(self) -> None:
        self.enabled = True
        if self._thread is None:
            self._thread = threading.Thread(target=self._refresh_forever, name="response-cache", daemon=True)
            self._thread.start()

    def _refresh_forever(self) -> None:
        while True:
            time.sleep(5)
            try:
                self._refresh_due()
            except Exception:
                log.exception("response cache refresh failed")

    def _refresh_due(self) -> None:
        now = time.monotonic()
        with self._lock:
            for key in [k for k, e in self._entries.items() if now - e.used_at > KEEP_FOR]:
                del self._entries[key]
            # Oldest first, so a slow round doesn't starve the same queries.
            due = sorted(
                ((k, e) for k, e in self._entries.items() if now - e.computed_at >= TTL),
                key=lambda item: item[1].computed_at,
            )
        for key, entry in due:
            with SessionLocal() as db:
                try:
                    value = entry.compute(db)
                except Exception:
                    log.exception("could not refresh %r", key)
                    continue
            with self._lock:
                if key in self._entries:
                    self._entries[key] = _Entry(value, entry.compute, time.monotonic(), self._entries[key].used_at)


response_cache = ResponseCache()
