"""Tests for matchup data export with cascade strategy (Issue #76).

Tests the cascade: Labs H2H -> Labs records -> co-occurrence proxy.
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from labs_db import LABS_SCHEMA


@pytest.fixture()
def jp_db() -> sqlite3.Connection:
    """In-memory JP database with co-occurrence data."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            player_count INTEGER,
            country TEXT DEFAULT 'JP',
            division TEXT DEFAULT 'open',
            tournament_type TEXT,
            prefecture TEXT,
            store_name TEXT,
            capacity INTEGER
        );
        CREATE TABLE IF NOT EXISTS placements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL REFERENCES tournaments(id),
            standing INTEGER NOT NULL,
            player_name TEXT,
            archetype TEXT,
            decklist_url TEXT
        );
        CREATE VIEW IF NOT EXISTS open_placements AS
            SELECT p.* FROM placements p
            JOIN tournaments t ON t.id = p.tournament_id
            WHERE t.division = 'open';
        CREATE TABLE IF NOT EXISTS meta_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generated_at TEXT NOT NULL,
            tournament_count INTEGER,
            deck_count INTEGER,
            date_range TEXT
        );
        CREATE TABLE IF NOT EXISTS archetype_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL REFERENCES meta_snapshots(id),
            archetype TEXT NOT NULL,
            meta_share REAL,
            deck_count INTEGER,
            tier TEXT,
            weighted_share REAL,
            best_placement INTEGER
        );
    """)

    # Seed tournaments
    for i in range(1, 4):
        conn.execute(
            "INSERT INTO tournaments (name, date, player_count, division) VALUES (?, ?, ?, ?)",
            (f"CL {i}", f"2026-03-{i:02d}", 32, "open"),
        )

    # Seed placements (3 archetypes across 3 tournaments)
    placements = [
        # Tournament 1
        (1, 1, "Charizard-Pidgeot", "P1"),
        (1, 2, "Charizard-Pidgeot", "P2"),
        (1, 3, "Dragapult-Dusknoir", "P3"),
        (1, 4, "Dragapult-Dusknoir", "P4"),
        (1, 5, "Lugia-Archeops", "P5"),
        (1, 6, "Lugia-Archeops", "P6"),
        # Tournament 2
        (2, 1, "Dragapult-Dusknoir", "P3"),
        (2, 2, "Charizard-Pidgeot", "P1"),
        (2, 3, "Lugia-Archeops", "P5"),
        (2, 4, "Charizard-Pidgeot", "P2"),
        # Tournament 3
        (3, 1, "Charizard-Pidgeot", "P1"),
        (3, 2, "Lugia-Archeops", "P5"),
        (3, 3, "Dragapult-Dusknoir", "P3"),
    ]
    for tid, standing, arch, pname in placements:
        conn.execute(
            "INSERT INTO placements (tournament_id, standing, archetype, player_name) "
            "VALUES (?, ?, ?, ?)",
            (tid, standing, arch, pname),
        )

    # Meta snapshot
    conn.execute(
        "INSERT INTO meta_snapshots (generated_at, tournament_count, deck_count) VALUES (?, ?, ?)",
        ("2026-03-25", 3, 13),
    )
    sid = conn.execute("SELECT MAX(id) FROM meta_snapshots").fetchone()[0]
    for arch, share, count in [
        ("Charizard-Pidgeot", 38.5, 5),
        ("Dragapult-Dusknoir", 30.8, 4),
        ("Lugia-Archeops", 30.8, 4),
    ]:
        conn.execute(
            "INSERT INTO archetype_stats (snapshot_id, archetype, meta_share, deck_count, tier) "
            "VALUES (?, ?, ?, ?, ?)",
            (sid, arch, share, count, "S"),
        )

    conn.commit()
    return conn


@pytest.fixture()
def labs_db_with_records() -> sqlite3.Connection:
    """In-memory Labs database with W-L-T records (no match-level data)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(LABS_SCHEMA)

    conn.executemany(
        "INSERT INTO tournaments (id, name, date, player_count, country, source) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("551", "Regional Houston", "2026-03-21", 500, "US", "limitless-labs"),
            ("552", "Regional Toronto", "2026-03-14", 400, "CA", "limitless-labs"),
        ],
    )

    conn.executemany(
        "INSERT INTO players (id, name, country) VALUES (?, ?, ?)",
        [
            ("p1", "Alice", "US"),
            ("p2", "Bob", "CA"),
            ("p3", "Charlie", "US"),
            ("p4", "Diana", "JP"),
            ("p5", "Eve", "US"),
            ("p6", "Frank", "MX"),
            ("p7", "Grace", "US"),
            ("p8", "Henry", "CA"),
        ],
    )

    # Placements with W-L-T records for 3 archetypes
    conn.executemany(
        "INSERT INTO placements (tournament_id, player_id, standing, archetype, "
        "record_w, record_l, record_t) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("551", "p1", 1, "Charizard-Pidgeot", 8, 1, 0),
            ("551", "p2", 5, "Charizard-Pidgeot", 6, 3, 0),
            ("551", "p3", 2, "Dragapult-Dusknoir", 7, 2, 0),
            ("551", "p4", 8, "Dragapult-Dusknoir", 5, 4, 0),
            ("551", "p5", 3, "Lugia-Archeops", 7, 2, 0),
            ("551", "p6", 10, "Lugia-Archeops", 4, 5, 0),
            ("552", "p7", 1, "Charizard-Pidgeot", 7, 1, 1),
            ("552", "p8", 4, "Dragapult-Dusknoir", 6, 2, 1),
        ],
    )
    conn.commit()
    return conn


@pytest.fixture()
def labs_db_with_matches(labs_db_with_records) -> sqlite3.Connection:
    """Labs database with match-level H2H data in addition to records."""
    conn = labs_db_with_records
    # Add enough matches to exceed LABS_MIN_MATCHES_TO_PUBLISH (30)
    # Generate 35 matches between Charizard-Pidgeot and Dragapult-Dusknoir
    for i in range(35):
        winner = "p1" if i % 3 != 0 else "p3"  # Charizard wins ~67%
        conn.execute(
            "INSERT INTO matches (id, tournament_id, round, player1_id, player2_id, "
            "winner_id, player1_archetype, player2_archetype) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"m{i}", "551", i + 1, "p1", "p3", winner, "Charizard-Pidgeot", "Dragapult-Dusknoir"),
        )
    conn.commit()
    return conn


@pytest.fixture()
def empty_labs_db() -> sqlite3.Connection:
    """Empty Labs database with schema but no data."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(LABS_SCHEMA)
    return conn


class TestExportMatchupData:
    """Test the cascade export_matchup_data function."""

    def test_cascade_falls_through_to_cooccurrence(self, jp_db, empty_labs_db, tmp_path):
        """When Labs DB is empty, cascade produces co-occurrence output."""
        from reports.json_export import export_matchup_data

        export_matchup_data(jp_db, tmp_path, labs_conn=empty_labs_db)

        matchup_file = tmp_path / "matchup.json"
        assert matchup_file.exists()
        data = json.loads(matchup_file.read_text())
        assert data["source"] == "co-occurrence"
        assert "archetypes" in data
        assert "matrix" in data
        assert "sample_sizes" in data

    def test_cascade_uses_labs_records_when_available(self, jp_db, labs_db_with_records, tmp_path):
        """When Labs has records but no matches, cascade uses labs-records."""
        from reports.json_export import export_matchup_data

        export_matchup_data(jp_db, tmp_path, labs_conn=labs_db_with_records)

        data = json.loads((tmp_path / "matchup.json").read_text())
        assert data["source"] == "labs-records"

    def test_cascade_uses_labs_h2h_when_matches_available(
        self, jp_db, labs_db_with_matches, tmp_path
    ):
        """When Labs has match data, cascade uses labs-h2h."""
        from reports.json_export import export_matchup_data

        export_matchup_data(jp_db, tmp_path, labs_conn=labs_db_with_matches)

        data = json.loads((tmp_path / "matchup.json").read_text())
        assert data["source"] == "labs-h2h"

    def test_output_includes_confidence_intervals_for_labs(
        self, jp_db, labs_db_with_records, tmp_path
    ):
        """Labs-sourced output includes confidence intervals."""
        from reports.json_export import export_matchup_data

        export_matchup_data(jp_db, tmp_path, labs_conn=labs_db_with_records)

        data = json.loads((tmp_path / "matchup.json").read_text())
        assert "confidence" in data
        # At least some cells should have non-null CI values
        has_ci = False
        for row in data["confidence"]:
            for cell in row:
                if cell.get("lower") is not None:
                    has_ci = True
                    break
        assert has_ci, "Expected at least one cell with confidence interval data"

    def test_cooccurrence_output_has_no_confidence_intervals(self, jp_db, empty_labs_db, tmp_path):
        """Co-occurrence output does not claim confidence intervals."""
        from reports.json_export import export_matchup_data

        export_matchup_data(jp_db, tmp_path, labs_conn=empty_labs_db)

        data = json.loads((tmp_path / "matchup.json").read_text())
        # Co-occurrence should not have confidence intervals
        assert "confidence" not in data or data.get("confidence") is None

    def test_cooccurrence_labeled_performance_advantage(self, jp_db, empty_labs_db, tmp_path):
        """Co-occurrence output metadata labels it as performance advantage."""
        from reports.json_export import export_matchup_data

        export_matchup_data(jp_db, tmp_path, labs_conn=empty_labs_db)

        data = json.loads((tmp_path / "matchup.json").read_text())
        assert data["source"] == "co-occurrence"
        assert data.get("methodology") == "Performance Advantage"

    def test_output_without_labs_connection(self, jp_db, tmp_path):
        """When no Labs connection provided, falls through to co-occurrence."""
        from reports.json_export import export_matchup_data

        export_matchup_data(jp_db, tmp_path, labs_conn=None)

        data = json.loads((tmp_path / "matchup.json").read_text())
        assert data["source"] == "co-occurrence"

    def test_labs_winrates_exported(self, jp_db, labs_db_with_records, tmp_path):
        """Labs win rates JSON is exported when Labs data exists."""
        from reports.json_export import export_matchup_data

        export_matchup_data(jp_db, tmp_path, labs_conn=labs_db_with_records)

        winrates_file = tmp_path / "labs-winrates.json"
        assert winrates_file.exists()
        data = json.loads(winrates_file.read_text())
        assert "archetypes" in data
        assert data["source"] == "labs-h2h"
        # Each archetype entry should have win rate and CI
        for entry in data["archetypes"]:
            assert "win_rate" in entry
            assert "ci_lower" in entry
            assert "ci_upper" in entry

    def test_no_labs_winrates_when_empty(self, jp_db, empty_labs_db, tmp_path):
        """No labs-winrates.json when Labs DB is empty."""
        from reports.json_export import export_matchup_data

        export_matchup_data(jp_db, tmp_path, labs_conn=empty_labs_db)

        assert not (tmp_path / "labs-winrates.json").exists()

    def test_empty_jp_db_produces_empty_matrix(self, tmp_path):
        """An empty JP DB with no data produces an empty matchup file."""
        from reports.json_export import export_matchup_data

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE meta_snapshots (id INTEGER PRIMARY KEY, generated_at TEXT, tournament_count INTEGER, deck_count INTEGER, date_range TEXT);
            CREATE TABLE archetype_stats (id INTEGER PRIMARY KEY, snapshot_id INTEGER, archetype TEXT, meta_share REAL, deck_count INTEGER, tier TEXT, weighted_share REAL, best_placement INTEGER);
            CREATE TABLE tournaments (id INTEGER PRIMARY KEY, name TEXT, date TEXT, player_count INTEGER, country TEXT DEFAULT 'JP', division TEXT DEFAULT 'open', tournament_type TEXT, prefecture TEXT, store_name TEXT, capacity INTEGER);
            CREATE TABLE placements (id INTEGER PRIMARY KEY, tournament_id INTEGER, standing INTEGER, player_name TEXT, archetype TEXT, decklist_url TEXT);
            CREATE VIEW open_placements AS SELECT p.* FROM placements p JOIN tournaments t ON t.id = p.tournament_id WHERE t.division = 'open';
        """)

        export_matchup_data(conn, tmp_path, labs_conn=None)

        matchup_file = tmp_path / "matchup.json"
        # Should either not exist or have empty archetypes
        if matchup_file.exists():
            data = json.loads(matchup_file.read_text())
            assert data["archetypes"] == []
