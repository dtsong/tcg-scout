"""Tests for division-based filtering across the pipeline."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.meta import compute_meta_snapshot
from scraper.pokemon_jp_api import LEAGUE_NAME_MAP, JPCityLeagueEvent


class TestOpenPlacementsView:
    def test_excludes_non_open_tournaments(self, db):
        """open_placements view should only return placements from open-division tournaments."""
        all_count = db.execute("SELECT COUNT(*) FROM placements").fetchone()[0]
        open_count = db.execute("SELECT COUNT(*) FROM open_placements").fetchone()[0]

        # t4 has division='senior' with 1 placement, so open should be 1 less
        assert open_count == all_count - 1

    def test_open_placements_columns_match(self, db):
        """open_placements view should have same columns as placements table."""
        placement_cols = [row[1] for row in db.execute("PRAGMA table_info(placements)")]
        # Views don't support PRAGMA table_info, so check via query
        open_row = db.execute("SELECT * FROM open_placements LIMIT 1").fetchone()
        assert open_row is not None
        for col in placement_cols:
            assert open_row[col] is not None or col == "player_name"  # Allow nulls in player_name


class TestMetaSnapshotDivisionFilter:
    def test_excludes_senior_division(self, db):
        """compute_meta_snapshot should only count open-division tournaments."""
        snapshot_id = compute_meta_snapshot(db)

        snapshot = db.execute(
            "SELECT tournament_count, deck_count FROM meta_snapshots WHERE id = ?",
            (snapshot_id,),
        ).fetchone()

        # 3 open tournaments, not 4 (t4 is senior)
        assert snapshot["tournament_count"] == 3
        # 6 open placements, not 7 (placement 7 is in senior tournament t4)
        assert snapshot["deck_count"] == 6

    def test_senior_placement_not_in_archetype_stats(self, db):
        """Senior division placements should not affect archetype deck counts."""
        snapshot_id = compute_meta_snapshot(db)

        charizard = db.execute(
            "SELECT deck_count FROM archetype_stats WHERE snapshot_id = ? AND archetype = 'Charizard ex'",
            (snapshot_id,),
        ).fetchone()

        # 3 open Charizard placements, not 4 (Greta's is in senior division)
        assert charizard["deck_count"] == 3


class TestLeagueNameMap:
    def test_known_open(self):
        assert LEAGUE_NAME_MAP["オープン"] == "open"

    def test_known_senior(self):
        assert LEAGUE_NAME_MAP["シニア"] == "senior"

    def test_known_junior(self):
        assert LEAGUE_NAME_MAP["ジュニア"] == "junior"

    def test_unknown_defaults_to_open(self):
        """Unknown league names should default to open with logging."""
        event = JPCityLeagueEvent.from_api(
            {
                "event_holding_id": 999,
                "event_date_params": "20260301",
                "leagueName": "未知のリーグ",
            }
        )
        assert event.division == "open"

    def test_missing_key_defaults_to_open(self):
        """Missing leagueName key should default to open."""
        event = JPCityLeagueEvent.from_api(
            {
                "event_holding_id": 999,
                "event_date_params": "20260301",
            }
        )
        assert event.division == "open"


try:
    from scraper.pokemon_jp import (
        _TOURNAMENT_DIVISION,
        JPEventResult,
        JPPlacement,
        store_cl_city_league_results,
    )

    _POKEMON_JP_AVAILABLE = True
except ImportError:
    _POKEMON_JP_AVAILABLE = False


@pytest.mark.skipif(not _POKEMON_JP_AVAILABLE, reason="scraper.pokemon_jp requires 'kernel' module")
class TestTournamentDivisionNormalization:
    def test_masters_maps_to_open(self):
        assert _TOURNAMENT_DIVISION["masters"] == "open"

    def test_seniors_maps_to_senior(self):
        assert _TOURNAMENT_DIVISION["seniors"] == "senior"

    def test_juniors_maps_to_junior(self):
        assert _TOURNAMENT_DIVISION["juniors"] == "junior"

    def test_store_normalizes_division(self, db):
        """store_cl_city_league_results should store 'open' not 'masters' in tournaments."""
        event = JPEventResult(
            event_id=88888,
            event_name="Test CL",
            division="masters",
            date="2026-03-15",
            placements=[
                JPPlacement(standing=1, player_name="Test", region="Tokyo"),
            ],
        )
        store_cl_city_league_results(db, event, decklists={})

        tournament = db.execute("SELECT division FROM tournaments WHERE id = 'jp-88888'").fetchone()
        assert tournament["division"] == "open"
