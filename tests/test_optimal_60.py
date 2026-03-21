"""Tests for analysis.optimal_60 — CL-boosted weighted consensus."""

import sqlite3

import pytest

from db import SCHEMA


@pytest.fixture()
def db_with_cl() -> sqlite3.Connection:
    """In-memory DB with both City League and Champions League data.

    Layout:
    - 3 City League tournaments (open division, tournament_type='city-league')
    - 1 Champions League tournament (open division, tournament_type='champions-league')
    - Archetype "Charizard ex":
        - 4 City League placements (standings 1, 4, 9, 16)
        - 3 CL placements (standings 1, 2, 4)
    - Archetype "Dragapult ex":
        - 2 City League placements (standings 2, 8)
        - 1 CL placement (standing 3)  -- below min_cl_decks threshold
    - Cards differ between CL and meta to test divergence metrics
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)

    # City League tournaments
    conn.executemany(
        "INSERT INTO tournaments (id, name, date, player_count, division, tournament_type) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("cl-t1", "Osaka CL", "2026-01-25", 64, "open", "city-league"),
            ("cl-t2", "Tokyo CL", "2026-02-10", 64, "open", "city-league"),
            ("cl-t3", "Nagoya CL", "2026-03-01", 64, "open", "city-league"),
            ("cl-fukuoka", "Fukuoka CL 2026", "2026-03-20", 7000, "open", "champions-league"),
        ],
    )

    # City League placements — Charizard ex
    conn.executemany(
        "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (1, "cl-t1", 1, "Alice", "Charizard ex"),
            (2, "cl-t2", 4, "Charlie", "Charizard ex"),
            (3, "cl-t3", 9, "Eve", "Charizard ex"),
            (4, "cl-t3", 16, "Grace", "Charizard ex"),
            # City League — Dragapult ex
            (5, "cl-t1", 2, "Bob", "Dragapult ex"),
            (6, "cl-t2", 8, "Diana", "Dragapult ex"),
            # CL placements — Charizard ex
            (10, "cl-fukuoka", 1, "CL-Winner", "Charizard ex"),
            (11, "cl-fukuoka", 2, "CL-Runner", "Charizard ex"),
            (12, "cl-fukuoka", 4, "CL-Fourth", "Charizard ex"),
            # CL — Dragapult ex (only 1, below min_cl_decks=3)
            (13, "cl-fukuoka", 3, "CL-Third", "Dragapult ex"),
        ],
    )

    # Decklist cards
    rows = []

    # --- Charizard ex City League decklists ---
    # All 4 City League placements have these "meta staple" cards
    for pid in [1, 2, 3, 4]:
        rows.append((pid, "card-nest", "Nest Ball", 4))
        rows.append((pid, "card-ultra", "Ultra Ball", 4))
        rows.append((pid, "card-boss", "Boss's Orders", 2))
        rows.append((pid, "card-char", "Charizard ex", 3))

    # Only placement 1 and 2 have Arven (meta flex card)
    rows.append((1, "card-arven", "Arven", 2))
    rows.append((2, "card-arven", "Arven", 2))

    # --- Charizard ex CL decklists ---
    for pid in [10, 11, 12]:
        rows.append((pid, "card-nest", "Nest Ball", 4))
        rows.append((pid, "card-ultra", "Ultra Ball", 4))
        rows.append((pid, "card-char", "Charizard ex", 3))
        # CL players run Switch (CL breakout card — not in City League lists)
        rows.append((pid, "card-switch", "Switch", 3))

    # CL players run Boss's Orders at 1 copy instead of 2
    rows.append((10, "card-boss", "Boss's Orders", 1))
    rows.append((11, "card-boss", "Boss's Orders", 1))
    rows.append((12, "card-boss", "Boss's Orders", 1))

    # --- Dragapult ex decklists ---
    for pid in [5, 6]:
        rows.append((pid, "card-nest", "Nest Ball", 4))
        rows.append((pid, "card-drag", "Dragapult ex", 3))
    rows.append((13, "card-nest", "Nest Ball", 4))
    rows.append((13, "card-drag", "Dragapult ex", 3))

    conn.executemany(
        "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
        rows,
    )

    conn.commit()
    yield conn
    conn.close()


class TestComputeOptimal60:
    def test_returns_none_for_few_decklists(self, db_with_cl):
        from analysis.optimal_60 import compute_optimal_60

        result = compute_optimal_60(db_with_cl, "Nonexistent Deck")
        assert result is None

    def test_basic_output_shape(self, db_with_cl):
        from analysis.optimal_60 import compute_optimal_60

        result = compute_optimal_60(db_with_cl, "Charizard ex")
        assert result is not None
        assert "quality_score" in result
        assert "cards" in result
        assert "cl_deck_count" in result
        assert "city_league_deck_count" in result
        assert "core_lock_rate" in result
        assert "innovation_index" in result
        assert result["cl_deck_count"] == 3
        assert result["city_league_deck_count"] == 4
        assert result["has_cl_data"] is True

    def test_card_has_cl_vs_meta_metrics(self, db_with_cl):
        from analysis.optimal_60 import compute_optimal_60

        result = compute_optimal_60(db_with_cl, "Charizard ex")
        cards_by_name = {c["card_name"]: c for c in result["cards"]}

        # Nest Ball is in all decklists (100% CL, 100% meta)
        nest = cards_by_name["Nest Ball"]
        assert nest["cl_inclusion_pct"] == 100.0
        assert nest["meta_inclusion_pct"] == 100.0
        assert abs(nest["inclusion_delta"]) < 1.0

    def test_cl_breakout_card_detected(self, db_with_cl):
        from analysis.optimal_60 import compute_optimal_60

        result = compute_optimal_60(db_with_cl, "Charizard ex")
        cards_by_name = {c["card_name"]: c for c in result["cards"]}

        # Switch is in 100% of CL lists but 0% of City League lists
        switch = cards_by_name["Switch"]
        assert switch["cl_inclusion_pct"] == 100.0
        assert switch["meta_inclusion_pct"] == 0.0
        assert switch["inclusion_delta"] == 100.0
        assert switch["insight"] is not None
        assert "CL breakout" in switch["insight"]

    def test_copy_divergence_detected(self, db_with_cl):
        from analysis.optimal_60 import compute_optimal_60

        result = compute_optimal_60(db_with_cl, "Charizard ex")
        cards_by_name = {c["card_name"]: c for c in result["cards"]}

        # Boss's Orders: 1 copy in CL, 2 in City League
        boss = cards_by_name["Boss's Orders"]
        assert boss["cl_avg_copies"] == 1.0
        assert boss["meta_avg_copies"] == 2.0

    def test_cl_boost_affects_blended_metrics(self, db_with_cl):
        from analysis.optimal_60 import compute_optimal_60

        # With CL boost
        boosted = compute_optimal_60(db_with_cl, "Charizard ex", cl_boost=5.0)
        # Without CL boost
        unboosted = compute_optimal_60(db_with_cl, "Charizard ex", cl_boost=1.0)

        boosted_switch = next(c for c in boosted["cards"] if c["card_name"] == "Switch")
        unboosted_switch = next(c for c in unboosted["cards"] if c["card_name"] == "Switch")

        # Boosted should give Switch higher blended inclusion
        assert boosted_switch["blended_inclusion_pct"] > unboosted_switch["blended_inclusion_pct"]

    def test_below_cl_threshold_no_cl_signal_tier(self, db_with_cl):
        from analysis.optimal_60 import compute_optimal_60

        # Dragapult has only 1 CL deck, below min_cl_decks=3
        result = compute_optimal_60(db_with_cl, "Dragapult ex")
        assert result is not None
        assert result["has_cl_data"] is False
        assert result["cl_deck_count"] == 1

        # No card should have "cl-signal" consensus
        for card in result["cards"]:
            assert card["consensus"] != "cl-signal"

    def test_category_totals_sum_to_60_or_less(self, db_with_cl):
        from analysis.optimal_60 import compute_optimal_60

        result = compute_optimal_60(db_with_cl, "Charizard ex")
        total = sum(c["count"] for c in result["cards"])
        assert total <= 60
        assert total == result["total_pokemon"] + result["total_trainer"] + result["total_energy"]

    def test_consensus_tiers_assigned(self, db_with_cl):
        from analysis.optimal_60 import compute_optimal_60

        result = compute_optimal_60(db_with_cl, "Charizard ex")
        consensus_values = {c["consensus"] for c in result["cards"]}
        # Should have at least core cards (Nest Ball, Ultra Ball, Charizard ex are universal)
        assert "core" in consensus_values

    def test_quality_score_is_reasonable(self, db_with_cl):
        from analysis.optimal_60 import compute_optimal_60

        result = compute_optimal_60(db_with_cl, "Charizard ex")
        assert 0 < result["quality_score"] <= 100


class TestInsightGeneration:
    def test_cl_breakout_insight(self):
        from analysis.optimal_60 import _generate_insight

        insight = _generate_insight(
            "Switch",
            "tech",
            60.0,
            95.0,
            40.0,
            3.0,
            2.0,
            5,
        )
        assert insight is not None
        assert "CL breakout" in insight

    def test_cl_cut_insight(self):
        from analysis.optimal_60 import _generate_insight

        insight = _generate_insight(
            "Judge",
            "tech",
            40.0,
            20.0,
            65.0,
            1.0,
            2.0,
            5,
        )
        assert insight is not None
        assert "CL cut" in insight

    def test_meta_staple_insight(self):
        from analysis.optimal_60 import _generate_insight

        insight = _generate_insight(
            "Nest Ball",
            "core",
            95.0,
            95.0,
            95.0,
            4.0,
            4.0,
            5,
        )
        assert insight is not None
        assert "Meta staple" in insight

    def test_copy_divergence_insight(self):
        from analysis.optimal_60 import _generate_insight

        insight = _generate_insight(
            "Boss's Orders",
            "flex",
            60.0,
            60.0,
            60.0,
            1.0,
            3.0,
            5,
        )
        assert insight is not None
        assert "Copy divergence" in insight

    def test_no_insight_for_unremarkable_card(self):
        from analysis.optimal_60 import _generate_insight

        insight = _generate_insight(
            "Some Card",
            "tech",
            30.0,
            30.0,
            30.0,
            2.0,
            2.0,
            5,
        )
        assert insight is None


class TestExportOptimal60:
    def test_export_creates_files(self, db_with_cl, tmp_path):
        """Verify export_optimal_60 produces index and per-archetype JSONs."""
        import json

        from reports.json_export import export_optimal_60

        # Need a meta snapshot for the export
        db_with_cl.execute(
            "INSERT INTO meta_snapshots (id, generated_at, tournament_count, deck_count) "
            "VALUES (1, '2026-03-20', 4, 10)"
        )
        db_with_cl.executemany(
            "INSERT INTO archetype_stats (snapshot_id, archetype, meta_share, deck_count, best_placement, tier) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, "Charizard ex", 50.0, 7, 1, "S"),
                (1, "Dragapult ex", 30.0, 3, 2, "A"),
            ],
        )
        db_with_cl.commit()

        export_optimal_60(db_with_cl, tmp_path, format_slug="nihil-zero")

        # Index should exist
        index_path = tmp_path / "optimal-60" / "index.json"
        assert index_path.exists()
        index = json.loads(index_path.read_text())
        assert index["format"] == "nihil-zero"
        assert index["cl_event"] == "Fukuoka CL 2026"
        assert len(index["archetypes"]) >= 1

        # Per-archetype file should exist
        charizard_path = tmp_path / "optimal-60" / "charizard-ex.json"
        assert charizard_path.exists()
        detail = json.loads(charizard_path.read_text())
        assert detail["archetype"] == "Charizard ex"
        assert detail["cl_deck_count"] == 3
        assert len(detail["cards"]) > 0
        # Check card shape
        card = detail["cards"][0]
        assert "blended_inclusion_pct" in card
        assert "cl_inclusion_pct" in card
        assert "meta_inclusion_pct" in card
        assert "insight" in card

    def test_export_works_without_cl_data(self, tmp_path):
        """Export should produce index even without CL tournaments."""
        import json
        import sqlite3

        from db import SCHEMA
        from reports.json_export import export_optimal_60

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)

        # Add a regular tournament with placements
        conn.execute(
            "INSERT INTO tournaments (id, name, date, player_count, division) "
            "VALUES ('t1', 'Test CL', '2026-03-01', 64, 'open')"
        )
        for pid in range(1, 5):
            conn.execute(
                "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
                "VALUES (?, 't1', ?, 'Player', 'Test Deck')",
                (pid, pid),
            )
            conn.execute(
                "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) "
                "VALUES (?, 'card-1', 'Nest Ball', 4)",
                (pid,),
            )
        conn.execute(
            "INSERT INTO meta_snapshots (id, generated_at, tournament_count, deck_count) "
            "VALUES (1, '2026-03-20', 1, 4)"
        )
        conn.execute(
            "INSERT INTO archetype_stats (snapshot_id, archetype, meta_share, deck_count, best_placement, tier) "
            "VALUES (1, 'Test Deck', 100.0, 4, 1, 'S')"
        )
        conn.commit()

        export_optimal_60(conn, tmp_path, format_slug="test-format")

        index_path = tmp_path / "optimal-60" / "index.json"
        assert index_path.exists()
        index = json.loads(index_path.read_text())
        assert index["cl_event"] is None
        assert len(index["archetypes"]) >= 1
        conn.close()
        conn.close()
