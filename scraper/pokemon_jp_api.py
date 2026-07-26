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
"""

import logging
from dataclasses import dataclass

import httpx

from config import POKEMON_JP_CITY_LEAGUE_EVENT_TYPES

logger = logging.getLogger(__name__)

BASE_URL = "https://players.pokemon-card.com"
PAGE_SIZE = 20  # event_search returns 20 per page


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

    Uses plain HTTP -- no browser rendering required for event data.
    Decklists still require Playwright (see PokemonJPClient).
    """

    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=BASE_URL,
            timeout=30.0,
            headers={"User-Agent": "Mozilla/5.0 Scout/1.0"},
        )

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
            resp = self._client.get(
                "/event_search",
                params={
                    "offset": offset,
                    "order": 4,  # Sort by date desc
                    "result_resist": 1,  # Only events with results
                    "event_type[]": POKEMON_JP_CITY_LEAGUE_EVENT_TYPES,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 200:
                logger.warning("API returned code %s", data.get("code"))
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
        resp = self._client.get(
            "/event_result_detail_search",
            params={
                "event_holding_id": event_holding_id,
                "offset": 0,
                "per_page": 64,
            },
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            if resp.status_code == 404:
                logger.warning("Event %d returned 404 (no results published yet)", event_holding_id)
                return {}, []
            raise
        data = resp.json()

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
        self._client.close()

    def __enter__(self) -> "PokemonJPAPIClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()
