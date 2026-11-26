"""snapshot_open_views: TEMP tables that shadow the dedup views during exports.

The views re-run a correlated dedup query on every read. The snapshot must
return the same rows, be visible to unqualified queries, and leave the views
in charge again once the block exits, also on error.
"""

import sqlite3

import pytest

from db import init_db, snapshot_open_views

VIEWS = ("open_placements", "open_tournaments")


def _rows(conn: sqlite3.Connection, name: str) -> list[tuple]:
    return [tuple(r) for r in conn.execute(f"SELECT * FROM {name} ORDER BY id")]


def _temp_objects(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM temp.sqlite_master")}


class TestSnapshotOpenViews:
    @pytest.mark.parametrize("view", VIEWS)
    def test_snapshot_returns_the_view_rows(self, db, view):
        expected = _rows(db, view)
        assert expected, "fixture should exercise non-empty views"
        with snapshot_open_views(db):
            assert _rows(db, view) == expected

    def test_unqualified_names_resolve_to_the_snapshot(self, db):
        with snapshot_open_views(db):
            kinds = dict(db.execute("SELECT name, type FROM temp.sqlite_master").fetchall())
            assert kinds["open_placements"] == "table"
            assert kinds["open_tournaments"] == "table"
            # A change under the snapshot stays invisible: proof the query read
            # the TEMP table and not the view.
            before = _rows(db, "open_placements")
            db.execute("UPDATE main.placements SET archetype = 'Changed Under Snapshot'")
            assert _rows(db, "open_placements") == before

    def test_views_take_over_again_after_exit(self, db):
        with snapshot_open_views(db):
            pass
        assert not set(VIEWS) & _temp_objects(db)
        assert {
            r[0] for r in db.execute("SELECT name FROM main.sqlite_master WHERE type='view'")
        } >= set(VIEWS)

    def test_snapshot_is_dropped_when_the_block_raises(self, db):
        with pytest.raises(RuntimeError), snapshot_open_views(db):
            raise RuntimeError("export failed")
        assert not set(VIEWS) & _temp_objects(db)

    def test_init_db_inside_a_snapshot_still_rebuilds_the_views(self, db):
        """init_db drops the views by their main. name, never the TEMP table."""
        with snapshot_open_views(db):
            init_db(db)
            assert {"open_placements", "open_tournaments"} <= _temp_objects(db)
        assert _rows(db, "open_placements")
