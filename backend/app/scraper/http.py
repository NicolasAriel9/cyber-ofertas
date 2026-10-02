"""Shared, polite HTTP client for every scraper: identifies itself, waits
between requests to the same host, and retries transient failures with
backoff. One instance per scrape run so connections are reused.
"""

import logging
import os
import time
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# A browser-like UA (some retailers serve an empty shell to unknown agents),
# plus a contact address so the traffic stays identifiable.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36 cyber-ofertas-personal-tool/0.2 (+https://github.com/NicolasAriel9/cyber-ofertas)"
)

# Seconds to wait between two requests to the same host.
REQUEST_DELAY = float(os.environ.get("SCRAPE_REQUEST_DELAY", "1.0"))
MAX_RETRIES = 3
RETRY_STATUSES = {429, 500, 502, 503, 504}


class PoliteClient:
    def __init__(self, delay: float = REQUEST_DELAY) -> None:
        self.delay = delay
        self._last_request_at: dict[str, float] = {}
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "es-CL,es;q=0.9"},
            timeout=30.0,
            follow_redirects=True,
        )

    def _wait_for_host(self, url: str) -> None:
        host = urlparse(url).netloc
        elapsed = time.monotonic() - self._last_request_at.get(host, 0.0)
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_at[host] = time.monotonic()

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        for attempt in range(1, MAX_RETRIES + 1):
            self._wait_for_host(url)
            try:
                response = self._client.request(method, url, **kwargs)
            except httpx.TransportError as exc:
                if attempt == MAX_RETRIES:
                    raise
                logger.warning("%s %s failed (%s), retry %d/%d", method, url, exc, attempt, MAX_RETRIES)
            else:
                if response.status_code not in RETRY_STATUSES or attempt == MAX_RETRIES:
                    response.raise_for_status()
                    return response
                logger.warning("%s %s -> %d, retry %d/%d", method, url, response.status_code, attempt, MAX_RETRIES)
            time.sleep(2**attempt)
        raise RuntimeError("unreachable")

    def get(self, url: str, params: dict | None = None, headers: dict | None = None) -> httpx.Response:
        return self.request("GET", url, params=params, headers=headers)

    def post_json(self, url: str, payload: dict, headers: dict | None = None):
        return self.request("POST", url, json=payload, headers=headers).json()

    def get_json(self, url: str, params: dict | None = None, headers: dict | None = None):
        return self.get(url, params=params, headers=headers).json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PoliteClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
