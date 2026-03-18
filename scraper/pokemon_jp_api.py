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

logger = logging.getLogger(__name__)

BASE_URL = "https://players.pokemon-card.com"
PAGE_SIZE = 20  # event_search returns 20 per page


@dataclass
class JPCityLeagueEvent:
    event_id: int  # event_holding_id
    date: str  # YYYY-MM-DD
    prefecture: str
    store_name: str
    capacity: int

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
        return cls(
            event_id=data.get("event_holding_id", data.get("event_id", 0)),
            date=date_iso,
            prefecture=data.get("prefecture_name", data.get("prefecture", "")),
            store_name=data.get("shop_name", data.get("store_name", "")),
            capacity=data.get("capacity", 0),
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
                    "event_type[]": ["3:1", "3:2", "3:7"],  # City League types
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
        resp = self._client.get(
            "/event_result_detail_search",
            params={
                "event_holding_id": event_holding_id,
                "offset": 0,
                "per_page": 64,  # Max out to get all placements
            },
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 200:
            logger.warning("API returned code %s for event %d", data.get("code"), event_holding_id)
            return []

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
        logger.info("Fetched %d results for event %d", len(results), event_holding_id)
        return results

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PokemonJPAPIClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()
