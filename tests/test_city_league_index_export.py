"""Tests for the city league index JSON export."""

import json
import sqlite3
from pathlib import Path

import pytest

from db import SCHEMA
from reports.json_export import _compute_city_league_index, export_city_league_index


@pytest.fixture()
def db_cl() -> sqlite3.Connection:
    """In-memory DB with city-league-style tournament data."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)

    # Tournaments (3 open, 1 senior)
    conn.executemany(
        "INSERT INTO tournaments (id, name, date, player_count, division, prefecture) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("t1", "City League Osaka", "2026-03-20", 64, "open", "Osaka"),
            ("t2", "City League Tokyo", "2026-03-15", 128, "open", "Tokyo"),
            ("t3", "City League Saitama", "2026-02-10", 32, "open", "Saitama"),
            ("t4", "Junior Cup", "2026-03-18", 16, "senior", None),
        ],
    )

    # Placements
    conn.executemany(
        "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            # t1: 6 players
            (1, "t1", 1, "Alice", "Charizard ex"),
            (2, "t1", 2, "Bob", "Dragapult ex"),
            (3, "t1", 3, "Charlie", "Charizard ex"),
            (4, "t1", 4, "Diana", "Raging Bolt ex"),
            (5, "t1", 5, "Eve", "Dragapult ex"),
            (6, "t1", 8, "Frank", "Unknown"),
            # t2: 4 players
            (7, "t2", 1, "Grace", "Dragapult ex"),
            (8, "t2", 2, "Hank", "Charizard ex"),
            (9, "t2", 3, "Ivy", "Unknown"),
            (10, "t2", 4, "Jake", "Raging Bolt ex"),
            # t3: 2 players
            (11, "t3", 1, "Kate", "Charizard ex"),
            (12, "t3", 2, "Leo", "Charizard ex"),
            # t4 (senior, should be excluded)
            (13, "t4", 1, "Mike", "Charizard ex"),
        ],
    )

    # Meta snapshot (needed for tier lookup)
    conn.execute(
        "INSERT INTO meta_snapshots (id, generated_at, tournament_count, deck_count) "
        "VALUES (1, '2026-03-20', 3, 12)"
    )
    conn.executemany(
        "INSERT INTO archetype_stats (snapshot_id, archetype, meta_share, deck_count, best_placement, tier) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "Charizard ex", 41.7, 5, 1, "S"),
            (1, "Dragapult ex", 25.0, 3, 1, "A"),
            (1, "Raging Bolt ex", 16.7, 2, 4, "B"),
            (1, "Unknown", 8.3, 1, 5, "Rogue"),
        ],
    )

    conn.commit()
    return conn


class TestComputeCityLeagueIndex:
    def test_returns_expected_structure(self, db_cl: sqlite3.Connection) -> None:
        data = _compute_city_league_index(db_cl)

        assert data["tournament_count"] == 3  # excludes senior
        assert data["deck_count"] == 12  # excludes senior placements
        assert data["date_range"]["start"] == "2026-02-10"
        assert data["date_range"]["end"] == "2026-03-20"
        assert isinstance(data["rising_archetypes"], list)
        assert isinstance(data["recent_winners"], list)
        assert isinstance(data["tournaments"], list)
        assert len(data["tournaments"]) == 3

    def test_excludes_senior_division(self, db_cl: sqlite3.Connection) -> None:
        data = _compute_city_league_index(db_cl)
        tournament_ids = [t["id"] for t in data["tournaments"]]
        assert "t4" not in tournament_ids

    def test_excludes_champions_league(self, db_cl: sqlite3.Connection) -> None:
        # Add a champions league tournament (open division)
        db_cl.execute(
            "INSERT INTO tournaments (id, name, date, player_count, division, tournament_type) "
            "VALUES ('t5', 'Champions League 2026', '2026-03-19', 256, 'open', 'champions-league')"
        )
        db_cl.execute(
            "INSERT INTO placements (tournament_id, standing, player_name, archetype) "
            "VALUES ('t5', 1, 'Champ', 'Charizard ex')"
        )
        db_cl.commit()
        data = _compute_city_league_index(db_cl)
        tournament_ids = [t["id"] for t in data["tournaments"]]
        assert "t5" not in tournament_ids

    def test_top_finishers_capped_at_4(self, db_cl: sqlite3.Connection) -> None:
        data = _compute_city_league_index(db_cl)
        for t in data["tournaments"]:
            assert len(t["top_finishers"]) <= 4
            for f in t["top_finishers"]:
                assert f["standing"] <= 4

    def test_top_finishers_have_required_fields(self, db_cl: sqlite3.Connection) -> None:
        data = _compute_city_league_index(db_cl)
        t1 = next(t for t in data["tournaments"] if t["id"] == "t1")
        assert len(t1["top_finishers"]) == 4
        first = t1["top_finishers"][0]
        assert first["standing"] == 1
        assert first["player_name"] == "Alice"
        assert first["archetype"] == "Charizard ex"
        assert first["slug"] == "charizard-ex"
        assert first["tier"] == "S"

    def test_archetype_distribution_shares(self, db_cl: sqlite3.Connection) -> None:
        data = _compute_city_league_index(db_cl)
        for t in data["tournaments"]:
            if t["archetype_distribution"]:
                total_share = sum(e["share"] for e in t["archetype_distribution"])
                assert abs(total_share - 1.0) < 0.01

    def test_recent_winners(self, db_cl: sqlite3.Connection) -> None:
        data = _compute_city_league_index(db_cl)
        assert len(data["recent_winners"]) <= 5
        # Most recent first
        if len(data["recent_winners"]) >= 2:
            assert data["recent_winners"][0]["date"] >= data["recent_winners"][1]["date"]
        # First winner is from most recent tournament
        assert data["recent_winners"][0]["tournament_name"] == "City League Osaka"
        assert data["recent_winners"][0]["archetype"] == "Charizard ex"

    def test_date_windowed(self, db_cl: sqlite3.Connection) -> None:
        data = _compute_city_league_index(db_cl, date_from="2026-03-01", date_to="2026-03-31")
        # Should only include t1 and t2 (March)
        assert data["tournament_count"] == 2
        dates = [t["date"] for t in data["tournaments"]]
        assert all(d >= "2026-03-01" for d in dates)

    def test_recent_winners_respect_date_window(self, db_cl: sqlite3.Connection) -> None:
        data = _compute_city_league_index(db_cl, date_from="2026-03-01", date_to="2026-03-31")
        # Kate won t3 on 2026-02-10 -- should be excluded from March window
        winner_names = [w["player_name"] for w in data["recent_winners"]]
        assert "Kate" not in winner_names
        # Alice (t1, 2026-03-20) and Grace (t2, 2026-03-15) should be present
        assert "Alice" in winner_names
        assert "Grace" in winner_names

    def test_prefecture_included(self, db_cl: sqlite3.Connection) -> None:
        data = _compute_city_league_index(db_cl)
        t1 = next(t for t in data["tournaments"] if t["id"] == "t1")
        assert t1["prefecture"] == "Osaka"

    def test_unknown_archetypes_handled(self, db_cl: sqlite3.Connection) -> None:
        data = _compute_city_league_index(db_cl)
        t1 = next(t for t in data["tournaments"] if t["id"] == "t1")
        dist_archetypes = [e["archetype"] for e in t1["archetype_distribution"]]
        assert "Unknown" in dist_archetypes

    def test_tournaments_sorted_by_date_desc(self, db_cl: sqlite3.Connection) -> None:
        data = _compute_city_league_index(db_cl)
        dates = [t["date"] for t in data["tournaments"]]
        assert dates == sorted(dates, reverse=True)

    def test_deduplicates_limitless_against_jp_api(self, db_cl: sqlite3.Connection) -> None:
        # Same physical event ingested from both scrapers on the same date.
        # open_tournaments view must drop the Limitless row when a jp-* row exists.
        db_cl.executemany(
            "INSERT INTO tournaments (id, name, date, player_count, division, prefecture, tournament_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("jp-999001", "東京都 Sample Store", "2026-03-22", 16, "open", "Tokyo", "city-league"),
                (
                    "https://limitlesstcg.com/tournaments/jp/9999",
                    "City League Tōkyō",
                    "2026-03-22",
                    16,
                    "open",
                    "Tokyo",
                    "city-league",
                ),
            ],
        )
        db_cl.executemany(
            "INSERT INTO placements (tournament_id, standing, player_name, archetype) VALUES (?, ?, ?, ?)",
            [
                ("jp-999001", 1, "JPWinner", "Charizard ex"),
                ("jp-999001", 2, "JPRunnerUp", "Dragapult ex"),
                ("https://limitlesstcg.com/tournaments/jp/9999", 1, "JPWinner", "Charizard ex"),
                ("https://limitlesstcg.com/tournaments/jp/9999", 2, "JPRunnerUp", "Dragapult ex"),
            ],
        )
        db_cl.commit()

        data = _compute_city_league_index(db_cl)
        ids = [t["id"] for t in data["tournaments"]]

        # Exactly one of the two entries for 2026-03-22 survives, and it is the jp-* source.
        assert "jp-999001" in ids
        assert "https://limitlesstcg.com/tournaments/jp/9999" not in ids
        # tournament_count = original 3 + 1 (deduped pair), not + 2.
        assert data["tournament_count"] == 4
        # Placements from the excluded Limitless row must not contribute to deck_count.
        assert data["deck_count"] == 12 + 2

    def test_count_matches_meta_snapshot_invariant(self, db_cl: sqlite3.Connection) -> None:
        # Regression guard: CL index tournament_count must never inflate relative
        # to a direct count over open_tournaments for the same window.
        db_cl.executemany(
            "INSERT INTO tournaments (id, name, date, player_count, division, prefecture, tournament_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("jp-888001", "JP Event", "2026-03-25", 16, "open", "Tokyo", "city-league"),
                (
                    "https://limitlesstcg.com/tournaments/jp/8888",
                    "Limitless mirror",
                    "2026-03-25",
                    16,
                    "open",
                    "Tokyo",
                    "city-league",
                ),
            ],
        )
        db_cl.execute(
            "INSERT INTO placements (tournament_id, standing, player_name, archetype) "
            "VALUES ('jp-888001', 1, 'Winner', 'Charizard ex')"
        )
        db_cl.commit()

        data = _compute_city_league_index(db_cl)
        expected = db_cl.execute(
            "SELECT COUNT(*) FROM open_tournaments WHERE tournament_type = 'city-league'"
        ).fetchone()[0]
        assert data["tournament_count"] == expected


class TestExportCityLeagueIndex:
    def test_writes_json_file(self, db_cl: sqlite3.Connection, tmp_path: Path) -> None:
        export_city_league_index(db_cl, tmp_path)
        outfile = tmp_path / "city-league-index.json"
        assert outfile.exists()
        data = json.loads(outfile.read_text())
        assert data["tournament_count"] == 3

    def test_empty_db(self, tmp_path: Path) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.commit()
        export_city_league_index(conn, tmp_path)
        outfile = tmp_path / "city-league-index.json"
        assert outfile.exists()
        data = json.loads(outfile.read_text())
        assert data["tournament_count"] == 0
        assert data["tournaments"] == []
