"""Tests for Labs database, matchup analysis, and CLI commands."""

import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from labs_db import LABS_SCHEMA, init_labs_db, make_match_id

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

        # Find Dragapult (4 placements: p1 Houston, p4 Houston, p6 Toronto, p1 Toronto)
        dragapult = next(
            (a for a in result["archetypes"] if a["archetype"] == "Dragapult ex"),
            None,
        )
        assert dragapult is not None
        assert dragapult["players"] == 4
        # Total: 14+8+10+7=39 wins, 1+6+3+5=15 losses, 1+2+1+2=6 ties, 60 total
        assert dragapult["total_wins"] == 39
        assert dragapult["total_losses"] == 15
        assert dragapult["total_ties"] == 6
        assert dragapult["total_matches"] == 60
        expected_wr = round(39 / 60, 4)
        assert dragapult["win_rate"] == expected_wr
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

    def test_specific_win_rate_values(self, labs_db):
        """Verify actual win rate computation from seed data matches."""
        from analysis.matchup import compute_labs_matchup_matrix

        result = compute_labs_matchup_matrix(labs_db, top_n=5, min_matches=1)
        archetypes = result["archetypes"]
        matrix = result["matrix"]

        drag_idx = archetypes.index("Dragapult ex")
        char_idx = archetypes.index("Charizard ex")

        # Matches: Charizard beats Dragapult in 551:r2 and 552:r1 (2 wins)
        # Dragapult beats Charizard in 551:r3 (1 win), total 3 matches
        # Dragapult vs Charizard win rate = 1/3
        assert result["sample_sizes"][drag_idx][char_idx] == 3
        assert matrix[drag_idx][char_idx] == round(1 / 3, 4)
        # Charizard vs Dragapult win rate = 2/3
        assert matrix[char_idx][drag_idx] == round(2 / 3, 4)

    def test_mirror_matches_excluded(self, labs_db):
        """Mirror matches should not appear in totals."""
        from analysis.matchup import compute_labs_matchup_matrix

        # Add a Dragapult mirror match
        labs_db.execute(
            "INSERT INTO matches (id, tournament_id, round, player1_id, player2_id, "
            "winner_id, player1_archetype, player2_archetype) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("551:r4:p1:p4", "551", 4, "p1", "p4", "p1", "Dragapult ex", "Dragapult ex"),
        )
        labs_db.commit()

        result = compute_labs_matchup_matrix(labs_db, top_n=5, min_matches=1)
        drag_idx = result["archetypes"].index("Dragapult ex")
        # Mirror match should not be counted
        assert result["sample_sizes"][drag_idx][drag_idx] == 0

    def test_falls_back_to_records(self, labs_db):
        """When matches table is empty, falls back to record-based analysis."""
        from analysis.matchup import compute_labs_matchup_matrix

        # Delete all matches
        labs_db.execute("DELETE FROM matches")
        labs_db.commit()

        result = compute_labs_matchup_matrix(labs_db, top_n=5, min_matches=1, min_encounters=1)
        assert result["source"] == "labs-records"
        # Verify matrix values are populated (not just structure)
        if result["archetypes"]:
            n = len(result["archetypes"])
            has_nonzero = any(
                result["matrix"][i][j] != 0.0 for i in range(n) for j in range(n) if i != j
            )
            assert has_nonzero, "Records-based matrix should have non-zero entries"

    def test_record_fallback_weighted_values(self, labs_db):
        """Verify record-based fallback produces correct weighted win rates."""
        from analysis.matchup import compute_labs_matchup_matrix

        # Delete matches to force fallback
        labs_db.execute("DELETE FROM matches")
        labs_db.commit()

        result = compute_labs_matchup_matrix(labs_db, top_n=5, min_matches=1, min_encounters=1)
        assert result["source"] == "labs-records"
        archetypes = result["archetypes"]
        matrix = result["matrix"]

        drag_idx = archetypes.index("Dragapult ex")
        char_idx = archetypes.index("Charizard ex")

        # Dragapult in Houston: p1 (14-1-1, wr=14/16), p4 (8-6-2, wr=8/16) -> avg=0.6875
        # Dragapult in Toronto: p6 (10-3-1, wr=10/14), p1 (7-5-2, wr=7/14) -> avg=0.607142...
        # Charizard in Houston: p2 (11-3-2, wr=11/16) -> avg=0.6875
        # Charizard in Toronto: p5 (12-1-1, wr=12/14) -> avg=0.857142...
        #
        # Houston: weight = min(2 Dragapult, 1 Charizard) = 1
        #   Dragapult contribution: 0.6875 * 1
        #   Charizard contribution: 0.6875 * 1
        # Toronto: weight = min(2 Dragapult, 1 Charizard) = 1
        #   Dragapult contribution: 0.607142... * 1
        #   Charizard contribution: 0.857142... * 1
        # Dragapult vs Charizard: (0.6875 + 0.607142...) / 2 = 0.6473...
        # Charizard vs Dragapult: (0.6875 + 0.857142...) / 2 = 0.7723...

        drag_vs_char = matrix[drag_idx][char_idx]
        char_vs_drag = matrix[char_idx][drag_idx]

        assert drag_vs_char == round((14 / 16 + 8 / 16) / 2 / 2 + (10 / 14 + 7 / 14) / 2 / 2, 4)
        # More directly: verify Charizard outperforms Dragapult (higher avg win rate)
        assert char_vs_drag > drag_vs_char, (
            "Charizard should have higher proxy win rate than Dragapult"
        )
        # Verify sample sizes match expected weights
        assert result["sample_sizes"][drag_idx][char_idx] == 2  # min(2,1) + min(2,1)

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


class TestUnknownArchetypeFiltering:
    """Verify that Unknown and NULL archetypes are excluded from analysis."""

    def test_unknown_excluded_from_winrates(self, labs_db):
        from analysis.matchup import compute_labs_archetype_winrates

        # Add placements with Unknown and NULL archetypes
        labs_db.execute(
            "INSERT INTO placements (tournament_id, player_id, standing, archetype, "
            "record_w, record_l, record_t) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("551", "p5", 100, "Unknown", 5, 5, 0),
        )
        labs_db.execute(
            "INSERT INTO placements (tournament_id, player_id, standing, archetype, "
            "record_w, record_l, record_t) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("551", "p6", 101, None, 5, 5, 0),
        )
        labs_db.commit()

        result = compute_labs_archetype_winrates(labs_db, top_n=20, min_players=1)
        archetype_names = [a["archetype"] for a in result["archetypes"]]
        assert "Unknown" not in archetype_names
        assert None not in archetype_names


class TestIngestTournament:
    """Test the ingest_tournament write path."""

    def test_successful_ingestion(self, labs_db):
        """Verify ingest stores tournaments, players, placements correctly."""
        from unittest.mock import patch

        from scraper.labs_limitless import (
            LabsLimitlessClient,
            LabsPlacement,
            LabsPlayer,
            LabsTournament,
        )

        client = LabsLimitlessClient()

        mock_tournament = LabsTournament(
            tournament_id="999",
            name="Test Regional",
            date="2026-03-20",
            player_count=100,
            country="US",
        )
        mock_standings = [
            LabsPlacement(
                standing=1,
                player=LabsPlayer(player_id="test-p1", name="TestPlayer", country="US"),
                archetype="Charizard ex",
                record_w=10,
                record_l=2,
                record_t=1,
            ),
        ]

        with (
            patch.object(client, "fetch_tournament_metadata", return_value=mock_tournament),
            patch.object(client, "fetch_standings", return_value=mock_standings),
        ):
            result = client.ingest_tournament(
                labs_db, tournament_id="999", labs_tournament_id="test", fetch_decklists=False
            )

        assert result["players"] == 1
        assert result["placements"] == 1
        assert result["decklists"] == 0

        # Verify data was written
        t = labs_db.execute("SELECT * FROM tournaments WHERE id='999'").fetchone()
        assert t["name"] == "Test Regional"

        p = labs_db.execute("SELECT * FROM placements WHERE tournament_id='999'").fetchone()
        assert p["archetype"] == "Charizard ex"
        assert p["record_w"] == 10

        client.close()

    def test_rollback_on_failure(self, labs_db):
        """Verify transaction rollback when Phase 2 DB write fails."""
        from unittest.mock import patch

        from scraper.labs_limitless import (
            LabsLimitlessClient,
            LabsPlacement,
            LabsPlayer,
            LabsTournament,
        )

        client = LabsLimitlessClient()

        mock_tournament = LabsTournament(
            tournament_id="998",
            name="Fail Regional",
            date="2026-03-20",
            player_count=50,
        )
        mock_standings = [
            LabsPlacement(
                standing=1,
                player=LabsPlayer(player_id="fail-p1", name="FailPlayer"),
                archetype="Dragapult ex",
                record_w=5,
                record_l=3,
                record_t=0,
            ),
        ]

        # Wrap connection to intercept placement INSERT and raise during Phase 2
        class FailingConnection:
            """Proxy that raises on placement INSERT to test rollback."""

            def __init__(self, real_conn):
                self._conn = real_conn

            def execute(self, sql, *args, **kwargs):
                if "INSERT INTO placements" in sql:
                    raise RuntimeError("Simulated DB failure during Phase 2 write")
                return self._conn.execute(sql, *args, **kwargs)

            def __getattr__(self, name):
                return getattr(self._conn, name)

        failing_conn = FailingConnection(labs_db)

        with (
            patch.object(client, "fetch_tournament_metadata", return_value=mock_tournament),
            patch.object(client, "fetch_standings", return_value=mock_standings),
        ):
            with pytest.raises(RuntimeError, match="Simulated DB failure"):
                client.ingest_tournament(
                    failing_conn,
                    tournament_id="998",
                    labs_tournament_id="test",
                    fetch_decklists=False,
                )

        # Tournament INSERT happened before the placement INSERT that failed,
        # but rollback should have undone it
        t = labs_db.execute("SELECT * FROM tournaments WHERE id='998'").fetchone()
        assert t is None, "Transaction rollback should have removed the tournament row"

        client.close()

    def test_decklist_ingestion(self, labs_db):
        """Verify decklist write path stores decklists and cards correctly."""
        from unittest.mock import patch

        from scraper.labs_limitless import (
            LabsDecklist,
            LabsLimitlessClient,
            LabsPlacement,
            LabsPlayer,
            LabsTournament,
        )

        client = LabsLimitlessClient()

        mock_tournament = LabsTournament(
            tournament_id="997",
            name="Decklist Regional",
            date="2026-03-20",
            player_count=50,
            country="US",
        )
        mock_standings = [
            LabsPlacement(
                standing=1,
                player=LabsPlayer(player_id="deck-p1", name="DeckPlayer", country="US"),
                archetype="Charizard ex",
                record_w=12,
                record_l=1,
                record_t=0,
                decklist_url="http://example.com/decks/list/42",
            ),
        ]
        mock_decklist = LabsDecklist(
            cards=[
                {
                    "count": 3,
                    "name": "Charizard ex",
                    "card_id": "OBF-006",
                    "set_code": "OBF",
                    "card_number": "006",
                },
                {
                    "count": 4,
                    "name": "Rare Candy",
                    "card_id": "SVI-191",
                    "set_code": "SVI",
                    "card_number": "191",
                },
            ],
            source_url="http://example.com/decks/list/42",
        )

        with (
            patch.object(client, "fetch_tournament_metadata", return_value=mock_tournament),
            patch.object(client, "fetch_standings", return_value=mock_standings),
            patch.object(client, "fetch_decklist", return_value=mock_decklist),
        ):
            result = client.ingest_tournament(
                labs_db, tournament_id="997", labs_tournament_id="test", fetch_decklists=True
            )

        assert result["decklists"] == 1
        assert result["decklist_failures"] == 0

        # Verify decklist row
        dl = labs_db.execute(
            "SELECT * FROM decklists WHERE tournament_id='997' AND player_id='deck-p1'"
        ).fetchone()
        assert dl is not None

        # Verify cards
        cards = labs_db.execute(
            "SELECT * FROM decklist_cards WHERE decklist_id=? ORDER BY card_name",
            (dl["id"],),
        ).fetchall()
        assert len(cards) == 2
        assert cards[0]["card_name"] == "Charizard ex"
        assert cards[0]["count"] == 3
        assert cards[1]["card_name"] == "Rare Candy"
        assert cards[1]["count"] == 4

        client.close()


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


# ---------------------------------------------------------------------------
# HTTP retry/backoff tests (#1)
# ---------------------------------------------------------------------------


class TestGetRetryBackoff:
    """Test _get() retry logic with mocked HTTP responses."""

    @pytest.fixture()
    def client(self):
        from scraper.labs_limitless import LabsLimitlessClient

        c = LabsLimitlessClient()
        yield c
        c.close()

    def _mock_response(self, status_code, url="http://test"):
        resp = MagicMock()
        resp.status_code = status_code
        resp.text = ""
        resp.request = MagicMock()
        resp.request.url = url
        resp.raise_for_status = MagicMock()
        if status_code >= 400:
            import httpx

            resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                f"Status {status_code}", request=resp.request, response=resp
            )
        return resp

    def test_retry_on_429_then_success(self, client):
        """429 should trigger retry; success on second attempt."""
        ok_resp = self._mock_response(200)
        client._client.get = MagicMock(side_effect=[self._mock_response(429), ok_resp])
        with patch.object(client, "_rate_limit"), patch("scraper.http_client.time.sleep"):
            result = client._get("http://test")
        assert result.status_code == 200
        assert client._client.get.call_count == 2

    def test_retry_on_500_then_success(self, client):
        """5xx should trigger retry; success on second attempt."""
        ok_resp = self._mock_response(200)
        client._client.get = MagicMock(side_effect=[self._mock_response(500), ok_resp])
        with patch.object(client, "_rate_limit"), patch("scraper.http_client.time.sleep"):
            result = client._get("http://test")
        assert result.status_code == 200

    def test_404_raises_immediately(self, client):
        """404 should raise HTTPStatusError without retry."""
        import httpx

        client._client.get = MagicMock(return_value=self._mock_response(404))
        with patch.object(client, "_rate_limit"), patch("scraper.http_client.time.sleep"):
            with pytest.raises(httpx.HTTPStatusError):
                client._get("http://test")
        assert client._client.get.call_count == 1

    def test_exhaustion_raises_after_all_retries(self, client):
        """All retries returning 500 should raise."""
        import httpx

        client._client.get = MagicMock(side_effect=[self._mock_response(500)] * client._max_retries)
        with patch.object(client, "_rate_limit"), patch("scraper.http_client.time.sleep"):
            with pytest.raises(httpx.HTTPError, match="Failed after"):
                client._get("http://test")

    def test_network_error_retries(self, client):
        """Network errors (ConnectError) should retry."""
        import httpx

        ok_resp = self._mock_response(200)
        client._client.get = MagicMock(
            side_effect=[httpx.ConnectError("Connection refused"), ok_resp]
        )
        with patch.object(client, "_rate_limit"), patch("scraper.http_client.time.sleep"):
            result = client._get("http://test")
        assert result.status_code == 200
        assert client._client.get.call_count == 2

    def test_network_error_exhaustion_raises(self, client):
        """Repeated network errors should raise after all retries."""
        import httpx

        client._client.get = MagicMock(
            side_effect=[httpx.ConnectError("Connection refused")] * client._max_retries
        )
        with patch.object(client, "_rate_limit"), patch("scraper.http_client.time.sleep"):
            with pytest.raises(httpx.HTTPError, match="Failed after"):
                client._get("http://test")


# ---------------------------------------------------------------------------
# Tournament metadata parsing tests (#2)
# ---------------------------------------------------------------------------


class TestFetchTournamentMetadata:
    """Test fetch_tournament_metadata HTML parsing."""

    @pytest.fixture()
    def client(self):
        from scraper.labs_limitless import LabsLimitlessClient

        c = LabsLimitlessClient()
        yield c
        c.close()

    def _mock_soup(self, client, html):
        from bs4 import BeautifulSoup

        with patch.object(client, "_soup", return_value=BeautifulSoup(html, "html.parser")):
            return client.fetch_tournament_metadata("551")

    def test_valid_page(self, client):
        html = """
        <html><body>
            <h1>Regional Houston, TX | Pokémon</h1>
            <span>21 Mar 26</span>
            <span>2635 Players</span>
            <img src="/flags/us.png" alt="US">
        </body></html>
        """
        result = self._mock_soup(client, html)
        assert result.name == "Regional Houston, TX"
        assert result.date == "2026-03-21"
        assert result.player_count == 2635
        assert result.country == "US"

    def test_strips_endash_limitless_suffix(self, client):
        """Live Limitless titles use ' – Limitless' (U+2013); suffix must be removed."""
        html = """
        <html><body>
            <h1>Regional Campinas – Limitless</h1>
            <span>16 May 26</span>
            <span>1725 Players</span>
            <img src="/flags/br.png" alt="BR">
        </body></html>
        """
        result = self._mock_soup(client, html)
        assert result.name == "Regional Campinas"

    def test_four_digit_year(self, client):
        html = """
        <html><body>
            <h1>Regional Toronto</h1>
            <span>14 Mar 2026</span>
            <span>1200 Players</span>
        </body></html>
        """
        result = self._mock_soup(client, html)
        assert result.date == "2026-03-14"

    def test_missing_date_raises(self, client):
        html = "<html><body><h1>Some Tournament</h1></body></html>"
        with pytest.raises(ValueError, match="Could not parse required metadata"):
            self._mock_soup(client, html)

    def test_missing_name_raises(self, client):
        html = "<html><body><span>21 Mar 26</span></body></html>"
        with pytest.raises(ValueError, match="Could not parse required metadata"):
            self._mock_soup(client, html)

    def test_missing_player_count_warns(self, client, caplog):
        import logging

        html = """
        <html><body>
            <h1>Regional Test</h1>
            <span>21 Mar 26</span>
        </body></html>
        """
        with caplog.at_level(logging.WARNING):
            result = self._mock_soup(client, html)
        assert result.player_count == 0
        assert "Could not parse player count" in caplog.text

    def test_comma_in_player_count(self, client):
        html = """
        <html><body>
            <h1>Big Regional</h1>
            <span>21 Mar 26</span>
            <span>2,635 Players</span>
        </body></html>
        """
        result = self._mock_soup(client, html)
        assert result.player_count == 2635


# ---------------------------------------------------------------------------
# Decklist parsing tests (#3)
# ---------------------------------------------------------------------------


class TestFetchDecklistParsing:
    """Test fetch_decklist parsing strategies."""

    @pytest.fixture()
    def client(self):
        from scraper.labs_limitless import LabsLimitlessClient

        c = LabsLimitlessClient()
        yield c
        c.close()

    def _mock_soup(self, client, html):
        from bs4 import BeautifulSoup

        with patch.object(client, "_soup", return_value=BeautifulSoup(html, "html.parser")):
            return client.fetch_decklist("http://example.com/decks/list/42")

    def test_card_link_strategy(self, client):
        html = """
        <html><body>
            <a class="card-link" href="/cards/OBF/006">
                <span class="card-count">3</span>
                <span class="card-name">Charizard ex</span>
            </a>
            <a class="card-link" href="/cards/SVI/191">
                <span class="card-count">4</span>
                <span class="card-name">Rare Candy</span>
            </a>
        </body></html>
        """
        result = self._mock_soup(client, html)
        assert result is not None
        assert len(result.cards) == 2
        assert result.cards[0]["name"] == "Charizard ex"
        assert result.cards[0]["count"] == 3
        assert result.cards[0]["set_code"] == "OBF"
        assert result.cards[0]["card_number"] == "006"
        assert result.cards[0]["card_id"] == "OBF-006"

    def test_text_format_fallback(self, client):
        html = """
        <html><body>
        <pre>
3 Charizard ex OBF 006
4 Rare Candy SVI 191
        </pre>
        </body></html>
        """
        result = self._mock_soup(client, html)
        assert result is not None
        assert len(result.cards) == 2
        assert result.cards[0]["name"] == "Charizard ex"
        assert result.cards[0]["count"] == 3

    def test_no_cards_returns_none(self, client):
        html = "<html><body><p>No decklist available</p></body></html>"
        result = self._mock_soup(client, html)
        assert result is None

    def test_unparseable_count_defaults_to_1(self, client):
        html = """
        <html><body>
            <a class="card-link" href="/cards/OBF/006">
                <span class="card-count">abc</span>
                <span class="card-name">Charizard ex</span>
            </a>
        </body></html>
        """
        result = self._mock_soup(client, html)
        assert result is not None
        assert result.cards[0]["count"] == 1

    def test_network_error_returns_none(self, client):
        import httpx

        with patch.object(client, "_soup", side_effect=httpx.ConnectError("Connection failed")):
            result = client.fetch_decklist("http://example.com/decks/list/42")
        assert result is None

    def test_timeout_error_returns_none(self, client):
        import httpx

        with patch.object(client, "_soup", side_effect=httpx.ReadTimeout("Read timed out")):
            result = client.fetch_decklist("http://example.com/decks/list/42")
        assert result is None

    def test_http_403_raises_and_logs_error(self, client, caplog):
        import logging

        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_request = MagicMock()
        exc = httpx.HTTPStatusError("Forbidden", request=mock_request, response=mock_resp)
        with caplog.at_level(logging.ERROR), patch.object(client, "_soup", side_effect=exc):
            with pytest.raises(httpx.HTTPStatusError):
                client.fetch_decklist("http://example.com/decks/list/42")
        assert "scraper may be blocked" in caplog.text


# ---------------------------------------------------------------------------
# fetch_standings integration tests
# ---------------------------------------------------------------------------


class TestFetchStandings:
    """Test fetch_standings with mocked HTML pages."""

    @pytest.fixture()
    def client(self):
        from scraper.labs_limitless import LabsLimitlessClient

        c = LabsLimitlessClient()
        yield c
        c.close()

    def test_no_table_raises_value_error(self, client):
        from bs4 import BeautifulSoup

        html = "<html><body><p>No standings here</p></body></html>"
        with patch.object(client, "_soup", return_value=BeautifulSoup(html, "html.parser")):
            with pytest.raises(ValueError, match="No standings table found"):
                client.fetch_standings("0058")

    def test_rows_with_few_cells_skipped_with_warning(self, client, caplog):
        import logging

        from bs4 import BeautifulSoup

        html = """
        <html><body><table>
            <tr><th>Rank</th><th>Player</th><th>Country</th><th>Record</th><th>Deck</th></tr>
            <tr><td>1.</td><td>Short</td></tr>
            <tr><td>2.</td>
                <td><a href="/players/100">Alice</a></td>
                <td><img src="/flags/us.png" alt="US"></td>
                <td>10 - 2 - 1</td>
                <td><img src="/pokemon/charizard.png" alt="Charizard"></td>
            </tr>
        </table></body></html>
        """
        with (
            caplog.at_level(logging.WARNING),
            patch.object(client, "_soup", return_value=BeautifulSoup(html, "html.parser")),
        ):
            placements = client.fetch_standings("0058")
        assert len(placements) == 1
        assert "Skipping standings row with 2 cells" in caplog.text

    def test_unknown_archetype_warning(self, client, caplog):
        import logging

        from bs4 import BeautifulSoup

        # Build a table where >50% are Unknown archetype
        rows = ["<tr><th>R</th><th>P</th><th>C</th><th>Rec</th><th>Deck</th></tr>"]
        for i in range(1, 4):
            rows.append(
                f"<tr><td>{i}.</td>"
                f'<td><a href="/players/{i}">Player{i}</a></td>'
                f"<td></td><td>5 - 3 - 0</td><td></td></tr>"
            )
        html = f"<html><body><table>{''.join(rows)}</table></body></html>"
        with (
            caplog.at_level(logging.WARNING),
            patch.object(client, "_soup", return_value=BeautifulSoup(html, "html.parser")),
        ):
            placements = client.fetch_standings("0058")
        assert all(p.archetype == "Unknown" for p in placements)
        assert "sprite parsing may be broken" in caplog.text


# ---------------------------------------------------------------------------
# ingest_tournament edge cases
# ---------------------------------------------------------------------------


class TestIngestEdgeCases:
    """Test ingest_tournament edge cases from review findings."""

    @pytest.fixture()
    def client(self):
        from scraper.labs_limitless import LabsLimitlessClient

        c = LabsLimitlessClient()
        yield c
        c.close()

    def test_empty_standings_raises_value_error(self, client, labs_db):
        from scraper.labs_limitless import LabsTournament

        mock_tournament = LabsTournament(
            tournament_id="900", name="Empty Regional", date="2026-03-20"
        )
        with (
            patch.object(client, "fetch_tournament_metadata", return_value=mock_tournament),
            patch.object(client, "fetch_standings", return_value=[]),
        ):
            with pytest.raises(ValueError, match="No standings found"):
                client.ingest_tournament(labs_db, tournament_id="900", labs_tournament_id="test")

    def test_max_placements_truncation(self, client, labs_db):
        from scraper.labs_limitless import LabsPlacement, LabsPlayer, LabsTournament

        mock_tournament = LabsTournament(
            tournament_id="901", name="Truncation Test", date="2026-03-20"
        )
        mock_standings = [
            LabsPlacement(
                standing=i,
                player=LabsPlayer(player_id=f"trunc-p{i}", name=f"Player{i}"),
                archetype="Charizard ex",
                record_w=10,
                record_l=2,
                record_t=0,
            )
            for i in range(1, 11)
        ]
        with (
            patch.object(client, "fetch_tournament_metadata", return_value=mock_tournament),
            patch.object(client, "fetch_standings", return_value=mock_standings),
        ):
            result = client.ingest_tournament(
                labs_db,
                tournament_id="901",
                labs_tournament_id="test",
                fetch_decklists=False,
                max_placements=3,
            )
        assert result["placements"] == 3

    def test_reingest_tournament_preserves_data(self, client, labs_db):
        """Calling ingest_tournament twice with the same data should not duplicate rows."""
        from scraper.labs_limitless import (
            LabsDecklist,
            LabsPlacement,
            LabsPlayer,
            LabsTournament,
        )

        mock_tournament = LabsTournament(
            tournament_id="950", name="Reingest Test", date="2026-03-20"
        )
        mock_standings = [
            LabsPlacement(
                standing=1,
                player=LabsPlayer(player_id="rp1", name="RePlayer1"),
                archetype="Charizard ex",
                record_w=10,
                record_l=2,
                record_t=0,
                decklist_url="http://example.com/decks/list/99",
            ),
        ]
        mock_decklist = LabsDecklist(
            cards=[
                {"name": "Charizard ex", "card_id": "SV5-123", "count": 3},
                {"name": "Rare Candy", "card_id": "SV1-191", "count": 4},
            ],
            source_url="http://example.com/decks/list/99",
        )

        for _ in range(2):
            with (
                patch.object(client, "fetch_tournament_metadata", return_value=mock_tournament),
                patch.object(client, "fetch_standings", return_value=mock_standings),
                patch.object(client, "fetch_decklist", return_value=mock_decklist),
            ):
                result = client.ingest_tournament(
                    labs_db,
                    tournament_id="950",
                    labs_tournament_id="test-reingest",
                )

        # Verify no duplicates
        assert result["placements"] == 1
        assert result["decklists"] == 1

        tournament_count = labs_db.execute(
            "SELECT COUNT(*) FROM tournaments WHERE id='950'"
        ).fetchone()[0]
        assert tournament_count == 1

        placement_count = labs_db.execute(
            "SELECT COUNT(*) FROM placements WHERE tournament_id='950'"
        ).fetchone()[0]
        assert placement_count == 1

        card_count = labs_db.execute(
            """SELECT COUNT(*) FROM decklist_cards dc
               JOIN decklists d ON dc.decklist_id = d.id
               WHERE d.tournament_id='950'"""
        ).fetchone()[0]
        assert card_count == 2

    def test_min_matches_threshold_zeroes_sparse_data(self, labs_db):
        """Verify min_matches threshold suppresses low-confidence cells."""
        from analysis.matchup import compute_labs_matchup_matrix

        # With min_matches=100 (very high), all non-diagonal cells should be None
        result = compute_labs_matchup_matrix(labs_db, top_n=5, min_matches=100)
        n = len(result["archetypes"])
        for i in range(n):
            for j in range(n):
                if i != j:
                    assert result["matrix"][i][j] is None


# ---------------------------------------------------------------------------
# Data class validation tests
# ---------------------------------------------------------------------------


class TestDataClassValidation:
    """Test __post_init__ validators on data classes."""

    def test_labs_player_empty_id_raises(self):
        from scraper.labs_limitless import LabsPlayer

        with pytest.raises(ValueError, match="player_id must be non-empty"):
            LabsPlayer(player_id="", name="Test")

    def test_labs_player_whitespace_id_raises(self):
        from scraper.labs_limitless import LabsPlayer

        with pytest.raises(ValueError, match="player_id must be non-empty"):
            LabsPlayer(player_id="   ", name="Test")

    def test_labs_placement_zero_standing_raises(self):
        from scraper.labs_limitless import LabsPlacement, LabsPlayer

        with pytest.raises(ValueError, match="standing must be >= 1"):
            LabsPlacement(
                standing=0,
                player=LabsPlayer(player_id="p1", name="Test"),
                archetype="Test",
            )

    def test_labs_placement_negative_record_raises(self):
        from scraper.labs_limitless import LabsPlacement, LabsPlayer

        with pytest.raises(ValueError, match="W/L/T records must be non-negative"):
            LabsPlacement(
                standing=1,
                player=LabsPlayer(player_id="p1", name="Test"),
                archetype="Test",
                record_w=-1,
            )

    def test_labs_tournament_empty_id_raises(self):
        from scraper.labs_limitless import LabsTournament

        with pytest.raises(ValueError, match="tournament_id must be non-empty"):
            LabsTournament(tournament_id="", name="Test", date="2026-01-01")

    def test_labs_tournament_empty_name_raises(self):
        from scraper.labs_limitless import LabsTournament

        with pytest.raises(ValueError, match="name must be non-empty"):
            LabsTournament(tournament_id="t1", name="", date="2026-01-01")


# ---------------------------------------------------------------------------
# Rate limiter unit tests
# ---------------------------------------------------------------------------


class TestRateLimiter:
    """Test RateLimitedHTTPClient._rate_limit() logic."""

    def test_under_limit_proceeds_immediately(self):
        """Requests under the RPM limit should proceed without sleeping."""
        from scraper.http_client import RateLimitedHTTPClient

        client = RateLimitedHTTPClient(max_rpm=5)
        try:
            with patch("scraper.http_client.time.sleep") as mock_sleep:
                client._rate_limit()
                mock_sleep.assert_not_called()
            assert len(client._request_timestamps) == 1
        finally:
            client.close()

    def test_at_limit_blocks(self):
        """Requests at the RPM limit should sleep until a slot opens."""
        from scraper.http_client import RateLimitedHTTPClient

        client = RateLimitedHTTPClient(max_rpm=2)
        try:
            # Pre-fill timestamps to simulate 2 recent requests
            now = __import__("time").monotonic()
            client._request_timestamps = [now - 10, now - 5]

            with patch("scraper.http_client.time.sleep") as mock_sleep:
                # After sleeping, re-check should find the slot available
                # since timestamps will be pruned after 60s. We simulate
                # the passage of time by having sleep advance monotonic.
                original_monotonic = __import__("time").monotonic

                call_count = [0]

                def fake_monotonic():
                    call_count[0] += 1
                    if call_count[0] > 4:
                        # After sleep, return time > 60s past oldest
                        return now + 61
                    return original_monotonic()

                with patch("scraper.http_client.time.monotonic", side_effect=fake_monotonic):
                    client._rate_limit()

                assert mock_sleep.called
        finally:
            client.close()

    def test_old_timestamps_pruned(self):
        """Timestamps older than 60s should be pruned."""
        from scraper.http_client import RateLimitedHTTPClient

        client = RateLimitedHTTPClient(max_rpm=5)
        try:
            now = __import__("time").monotonic()
            # Add timestamps from 90s ago (should be pruned)
            client._request_timestamps = [now - 90, now - 80, now - 70]

            client._rate_limit()
            # Old timestamps should be pruned, only the new one remains
            assert len(client._request_timestamps) == 1
        finally:
            client.close()


# ---------------------------------------------------------------------------
# Winner ID mismatch test
# ---------------------------------------------------------------------------


class TestWinnerIdMismatch:
    """Test that invalid winner_id rows are excluded from H2H matrix."""

    def test_mismatch_skipped_and_warned(self, labs_db, caplog):
        """Matches with winner_id matching neither player should be skipped."""
        from analysis.matchup import compute_labs_matchup_matrix

        # Insert a match with a winner_id that doesn't match either player
        labs_db.execute(
            "INSERT INTO matches (id, tournament_id, round, player1_id, player2_id, "
            "winner_id, player1_archetype, player2_archetype) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "551:r99:p1:p2",
                "551",
                99,
                "p1",
                "p2",
                "ghost_player",
                "Dragapult ex",
                "Charizard ex",
            ),
        )
        labs_db.commit()

        import logging

        with caplog.at_level(logging.WARNING):
            result = compute_labs_matchup_matrix(labs_db, min_matches=1)

        # Should have warned about skipped matches
        assert any("Skipped" in msg and "winner_id" in msg for msg in caplog.messages)

        # The mismatch match should NOT be counted in the totals
        # Original seed: Drag vs Char has 3 valid matches:
        #   551:r2 (Char beat Drag), 551:r3 (Drag beat Char), 552:r1 (Char beat Drag)
        # The ghost_player match should be excluded, keeping totals at 3
        archetypes = result["archetypes"]
        assert "Dragapult ex" in archetypes
        assert "Charizard ex" in archetypes
        di = archetypes.index("Dragapult ex")
        ci = archetypes.index("Charizard ex")
        sample = result["sample_sizes"][di][ci]
        assert sample == 3


# ---------------------------------------------------------------------------
# Consecutive fetch failure abort test
# ---------------------------------------------------------------------------


class TestConsecutiveFetchFailureAbort:
    """Test that ingest_tournament aborts after consecutive decklist failures."""

    @pytest.fixture()
    def client(self):
        from scraper.labs_limitless import LabsLimitlessClient

        c = LabsLimitlessClient()
        yield c
        c.close()

    def test_aborts_after_three_consecutive_failures(self, client, labs_db, caplog):
        """Should stop fetching decklists after 3 consecutive None returns."""
        from scraper.labs_limitless import LabsPlacement, LabsPlayer, LabsTournament

        # Mock fetch_tournament_metadata and fetch_standings
        tournament = LabsTournament(
            tournament_id="999", name="Test Regional", date="2026-03-20", player_count=8
        )
        placements = [
            LabsPlacement(
                standing=i,
                player=LabsPlayer(player_id=f"tp{i}", name=f"Player {i}"),
                archetype="Dragapult ex",
                decklist_url=f"https://example.com/decks/{i}",
            )
            for i in range(1, 7)  # 6 placements, all with decklist URLs
        ]

        with (
            patch.object(client, "fetch_tournament_metadata", return_value=tournament),
            patch.object(client, "fetch_standings", return_value=placements),
            patch.object(client, "fetch_decklist", return_value=None) as mock_fetch,
        ):
            import logging

            with caplog.at_level(logging.ERROR):
                result = client.ingest_tournament(labs_db, "999", "0099")

        # Should have stopped after 3 failures, not tried all 6
        assert mock_fetch.call_count == 3
        assert result["decklist_failures"] == 3
        assert any("Aborting decklist fetches" in msg for msg in caplog.messages)

    def test_success_resets_counter(self, client, labs_db):
        """A successful fetch between failures should reset the counter."""
        from scraper.labs_limitless import (
            LabsDecklist,
            LabsPlacement,
            LabsPlayer,
            LabsTournament,
        )

        tournament = LabsTournament(
            tournament_id="998", name="Test Regional 2", date="2026-03-19", player_count=6
        )
        placements = [
            LabsPlacement(
                standing=i,
                player=LabsPlayer(player_id=f"tp{i}", name=f"Player {i}"),
                archetype="Charizard ex",
                decklist_url=f"https://example.com/decks/{i}",
            )
            for i in range(1, 7)  # 6 placements
        ]

        success = LabsDecklist(cards=[{"name": "Charizard ex", "card_id": "OBF-125", "count": 3}])

        # Pattern: fail, fail, success, fail, fail, success — never hits 3 consecutive
        side_effects = [None, None, success, None, None, success]

        with (
            patch.object(client, "fetch_tournament_metadata", return_value=tournament),
            patch.object(client, "fetch_standings", return_value=placements),
            patch.object(client, "fetch_decklist", side_effect=side_effects) as mock_fetch,
        ):
            result = client.ingest_tournament(labs_db, "998", "0098")

        # All 6 should be attempted (counter resets on success)
        assert mock_fetch.call_count == 6
        assert result["decklists"] == 2
        assert result["decklist_failures"] == 4

    def test_auth_blocked_circuit_breaker(self, client, labs_db):
        """HTTP 401/403 during decklist fetch should abort immediately."""
        import httpx

        from scraper.labs_limitless import LabsPlacement, LabsPlayer, LabsTournament

        tournament = LabsTournament(tournament_id="997", name="Auth Block Test", date="2026-03-20")
        placements = [
            LabsPlacement(
                standing=i,
                player=LabsPlayer(player_id=f"auth-p{i}", name=f"Player {i}"),
                archetype="Charizard ex",
                decklist_url=f"https://example.com/decks/{i}",
            )
            for i in range(1, 5)
        ]

        mock_request = MagicMock()
        mock_response = MagicMock(status_code=403)
        exc = httpx.HTTPStatusError("Forbidden", request=mock_request, response=mock_response)

        with (
            patch.object(client, "fetch_tournament_metadata", return_value=tournament),
            patch.object(client, "fetch_standings", return_value=placements),
            patch.object(client, "fetch_decklist", side_effect=exc) as mock_fetch,
        ):
            result = client.ingest_tournament(labs_db, "997", "0097")

        # Should abort after first 403 — only 1 call
        assert mock_fetch.call_count == 1
        # All 4 counted as failures
        assert result["decklist_failures"] == 4
        assert result["decklists"] == 0


class TestRecordFallbackZeroMatches:
    """Test record-based fallback with zero-total-match edge case."""

    def test_zero_records_produce_valid_matrix(self):
        """Archetypes with all-zero W-L-T should be filtered (NULL avg_wr)."""
        from analysis.matchup import compute_labs_matchup_matrix

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(LABS_SCHEMA)

        conn.execute("INSERT INTO tournaments (id, name, date) VALUES ('t1', 'Test', '2026-01-01')")
        conn.execute("INSERT INTO players (id, name) VALUES ('p1', 'Player1')")
        conn.execute("INSERT INTO players (id, name) VALUES ('p2', 'Player2')")
        # Both have zero records
        conn.execute(
            "INSERT INTO placements (tournament_id, player_id, standing, archetype, record_w, record_l, record_t) "
            "VALUES ('t1', 'p1', 1, 'Charizard ex', 0, 0, 0)"
        )
        conn.execute(
            "INSERT INTO placements (tournament_id, player_id, standing, archetype, record_w, record_l, record_t) "
            "VALUES ('t1', 'p2', 2, 'Dragapult ex', 0, 0, 0)"
        )
        conn.commit()

        result = compute_labs_matchup_matrix(conn, top_n=5)
        conn.close()

        # With zero records, avg_wr is NULL and filtered out — non-diagonal cells
        # should be None (insufficient data), not 0.0 or NaN
        for i, row in enumerate(result["matrix"]):
            for j, val in enumerate(row):
                if i == j:
                    assert val == 0.5  # Mirror match
                else:
                    assert val is None, (
                        f"Expected None for insufficient data at [{i}][{j}], got {val}"
                    )


class TestEmptyArchetypeNormalization:
    """Verify that empty archetype from normalize_archetype becomes 'Unknown'."""

    def test_empty_archetype_becomes_unknown(self) -> None:
        """When normalize_archetype returns '', the placement should use 'Unknown'."""
        from scraper.labs_limitless import LabsLimitlessClient

        client = LabsLimitlessClient()

        # Build a minimal row with no sprites and no text fallback
        from bs4 import BeautifulSoup

        html = (
            "<tr>"
            "<td>1.</td>"
            "<td><a href='/players/999'>TestPlayer</a></td>"
            "<td></td>"
            "<td>10 - 2 - 0</td>"
            "<td></td>"
            "</tr>"
        )
        soup = BeautifulSoup(html, "html.parser")
        cells = soup.find_all("td")

        with patch("scraper.labs_limitless.normalize_archetype", return_value=""):
            placement = client._parse_standings_row(cells)

        assert placement is not None
        assert placement.archetype == "Unknown"
        client.close()


class TestDateParsingNonAsciiMonth:
    """Verify date parsing handles unrecognized month names gracefully."""

    def test_unrecognized_month_raises_with_context(self) -> None:
        """When month isn't in _MONTH_TO_NUM, metadata parse raises ValueError."""
        from scraper.labs_limitless import LabsLimitlessClient

        client = LabsLimitlessClient()

        # Page with a non-ASCII month that won't match the regex
        html = "<html><h1>Test Tournament</h1><span>21 Mär 2026</span></html>"
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.status_code = 200

        with patch.object(client, "_get", return_value=mock_response):
            with pytest.raises(ValueError, match="Could not parse required metadata"):
                client.fetch_tournament_metadata("999")

        client.close()


class TestFetchTournamentMetadataLabsId:
    """fetch_tournament_metadata extracts labs_tournament_id when the page links to Labs."""

    @pytest.fixture()
    def client(self):
        from scraper.labs_limitless import LabsLimitlessClient

        c = LabsLimitlessClient()
        yield c
        c.close()

    def test_extracts_labs_id_from_standings_link(self, client) -> None:
        html = """
        <html>
          <h1>Regional Campinas</h1>
          <span>16 May 2026</span>
          <span>1725 Players</span>
          <a href="https://labs.limitlesstcg.com/0065/standings">Standings</a>
        </html>
        """
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.status_code = 200

        with patch.object(client, "_get", return_value=mock_response):
            t = client.fetch_tournament_metadata("544")
        assert t.labs_tournament_id == "0065"
        assert t.name == "Regional Campinas"
        assert t.date == "2026-05-16"

    def test_labs_id_none_when_no_standings_link(self, client) -> None:
        html = """
        <html>
          <h1>Some Local Event</h1>
          <span>1 Apr 2026</span>
          <span>50 Players</span>
        </html>
        """
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.status_code = 200

        with patch.object(client, "_get", return_value=mock_response):
            t = client.fetch_tournament_metadata("777")
        assert t.labs_tournament_id is None


class TestParseListingRow:
    """_parse_listing_row maps a /tournaments table row to LabsTournamentListing."""

    @pytest.fixture()
    def client(self):
        from scraper.labs_limitless import LabsLimitlessClient

        c = LabsLimitlessClient()
        yield c
        c.close()

    @staticmethod
    def _make_row(cells_html: list[str]):
        from bs4 import BeautifulSoup

        html = "<table><tr>" + "".join(f"<td>{c}</td>" for c in cells_html) + "</tr></table>"
        soup = BeautifulSoup(html, "html.parser")
        return soup.find("tr")

    def test_basic_regional_row(self, client) -> None:
        row = self._make_row(
            [
                "16 May 26",
                '<img src="https://r2.limitlesstcg.net/flags/BR.png" alt="BR">',
                '<a href="/tournaments/544">Regional Campinas</a>',
                '<img alt="standard" class="format" src="x.png">',
                "1725",
                '<a href="/players/1198">Matias</a>',
            ]
        )
        listing = client._parse_listing_row(row)
        assert listing is not None
        assert listing.tournament_id == "544"
        assert listing.name == "Regional Campinas"
        assert listing.date == "2026-05-16"
        assert listing.country == "BR"
        assert listing.player_count == 1725
        assert listing.format_string == "standard"

    def test_missing_link_returns_none(self, client) -> None:
        row = self._make_row(
            [
                "16 May 26",
                '<img alt="US">',
                "No link here",
                "",
                "100",
            ]
        )
        assert client._parse_listing_row(row) is None

    def test_unparseable_date_returns_none(self, client) -> None:
        row = self._make_row(
            [
                "TBD",
                '<img alt="US">',
                '<a href="/tournaments/999">X</a>',
                "",
                "100",
            ]
        )
        assert client._parse_listing_row(row) is None

    def test_player_count_with_comma(self, client) -> None:
        row = self._make_row(
            [
                "09 May 26",
                '<img alt="JP">',
                '<a href="/tournaments/567">Champions League Aichi</a>',
                "",
                "8,000",
            ]
        )
        listing = client._parse_listing_row(row)
        assert listing is not None
        assert listing.player_count == 8000


class TestListTournaments:
    """list_tournaments fetches the listing page and filters by date."""

    @pytest.fixture()
    def client(self):
        from scraper.labs_limitless import LabsLimitlessClient

        c = LabsLimitlessClient()
        yield c
        c.close()

    @staticmethod
    def _make_listing_html(rows: list[tuple[str, str, str, str, str, int]]) -> str:
        """Build a listing HTML page from (date, country, tid, name, format, players) tuples."""
        body = [
            "<html><body><table><tr><th>Date</th><th>Country</th><th>Name</th><th></th><th>Players</th><th>Winner</th></tr>"
        ]
        for date_text, country, tid, name, fmt, players in rows:
            body.append(
                f"<tr>"
                f"<td>{date_text}</td>"
                f'<td><img src="x" alt="{country}"></td>'
                f'<td><a href="/tournaments/{tid}">{name}</a></td>'
                f'<td><img alt="{fmt}" class="format"></td>'
                f"<td>{players}</td>"
                f"<td></td>"
                f"</tr>"
            )
        body.append("</table></body></html>")
        return "".join(body)

    def test_returns_all_when_no_since(self, client) -> None:
        html = self._make_listing_html(
            [
                ("16 May 26", "BR", "544", "Regional Campinas", "standard", 1725),
                ("09 May 26", "US", "558", "Regional Los Angeles", "standard", 1849),
                ("25 Apr 26", "CZ", "539", "Regional Prague", "standard", 1370),
            ]
        )
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.status_code = 200

        with patch.object(client, "_get", return_value=mock_response):
            listings = client.list_tournaments()
        assert len(listings) == 3
        assert [t.tournament_id for t in listings] == ["544", "558", "539"]

    def test_since_filter_stops_at_cutoff(self, client) -> None:
        html = self._make_listing_html(
            [
                ("16 May 26", "BR", "544", "Regional Campinas", "standard", 1725),
                ("09 May 26", "US", "558", "Regional Los Angeles", "standard", 1849),
                ("25 Apr 26", "CZ", "539", "Regional Prague", "standard", 1370),
            ]
        )
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.status_code = 200

        with patch.object(client, "_get", return_value=mock_response):
            listings = client.list_tournaments(since="2026-05-01")
        assert [t.tournament_id for t in listings] == ["544", "558"]

    def test_empty_table_returns_empty_list(self, client) -> None:
        html = "<html><body><p>no table here</p></body></html>"
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.status_code = 200

        with patch.object(client, "_get", return_value=mock_response):
            listings = client.list_tournaments()
        assert listings == []
