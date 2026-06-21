"""Tests for db.py — connection helpers and schema management."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import SCHEMA, get_connection, get_format_connection, init_db, reset_db


class TestOpenPlacementsDeduplication:
    """open_placements view must not double-count events that appear in both
    the JP API (id LIKE 'jp-%') and Limitless (URL id) sources on the same date."""

    def _make_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        return conn

    def test_excludes_limitless_when_jp_api_covers_same_date(self):
        conn = self._make_db()
        # Same date, same division — both sources
        conn.executemany(
            "INSERT INTO tournaments (id, name, date, division) VALUES (?, ?, ?, ?)",
            [
                ("jp-952716", "埼玉県 somestore", "2026-03-21", "open"),
                (
                    "https://limitlesstcg.com/tournaments/jp/4359",
                    "City League Saitama",
                    "2026-03-21",
                    "open",
                ),
            ],
        )
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) VALUES (?, ?, ?, ?, ?)",
            [
                (1, "jp-952716", 1, "Alice", "Charizard ex"),
                (2, "jp-952716", 2, "Bob", "Dragapult ex"),
                (3, "https://limitlesstcg.com/tournaments/jp/4359", 1, "Alice", "Charizard ex"),
                (4, "https://limitlesstcg.com/tournaments/jp/4359", 2, "Bob", "Dragapult ex"),
            ],
        )
        conn.commit()

        rows = conn.execute("SELECT * FROM open_placements").fetchall()
        tournament_ids = {r["tournament_id"] for r in rows}

        assert "jp-952716" in tournament_ids
        assert "https://limitlesstcg.com/tournaments/jp/4359" not in tournament_ids
        assert len(rows) == 2  # 2 JP placements, not 4

    def test_includes_same_date_different_store_events(self):
        conn = self._make_db()
        conn.executemany(
            "INSERT INTO tournaments (id, name, date, division, store_name) VALUES (?, ?, ?, ?, ?)",
            [
                ("jp-952716", "埼玉県 Store A", "2026-03-21", "open", "Store A"),
                (
                    "https://limitlesstcg.com/tournaments/jp/4360",
                    "City League Store B",
                    "2026-03-21",
                    "open",
                    "Store B",
                ),
            ],
        )
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) VALUES (?, ?, ?, ?, ?)",
            [
                (1, "jp-952716", 1, "Alice", "Charizard ex"),
                (2, "https://limitlesstcg.com/tournaments/jp/4360", 1, "Carol", "Gardevoir ex"),
            ],
        )
        conn.commit()

        rows = conn.execute("SELECT * FROM open_placements ORDER BY id").fetchall()

        assert [r["tournament_id"] for r in rows] == [
            "jp-952716",
            "https://limitlesstcg.com/tournaments/jp/4360",
        ]

    def test_includes_limitless_when_no_jp_api_on_that_date(self):
        conn = self._make_db()
        # Limitless-only date
        conn.execute(
            "INSERT INTO tournaments (id, name, date, division) VALUES (?, ?, ?, ?)",
            (
                "https://limitlesstcg.com/tournaments/jp/4300",
                "City League Aichi",
                "2026-03-17",
                "open",
            ),
        )
        conn.execute(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) VALUES (?, ?, ?, ?, ?)",
            (1, "https://limitlesstcg.com/tournaments/jp/4300", 1, "Carol", "Raging Bolt ex"),
        )
        conn.commit()

        rows = conn.execute("SELECT * FROM open_placements").fetchall()
        assert len(rows) == 1
        assert rows[0]["tournament_id"] == "https://limitlesstcg.com/tournaments/jp/4300"

    def test_deduplication_is_per_division(self):
        conn = self._make_db()
        # JP API has open; Limitless has senior — both should be included
        conn.executemany(
            "INSERT INTO tournaments (id, name, date, division) VALUES (?, ?, ?, ?)",
            [
                ("jp-100001", "Store Open", "2026-03-21", "open"),
                (
                    "https://limitlesstcg.com/tournaments/jp/9999",
                    "City League Senior",
                    "2026-03-21",
                    "senior",
                ),
            ],
        )
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) VALUES (?, ?, ?, ?, ?)",
            [
                (1, "jp-100001", 1, "Dave", "Charizard ex"),
                (2, "https://limitlesstcg.com/tournaments/jp/9999", 1, "Eve", "Dragapult ex"),
            ],
        )
        conn.commit()

        rows = conn.execute("SELECT * FROM open_placements").fetchall()
        # Only open division; senior Limitless event is not open so excluded by existing filter
        assert len(rows) == 1
        assert rows[0]["tournament_id"] == "jp-100001"


class TestGetFormatConnection:
    def test_returns_connection(self, tmp_path, monkeypatch):
        monkeypatch.setattr("db.DATA_DIR", tmp_path)
        conn = get_format_connection("nihil-zero")
        assert isinstance(conn, sqlite3.Connection)
        # Verify row_factory is set
        conn.execute("CREATE TABLE t (a TEXT)")
        conn.execute("INSERT INTO t VALUES ('x')")
        row = conn.execute("SELECT a FROM t").fetchone()
        assert row["a"] == "x"
        conn.close()

    def test_creates_data_dir(self, tmp_path, monkeypatch):
        data_dir = tmp_path / "subdir" / "data"
        monkeypatch.setattr("db.DATA_DIR", data_dir)
        conn = get_format_connection("nihil-zero")
        assert data_dir.exists()
        conn.close()


class TestGetConnection:
    def test_returns_default_format_connection(self, tmp_path, monkeypatch):
        monkeypatch.setattr("db.DATA_DIR", tmp_path)
        conn = get_connection()
        assert isinstance(conn, sqlite3.Connection)
        conn.close()


class TestInitDb:
    def test_creates_tables_on_existing_conn(self):
        conn = sqlite3.connect(":memory:")
        init_db(conn)
        tables = [
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]
        assert "cards" in tables
        assert "tournaments" in tables
        assert "placements" in tables
        conn.close()

    def test_creates_tables_without_conn(self, tmp_path, monkeypatch):
        monkeypatch.setattr("db.DATA_DIR", tmp_path)
        init_db()
        # Verify file was created and has tables
        from config import DEFAULT_FORMAT, FORMATS

        db_path = tmp_path / FORMATS[DEFAULT_FORMAT]["db_name"]
        assert db_path.exists()


class TestMigrations:
    def test_adds_weighted_share_to_existing_db(self):
        """Simulate upgrading a DB that predates the weighted_share column."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        # Create schema without weighted_share
        conn.execute(
            """CREATE TABLE archetype_stats (
                snapshot_id INTEGER,
                archetype TEXT,
                meta_share REAL,
                deck_count INTEGER,
                best_placement INTEGER,
                tier TEXT,
                PRIMARY KEY (snapshot_id, archetype)
            )"""
        )
        # Also need the other tables for init_db to succeed
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tournaments (id TEXT PRIMARY KEY, name TEXT, date TEXT, player_count INTEGER, division TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS cards (id TEXT PRIMARY KEY, name_en TEXT NOT NULL)"
        )
        conn.execute("CREATE TABLE IF NOT EXISTS placements (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE IF NOT EXISTS decklist_cards (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE IF NOT EXISTS cl_events (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE IF NOT EXISTS cl_placements (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE IF NOT EXISTS cl_decklist_cards (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE IF NOT EXISTS meta_snapshots (id INTEGER PRIMARY KEY)")
        conn.commit()

        # Verify column doesn't exist yet
        cols = {row[1] for row in conn.execute("PRAGMA table_info(archetype_stats)")}
        assert "weighted_share" not in cols

        init_db(conn)

        # Verify migration added the column
        cols = {row[1] for row in conn.execute("PRAGMA table_info(archetype_stats)")}
        assert "weighted_share" in cols
        conn.close()


class TestResetDb:
    def test_drops_and_recreates(self, tmp_path, monkeypatch):
        monkeypatch.setattr("db.DATA_DIR", tmp_path)
        # Create initial DB with some data
        conn = get_format_connection("nihil-zero")
        init_db(conn)
        conn.execute("INSERT INTO tournaments (id, name, date) VALUES ('t1', 'Test', '2026-01-01')")
        conn.commit()
        conn.close()

        # Reset should wipe everything
        reset_db("nihil-zero")
        conn = get_format_connection("nihil-zero")
        count = conn.execute("SELECT COUNT(*) FROM tournaments").fetchone()[0]
        assert count == 0
        conn.close()

    def test_reset_nonexistent_db(self, tmp_path, monkeypatch):
        monkeypatch.setattr("db.DATA_DIR", tmp_path)
        # Should work even if DB doesn't exist yet
        reset_db("nihil-zero")
        from config import FORMATS

        db_path = tmp_path / FORMATS["nihil-zero"]["db_name"]
        assert db_path.exists()
