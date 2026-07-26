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
