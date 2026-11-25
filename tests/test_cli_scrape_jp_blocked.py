"""`scout scrape-jp` when Cloudflare blocks players.pokemon-card.com.

The block is decided per runner IP: on roughly 4 of every 10 scheduled runs in
October-November 2026 the very first request was challenged and stayed
challenged through every retry. `scrape-jp` runs under `set -e` between the
Limitless scrape and the export, so failing there discarded that run's Limitless
results too and nothing was published. A blocked run is now skipped (the next
unblocked run stores whatever is still missing) unless official results have
fallen more than ``JP_API_BLOCK_TOLERANCE_DAYS`` behind Limitless, and any other
API failure still fails the command.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cli import cli
from config import JP_API_BLOCK_TOLERANCE_DAYS
from db import init_db
from scraper.pokemon_jp_api import (
    JPAPIBlockedError,
    JPAPIError,
    JPCityLeagueEvent,
    JPCityLeagueResult,
)

BLOCKED = JPAPIBlockedError("JP API /event_search returned HTTP 403 after 3 retries")


class _ScriptedClient:
    """Stands in for PokemonJPAPIClient: a listing plus per-event results or errors."""

    def __init__(self, listing, results=None):
        self._listing = listing
        self._results = results or {}
        self.results_requested: list[int] = []

    def fetch_cl_events(self, start: str, end: str):
        if isinstance(self._listing, Exception):
            raise self._listing
        return self._listing

    def fetch_event_results(self, event_id: int):
        self.results_requested.append(event_id)
        outcome = self._results[event_id]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def close(self) -> None:
        pass


def _event(event_id: int, date: str) -> JPCityLeagueEvent:
    return JPCityLeagueEvent(
        event_id=event_id,
        date=date,
        prefecture="東京都",
        store_name=f"Shop {event_id}",
        capacity=64,
        division="open",
        event_title="シティリーグ2027 シーズン1 オープンリーグ",
    )


def _results() -> list[JPCityLeagueResult]:
    return [JPCityLeagueResult(rank=1, player_name="A", player_id="1", area="東京", deck_id=None)]


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "format.db"
    conn = sqlite3.connect(path)
    init_db(conn)
    conn.close()
    return path


def _add_tournament(db_path: Path, tournament_id: str, date: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO tournaments (id, name, date, country, division, tournament_type) "
        "VALUES (?, 'City League', ?, 'JP', 'open', 'city-league')",
        (tournament_id, date),
    )
    conn.commit()
    conn.close()


def _stored_official_ids(db_path: Path) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {r[0] for r in conn.execute("SELECT id FROM tournaments WHERE id LIKE 'jp-%'")}
    finally:
        conn.close()


def _scrape_jp(db_path: Path, client: _ScriptedClient):
    def connect(_slug: str) -> sqlite3.Connection:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    with (
        patch("cli.get_format_connection", side_effect=connect),
        patch("scraper.pokemon_jp_api.PokemonJPAPIClient", return_value=client),
    ):
        return CliRunner().invoke(
            cli, ["--format", "storm-emeralda", "scrape-jp", "--no-decklists"]
        )


def test_blocked_listing_is_skipped_so_the_pipeline_can_publish(db_path):
    _add_tournament(db_path, "jp-1", "2026-10-13")
    _add_tournament(db_path, "https://limitlesstcg.com/tournaments/jp/5073", "2026-10-14")

    result = _scrape_jp(db_path, _ScriptedClient(listing=BLOCKED))

    assert result.exit_code == 0, result.output
    assert "WARNING: JP API blocked" in result.output
    assert _stored_official_ids(db_path) == {"jp-1"}


def test_block_fails_once_official_results_are_overdue(db_path):
    """A block that never lifts must not hide behind fresh Limitless data forever."""
    _add_tournament(db_path, "jp-1", "2026-10-13")
    _add_tournament(db_path, "https://limitlesstcg.com/tournaments/jp/5200", "2026-11-15")

    result = _scrape_jp(db_path, _ScriptedClient(listing=BLOCKED))

    assert result.exit_code == 1, result.output
    assert "official results are 33 days behind Limitless" in result.output


def test_lag_is_measured_from_the_window_start_before_any_official_event(db_path):
    """A new format has no jp- rows yet; a block from day one still has to surface."""
    within, beyond = JP_API_BLOCK_TOLERANCE_DAYS, JP_API_BLOCK_TOLERANCE_DAYS + 1
    # storm-emeralda's window opens 2026-08-14.
    _add_tournament(db_path, "https://limitlesstcg.com/tournaments/jp/1", f"2026-08-{14 + within}")
    assert _scrape_jp(db_path, _ScriptedClient(listing=BLOCKED)).exit_code == 0

    _add_tournament(db_path, "https://limitlesstcg.com/tournaments/jp/2", f"2026-08-{14 + beyond}")
    assert _scrape_jp(db_path, _ScriptedClient(listing=BLOCKED)).exit_code == 1


def test_block_partway_through_keeps_fetched_events_and_stops_retrying(db_path):
    """Hundreds of events can be pending; each one would otherwise burn the full backoff."""
    listing = [_event(3, "2026-11-15"), _event(2, "2026-11-14"), _event(1, "2026-11-13")]
    client = _ScriptedClient(listing, {3: _results(), 2: BLOCKED, 1: _results()})

    result = _scrape_jp(db_path, client)

    assert result.exit_code == 0, result.output
    assert "WARNING: JP API blocked" in result.output
    assert client.results_requested == [3, 2], "no further requests once blocked"
    assert _stored_official_ids(db_path) == {"jp-3"}, "events 2 and 1 stay pending for the next run"


def test_rejected_query_still_fails_the_command(db_path):
    """Only a Cloudflare block is skippable: a 400 is a bug that needs a code change."""
    client = _ScriptedClient(listing=JPAPIError("JP API /event_search returned HTTP 400"))

    result = _scrape_jp(db_path, client)

    assert result.exit_code != 0
    assert isinstance(result.exception, JPAPIError)
    assert not isinstance(result.exception, JPAPIBlockedError)
