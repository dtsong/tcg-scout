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
        self.calls.append(url)
        path = urlparse(url).path
        queue = self.scripts[path]
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

    def test_requests_are_absolute_and_carry_repeated_event_type_params(self):
        session = _FakeSession({"/event_search": [_FakeResponse(200, {"code": 200, "event": []})]})
        PokemonJPAPIClient(session=session).fetch_cl_events("2026-08-14", "2026-12-10")

        assert session.calls[0].startswith(f"{BASE_URL}/event_search?")
        query = parse_qs(urlparse(session.calls[0]).query)
        assert query["result_resist"] == ["1"]
        assert len(query["event_type[]"]) >= 8, "every City League season code must be sent"

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

        events = PokemonJPAPIClient(session=session).fetch_cl_events("2026-08-14", "2026-12-10")

        assert [e.event_id for e in events] == [2, 1]
        assert len(session.calls) == 2, "stops paging once an event predates the window"
        offsets = [parse_qs(urlparse(u).query)["offset"] for u in session.calls]
        assert offsets == [["0"], ["20"]]

    def test_retries_once_on_403_then_succeeds(self, monkeypatch):
        monkeypatch.setattr(pokemon_jp_api.time, "sleep", lambda _s: None)
        payload = {"code": 200, "eventCount": 1, "event": [_event(9, "20260920")]}
        session = _FakeSession({"/event_search": [_FakeResponse(403), _FakeResponse(200, payload)]})

        events = PokemonJPAPIClient(session=session).fetch_cl_events("2026-08-14", "2026-12-10")

        assert [e.event_id for e in events] == [9]
        assert len(session.calls) == 2

    def test_persistent_403_raises_instead_of_silently_returning_nothing(self, monkeypatch):
        """A silent empty result would look like a quiet season and mask the block."""
        monkeypatch.setattr(pokemon_jp_api.time, "sleep", lambda _s: None)
        session = _FakeSession({"/event_search": [_FakeResponse(403)]})

        with pytest.raises(JPAPIError, match="403"):
            PokemonJPAPIClient(session=session).fetch_cl_events("2026-08-14", "2026-12-10")


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
