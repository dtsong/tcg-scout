"""Tests for backfill-archetypes CLI command.

Backfill should key on (date, player_name) rather than (date, standing) so it
doesn't collapse when multiple tournaments share a prefecture/day. Player
names are nearly unique per date; standings repeat.
"""

from datetime import date
from unittest.mock import patch

from click.testing import CliRunner

from cli import cli
from scraper.limitless import LimitlessPlacement, LimitlessTournament


def _stub_limitless(tournaments_with_placements):
    """Return a LimitlessClient stub that yields the given canned data."""

    class _Stub:
        def __init__(self):
            self._map = {t.source_url: p for t, p in tournaments_with_placements}

        def fetch_jp_city_league_listings(self, _start, _end):
            return [t for t, _ in tournaments_with_placements]

        def fetch_jp_city_league_placements(self, url, _max=32):
            return self._map.get(url, [])

    return _Stub


def _make_db(tmp_path, rows):
    """Create a ninja-spinner DB with the given JP Unknown placements."""
    import sqlite3

    from db import SCHEMA

    db_path = tmp_path / "ninja-spinner.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    for tid, name, d in {(r["tid"], r["tname"], r["date"]) for r in rows}:
        conn.execute(
            "INSERT INTO tournaments (id, name, date, country, division) "
            "VALUES (?, ?, ?, 'JP', 'open')",
            (tid, name, d),
        )
    for r in rows:
        conn.execute(
            "INSERT INTO placements (tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, 'Unknown')",
            (r["tid"], r["standing"], r["player_name"]),
        )
    conn.commit()
    conn.close()
    return db_path


def _run_backfill(db_path, stub_cls):
    with (
        patch("scraper.limitless.LimitlessClient", stub_cls),
        patch("cli.get_format_connection") as mock_conn,
    ):
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        mock_conn.return_value = conn
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--format", "ninja-spinner", "backfill-archetypes"], catch_exceptions=False
        )
        conn.close()
    return result


def _read_archetypes(db_path):
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT tournament_id, standing, player_name, archetype FROM placements ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


class TestBackfillArchetypes:
    def test_matches_by_player_name_across_distinct_tournaments(self, tmp_path):
        """JP placements get Limitless archetypes via (date, player_name) key
        even when multiple tournaments share the same prefecture/day/standing."""
        # Two JP tournaments on same day, same standing-1 placement, different players.
        # Keying on (date, standing) alone would be ambiguous.
        jp_rows = [
            {
                "tid": "jp-1",
                "tname": "愛知県 Store A",
                "date": "2026-04-12",
                "standing": 1,
                "player_name": "alice",
            },
            {
                "tid": "jp-2",
                "tname": "愛知県 Store B",
                "date": "2026-04-12",
                "standing": 1,
                "player_name": "bob",
            },
        ]
        db_path = _make_db(tmp_path, jp_rows)

        # Limitless shows the same two players at standing 1 in distinct tournaments.
        lim_data = [
            (
                LimitlessTournament(
                    name="City League Aichi",
                    tournament_date=date(2026, 4, 12),
                    source_url="https://limitlesstcg.com/tournaments/jp/1",
                ),
                [LimitlessPlacement(placement=1, player_name="alice", archetype="Dragapult ex")],
            ),
            (
                LimitlessTournament(
                    name="City League Aichi",
                    tournament_date=date(2026, 4, 12),
                    source_url="https://limitlesstcg.com/tournaments/jp/2",
                ),
                [LimitlessPlacement(placement=1, player_name="bob", archetype="Charizard ex")],
            ),
        ]

        result = _run_backfill(db_path, _stub_limitless(lim_data))
        assert result.exit_code == 0, result.output

        rows = _read_archetypes(db_path)
        archetypes = {r["player_name"]: r["archetype"] for r in rows}
        assert archetypes == {"alice": "Dragapult ex", "bob": "Charizard ex"}

    def test_ambiguous_same_key_different_archetypes_is_skipped(self, tmp_path):
        """If the same (date, player_name) maps to conflicting archetypes in
        Limitless data, leave the placement as Unknown."""
        jp_rows = [
            {
                "tid": "jp-1",
                "tname": "東京都 Store A",
                "date": "2026-04-12",
                "standing": 1,
                "player_name": "aki",
            },
        ]
        db_path = _make_db(tmp_path, jp_rows)

        lim_data = [
            (
                LimitlessTournament(
                    name="City League Tōkyō",
                    tournament_date=date(2026, 4, 12),
                    source_url="https://limitlesstcg.com/tournaments/jp/10",
                ),
                [LimitlessPlacement(placement=1, player_name="aki", archetype="Dragapult ex")],
            ),
            (
                LimitlessTournament(
                    name="City League Tōkyō",
                    tournament_date=date(2026, 4, 12),
                    source_url="https://limitlesstcg.com/tournaments/jp/11",
                ),
                [LimitlessPlacement(placement=5, player_name="aki", archetype="Charizard ex")],
            ),
        ]

        result = _run_backfill(db_path, _stub_limitless(lim_data))
        assert result.exit_code == 0, result.output

        rows = _read_archetypes(db_path)
        assert rows[0]["archetype"] == "Unknown"

    def test_same_key_same_archetype_is_not_ambiguous(self, tmp_path):
        """Seeing the same (date, player_name, archetype) twice (e.g. from
        overlapping listings) is not ambiguous; the placement still updates."""
        jp_rows = [
            {
                "tid": "jp-1",
                "tname": "大阪府 Store A",
                "date": "2026-04-12",
                "standing": 3,
                "player_name": "yuki",
            },
        ]
        db_path = _make_db(tmp_path, jp_rows)

        lim_data = [
            (
                LimitlessTournament(
                    name="City League Ōsaka",
                    tournament_date=date(2026, 4, 12),
                    source_url="https://limitlesstcg.com/tournaments/jp/20",
                ),
                [LimitlessPlacement(placement=3, player_name="yuki", archetype="Gardevoir ex")],
            ),
            (
                LimitlessTournament(
                    name="City League Ōsaka",
                    tournament_date=date(2026, 4, 12),
                    source_url="https://limitlesstcg.com/tournaments/jp/21",
                ),
                [LimitlessPlacement(placement=3, player_name="yuki", archetype="Gardevoir ex")],
            ),
        ]

        result = _run_backfill(db_path, _stub_limitless(lim_data))
        assert result.exit_code == 0, result.output

        rows = _read_archetypes(db_path)
        assert rows[0]["archetype"] == "Gardevoir ex"

    def test_placements_without_player_name_are_ignored(self, tmp_path):
        """A JP placement with no player_name cannot be backfilled via this path."""
        jp_rows = [
            {
                "tid": "jp-1",
                "tname": "東京都 Store A",
                "date": "2026-04-12",
                "standing": 1,
                "player_name": None,
            },
        ]
        db_path = _make_db(tmp_path, jp_rows)

        lim_data = [
            (
                LimitlessTournament(
                    name="City League Tōkyō",
                    tournament_date=date(2026, 4, 12),
                    source_url="https://limitlesstcg.com/tournaments/jp/30",
                ),
                [LimitlessPlacement(placement=1, player_name=None, archetype="Dragapult ex")],
            ),
        ]

        result = _run_backfill(db_path, _stub_limitless(lim_data))
        assert result.exit_code == 0, result.output

        rows = _read_archetypes(db_path)
        assert rows[0]["archetype"] == "Unknown"
