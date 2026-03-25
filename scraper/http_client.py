"""Rate-limited HTTP client base class for Limitless scrapers."""

import logging
import re
import threading
import time
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# Shared regex for text-format decklist line parsing (used by both scrapers)
DECKLIST_LINE_RE = re.compile(r"^(\d+)\s+(.+?)\s+([A-Z0-9]{2,5}[A-Z]?|Energy)\s+(\d+|[A-Z]+\d*)$")


def parse_card_links(soup: BeautifulSoup, decklist_url: str) -> list[dict[str, Any]]:
    """Parse structured card-link elements from a decklist page.

    Shared by both JP and Labs scrapers since the HTML format is identical.

    Returns:
        List of card dicts with keys: count, name, set_code, card_number, card_id.
    """
    cards: list[dict[str, Any]] = []
    card_links = soup.find_all("a", class_="card-link")
    if not card_links:
        return cards

    for link in card_links:
        href = link.get("href", "").split("?")[0].rstrip("/")
        parts = href.split("/")

        set_code = parts[2] if len(parts) > 2 else ""
        card_number = parts[3] if len(parts) > 3 else ""

        count_el = link.find("span", class_="card-count")
        name_el = link.find("span", class_="card-name")

        count = 1
        if count_el:
            try:
                count = int(count_el.get_text(strip=True))
            except ValueError:
                logger.warning(
                    "Could not parse card count %r in decklist %s, defaulting to 1",
                    count_el.get_text(strip=True),
                    decklist_url,
                )

        name = name_el.get_text(strip=True) if name_el else link.get_text(strip=True)
        if not name:
            continue

        cards.append(
            {
                "count": count,
                "name": name,
                "set_code": set_code,
                "card_number": card_number,
                "card_id": f"{set_code}-{card_number}" if set_code and card_number else name,
            }
        )
    return cards


def extract_sprites(cell: Tag, join_sep: str = " ") -> tuple[str, list[str]]:
    """Extract archetype name and sprite URLs from an HTML element.

    Shared by both JP and Labs scrapers. Looks for <img> tags and extracts
    Pokemon names from alt text or filenames.

    Args:
        cell: A BeautifulSoup Tag containing sprite images.
        join_sep: Separator for joining multiple Pokemon names.

    Returns:
        Tuple of (archetype_string, list_of_sprite_urls).
    """
    sprite_urls: list[str] = []
    names: list[str] = []

    imgs = cell.find_all("img") if cell else []
    for img in imgs:
        src = img.get("src", "")
        alt = img.get("alt", "")

        if src:
            sprite_urls.append(src)

        if alt and alt.strip():
            names.append(alt.strip())
        elif src:
            filename_match = re.search(r"/([a-zA-Z0-9_-]+)\.png", src)
            if filename_match:
                raw = filename_match.group(1).replace("_", " ").replace("-", " ")
                names.append(raw.title())

    # Also check link text as fallback
    link = cell.find("a")
    if link and not names:
        text = link.get_text(strip=True)
        if text:
            names.append(text)

    archetype = join_sep.join(names) if names else ""
    return archetype, sprite_urls


class RateLimitedHTTPClient:
    """HTTP client with rate limiting, retries, and exponential backoff."""

    def __init__(
        self,
        *,
        base_url: str = "",
        max_rpm: int = 20,
        timeout: float = 30.0,
        max_retries: int = 3,
        user_agent: str = "TrainerLab-Scout/1.0",
        use_base_url: bool = False,
    ) -> None:
        self._base_url = base_url
        self._max_rpm = max_rpm
        self._timeout = timeout
        self._max_retries = max_retries
        self._request_timestamps: list[float] = []
        self._lock = threading.Lock()
        client_kwargs: dict[str, Any] = {
            "timeout": timeout,
            "follow_redirects": True,
            "headers": {"User-Agent": user_agent},
        }
        if use_base_url and base_url:
            client_kwargs["base_url"] = base_url
        self._client = httpx.Client(**client_kwargs)

    def _rate_limit(self) -> None:
        """Block until a request slot is available."""
        while True:
            with self._lock:
                now = time.monotonic()
                self._request_timestamps = [
                    ts for ts in self._request_timestamps if now - ts < 60.0
                ]
                if len(self._request_timestamps) < self._max_rpm:
                    self._request_timestamps.append(now)
                    return
                oldest = self._request_timestamps[0]
                wait = 60.0 - (now - oldest) + 0.1
            # Sleep outside the lock so other threads aren't blocked
            if wait > 0:
                logger.debug("Rate limit reached, sleeping %.1fs", wait)
                time.sleep(wait)

    def _get(self, url: str) -> httpx.Response:
        """GET with rate limiting, retries, and exponential backoff."""
        base_delay = 1.0
        last_exc: Exception | None = None
        last_response: httpx.Response | None = None

        for attempt in range(self._max_retries):
            self._rate_limit()
            try:
                response = self._client.get(url)
                last_response = response

                if response.status_code == 404:
                    raise httpx.HTTPStatusError(
                        "Not Found",
                        request=response.request,
                        response=response,
                    )

                if response.status_code == 429 or response.status_code >= 500:
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        "Retryable status %d for %s, retrying in %.1fs (attempt %d/%d)",
                        response.status_code,
                        url,
                        delay,
                        attempt + 1,
                        self._max_retries,
                    )
                    time.sleep(delay)
                    continue

                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as exc:
                logger.error(
                    "HTTP %d for %s (attempt %d, not retrying)",
                    exc.response.status_code,
                    url,
                    attempt + 1,
                )
                raise
            except httpx.HTTPError as exc:
                last_exc = exc
                delay = base_delay * (2**attempt)
                logger.warning(
                    "Request error for %s: %s, retrying in %.1fs (attempt %d/%d)",
                    url,
                    exc,
                    delay,
                    attempt + 1,
                    self._max_retries,
                )
                time.sleep(delay)

        # Two exhaustion paths:
        # 1. Retryable status codes (429/5xx) — last_exc is None, last_response is set
        # 2. Network errors (timeout, connect) — last_exc is set
        if last_response is not None and last_exc is None:
            raise httpx.HTTPError(
                f"Failed after {self._max_retries} retries with retryable status codes"
                f" (last status: {last_response.status_code})"
            )
        # Network error path — last_exc is guaranteed non-None here because
        # the only way to reach this point without last_response is via the
        # except httpx.HTTPError branch which always sets last_exc.
        assert last_exc is not None, "unreachable: loop must set last_exc or last_response"
        raise httpx.HTTPError(f"Failed after {self._max_retries} retries: {last_exc}") from last_exc

    def _soup(self, url: str) -> BeautifulSoup:
        """Fetch a page and return parsed BeautifulSoup."""
        resp = self._get(url)
        return BeautifulSoup(resp.text, "html.parser")

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> "RateLimitedHTTPClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
