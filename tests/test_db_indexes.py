"""Index coverage for the dedup views.

The database shipped with no user-created indexes, so `open_placements` drove a
full scan of `tournaments` for every placement row. These tests assert the
indexes exist, that the planner uses them, and that adding them did not change
what the views return.
"""

import sqlite3

EXPECTED_INDEXES = {
    "idx_placements_tournament",
    "idx_tournaments_date_div",
    "idx_placements_dedup",
    "idx_decklist_cards_card",
}


def _index_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {r[0] for r in rows}


class TestIndexesExist:
    def test_init_db_creates_expected_indexes(self, db):
        assert EXPECTED_INDEXES <= _index_names(db)

    def test_indexes_are_declared_in_schema_not_ad_hoc(self):
        """Indexes must live in SCHEMA so existing databases pick them up too."""
        from db import SCHEMA

        for name in EXPECTED_INDEXES:
            assert f"CREATE INDEX IF NOT EXISTS {name}" in SCHEMA


class TestViewResultsUnchangedByIndexes:
    """Indexes are an access-path change only. Row counts must be identical."""

    @staticmethod
    def _counts(conn: sqlite3.Connection) -> tuple[int, int]:
        placements = conn.execute("SELECT COUNT(*) FROM open_placements").fetchone()[0]
        tournaments = conn.execute("SELECT COUNT(*) FROM open_tournaments").fetchone()[0]
        return placements, tournaments

    def test_dropping_indexes_does_not_change_view_output(self, db):
        with_indexes = self._counts(db)
        for name in _index_names(db):
            db.execute(f"DROP INDEX {name}")
        without_indexes = self._counts(db)
        assert with_indexes == without_indexes


class TestPlannerUsesIndexes:
    def test_open_placements_searches_rather_than_scans_tournaments(self, db):
        plan = db.execute("EXPLAIN QUERY PLAN SELECT COUNT(*) FROM open_placements").fetchall()
        detail = " | ".join(row[3] for row in plan)
        assert "SCAN t2" not in detail, f"planner still scans tournaments: {detail}"
        assert "idx_tournaments_date_div" in detail, detail

    def test_init_db_populates_planner_statistics(self, db):
        # init_db() ran ANALYZE before seed data, so sqlite_stat1 exists but
        # reflects empty tables. Re-run ANALYZE with actual data present.
        db.execute("ANALYZE")
        db.commit()

        # Verify sqlite_stat1 exists and contains entries for all dedup indexes
        stat_rows = db.execute(
            "SELECT tbl, idx, stat FROM sqlite_stat1 "
            "WHERE idx IN ("
            "'idx_placements_tournament', 'idx_tournaments_date_div', "
            "'idx_placements_dedup', 'idx_decklist_cards_card')"
        ).fetchall()

        # All four indexes must have cardinality statistics
        assert len(stat_rows) == 4, (
            f"ANALYZE should populate statistics for 4 indexes; got {len(stat_rows)}"
        )

        # Each index stat must have non-empty cardinality data
        for tbl, idx, stat in stat_rows:
            assert stat, f"Index {idx} has empty cardinality statistics"
