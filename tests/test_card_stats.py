"""Tests for analysis/card_stats.py — individual card intelligence."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.card_stats import (
    _card_slug,
    _compute_trend_direction,
    build_category_lookup,
    classify_card,
    compute_card_detail,
    compute_card_stats,
    generate_card_verdict,
)
from db import SCHEMA


class TestCardSlug:
    def test_simple_name(self):
        assert _card_slug("Rare Candy") == "rare-candy"

    def test_special_chars(self):
        assert _card_slug("Boss's Orders") == "boss-s-orders"

    def test_ex_name(self):
        assert _card_slug("Fezandipiti ex") == "fezandipiti-ex"


class TestComputeCardStats:
    def test_returns_cards(self, db):
        cards = compute_card_stats(db)
        assert len(cards) > 0

    def test_excludes_basic_energy(self, db):
        cards = compute_card_stats(db)
        names = {c["card_name"] for c in cards}
        assert "Fire Energy" not in names
        assert "Basic Fire Energy" not in names

    def test_card_has_required_fields(self, db):
        cards = compute_card_stats(db)
        card = cards[0]
        assert "card_name" in card
        assert "card_slug" in card
        assert "usage_pct" in card
        assert "avg_copies" in card
        assert "total_appearances" in card
        assert "weighted_score" in card
        assert "category" in card

    def test_usage_pct_is_correct(self, db):
        cards = compute_card_stats(db)
        # Nest Ball appears in all 6 placements, total_decks = 6
        nest_ball = next(c for c in cards if c["card_name"] == "Nest Ball")
        assert nest_ball["usage_pct"] == 100.0
        assert nest_ball["total_appearances"] == 6

    def test_sorted_by_appearances(self, db):
        cards = compute_card_stats(db)
        for i in range(len(cards) - 1):
            assert cards[i]["total_appearances"] >= cards[i + 1]["total_appearances"]

    def test_empty_db_returns_empty(self):
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        assert compute_card_stats(conn) == []
        conn.close()


class TestComputeCardDetail:
    def test_returns_detail(self, db):
        detail = compute_card_detail(db, "Nest Ball")
        assert detail is not None
        assert detail["card_name"] == "Nest Ball"

    def test_returns_none_for_unknown(self, db):
        detail = compute_card_detail(db, "Nonexistent Card")
        assert detail is None

    def test_empty_db_returns_none(self):
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        assert compute_card_detail(conn, "Any Card") is None
        conn.close()

    def test_has_archetypes(self, db):
        detail = compute_card_detail(db, "Nest Ball")
        assert len(detail["archetypes"]) > 0
        arch = detail["archetypes"][0]
        assert "name" in arch
        assert "slug" in arch
        assert "usage_count" in arch
        assert "tier" in arch

    def test_has_copy_distribution(self, db):
        detail = compute_card_detail(db, "Nest Ball")
        assert len(detail["copy_distribution"]) > 0
        entry = detail["copy_distribution"][0]
        assert "copies" in entry
        assert "count" in entry

    def test_has_weekly_usage(self, db):
        detail = compute_card_detail(db, "Nest Ball")
        assert len(detail["weekly_usage"]) > 0
        week = detail["weekly_usage"][0]
        assert "week" in week
        assert "usage_pct" in week
        assert "avg_copies" in week

    def test_has_trend_direction(self, db):
        detail = compute_card_detail(db, "Nest Ball")
        assert detail["trend_direction"] in ("surging", "stable", "declining")


class TestClassifyCard:
    def test_energy_switch_is_trainer(self):
        assert classify_card("Energy Switch") == "Trainer"

    def test_energy_search_is_trainer(self):
        assert classify_card("Energy Search") == "Trainer"

    def test_energy_retrieval_is_trainer(self):
        assert classify_card("Energy Retrieval") == "Trainer"

    def test_basic_energy_is_energy(self):
        assert classify_card("Double Turbo Energy") == "Energy"

    def test_pokemon_ex(self):
        assert classify_card("Charizard ex") == "Pokemon"

    def test_supporter_boss(self):
        assert classify_card("Boss's Orders") == "Trainer"

    def test_supporter_iono(self):
        assert classify_card("Iono") == "Trainer"

    def test_item_nest_ball(self):
        assert classify_card("Nest Ball") == "Trainer"

    def test_item_rare_candy(self):
        assert classify_card("Rare Candy") == "Trainer"

    def test_unknown_pokemon(self):
        assert classify_card("Pikachu") == "Pokemon"


class TestClassifyCardWithSupertype:
    def test_heuristic_classifies_trainer_cards_correctly(self):
        """Trainer cards with non-obvious names are classified correctly."""
        assert classify_card("Wally's Compassion") == "Trainer"
        assert classify_card("Premium Power Pro") == "Trainer"
        assert classify_card("Scoop Up Cyclone") == "Trainer"
        assert classify_card("Precious Trolley") == "Trainer"
        assert classify_card("Morty's Conviction") == "Trainer"

    def test_supertype_from_db_overrides_heuristic(self, db):
        """DB supertype should override heuristic even when they disagree."""
        # "Eevee" would be classified as Pokemon by heuristic, but we mark it as Trainer
        # to prove the DB value takes precedence
        db.execute(
            "INSERT OR REPLACE INTO cards (id, name_en, set_code, supertype) VALUES (?, ?, ?, ?)",
            ("test-001", "Mysterious Card", "test", "Trainer"),
        )
        db.execute(
            "INSERT OR IGNORE INTO decklist_cards (placement_id, card_id, card_name, count) "
            "VALUES (?, ?, ?, ?)",
            (1, "test-001", "Mysterious Card", 2),
        )
        db.commit()

        cards = compute_card_stats(db)
        card = next(c for c in cards if c["card_name"] == "Mysterious Card")
        # Heuristic would return "Pokemon" (no trainer keywords match), but DB says "Trainer"
        assert card["category"] == "Trainer"

    def test_detail_uses_supertype_from_db(self, db):
        """compute_card_detail also respects supertype from cards table."""
        db.execute(
            "INSERT OR REPLACE INTO cards (id, name_en, set_code, supertype) VALUES (?, ?, ?, ?)",
            ("test-002", "Precious Trolley", "test", "Trainer"),
        )
        db.execute(
            "INSERT OR IGNORE INTO decklist_cards (placement_id, card_id, card_name, count) "
            "VALUES (?, ?, ?, ?)",
            (1, "test-002", "Precious Trolley", 1),
        )
        db.commit()

        detail = compute_card_detail(db, "Precious Trolley")
        assert detail is not None
        assert detail["category"] == "Trainer"


class TestBuildCategoryLookup:
    def test_loads_from_db(self, db):
        db.execute("UPDATE cards SET supertype = 'Pokemon' WHERE name_en = 'Charizard ex'")
        db.execute("UPDATE cards SET supertype = 'Trainer' WHERE name_en = 'Rare Candy'")
        db.commit()
        lookup = build_category_lookup(db)
        assert lookup["Charizard ex"] == "Pokemon"
        assert lookup["Rare Candy"] == "Trainer"

    def test_classify_card_uses_lookup(self):
        lookup = {"Sacred Ash": "Trainer", "Unfair Stamp": "Trainer"}
        # Without lookup, "Sacred Ash" would be misclassified as Pokemon
        assert classify_card("Sacred Ash", lookup) == "Trainer"
        assert classify_card("Unfair Stamp", lookup) == "Trainer"

    def test_classify_card_falls_back_to_heuristic(self):
        # Non-empty lookup that doesn't contain the queried card
        lookup = {"Unrelated Card": "Pokemon"}
        assert classify_card("Nest Ball", lookup) == "Trainer"
        assert classify_card("Charizard ex", lookup) == "Pokemon"

    def test_classify_card_empty_lookup_falls_through(self):
        # Empty dict is not None — should still enter lookup branch
        lookup = {}
        assert classify_card("Nest Ball", lookup) == "Trainer"
        assert classify_card("Charizard ex", lookup) == "Pokemon"

    def test_classify_card_without_lookup(self):
        assert classify_card("Nest Ball") == "Trainer"
        assert classify_card("Charizard ex") == "Pokemon"


class TestPokemonNamesFallback:
    """Test the _POKEMON_NAMES fallback classification path."""

    def test_pokemon_in_name_set_classified_correctly(self, monkeypatch):
        monkeypatch.setattr("analysis.card_stats._POKEMON_NAMES", {"pikachu", "charizard"})
        # Not matched by any heuristic, but in the name set
        assert classify_card("Pikachu") == "Pokemon"

    def test_unknown_card_defaults_to_trainer(self, monkeypatch):
        monkeypatch.setattr("analysis.card_stats._POKEMON_NAMES", {"pikachu"})
        # Not in name set, not matched by heuristics
        assert classify_card("Sacred Ash") == "Trainer"

    def test_ex_suffix_stripped_for_lookup(self, monkeypatch):
        monkeypatch.setattr("analysis.card_stats._POKEMON_NAMES", {"charizard"})
        # "charizard ex" -> base "charizard" found in set
        assert classify_card("Charizard ex") == "Pokemon"

    def test_empty_name_set_falls_through_to_trainer_default(self, monkeypatch):
        monkeypatch.setattr("analysis.card_stats._POKEMON_NAMES", set())
        # Without the name set, unknown cards also default to Trainer
        assert classify_card("Sacred Ash") == "Trainer"


class TestComputeTrendDirection:
    def test_stable(self):
        data = [
            {"usage_pct": 50.0},
            {"usage_pct": 51.0},
            {"usage_pct": 49.0},
            {"usage_pct": 50.0},
        ]
        assert _compute_trend_direction(data) == "stable"

    def test_surging(self):
        data = [
            {"usage_pct": 10.0},
            {"usage_pct": 12.0},
            {"usage_pct": 20.0},
            {"usage_pct": 25.0},
        ]
        assert _compute_trend_direction(data) == "surging"

    def test_declining(self):
        data = [
            {"usage_pct": 50.0},
            {"usage_pct": 48.0},
            {"usage_pct": 30.0},
            {"usage_pct": 25.0},
        ]
        assert _compute_trend_direction(data) == "declining"

    def test_single_entry(self):
        assert _compute_trend_direction([{"usage_pct": 50.0}]) == "stable"


class TestGenerateCardVerdict:
    def test_staple_card(self):
        card = {
            "total_appearances": 100,
            "avg_copies": 4.0,
            "unique_archetypes": 8,
            "archetypes": [
                {"tier": "S"},
                {"tier": "S"},
                {"tier": "A"},
                {"tier": "B"},
                {"tier": "B"},
                {"tier": "C"},
                {"tier": "Rogue"},
                {"tier": "Rogue"},
            ],
        }
        verdict = generate_card_verdict(card)
        assert "Core 4-of" in verdict
        assert "S-tier" in verdict

    def test_flex_card(self):
        card = {
            "total_appearances": 10,
            "avg_copies": 1.0,
            "unique_archetypes": 3,
            "archetypes": [{"tier": "B"}, {"tier": "C"}, {"tier": "Rogue"}],
        }
        verdict = generate_card_verdict(card)
        assert "Flex tech" in verdict

    def test_niche_card(self):
        card = {
            "total_appearances": 2,
            "avg_copies": 1.0,
            "unique_archetypes": 1,
            "archetypes": [{"tier": "Rogue"}],
        }
        verdict = generate_card_verdict(card)
        assert "Niche pick" in verdict
