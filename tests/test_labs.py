"""Tests for Labs database, matchup analysis, and CLI commands."""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from labs_db import LABS_SCHEMA, init_labs_db, make_match_id

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def labs_db() -> sqlite3.Connection:
    """In-memory Labs database with seed data for matchup testing.

    Seed data:
    - 2 tournaments (Houston Regional, Toronto Regional)
    - 6 players
    - 8 placements across 3 archetypes with W-L-T records
    - 4 matches (for H2H testing)
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(LABS_SCHEMA)

    # Tournaments
    conn.executemany(
        "INSERT INTO tournaments (id, name, date, player_count, country, source) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("551", "Regional Houston, TX", "2026-03-21", 2635, "US", "limitless-labs"),
            ("552", "Regional Toronto", "2026-03-14", 1200, "CA", "limitless-labs"),
        ],
    )

    # Players
    conn.executemany(
        "INSERT INTO players (id, name, country) VALUES (?, ?, ?)",
        [
            ("p1", "Alice", "US"),
            ("p2", "Bob", "US"),
            ("p3", "Charlie", "CA"),
            ("p4", "Diana", "JP"),
            ("p5", "Eve", "US"),
            ("p6", "Frank", "MX"),
        ],
    )

    # Placements with W-L-T records
    conn.executemany(
        "INSERT INTO placements (id, tournament_id, player_id, standing, archetype, "
        "record_w, record_l, record_t) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            # Houston
            (1, "551", "p1", 1, "Dragapult ex", 14, 1, 1),
            (2, "551", "p2", 5, "Charizard ex", 11, 3, 2),
            (3, "551", "p3", 20, "Gardevoir ex", 9, 5, 2),
            (4, "551", "p4", 50, "Dragapult ex", 8, 6, 2),
            # Toronto
            (5, "552", "p5", 1, "Charizard ex", 12, 1, 1),
            (6, "552", "p6", 3, "Dragapult ex", 10, 3, 1),
            (7, "552", "p3", 10, "Gardevoir ex", 8, 4, 2),
            (8, "552", "p1", 15, "Dragapult ex", 7, 5, 2),
        ],
    )

    # Matches (H2H round-by-round data)
    conn.executemany(
        "INSERT INTO matches (id, tournament_id, round, player1_id, player2_id, "
        "winner_id, player1_archetype, player2_archetype) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("551:r1:p1:p3", "551", 1, "p1", "p3", "p1", "Dragapult ex", "Gardevoir ex"),
            ("551:r2:p2:p4", "551", 2, "p2", "p4", "p2", "Charizard ex", "Dragapult ex"),
            ("551:r3:p1:p2", "551", 3, "p1", "p2", "p1", "Dragapult ex", "Charizard ex"),
            ("552:r1:p5:p6", "552", 1, "p5", "p6", "p5", "Charizard ex", "Dragapult ex"),
        ],
    )

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture()
def labs_db_empty() -> sqlite3.Connection:
    """Empty Labs database with schema only."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(LABS_SCHEMA)
    conn.commit()
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestLabsSchema:
    def test_init_creates_tables(self, labs_db_empty):
        tables = {
            row[0]
            for row in labs_db_empty.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        expected = {
            "tournaments",
            "players",
            "matches",
            "placements",
            "decklists",
            "decklist_cards",
            "archetype_mapping",
        }
        assert expected.issubset(tables)

    def test_init_idempotent(self, labs_db_empty):
        # Running init twice should not raise
        init_labs_db(labs_db_empty)
        init_labs_db(labs_db_empty)

    def test_make_match_id_deterministic(self):
        # Same match should get same ID regardless of player order
        id1 = make_match_id("t1", 1, "alice", "bob")
        id2 = make_match_id("t1", 1, "bob", "alice")
        assert id1 == id2

    def test_make_match_id_unique(self):
        id1 = make_match_id("t1", 1, "alice", "bob")
        id2 = make_match_id("t1", 2, "alice", "bob")
        assert id1 != id2


# ---------------------------------------------------------------------------
# Matchup analysis tests
# ---------------------------------------------------------------------------


class TestLabsArchetypeWinrates:
    def test_computes_winrates(self, labs_db):
        from analysis.matchup import compute_labs_archetype_winrates

        result = compute_labs_archetype_winrates(labs_db, top_n=10, min_players=1)
        assert result["source"] == "labs-h2h"
        assert result["tournament_count"] == 2
        assert len(result["archetypes"]) > 0

        # Find Dragapult (3 players: p1, p4, p6 + p1 again)
        dragapult = next(
            (a for a in result["archetypes"] if a["archetype"] == "Dragapult ex"),
            None,
        )
        assert dragapult is not None
        assert dragapult["players"] == 4  # p1 Houston, p4 Houston, p6 Toronto, p1 Toronto
        assert dragapult["total_wins"] > 0
        assert 0.0 < dragapult["win_rate"] < 1.0
        assert dragapult["ci_lower"] <= dragapult["win_rate"]
        assert dragapult["ci_upper"] >= dragapult["win_rate"]

    def test_empty_db_returns_empty(self, labs_db_empty):
        from analysis.matchup import compute_labs_archetype_winrates

        result = compute_labs_archetype_winrates(labs_db_empty)
        assert result["archetypes"] == []
        assert result["tournament_count"] == 0

    def test_min_players_filter(self, labs_db):
        from analysis.matchup import compute_labs_archetype_winrates

        result = compute_labs_archetype_winrates(labs_db, top_n=10, min_players=3)
        # Only Dragapult (4 players) should pass with min_players=3
        archetypes = [a["archetype"] for a in result["archetypes"]]
        assert "Dragapult ex" in archetypes


class TestLabsMatchupMatrix:
    def test_h2h_from_matches(self, labs_db):
        from analysis.matchup import compute_labs_matchup_matrix

        # Use min_matches=1 since we only have 4 test matches
        result = compute_labs_matchup_matrix(labs_db, top_n=5, min_matches=1)
        assert result["source"] == "labs-h2h"
        assert len(result["archetypes"]) > 0
        assert len(result["matrix"]) == len(result["archetypes"])
        assert len(result["confidence"]) == len(result["archetypes"])

    def test_matrix_diagonal_is_half(self, labs_db):
        from analysis.matchup import compute_labs_matchup_matrix

        result = compute_labs_matchup_matrix(labs_db, top_n=5, min_matches=1)
        n = len(result["archetypes"])
        for i in range(n):
            assert result["matrix"][i][i] == 0.5

    def test_falls_back_to_records(self, labs_db):
        """When matches table is empty, falls back to record-based analysis."""
        from analysis.matchup import compute_labs_matchup_matrix

        # Delete all matches
        labs_db.execute("DELETE FROM matches")
        labs_db.commit()

        result = compute_labs_matchup_matrix(labs_db, top_n=5, min_matches=1)
        assert result["source"] == "labs-records"

    def test_empty_db(self, labs_db_empty):
        from analysis.matchup import compute_labs_matchup_matrix

        result = compute_labs_matchup_matrix(labs_db_empty)
        assert result["archetypes"] == []
        assert result["matrix"] == []


class TestWilsonCI:
    def test_zero_total(self):
        from analysis.matchup import _wilson_ci

        lo, hi = _wilson_ci(0, 0)
        assert lo == 0.0
        assert hi == 0.0

    def test_perfect_record(self):
        from analysis.matchup import _wilson_ci

        lo, hi = _wilson_ci(10, 10)
        assert lo > 0.5
        assert hi <= 1.0

    def test_fifty_fifty(self):
        from analysis.matchup import _wilson_ci

        lo, hi = _wilson_ci(50, 100)
        assert lo < 0.5
        assert hi > 0.5

    def test_bounds_valid(self):
        from analysis.matchup import _wilson_ci

        lo, hi = _wilson_ci(7, 20)
        assert 0.0 <= lo <= hi <= 1.0


# ---------------------------------------------------------------------------
# CLI registration tests
# ---------------------------------------------------------------------------


class TestCLICommands:
    def test_scrape_labs_registered(self):
        from cli import cli

        commands = list(cli.commands.keys())
        assert "scrape-labs" in commands

    def test_labs_matchups_registered(self):
        from cli import cli

        commands = list(cli.commands.keys())
        assert "labs-matchups" in commands
