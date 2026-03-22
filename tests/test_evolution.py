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
    def test_returns_dict_with_highlights_and_movements(self, db):
        result = compute_meta_evolution(db)
        assert isinstance(result, dict)
        assert "highlights" in result
        assert "movements" in result
        assert isinstance(result["highlights"], list)
        assert isinstance(result["movements"], list)

    def test_movement_structure(self, db):
        result = compute_meta_evolution(db)
        for m in result["movements"]:
            assert "card" in m
            assert "archetype" in m
            assert "archetype_slug" in m
            # Slug must be lowercase with no spaces
            assert m["archetype_slug"] == m["archetype_slug"].lower()
            assert " " not in m["archetype_slug"]
            assert "deck_count" in m
            assert isinstance(m["deck_count"], int)
            assert "direction" in m
            assert m["direction"] in ("adopted", "dropped")
            assert "from_pct" in m
            assert "to_pct" in m
            assert "delta" in m
            assert "week" in m

    def test_limited_to_top_n(self, db):
        result = compute_meta_evolution(db, top_n=3)
        assert len(result["highlights"]) <= 3

    def test_highlights_subset_of_movements(self, db):
        result = compute_meta_evolution(db)
        assert len(result["highlights"]) <= len(result["movements"])
        for h in result["highlights"]:
            assert h in result["movements"]

    def test_sorted_by_recency(self, db):
        result = compute_meta_evolution(db)
        movements = result["movements"]
        for i in range(len(movements) - 1):
            assert movements[i]["week"] >= movements[i + 1]["week"]


class TestDecklistDenominator:
    """Inclusion rates should only count placements that have decklists."""

    def test_placements_without_decklists_excluded_from_denominator(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)

        # Two weeks of tournaments
        conn.executemany(
            "INSERT INTO tournaments (id, name, date, player_count) VALUES (?, ?, ?, ?)",
            [
                ("t1", "Week 1", "2026-01-20", 64),
                ("t2", "Week 2", "2026-01-27", 64),
            ],
        )

        # Week 1: 1 placement WITH decklist containing Night Stretcher
        # Week 2: 3 placements but only 1 has a decklist (also with Night Stretcher)
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (1, "t1", 1, "Alice", "Mega Lucario"),
                (2, "t2", 1, "Bob", "Mega Lucario"),
                (3, "t2", 2, "Charlie", "Mega Lucario"),  # no decklist
                (4, "t2", 3, "Diana", "Mega Lucario"),  # no decklist
            ],
        )

        # Decklists: only placements 1 and 2 have decklist data
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [
                (1, "card-ns", "Night Stretcher", 2),
                (1, "card-ub", "Ultra Ball", 4),
                (2, "card-ns", "Night Stretcher", 2),
                (2, "card-ub", "Ultra Ball", 4),
            ],
        )
        conn.commit()

        result = compute_archetype_evolution(conn, "Mega Lucario")

        # Night Stretcher is at 100% both weeks (1/1 and 1/1 decklist placements).
        # Without the fix, week 2 would show 1/3 = 33%, triggering a false "drop".
        # With the fix, no drop events should be reported for Night Stretcher.
        for event in result:
            dropped_cards = [c["card"] for c in event["dropped"]]
            assert "Night Stretcher" not in dropped_cards, (
                f"Night Stretcher falsely reported as dropped: {event}"
            )

        conn.close()

    def test_week_with_no_decklists_skipped(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)

        conn.executemany(
            "INSERT INTO tournaments (id, name, date, player_count) VALUES (?, ?, ?, ?)",
            [
                ("t1", "Week 1", "2026-01-20", 64),
                ("t2", "Week 2", "2026-01-27", 64),
            ],
        )

        # Week 1: placement with decklist; Week 2: placement without decklist
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (1, "t1", 1, "Alice", "Test Deck"),
                (2, "t2", 1, "Bob", "Test Deck"),  # no decklist
            ],
        )

        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [
                (1, "card-ns", "Night Stretcher", 2),
            ],
        )
        conn.commit()

        result = compute_archetype_evolution(conn, "Test Deck")

        # Week 2 has no decklists, so no comparison should happen.
        # Without the fix, Night Stretcher would show 100% -> 0% (false drop).
        for event in result:
            dropped_cards = [c["card"] for c in event["dropped"]]
            assert "Night Stretcher" not in dropped_cards

        conn.close()


class TestJpEnCardNameMerging:
    """JP and EN card names for the same card must be merged before computing rates."""

    def test_mixed_languages_no_false_adoption(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)

        # Simulate card_mappings for JP->EN translation
        conn.executemany(
            "INSERT INTO cards (id, name_en, name_jp, set_code) VALUES (?, ?, ?, ?)",
            [
                ("c-ns", "Night Stretcher", "夜のタンカ", "SV1"),
                ("c-bo", "Boss's Orders", "ボスの指令", "SV1"),
            ],
        )

        # Two weeks of tournaments
        conn.executemany(
            "INSERT INTO tournaments (id, name, date, player_count) VALUES (?, ?, ?, ?)",
            [
                ("t1", "Week 1 JP", "2026-03-10", 64),
                ("t2", "Week 2 EN", "2026-03-17", 32),
            ],
        )

        # Week 1: 3 JP placements with decklists
        # Week 2: 2 EN placements with decklists
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (1, "t1", 1, "Player A", "Archaludon ex"),
                (2, "t1", 2, "Player B", "Archaludon ex"),
                (3, "t1", 3, "Player C", "Archaludon ex"),
                (4, "t2", 1, "Player D", "Archaludon ex"),
                (5, "t2", 2, "Player E", "Archaludon ex"),
            ],
        )

        # Week 1 decklists: JP card names, all 3 have Night Stretcher and Boss's Orders
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [
                (1, "c-ns", "夜のタンカ", 2),
                (1, "c-bo", "ボスの指令", 2),
                (2, "c-ns", "夜のタンカ", 2),
                (2, "c-bo", "ボスの指令", 2),
                (3, "c-ns", "夜のタンカ", 2),
                (3, "c-bo", "ボスの指令", 2),
                # Week 2 decklists: EN card names, both have same cards
                (4, "c-ns", "Night Stretcher", 2),
                (4, "c-bo", "Boss's Orders", 2),
                (5, "c-ns", "Night Stretcher", 2),
                (5, "c-bo", "Boss's Orders", 2),
            ],
        )
        conn.commit()

        from analysis.card_stats import build_jp_en_lookup

        lookup = build_jp_en_lookup(conn)
        result = compute_archetype_evolution(conn, "Archaludon ex", jp_en_lookup=lookup)

        # Both cards are at 100% in both weeks (JP and EN names merged).
        # Without the fix: JP names treated as separate cards ->
        #   "Night Stretcher" goes from 0% to 100% (false adoption)
        #   "夜のタンカ" goes from 100% to 0% (false drop)
        for event in result:
            adopted_cards = [c["card"] for c in event["adopted"]]
            dropped_cards = [c["card"] for c in event["dropped"]]
            assert "Night Stretcher" not in adopted_cards, (
                f"Night Stretcher falsely reported as adopted: {event}"
            )
            assert "Boss's Orders" not in adopted_cards, (
                f"Boss's Orders falsely reported as adopted: {event}"
            )
            assert "Night Stretcher" not in dropped_cards
            assert "Boss's Orders" not in dropped_cards

        conn.close()

    def test_without_lookup_names_split(self):
        """Without jp_en_lookup, JP and EN names are separate (regression guard)."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)

        conn.executemany(
            "INSERT INTO tournaments (id, name, date, player_count) VALUES (?, ?, ?, ?)",
            [
                ("t1", "Week 1", "2026-03-10", 64),
                ("t2", "Week 2", "2026-03-17", 32),
            ],
        )

        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (1, "t1", 1, "A", "Test Deck"),
                (2, "t2", 1, "B", "Test Deck"),
            ],
        )

        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [
                (1, "c-ns", "夜のタンカ", 2),
                (2, "c-ns", "Night Stretcher", 2),
            ],
        )
        conn.commit()

        # Without lookup, "Night Stretcher" goes from 0% -> 100% (adoption event)
        result = compute_archetype_evolution(conn, "Test Deck", jp_en_lookup=None)
        all_adopted = []
        for event in result:
            all_adopted.extend(c["card"] for c in event["adopted"])
        assert "Night Stretcher" in all_adopted

        conn.close()

    def test_jp_energy_names_filtered_after_translation(self):
        """Japanese energy names should be filtered out after translation."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)

        conn.executemany(
            "INSERT INTO cards (id, name_en, name_jp, set_code) VALUES (?, ?, ?, ?)",
            [
                ("e-psy", "Psychic Energy", "基本超エネルギー", "SV1"),
                ("c-ns", "Night Stretcher", "夜のタンカ", "SV1"),
            ],
        )

        conn.executemany(
            "INSERT INTO tournaments (id, name, date, player_count) VALUES (?, ?, ?, ?)",
            [
                ("t1", "Week 1", "2026-03-10", 64),
                ("t2", "Week 2", "2026-03-17", 32),
            ],
        )

        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (1, "t1", 1, "A", "Test Deck"),
                (2, "t2", 1, "B", "Test Deck"),
            ],
        )

        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [
                (1, "c-ns", "夜のタンカ", 2),
                (1, "e-psy", "基本超エネルギー", 8),
                (2, "c-ns", "Night Stretcher", 2),
                (2, "e-psy", "Psychic Energy", 8),
            ],
        )
        conn.commit()

        from analysis.card_stats import build_jp_en_lookup

        lookup = build_jp_en_lookup(conn)
        result = compute_archetype_evolution(conn, "Test Deck", jp_en_lookup=lookup)

        # Energy cards should not appear in any events
        for event in result:
            all_cards = [c["card"] for c in event["adopted"]] + [
                c["card"] for c in event["dropped"]
            ]
            assert "Psychic Energy" not in all_cards
            assert "基本超エネルギー" not in all_cards

        conn.close()
