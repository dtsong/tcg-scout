"""Rate-limited HTTP client base class for Limitless scrapers."""

import logging
import threading
import time
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


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
                    self._request_timestamps.append(time.monotonic())
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

        for attempt in range(self._max_retries):
            self._rate_limit()
            try:
                response = self._client.get(url)

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

            except httpx.HTTPStatusError:
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

        if last_exc is None:
            raise httpx.HTTPError(
                f"Failed after {self._max_retries} retries with retryable status codes "
                f"(last status: {response.status_code})"
            )
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
