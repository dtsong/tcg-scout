"""Tests for analysis/card_stats.py — individual card intelligence."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.card_stats import (
    _card_slug,
    _compute_trend_direction,
    compute_card_detail,
    compute_card_stats,
    generate_card_verdict,
)


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


class TestComputeCardDetail:
    def test_returns_detail(self, db):
        detail = compute_card_detail(db, "Nest Ball")
        assert detail is not None
        assert detail["card_name"] == "Nest Ball"

    def test_returns_none_for_unknown(self, db):
        detail = compute_card_detail(db, "Nonexistent Card")
        assert detail is None

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
