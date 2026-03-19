"""Tests for analysis/evolution.py — archetype evolution tracking."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.evolution import compute_archetype_evolution, compute_meta_evolution
from db import SCHEMA


class TestComputeArchetypeEvolution:
    def test_returns_list(self, db):
        result = compute_archetype_evolution(db, "Charizard ex")
        assert isinstance(result, list)

    def test_event_structure(self, db):
        result = compute_archetype_evolution(db, "Charizard ex")
        for event in result:
            assert "week" in event
            assert "adopted" in event
            assert "dropped" in event
            assert isinstance(event["adopted"], list)
            assert isinstance(event["dropped"], list)

    def test_adoption_has_card_info(self, db):
        result = compute_archetype_evolution(db, "Charizard ex")
        for event in result:
            for card in event["adopted"]:
                assert "card" in card
                assert "from_pct" in card
                assert "to_pct" in card

    def test_empty_for_unknown_archetype(self, db):
        result = compute_archetype_evolution(db, "Nonexistent Archetype")
        assert result == []

    def test_empty_for_single_week_archetype(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT INTO tournaments (id, name, date, player_count) VALUES (?, ?, ?, ?)",
            ("t1", "Test", "2026-02-01", 64),
        )
        conn.execute(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            (1, "t1", 1, "Alice", "Test Deck"),
        )
        conn.commit()
        result = compute_archetype_evolution(conn, "Test Deck")
        assert result == []
        conn.close()


class TestComputeMetaEvolution:
    def test_returns_list(self, db):
        result = compute_meta_evolution(db)
        assert isinstance(result, list)

    def test_movement_structure(self, db):
        result = compute_meta_evolution(db)
        for m in result:
            assert "card" in m
            assert "archetype" in m
            assert "direction" in m
            assert m["direction"] in ("adopted", "dropped")
            assert "from_pct" in m
            assert "to_pct" in m
            assert "week" in m

    def test_limited_to_top_n(self, db):
        result = compute_meta_evolution(db, top_n=3)
        assert len(result) <= 3

    def test_sorted_by_recency(self, db):
        result = compute_meta_evolution(db)
        for i in range(len(result) - 1):
            assert result[i]["week"] >= result[i + 1]["week"]
