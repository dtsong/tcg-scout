"""HTTP API client for players.pokemon-card.com.

Discovered API endpoints (no browser rendering required):

1. Event Listing:
   GET /event_search?offset=0&order=4&result_resist=1&event_type[]=3:1&event_type[]=3:2&event_type[]=3:7
   Returns: { code, event: [...], eventCount }
   Each event has: event_holding_id, event_date_params (YYYYMMDD), shop_name,
   prefecture_name, capacity, event_title, etc.
   Pagination: offset param (20 per page)

2. Event Results (placements):
   GET /event_result_detail_search?event_holding_id={id}&offset=0&per_page=64
   Returns: { code, count, event: {metadata}, results: [...] }
   Each result has: rank, name, player_id, area, deck_id, point

3. Decklists:
   NO API endpoint found. Deck codes (e.g. "niQgLg-PR7m4f-Q9NPLL") are decoded
   client-side on the deck confirm page. Still requires Playwright for extraction.

Transport: the host is fronted by Cloudflare bot management, which 403s any
client whose TLS fingerprint is not a browser (httpx, requests, curl). curl_cffi
with Chrome impersonation passes cleanly; see PokemonJPAPIClient.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from config import POKEMON_JP_CITY_LEAGUE_EVENT_TYPES

logger = logging.getLogger(__name__)

BASE_URL = "https://players.pokemon-card.com"
PAGE_SIZE = 20  # event_search returns 20 per page
# curl_cffi impersonation target. Cloudflare fingerprints the TLS handshake, so
# this must be a real browser profile, not just a User-Agent string.
IMPERSONATE_BROWSER = "chrome"


class JPAPIError(RuntimeError):
    """Non-retryable HTTP failure from players.pokemon-card.com."""


LEAGUE_NAME_MAP = {
    "オープン": "open",
    "マスター": "open",  # Masters league treated as open division
    "シニア": "senior",
    "ジュニア": "junior",
}

# CL division name extraction from event titles
CL_DIVISION_MAP = {
    "マスター": "masters",
    "シニア": "seniors",
    "ジュニア": "juniors",
}

# Championship-tier markers in official JP event titles. These events are run by
# TPC rather than a card shop, so they carry no shop_name and must be classified
# from the title alone.
#   ポケモンジャパンチャンピオンシップス -- Pokemon Japan Championships (PJCS)
#   チャンピオンズリーグ                 -- Champions League
_CHAMPIONSHIP_TITLE_MARKERS = (
    "ジャパンチャンピオンシップス",
    "チャンピオンズリーグ",
)


def classify_jp_tournament_type(event_title: str) -> str:
    """Derive a Scout ``tournament_type`` from an official JP event title.

    Returns ``"championship"`` for national majors, else ``"city-league"``.
    """
    if any(marker in event_title for marker in _CHAMPIONSHIP_TITLE_MARKERS):
        return "championship"
    return "city-league"


@dataclass
class JPCityLeagueEvent:
    event_id: int  # event_holding_id
    date: str  # YYYY-MM-DD
    prefecture: str
    store_name: str
    capacity: int
    division: str  # open, senior, junior
    event_title: str = ""  # Official title; the only name national events carry

    @property
    def tournament_type(self) -> str:
        """Classify from the official title.

        Championship-tier events (PJCS, Champions League) are national/regional
        majors, not shop-run City Leagues, and are surfaced differently on the site.
        """
        return classify_jp_tournament_type(self.event_title)

    @property
    def display_name(self) -> str:
        """Human-readable event name.

        City League events are identified by prefecture + shop. National events
        have no shop (``shop_name`` is null in the API) and carry their identity
        in ``event_title``; a bare prefecture is not an event name, so the shop
        form is only used when a shop is actually present.
        """
        if self.store_name:
            return f"{self.prefecture} {self.store_name}".strip()
        return self.event_title or self.prefecture or f"City League {self.date}"

    @classmethod
    def from_api(cls, data: dict) -> "JPCityLeagueEvent":
        date_raw = data.get("event_date_params", data.get("date", ""))
        # Convert YYYYMMDD to YYYY-MM-DD
        if len(date_raw) == 8 and date_raw.isdigit():
            date_iso = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
        elif "/" in date_raw:
            date_iso = date_raw.replace("/", "-")
        else:
            date_iso = date_raw
        league_jp = data.get("leagueName", "オープン")
        division = LEAGUE_NAME_MAP.get(league_jp)
        if division is None:
            logger.warning(
                "Unknown leagueName %r for event %s, defaulting to 'open'",
                league_jp,
                data.get("event_holding_id", "?"),
            )
            division = "open"

        # National events send these keys with an explicit null, so `.get(k, "")`
        # is not enough -- the default only fires when the key is absent.
        def _text(*keys: str) -> str:
            for key in keys:
                value = data.get(key)
                if value:
                    return str(value)
            return ""

        return cls(
            event_id=data.get("event_holding_id", data.get("event_id", 0)),
            date=date_iso,
            prefecture=_text("prefecture_name", "prefecture"),
            store_name=_text("shop_name", "store_name"),
            capacity=data.get("capacity") or 0,
            division=division,
            event_title=_text("event_title"),
        )


@dataclass
class JPCityLeagueResult:
    rank: int
    player_name: str
    player_id: str
    area: str
    deck_id: str | None  # Deck code for fetching decklist


class PokemonJPAPIClient:
    """Fetch City League event listings and results from pokemon-card.com API.

    Plain HTTP, no browser rendering. The host sits behind Cloudflare bot
    management that rejects non-browser TLS fingerprints with 403 regardless of
    User-Agent (observed 2026-07-28 onward), so requests go through curl_cffi
    with Chrome impersonation. Decklists still require a browser (PokemonJPClient).
    """

    # Cloudflare occasionally serves transient 403/5xx responses before a clean
    # session is established. One retry was not enough on the 2026-09-17 scheduled
    # run, so retries back off exponentially: 2s, 4s, 8s (14s worst case).
    _RETRY_STATUSES = frozenset({403, 429, 500, 502, 503, 504})
    _RETRY_DELAYS_SECONDS = (2.0, 4.0, 8.0)

    def __init__(self, *, session: Any | None = None) -> None:
        if session is None:
            from curl_cffi import requests as cffi_requests

            session = cffi_requests.Session(impersonate=IMPERSONATE_BROWSER, timeout=30.0)
        self._session = session

    def _get_json(self, path: str, params: dict[str, Any]) -> dict | None:
        """GET a JSON endpoint. Returns None on 404 (results not published)."""
        url = f"{BASE_URL}{path}?{urlencode(params, doseq=True)}"
        resp = self._session.get(url)
        for delay in self._RETRY_DELAYS_SECONDS:
            if resp.status_code not in self._RETRY_STATUSES:
                break
            logger.warning(
                "JP API %s returned %d, retrying in %.0fs", path, resp.status_code, delay
            )
            time.sleep(delay)
            resp = self._session.get(url)
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise JPAPIError(f"JP API {path} returned HTTP {resp.status_code}")
        return resp.json()

    def fetch_cl_events(self, start: str, end: str) -> list[JPCityLeagueEvent]:
        """Fetch City League events in a date range.

        Args:
            start: Start date YYYY-MM-DD (inclusive)
            end: End date YYYY-MM-DD (inclusive)

        Returns:
            List of events within the date range, newest first.
        """
        events: list[JPCityLeagueEvent] = []
        offset = 0

        while True:
            data = self._get_json(
                "/event_search",
                {
                    "offset": offset,
                    "order": 4,  # Sort by date desc
                    "result_resist": 1,  # Only events with results
                    "event_type[]": POKEMON_JP_CITY_LEAGUE_EVENT_TYPES,
                },
            )
            if data is None or data.get("code") != 200:
                logger.warning("API returned code %s", None if data is None else data.get("code"))
                break

            page_events = data.get("event", [])
            if not page_events:
                break

            for raw in page_events:
                evt = JPCityLeagueEvent.from_api(raw)
                # Filter by date range
                if evt.date < start:
                    # Past our window (events are newest-first)
                    return events
                if evt.date <= end:
                    events.append(evt)

            offset += PAGE_SIZE
            total = data.get("eventCount", 0)
            if offset >= total:
                break

            logger.info("Fetched %d events so far (offset %d/%d)", len(events), offset, total)

        return events

    def fetch_event_results(self, event_holding_id: int) -> list[JPCityLeagueResult]:
        """Fetch placements for a specific event.

        Args:
            event_holding_id: The event's holding ID from the listing.

        Returns:
            List of placements sorted by rank.
        """
        _, results = self.fetch_event_with_metadata(event_holding_id)
        return results

    def fetch_event_with_metadata(
        self, event_holding_id: int
    ) -> tuple[dict, list[JPCityLeagueResult]]:
        """Fetch event metadata and placements in one call.

        Returns:
            Tuple of (event_metadata_dict, list_of_results).
            event_metadata_dict has keys: event_title, event_date_params, leagueName, etc.
        """
        data = self._get_json(
            "/event_result_detail_search",
            {"event_holding_id": event_holding_id, "offset": 0, "per_page": 64},
        )
        if data is None:
            logger.warning("Event %d returned 404 (no results published yet)", event_holding_id)
            return {}, []

        if data.get("code") != 200:
            logger.warning("API returned code %s for event %d", data.get("code"), event_holding_id)
            return {}, []

        event_meta = data.get("event", {})

        results = []
        for r in data.get("results", []):
            results.append(
                JPCityLeagueResult(
                    rank=r.get("rank", 0),
                    player_name=r.get("name", ""),
                    player_id=r.get("player_id", ""),
                    area=r.get("area", ""),
                    deck_id=r.get("deck_id") or None,
                )
            )

        results.sort(key=lambda r: r.rank)
        logger.info(
            "Fetched %d results for event %d (%s)",
            len(results),
            event_holding_id,
            event_meta.get("event_title", "?"),
        )
        return event_meta, results

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "PokemonJPAPIClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()
