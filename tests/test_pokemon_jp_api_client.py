"""Transport-level tests for PokemonJPAPIClient.

players.pokemon-card.com sits behind Cloudflare bot management. From 2026-07-28
every scheduled build died with ``403 Forbidden`` on the event listing because
httpx's TLS fingerprint is not a browser's. The client now goes through
curl_cffi with Chrome impersonation; these tests pin that contract and the
pagination / 404 semantics using a fake session so nothing touches the network.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

import pytest

from config import POKEMON_JP_CITY_LEAGUE_EVENT_TYPES
from scraper import pokemon_jp_api
from scraper.pokemon_jp_api import (
    BASE_URL,
    IMPERSONATE_BROWSER,
    JPAPIError,
    PokemonJPAPIClient,
)


@dataclass
class _FakeResponse:
    status_code: int
    payload: dict | None = None

    def json(self) -> dict:
        assert self.payload is not None
        return self.payload


@dataclass
class _FakeSession:
    """Scripted responses keyed by endpoint path, consumed in order."""

    scripts: dict[str, list[_FakeResponse]]
    calls: list[str] = field(default_factory=list)
    closed: bool = False

    def get(self, url: str) -> _FakeResponse:
        """Route by ``path#event_type`` when scripted that way, else by path."""
        self.calls.append(url)
        parsed = urlparse(url)
        types = parse_qs(parsed.query).get("event_type[]", [])
        typed_key = f"{parsed.path}#{types[0]}" if len(types) == 1 else None
        queue = self.scripts.get(typed_key) or self.scripts[parsed.path]
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def close(self) -> None:
        self.closed = True


def _event(event_id: int, date_yyyymmdd: str) -> dict:
    return {
        "event_holding_id": event_id,
        "event_date_params": date_yyyymmdd,
        "prefecture_name": "東京都",
        "shop_name": f"Shop {event_id}",
        "capacity": 64,
        "leagueName": "オープン",
        "event_title": "シティリーグ2027 シーズン1 オープンリーグ",
    }


class TestTransportContract:
    def test_default_session_impersonates_a_browser(self):
        """A plain User-Agent is not enough: Cloudflare fingerprints the TLS handshake."""
        source = inspect.getsource(PokemonJPAPIClient.__init__)
        assert "curl_cffi" in source
        assert "impersonate=IMPERSONATE_BROWSER" in source
        assert IMPERSONATE_BROWSER.startswith("chrome")

    def test_httpx_is_no_longer_the_transport(self):
        """httpx gets 403 from this host; a regression to it would re-break the pipeline."""
        module_source = inspect.getsource(pokemon_jp_api)
        assert "import httpx" not in module_source

    def test_requests_are_absolute_and_query_one_event_type_at_a_time(self):
        """One request per type: a retired type code then fails alone, not the whole listing."""
        session = _FakeSession({"/event_search": [_FakeResponse(200, {"code": 200, "event": []})]})
        PokemonJPAPIClient(session=session).fetch_cl_events("2026-08-14", "2026-12-10")

        assert all(u.startswith(f"{BASE_URL}/event_search?") for u in session.calls)
        queries = [parse_qs(urlparse(u).query) for u in session.calls]
        assert all(q["result_resist"] == ["1"] for q in queries)
        assert all(len(q["event_type[]"]) == 1 for q in queries)
        sent = [q["event_type[]"][0] for q in queries]
        assert sent == list(POKEMON_JP_CITY_LEAGUE_EVENT_TYPES)

    def test_close_releases_the_session(self):
        session = _FakeSession({})
        with PokemonJPAPIClient(session=session):
            pass
        assert session.closed


class TestFetchClEvents:
    def test_walks_pages_until_start_date_and_filters_by_end(self):
        page1 = {
            "code": 200,
            "eventCount": 40,
            "event": [_event(3, "20261215"), _event(2, "20261001")],
        }
        page2 = {
            "code": 200,
            "eventCount": 40,
            "event": [_event(1, "20260901"), _event(0, "20260701")],
        }
        session = _FakeSession(
            {"/event_search": [_FakeResponse(200, page1), _FakeResponse(200, page2)]}
        )

        events = PokemonJPAPIClient(session=session).fetch_cl_events(
            "2026-08-14", "2026-12-10", event_types=["3:2"]
        )

        assert [e.event_id for e in events] == [2, 1]
        assert len(session.calls) == 2, "stops paging once an event predates the window"
        offsets = [parse_qs(urlparse(u).query)["offset"] for u in session.calls]
        assert offsets == [["0"], ["20"]]

    def test_retries_with_backoff_on_403_then_succeeds(self, monkeypatch):
        """Two transient 403s (the 2026-09-17 scheduled run saw this) must not fail the scrape."""
        slept: list[float] = []
        monkeypatch.setattr(pokemon_jp_api.time, "sleep", slept.append)
        payload = {"code": 200, "eventCount": 1, "event": [_event(9, "20260920")]}
        session = _FakeSession(
            {"/event_search": [_FakeResponse(403), _FakeResponse(403), _FakeResponse(200, payload)]}
        )

        events = PokemonJPAPIClient(session=session).fetch_cl_events(
            "2026-08-14", "2026-12-10", event_types=["3:2"]
        )

        assert [e.event_id for e in events] == [9]
        assert len(session.calls) == 3
        assert slept == [2.0, 4.0], "exponential backoff between attempts"

    def test_persistent_403_raises_after_all_retries(self, monkeypatch):
        """A silent empty result would look like a quiet season and mask the block."""
        slept: list[float] = []
        monkeypatch.setattr(pokemon_jp_api.time, "sleep", slept.append)
        session = _FakeSession({"/event_search": [_FakeResponse(403)]})

        with pytest.raises(JPAPIError, match="403"):
            PokemonJPAPIClient(session=session).fetch_cl_events(
                "2026-08-14", "2026-12-10", event_types=["3:2"]
            )

        assert len(session.calls) == 1 + len(PokemonJPAPIClient._RETRY_DELAYS_SECONDS)
        assert slept == [2.0, 4.0, 8.0]

    def test_rejected_event_type_is_skipped_and_other_types_still_collected(self):
        """From 2026-10-15 the API answered 400 for ``3:8`` and every scheduled scrape died."""
        cl = {"code": 200, "eventCount": 1, "event": [_event(20, "20261123")]}
        city = {
            "code": 200,
            "eventCount": 2,
            "event": [_event(11, "20261115"), _event(10, "20261001")],
        }
        session = _FakeSession(
            {
                "/event_search#3:1": [_FakeResponse(200, cl)],
                "/event_search#3:2": [_FakeResponse(200, city)],
                "/event_search#3:8": [_FakeResponse(400, {"code": 400})],
                "/event_search": [_FakeResponse(404)],
            }
        )

        events = PokemonJPAPIClient(session=session).fetch_cl_events(
            "2026-08-14", "2026-12-10", event_types=["3:1", "3:8", "3:2"]
        )

        assert [e.event_id for e in events] == [20, 11, 10], "merged newest first"

    def test_event_listed_under_two_types_is_returned_once(self):
        payload = {"code": 200, "eventCount": 1, "event": [_event(5, "20261010")]}
        session = _FakeSession({"/event_search": [_FakeResponse(200, payload)]})

        events = PokemonJPAPIClient(session=session).fetch_cl_events(
            "2026-08-14", "2026-12-10", event_types=["3:1", "3:2"]
        )

        assert [e.event_id for e in events] == [5]

    def test_every_type_rejected_raises(self):
        """If no type is accepted, the request shape changed; an empty list would hide that."""
        session = _FakeSession({"/event_search": [_FakeResponse(400, {"code": 400})]})

        with pytest.raises(JPAPIError, match="400"):
            PokemonJPAPIClient(session=session).fetch_cl_events(
                "2026-08-14", "2026-12-10", event_types=["3:1", "3:2"]
            )

    def test_success_path_never_sleeps(self, monkeypatch):
        slept: list[float] = []
        monkeypatch.setattr(pokemon_jp_api.time, "sleep", slept.append)
        payload = {"code": 200, "eventCount": 0, "event": []}
        session = _FakeSession({"/event_search": [_FakeResponse(200, payload)]})

        PokemonJPAPIClient(session=session).fetch_cl_events("2026-08-14", "2026-12-10")

        assert slept == []


class TestFetchEventWithMetadata:
    def test_404_means_results_not_published(self):
        session = _FakeSession({"/event_result_detail_search": [_FakeResponse(404)]})

        meta, results = PokemonJPAPIClient(session=session).fetch_event_with_metadata(1032092)

        assert meta == {} and results == []

    def test_results_are_sorted_by_rank_and_deck_ids_normalised(self):
        payload = {
            "code": 200,
            "event": {"event_title": "CL 2027 Yokohama"},
            "results": [
                {"rank": 2, "name": "B", "player_id": "2", "area": "", "deck_id": ""},
                {"rank": 1, "name": "A", "player_id": "1", "area": "", "deck_id": "abc-def"},
            ],
        }
        session = _FakeSession({"/event_result_detail_search": [_FakeResponse(200, payload)]})

        meta, results = PokemonJPAPIClient(session=session).fetch_event_with_metadata(1)

        assert meta["event_title"] == "CL 2027 Yokohama"
        assert [r.rank for r in results] == [1, 2]
        assert results[0].deck_id == "abc-def"
        assert results[1].deck_id is None
