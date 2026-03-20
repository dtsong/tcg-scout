"""Tests for analysis.deep_dive module."""

import sqlite3

import pytest

from analysis.deep_dive import (
    compute_notable_techs,
    compute_placement_distribution,
    compute_weekly_card_timeline,
    compute_weighted_consensus_60,
)


@pytest.fixture()
def deep_db() -> sqlite3.Connection:
    """In-memory DB with enough data for deep dive analysis."""
    from db import SCHEMA

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)

    # 3 tournaments across 3 weeks
    conn.executemany(
        "INSERT INTO tournaments (id, name, date, player_count, division) VALUES (?, ?, ?, ?, ?)",
        [
            ("t1", "Week 1", "2026-01-27", 64, "open"),
            ("t2", "Week 2", "2026-02-03", 64, "open"),
            ("t3", "Week 3", "2026-02-10", 64, "open"),
        ],
    )

    # 5 placements for "Test Deck" with varying standings
    conn.executemany(
        "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (1, "t1", 1, "Alice", "Test Deck"),
            (2, "t1", 8, "Bob", "Test Deck"),
            (3, "t2", 4, "Charlie", "Test Deck"),
            (4, "t3", 2, "Diana", "Test Deck"),
            (5, "t3", 16, "Eve", "Test Deck"),
        ],
    )

    # Decklists - universal cards in all decks
    rows = []
    for pid in range(1, 6):
        rows.append((pid, "c-ultra", "Ultra Ball", 4))
        rows.append((pid, "c-nest", "Nest Ball", 4))
        rows.append((pid, "c-boss", "Boss's Orders", 2))
        rows.append((pid, "c-main-ex", "Main ex", 3))

    # Card only in 1st place deck (high weight)
    rows.append((1, "c-tech-a", "Tech Card A", 2))
    # Card only in 16th place deck (low weight)
    rows.append((5, "c-tech-b", "Tech Card B", 2))
    # Card adopted only in week 3
    rows.append((4, "c-new", "New Tech", 1))
    rows.append((5, "c-new", "New Tech", 1))
    # Card dropped after week 1
    rows.append((1, "c-old", "Old Tech", 2))
    rows.append((2, "c-old", "Old Tech", 2))

    conn.executemany(
        "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
        rows,
    )

    # Low-data archetype with only 2 decklists
    conn.executemany(
        "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (10, "t1", 3, "Frank", "Low Data Deck"),
            (11, "t2", 5, "Greta", "Low Data Deck"),
        ],
    )
    conn.executemany(
        "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
        [
            (10, "c-ultra", "Ultra Ball", 4),
            (11, "c-ultra", "Ultra Ball", 4),
        ],
    )

    # Meta snapshot
    conn.execute(
        "INSERT INTO meta_snapshots (id, generated_at, tournament_count, deck_count) "
        "VALUES (?, ?, ?, ?)",
        (1, "2026-02-15T00:00:00", 3, 5),
    )
    conn.executemany(
        "INSERT INTO archetype_stats (snapshot_id, archetype, meta_share, deck_count, best_placement, tier) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "Test Deck", 71.4, 5, 1, "S"),
            (1, "Low Data Deck", 28.6, 2, 3, "A"),
        ],
    )

    conn.commit()
    yield conn
    conn.close()


def test_weighted_consensus_respects_60_card_limit(deep_db):
    """With limited test data, consensus uses all available cards.
    With real data (many unique cards), the greedy fill stops at 60.
    """
    result = compute_weighted_consensus_60(deep_db, "Test Deck")
    assert result is not None
    total = sum(c["count"] for c in result["cards"])
    # Test data has few unique cards, so total is less than 60
    assert total <= 60
    assert total > 0
    # Verify quality_score is computed
    assert result["quality_score"] > 0
    # Verify category totals are consistent
    cat_total = result["total_pokemon"] + result["total_trainer"] + result["total_energy"]
    assert cat_total == total


def test_higher_placement_weights_more(deep_db):
    result = compute_weighted_consensus_60(deep_db, "Test Deck")
    assert result is not None
    cards_by_name = {c["card_name"]: c for c in result["cards"]}

    # Tech Card A (in 1st place, weight 3.0) should have higher weighted inclusion
    # than Tech Card B (in 16th place, weight 1.2)
    tech_a = cards_by_name.get("Tech Card A")
    tech_b = cards_by_name.get("Tech Card B")
    assert tech_a is not None
    assert tech_b is not None
    assert tech_a["weighted_inclusion_pct"] > tech_b["weighted_inclusion_pct"]


def test_consensus_labels(deep_db):
    result = compute_weighted_consensus_60(deep_db, "Test Deck")
    assert result is not None
    cards_by_name = {c["card_name"]: c for c in result["cards"]}

    # Universal cards should be "core" (100% inclusion)
    assert cards_by_name["Ultra Ball"]["consensus"] == "core"
    assert cards_by_name["Nest Ball"]["consensus"] == "core"

    # Tech cards in only 1 deck should be "tech"
    assert cards_by_name["Tech Card A"]["consensus"] == "tech"


def test_skip_low_data_archetypes(deep_db):
    result = compute_weighted_consensus_60(deep_db, "Low Data Deck")
    assert result is None


def test_weekly_timeline_computation(deep_db):
    result = compute_weekly_card_timeline(deep_db, "Test Deck")
    assert result is not None
    assert len(result["weeks"]) == 3

    cards_by_name = {c["card_name"]: c for c in result["cards"]}
    # Old Tech appears in week 1 (100% of 2 decks) but not weeks 2-3
    old_tech = cards_by_name.get("Old Tech")
    assert old_tech is not None
    assert old_tech["timeline"][0] == 100.0
    assert old_tech["timeline"][2] == 0.0


def test_placement_distribution(deep_db):
    placements = [
        {"standing": 1},
        {"standing": 2},
        {"standing": 4},
        {"standing": 8},
        {"standing": 16},
    ]
    result = compute_placement_distribution(placements)
    brackets = {b["bracket"]: b["count"] for b in result}
    assert brackets["1st"] == 1
    assert brackets["2nd"] == 1
    assert brackets["3rd-4th"] == 1
    assert brackets["5th-8th"] == 1
    assert brackets["9th-16th"] == 1
    total_pct = sum(b["pct"] for b in result)
    assert abs(total_pct - 100.0) < 0.5


def test_notable_techs():
    timeline_data = {
        "weeks": ["2026-01-27", "2026-02-03", "2026-02-10"],
        "cards": [
            {
                "card_name": "Rising Card",
                "category": "Trainer",
                "timeline": [0.0, 30.0, 80.0],
                "copies_timeline": [0.0, 1.0, 2.0],
                "trend": "adopted",
                "total_delta": 80.0,
            },
        ],
    }
    result = compute_notable_techs(timeline_data)
    assert len(result) == 1
    assert result[0]["card_name"] == "Rising Card"
    assert result[0]["event"] == "surged"


def test_nonexistent_archetype(deep_db):
    assert compute_weighted_consensus_60(deep_db, "Does Not Exist") is None
    assert compute_weekly_card_timeline(deep_db, "Does Not Exist") is None
