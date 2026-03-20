"""Tests for analysis/tech_forecast.py — tech card weather forecast."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.tech_forecast import compute_tech_forecast
from db import SCHEMA


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


class TestComputeTechForecast:
    def test_returns_dict_with_cards(self, db):
        result = compute_tech_forecast(db, {"Nest Ball", "Iono"})
        assert isinstance(result, dict)
        assert "generated_at" in result
        assert "cards" in result
        assert isinstance(result["cards"], list)

    def test_card_structure(self, db):
        result = compute_tech_forecast(db, {"Nest Ball"})
        assert len(result["cards"]) == 1
        card = result["cards"][0]
        assert "card_name" in card
        assert "current_adoption_pct" in card
        assert "current_avg_copies" in card
        assert "trend_direction" in card
        assert card["trend_direction"] in ("rising", "falling", "stable", "new")
        assert "trend_delta" in card
        assert "weekly_data" in card
        assert isinstance(card["weekly_data"], list)
        assert "top_archetypes" in card
        assert isinstance(card["top_archetypes"], list)

    def test_weekly_data_entry_structure(self, db):
        result = compute_tech_forecast(db, {"Nest Ball"})
        card = result["cards"][0]
        for entry in card["weekly_data"]:
            assert "week" in entry
            assert "adoption_pct" in entry
            assert "avg_copies" in entry
            assert "deck_count" in entry
            assert "total_decks" in entry

    def test_top_archetypes_entry_structure(self, db):
        result = compute_tech_forecast(db, {"Nest Ball"})
        card = result["cards"][0]
        for arch in card["top_archetypes"]:
            assert "archetype" in arch
            assert "inclusion_pct" in arch
            assert "avg_copies" in arch

    def test_only_watchlist_cards_included(self, db):
        result = compute_tech_forecast(db, {"Nest Ball"})
        names = {c["card_name"] for c in result["cards"]}
        assert names == {"Nest Ball"}

    def test_adoption_pct_calculation(self):
        conn = _make_db()

        # Week 1 (2026-01-05): 4 decks, card in 2 => 50%
        # Week 2 (2026-01-12): 4 decks, card in 4 => 100%
        conn.executemany(
            "INSERT INTO tournaments (id, name, date, player_count) VALUES (?, ?, ?, ?)",
            [
                ("t1", "Week 1 Event", "2026-01-05", 32),
                ("t2", "Week 2 Event", "2026-01-12", 32),
            ],
        )
        placements = [(i, "t1" if i <= 4 else "t2", i, f"P{i}", "Deck A") for i in range(1, 9)]
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            placements,
        )
        # All 8 decks get a filler card so they appear in placement_rows
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [(i, "filler", "Filler Card", 1) for i in range(1, 9)],
        )
        # Target card in placements 1-2 (week 1, 2 of 4 decks) and 5-8 (week 2, all 4 decks)
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [(i, "target", "Target Card", 2) for i in [1, 2, 5, 6, 7, 8]],
        )
        conn.commit()

        result = compute_tech_forecast(conn, {"Target Card"})
        card = result["cards"][0]

        week_map = {entry["week"]: entry for entry in card["weekly_data"]}
        assert len(week_map) == 2

        wk1 = min(week_map)
        wk2 = max(week_map)
        assert week_map[wk1]["adoption_pct"] == 50.0
        assert week_map[wk2]["adoption_pct"] == 100.0

        conn.close()

    def test_avg_copies_calculation(self):
        conn = _make_db()

        conn.execute(
            "INSERT INTO tournaments (id, name, date, player_count) VALUES (?, ?, ?, ?)",
            ("t1", "Test Event", "2026-01-05", 32),
        )
        # 3 decks: 2 include the card (with 3 and 1 copies), 1 does not
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            [(1, "t1", 1, "A", "Deck A"), (2, "t1", 2, "B", "Deck A"), (3, "t1", 3, "C", "Deck A")],
        )
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [
                (1, "filler", "Filler Card", 1),
                (2, "filler", "Filler Card", 1),
                (3, "filler", "Filler Card", 1),
                (1, "target", "Target Card", 3),
                (2, "target", "Target Card", 1),
                # placement 3 does NOT have Target Card
            ],
        )
        conn.commit()

        result = compute_tech_forecast(conn, {"Target Card"})
        card = result["cards"][0]
        # avg_copies = (3 + 1) / 2 = 2.0 (only decks that include it)
        assert card["current_avg_copies"] == 2.0

        conn.close()

    def test_trend_direction_rising(self):
        conn = _make_db()

        # Week 1: card in 1 of 10 decks (10%), Week 2: card in 8 of 10 decks (80%)
        conn.executemany(
            "INSERT INTO tournaments (id, name, date, player_count) VALUES (?, ?, ?, ?)",
            [("t1", "Wk1", "2026-01-05", 64), ("t2", "Wk2", "2026-01-12", 64)],
        )
        placements = [(i, "t1" if i <= 10 else "t2", i, f"P{i}", "Deck A") for i in range(1, 21)]
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            placements,
        )
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [(i, "filler", "Filler Card", 1) for i in range(1, 21)],
        )
        # Card in 1 deck in week 1, 8 decks in week 2
        card_rows = [(1, "target", "Target Card", 2)] + [
            (i, "target", "Target Card", 2) for i in range(11, 19)
        ]
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            card_rows,
        )
        conn.commit()

        result = compute_tech_forecast(conn, {"Target Card"})
        card = result["cards"][0]
        assert card["trend_direction"] == "rising"
        assert card["trend_delta"] > 2.0

        conn.close()

    def test_trend_direction_falling(self):
        conn = _make_db()

        # Week 1: card in 8 of 10 decks (80%), Week 2: card in 1 of 10 decks (10%)
        conn.executemany(
            "INSERT INTO tournaments (id, name, date, player_count) VALUES (?, ?, ?, ?)",
            [("t1", "Wk1", "2026-01-05", 64), ("t2", "Wk2", "2026-01-12", 64)],
        )
        placements = [(i, "t1" if i <= 10 else "t2", i, f"P{i}", "Deck A") for i in range(1, 21)]
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            placements,
        )
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [(i, "filler", "Filler Card", 1) for i in range(1, 21)],
        )
        # Card in 8 decks week 1, 1 deck week 2
        card_rows = [(i, "target", "Target Card", 2) for i in range(1, 9)] + [
            (11, "target", "Target Card", 2)
        ]
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            card_rows,
        )
        conn.commit()

        result = compute_tech_forecast(conn, {"Target Card"})
        card = result["cards"][0]
        assert card["trend_direction"] == "falling"
        assert card["trend_delta"] < -2.0

        conn.close()

    def test_trend_direction_stable(self):
        conn = _make_db()

        # Week 1: 5 of 10 decks (50%), Week 2: 5 of 10 decks (50%) => delta = 0.0
        conn.executemany(
            "INSERT INTO tournaments (id, name, date, player_count) VALUES (?, ?, ?, ?)",
            [("t1", "Wk1", "2026-01-05", 64), ("t2", "Wk2", "2026-01-12", 64)],
        )
        placements = [(i, "t1" if i <= 10 else "t2", i, f"P{i}", "Deck A") for i in range(1, 21)]
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            placements,
        )
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [(i, "filler", "Filler Card", 1) for i in range(1, 21)],
        )
        # 5 decks per week
        card_rows = [
            (i, "target", "Target Card", 2) for i in list(range(1, 6)) + list(range(11, 16))
        ]
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            card_rows,
        )
        conn.commit()

        result = compute_tech_forecast(conn, {"Target Card"})
        card = result["cards"][0]
        assert card["trend_direction"] == "stable"
        assert abs(card["trend_delta"]) <= 2.0

        conn.close()

    def test_trend_direction_new(self):
        conn = _make_db()

        # Week 1: card absent (0%), Week 2: card present (50%)
        conn.executemany(
            "INSERT INTO tournaments (id, name, date, player_count) VALUES (?, ?, ?, ?)",
            [("t1", "Wk1", "2026-01-05", 64), ("t2", "Wk2", "2026-01-12", 64)],
        )
        placements = [(i, "t1" if i <= 4 else "t2", i, f"P{i}", "Deck A") for i in range(1, 9)]
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            placements,
        )
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [(i, "filler", "Filler Card", 1) for i in range(1, 9)],
        )
        # Card only in week 2
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [(i, "target", "Target Card", 2) for i in [5, 6]],
        )
        conn.commit()

        result = compute_tech_forecast(conn, {"Target Card"})
        card = result["cards"][0]
        assert card["trend_direction"] == "new"

        conn.close()

    def test_top_archetypes_limited_to_5(self):
        conn = _make_db()

        conn.execute(
            "INSERT INTO tournaments (id, name, date, player_count) VALUES (?, ?, ?, ?)",
            ("t1", "Big Event", "2026-01-05", 128),
        )
        archetypes = [f"Archetype {i}" for i in range(1, 8)]  # 7 distinct archetypes
        placements = [
            (i, "t1", i, f"P{i}", archetypes[(i - 1) % len(archetypes)]) for i in range(1, 8)
        ]
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            placements,
        )
        # All 7 decks have the filler and the target card
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [(i, "filler", "Filler Card", 1) for i in range(1, 8)]
            + [(i, "target", "Target Card", 2) for i in range(1, 8)],
        )
        conn.commit()

        result = compute_tech_forecast(conn, {"Target Card"})
        card = result["cards"][0]
        assert len(card["top_archetypes"]) <= 5

        conn.close()

    def test_sorted_by_volatility(self):
        conn = _make_db()

        # Two weeks of data so trend deltas can differ
        conn.executemany(
            "INSERT INTO tournaments (id, name, date, player_count) VALUES (?, ?, ?, ?)",
            [("t1", "Wk1", "2026-01-05", 64), ("t2", "Wk2", "2026-01-12", 64)],
        )
        placements = [(i, "t1" if i <= 10 else "t2", i, f"P{i}", "Deck A") for i in range(1, 21)]
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            placements,
        )
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [(i, "filler", "Filler Card", 1) for i in range(1, 21)],
        )
        # Card A: big swing (1 -> 9 of 10 decks)
        # Card B: tiny swing (5 -> 6 of 10 decks)
        card_rows = (
            [(1, "card-a", "Card A", 1)]
            + [(i, "card-a", "Card A", 1) for i in range(11, 20)]
            + [(i, "card-b", "Card B", 1) for i in range(1, 6)]
            + [(i, "card-b", "Card B", 1) for i in range(11, 17)]
        )
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            card_rows,
        )
        conn.commit()

        result = compute_tech_forecast(conn, {"Card A", "Card B"})
        cards = result["cards"]
        assert len(cards) == 2
        assert abs(cards[0]["trend_delta"]) >= abs(cards[1]["trend_delta"])

        conn.close()

    def test_trend_direction_single_week_new(self):
        conn = _make_db()

        conn.execute(
            "INSERT INTO tournaments (id, name, date, player_count, division) VALUES (?, ?, ?, ?, ?)",
            ("t1", "Single Event", "2026-01-05", 32, "open"),
        )
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            [(1, "t1", 1, "A", "Deck A"), (2, "t1", 2, "B", "Deck A")],
        )
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [
                (1, "filler", "Filler Card", 1),
                (2, "filler", "Filler Card", 1),
                (1, "target", "Target Card", 2),
            ],
        )
        conn.commit()

        result = compute_tech_forecast(conn, {"Target Card"})
        card = result["cards"][0]
        assert card["trend_direction"] == "new"
        assert card["trend_delta"] == 0.0
        assert len(card["weekly_data"]) == 1

        conn.close()

    def test_trend_direction_single_week_stable(self):
        conn = _make_db()

        conn.execute(
            "INSERT INTO tournaments (id, name, date, player_count, division) VALUES (?, ?, ?, ?, ?)",
            ("t1", "Single Event", "2026-01-05", 32, "open"),
        )
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            [(1, "t1", 1, "A", "Deck A"), (2, "t1", 2, "B", "Deck A")],
        )
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [(1, "filler", "Filler Card", 1), (2, "filler", "Filler Card", 1)],
        )
        conn.commit()

        # "Absent Card" is in watchlist but in zero decks => 0% adoption => stable
        result = compute_tech_forecast(conn, {"Absent Card"})
        card = result["cards"][0]
        assert card["trend_direction"] == "stable"
        assert card["trend_delta"] == 0.0

        conn.close()

    def test_top_archetypes_sorted_by_inclusion_pct(self):
        conn = _make_db()

        conn.execute(
            "INSERT INTO tournaments (id, name, date, player_count, division) VALUES (?, ?, ?, ?, ?)",
            ("t1", "Big Event", "2026-01-05", 128, "open"),
        )
        # Archetype A: 1 deck with card out of 3 total (33.3%)
        # Archetype B: 2 decks with card out of 2 total (100%)
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (1, "t1", 1, "P1", "Archetype A"),
                (2, "t1", 2, "P2", "Archetype A"),
                (3, "t1", 3, "P3", "Archetype A"),
                (4, "t1", 4, "P4", "Archetype B"),
                (5, "t1", 5, "P5", "Archetype B"),
            ],
        )
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [(i, "filler", "Filler Card", 1) for i in range(1, 6)]
            + [
                (1, "target", "Target Card", 2),
                (4, "target", "Target Card", 3),
                (5, "target", "Target Card", 1),
            ],
        )
        conn.commit()

        result = compute_tech_forecast(conn, {"Target Card"})
        card = result["cards"][0]
        archetypes = card["top_archetypes"]
        assert len(archetypes) == 2
        assert archetypes[0]["archetype"] == "Archetype B"
        assert archetypes[0]["inclusion_pct"] == 100.0
        assert archetypes[1]["archetype"] == "Archetype A"
        assert archetypes[1]["inclusion_pct"] == 33.3

        conn.close()

    def test_division_filter_excludes_non_open(self):
        conn = _make_db()

        # Open tournament: 2 decks, both have card => 100%
        # Junior tournament: 2 decks, neither has card
        conn.executemany(
            "INSERT INTO tournaments (id, name, date, player_count, division) VALUES (?, ?, ?, ?, ?)",
            [
                ("t1", "Open Event", "2026-01-05", 32, "open"),
                ("t2", "Junior Event", "2026-01-05", 16, "junior"),
            ],
        )
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (1, "t1", 1, "A", "Deck A"),
                (2, "t1", 2, "B", "Deck A"),
                (3, "t2", 1, "C", "Deck B"),
                (4, "t2", 2, "D", "Deck B"),
            ],
        )
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [
                (1, "filler", "Filler Card", 1),
                (2, "filler", "Filler Card", 1),
                (3, "filler", "Filler Card", 1),
                (4, "filler", "Filler Card", 1),
                (1, "target", "Target Card", 2),
                (2, "target", "Target Card", 2),
            ],
        )
        conn.commit()

        result = compute_tech_forecast(conn, {"Target Card"})
        card = result["cards"][0]
        # Should be 100% (2/2 open decks), not 50% (2/4 total decks)
        assert card["current_adoption_pct"] == 100.0

        conn.close()

    def test_empty_watchlist(self, db):
        result = compute_tech_forecast(db, set())
        assert result["cards"] == []

    def test_empty_database(self):
        conn = _make_db()
        conn.commit()

        result = compute_tech_forecast(conn, {"Nest Ball"})
        assert result["cards"] == []

        conn.close()

    def test_jp_card_names_resolved_to_en(self):
        conn = _make_db()

        # Set up a cards table entry for JP→EN mapping
        conn.execute(
            "INSERT INTO cards (id, name_en, name_jp, set_code) VALUES (?, ?, ?, ?)",
            ("SV-001", "Nest Ball", "ネストボール", "SV1"),
        )
        conn.execute(
            "INSERT INTO tournaments (id, name, date, player_count, division) VALUES (?, ?, ?, ?, ?)",
            ("t1", "Event", "2026-01-05", 32, "open"),
        )
        conn.executemany(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?, ?)",
            [(1, "t1", 1, "A", "Deck A"), (2, "t1", 2, "B", "Deck A")],
        )
        # Card stored with JP name in decklist_cards
        conn.executemany(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            [
                (1, "filler", "Filler Card", 1),
                (2, "filler", "Filler Card", 1),
                (1, "SV-001", "ネストボール", 2),
                (2, "SV-001", "ネストボール", 3),
            ],
        )
        conn.commit()

        # Watchlist uses EN name, should still match JP entries
        result = compute_tech_forecast(conn, {"Nest Ball"})
        assert len(result["cards"]) == 1
        card = result["cards"][0]
        assert card["card_name"] == "Nest Ball"
        assert card["current_adoption_pct"] == 100.0
        assert card["current_avg_copies"] == 2.5  # (2 + 3) / 2

        conn.close()
