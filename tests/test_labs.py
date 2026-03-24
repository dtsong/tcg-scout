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


# ---------------------------------------------------------------------------
# Scraper HTML parsing tests
# ---------------------------------------------------------------------------


class TestParseStandingsRow:
    """Test _parse_standings_row with realistic HTML snippets."""

    @pytest.fixture()
    def client(self):
        from scraper.labs_limitless import LabsLimitlessClient

        c = LabsLimitlessClient()
        yield c
        c.close()

    @staticmethod
    def _make_cells(html_cells: list[str]):
        from bs4 import BeautifulSoup

        html = "<table><tr>" + "".join(f"<td>{c}</td>" for c in html_cells) + "</tr></table>"
        soup = BeautifulSoup(html, "html.parser")
        return soup.find("tr").find_all("td")

    def test_basic_row(self, client):
        cells = self._make_cells(
            [
                "1.",
                '<a href="/players/1790">Alice</a>',
                '<img src="/flags/us.png" alt="US">',
                "14 - 1 - 1",
                '<img src="/pokemon/dragapult.png" alt="Dragapult"> '
                '<img src="/pokemon/pidgeot.png" alt="Pidgeot">',
            ]
        )
        result = client._parse_standings_row(cells)
        assert result is not None
        assert result.standing == 1
        assert result.player.player_id == "1790"
        assert result.player.name == "Alice"
        assert result.player.country == "US"
        assert result.record_w == 14
        assert result.record_l == 1
        assert result.record_t == 1
        assert "Dragapult" in result.archetype
        assert len(result.sprite_urls) == 2

    def test_missing_player_link(self, client):
        cells = self._make_cells(
            [
                "5.",
                "Bob Smith",
                "",
                "10 - 3 - 1",
                '<img src="/pokemon/charizard.png" alt="Charizard">',
            ]
        )
        result = client._parse_standings_row(cells)
        assert result is not None
        assert result.player.player_id == "unknown-Bob Smith"
        assert result.player.name == "Bob Smith"

    def test_missing_sprites_falls_back_to_unknown(self, client):
        cells = self._make_cells(
            [
                "20.",
                '<a href="/players/99">Charlie</a>',
                "",
                "8 - 5 - 1",
                "",
            ]
        )
        result = client._parse_standings_row(cells)
        assert result is not None
        assert result.archetype == "Unknown"

    def test_invalid_rank_returns_none(self, client):
        cells = self._make_cells(
            [
                "abc",
                '<a href="/players/1">Test</a>',
                "",
                "5 - 3 - 0",
                "",
            ]
        )
        result = client._parse_standings_row(cells)
        assert result is None


class TestExtractArchetype:
    """Test _extract_archetype with HTML snippets."""

    @staticmethod
    def _make_cell(html: str):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(f"<td>{html}</td>", "html.parser")
        return soup.find("td")

    def test_sprites_with_alt_text(self):
        from scraper.labs_limitless import LabsLimitlessClient

        cell = self._make_cell(
            '<img src="/pokemon/dragapult.png" alt="Dragapult"> '
            '<img src="/pokemon/pidgeot.png" alt="Pidgeot">'
        )
        archetype, urls = LabsLimitlessClient._extract_archetype(cell)
        assert archetype == "Dragapult Pidgeot"
        assert len(urls) == 2

    def test_sprites_without_alt_derives_from_filename(self):
        from scraper.labs_limitless import LabsLimitlessClient

        cell = self._make_cell('<img src="/pokemon/gardevoir_ex.png">')
        archetype, urls = LabsLimitlessClient._extract_archetype(cell)
        assert "Gardevoir" in archetype
        assert len(urls) == 1

    def test_link_text_fallback(self):
        from scraper.labs_limitless import LabsLimitlessClient

        cell = self._make_cell('<a href="/decks/list/123">Raging Bolt</a>')
        archetype, urls = LabsLimitlessClient._extract_archetype(cell)
        assert archetype == "Raging Bolt"
        assert urls == []

    def test_empty_cell(self):
        from scraper.labs_limitless import LabsLimitlessClient

        cell = self._make_cell("")
        archetype, urls = LabsLimitlessClient._extract_archetype(cell)
        assert archetype == ""
        assert urls == []


class TestReingestionIdempotency:
    """Verify that re-scraping the same tournament doesn't create duplicates."""

    def test_placement_unique_constraint(self, labs_db):
        # Re-insert same placement — should replace, not duplicate
        labs_db.execute(
            "INSERT OR REPLACE INTO placements "
            "(tournament_id, player_id, standing, archetype, record_w, record_l, record_t) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("551", "p1", 1, "Dragapult ex", 14, 1, 1),
        )
        labs_db.commit()
        count = labs_db.execute(
            "SELECT COUNT(*) FROM placements WHERE tournament_id='551' AND player_id='p1'"
        ).fetchone()[0]
        assert count == 1

    def test_decklist_unique_constraint(self, labs_db):
        # Insert a decklist, then re-insert — should not duplicate
        labs_db.execute(
            "INSERT OR REPLACE INTO decklists (placement_id, player_id, tournament_id) "
            "VALUES (?, ?, ?)",
            (1, "p1", "551"),
        )
        labs_db.commit()
        labs_db.execute(
            "INSERT OR REPLACE INTO decklists (placement_id, player_id, tournament_id) "
            "VALUES (?, ?, ?)",
            (1, "p1", "551"),
        )
        labs_db.commit()
        count = labs_db.execute(
            "SELECT COUNT(*) FROM decklists WHERE tournament_id='551' AND player_id='p1'"
        ).fetchone()[0]
        assert count == 1
