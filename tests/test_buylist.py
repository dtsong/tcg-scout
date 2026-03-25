"""Tests for analysis/buylist.py — priority-scored buy list generation."""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.buylist import BASIC_ENERGY_NAMES, generate_buylist
from db import SCHEMA


@pytest.fixture()
def db_buylist() -> sqlite3.Connection:
    """In-memory SQLite database tailored for buylist tests.

    Layout:
    - 3 open tournaments, 1 senior (filtered out by open_placements view)
    - 3 archetypes with tiers: S (Charizard ex), A (Dragapult ex), B (Raging Bolt ex)
    - 2 placements per archetype (all open division), each with decklists
    - Cards table with rotation_legal=1 and rotation_legal=0 entries
    - A basic energy card in decklists (should be excluded)
    - Pokemon and Trainer supertypes for core threshold testing
    - One card_id not in the cards table (unresolved, should be included)
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)

    # --- Tournaments ---
    conn.executemany(
        "INSERT INTO tournaments (id, name, date, player_count, division) VALUES (?, ?, ?, ?, ?)",
        [
            ("t1", "Osaka CL", "2026-02-01", 64, "open"),
            ("t2", "Tokyo CL", "2026-02-08", 64, "open"),
            ("t3", "Nagoya CL", "2026-02-15", 64, "open"),
            ("t4", "Senior Cup", "2026-02-10", 32, "senior"),
        ],
    )

    # --- Placements ---
    # Charizard ex: placements 1, 2 (open)
    # Dragapult ex: placements 3, 4 (open)
    # Raging Bolt ex: placements 5, 6 (open)
    # Senior placement 7 (should be invisible to open_placements)
    conn.executemany(
        "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (1, "t1", 1, "Alice", "Charizard ex"),
            (2, "t2", 2, "Bob", "Charizard ex"),
            (3, "t1", 3, "Charlie", "Dragapult ex"),
            (4, "t2", 4, "Diana", "Dragapult ex"),
            (5, "t3", 1, "Eve", "Raging Bolt ex"),
            (6, "t3", 8, "Frank", "Raging Bolt ex"),
            (7, "t4", 1, "Greta", "Charizard ex"),
        ],
    )

    # --- Cards table ---
    conn.executemany(
        "INSERT INTO cards (id, name_en, name_jp, set_code, set_number, image_url, supertype, rotation_legal) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("card-zard", "Charizard ex", "リザードンex", "sv5", "001", None, "Pokemon", 1),
            ("card-draga", "Dragapult ex", "ドラパルトex", "sv5", "002", None, "Pokemon", 1),
            ("card-bolt", "Raging Bolt ex", "タケルライコex", "sv5", "003", None, "Pokemon", 1),
            ("card-nest", "Nest Ball", "ネストボール", "sv5", "100", None, "Trainer", 1),
            ("card-boss", "Boss's Orders", "ボスの指令", "sv5", "101", None, "Trainer", 1),
            ("card-rotated", "Old Trainer", "旧トレーナー", "sv1", "050", None, "Trainer", 0),
            (
                "card-energy",
                "Basic Fire Energy",
                "基本炎エネルギー",
                "sve",
                "001",
                None,
                "Energy",
                1,
            ),
        ],
    )

    # --- Decklist cards ---
    decklist_rows = []

    # Charizard ex placements (1, 2): shared core cards
    for pid in [1, 2]:
        decklist_rows.extend(
            [
                (pid, "card-zard", "Charizard ex", 3),  # Pokemon, avg 3, inclusion 100%
                (pid, "card-nest", "Nest Ball", 4),  # Trainer, avg 4, inclusion 100%
                (pid, "card-boss", "Boss's Orders", 2),  # Trainer, avg 2, inclusion 100%
                (pid, "card-rotated", "Old Trainer", 2),  # rotation_legal=0, should be excluded
                (pid, "card-energy", "Basic Fire Energy", 4),  # basic energy, should be excluded
            ]
        )

    # Dragapult ex placements (3, 4): share some cards with Charizard
    for pid in [3, 4]:
        decklist_rows.extend(
            [
                (pid, "card-draga", "Dragapult ex", 3),  # Pokemon, avg 3, inclusion 100%
                (pid, "card-nest", "Nest Ball", 4),  # shared with Charizard
                (pid, "card-boss", "Boss's Orders", 2),  # shared with Charizard
            ]
        )

    # Raging Bolt ex placements (5, 6): share Nest Ball and Boss
    for pid in [5, 6]:
        decklist_rows.extend(
            [
                (pid, "card-bolt", "Raging Bolt ex", 3),  # Pokemon, avg 3, inclusion 100%
                (pid, "card-nest", "Nest Ball", 4),  # shared across all 3 archetypes
                (pid, "card-boss", "Boss's Orders", 2),  # shared across all 3 archetypes
            ]
        )

    # One placement with an unresolved card (not in cards table)
    decklist_rows.append((1, "card-unknown", "Mystery Card", 2))

    conn.executemany(
        "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
        decklist_rows,
    )

    # --- Meta snapshot ---
    conn.execute(
        "INSERT INTO meta_snapshots (id, generated_at, tournament_count, deck_count) "
        "VALUES (?, ?, ?, ?)",
        (1, "2026-03-01T00:00:00", 3, 6),
    )
    conn.executemany(
        "INSERT INTO archetype_stats (snapshot_id, archetype, meta_share, deck_count, best_placement, tier, weighted_share) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "Charizard ex", 33.3, 2, 1, "S", 40.0),
            (1, "Dragapult ex", 33.3, 2, 3, "A", 30.0),
            (1, "Raging Bolt ex", 33.3, 2, 1, "B", 30.0),
        ],
    )

    conn.commit()
    yield conn
    conn.close()


# --- Basic return behavior ---


class TestBuylistBasicBehavior:
    """Tests for fundamental return conditions."""

    def test_returns_nonempty_for_sab_archetypes(self, db_buylist):
        result = generate_buylist(db_buylist, snapshot_id=1)
        assert len(result) > 0

    def test_returns_list_of_dicts(self, db_buylist):
        result = generate_buylist(db_buylist, snapshot_id=1)
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, dict)

    def test_empty_for_nonexistent_snapshot(self, db_buylist):
        result = generate_buylist(db_buylist, snapshot_id=999)
        assert result == []

    def test_empty_when_only_rogue_and_c_tiers(self, db_buylist):
        """All archetypes are Rogue or C tier -- no S/A/B means empty buylist."""
        db_buylist.execute("DELETE FROM archetype_stats")
        db_buylist.executemany(
            "INSERT INTO archetype_stats (snapshot_id, archetype, meta_share, deck_count, best_placement, tier, weighted_share) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "Charizard ex", 2.0, 2, 1, "C", 3.0),
                (1, "Dragapult ex", 0.5, 1, 3, "Rogue", 0.8),
            ],
        )
        db_buylist.commit()

        result = generate_buylist(db_buylist, snapshot_id=1)
        assert result == []

    def test_empty_for_empty_snapshot(self, db_buylist):
        """Snapshot exists but has no archetype_stats rows."""
        db_buylist.execute(
            "INSERT INTO meta_snapshots (id, generated_at, tournament_count, deck_count) "
            "VALUES (?, ?, ?, ?)",
            (99, "2026-03-15T00:00:00", 0, 0),
        )
        db_buylist.commit()

        result = generate_buylist(db_buylist, snapshot_id=99)
        assert result == []


# --- Card filtering ---


class TestBuylistCardFiltering:
    """Tests for energy exclusion and rotation legality filtering."""

    def test_excludes_basic_energy_cards(self, db_buylist):
        result = generate_buylist(db_buylist, snapshot_id=1)
        card_names = {r["card_name"] for r in result}
        assert "Basic Fire Energy" not in card_names

    def test_basic_energy_names_set_is_nonempty(self):
        """Sanity check that the BASIC_ENERGY_NAMES constant is populated."""
        assert len(BASIC_ENERGY_NAMES) > 0
        assert "Basic Fire Energy" in BASIC_ENERGY_NAMES
        assert "Fire Energy" in BASIC_ENERGY_NAMES

    def test_excludes_rotation_illegal_cards(self, db_buylist):
        """Cards with rotation_legal=0 in the cards table are excluded."""
        result = generate_buylist(db_buylist, snapshot_id=1)
        card_ids = {r["card_id"] for r in result if r["card_id"] is not None}
        assert "card-rotated" not in card_ids
        card_names = {r["card_name"] for r in result}
        assert "Old Trainer" not in card_names

    def test_includes_cards_not_in_cards_table(self, db_buylist):
        """Cards with IDs not in the cards table bypass rotation check and are included."""
        result = generate_buylist(db_buylist, snapshot_id=1)
        card_names = {r["card_name"] for r in result}
        assert "Mystery Card" in card_names

    def test_unresolved_card_has_null_fields(self, db_buylist):
        """Cards not in cards table should have card_id=None, set_code=None, set_number=None."""
        result = generate_buylist(db_buylist, snapshot_id=1)
        mystery = next(r for r in result if r["card_name"] == "Mystery Card")
        assert mystery["card_id"] is None
        assert mystery["set_code"] is None
        assert mystery["set_number"] is None


# --- Priority scoring ---


class TestBuylistPriorityScoring:
    """Tests for priority_score calculation and sorting."""

    def test_priority_score_uses_tier_weights(self, db_buylist):
        """priority_score += avg_copies * tier_weight per archetype.

        Nest Ball: avg 4 copies in all 3 archetypes.
        S(Charizard) contribution: 4 * 5 = 20
        A(Dragapult) contribution: 4 * 3 = 12
        B(Raging Bolt) contribution: 4 * 1 = 4
        Total: 36.0
        """
        result = generate_buylist(db_buylist, snapshot_id=1)
        nest = next(r for r in result if r["card_name"] == "Nest Ball")
        assert nest["priority_score"] == 36.0

    def test_single_archetype_priority_score(self, db_buylist):
        """Charizard ex card only in S-tier archetype: avg 3 * weight 5 = 15.0."""
        result = generate_buylist(db_buylist, snapshot_id=1)
        zard = next(r for r in result if r["card_name"] == "Charizard ex")
        assert zard["priority_score"] == 15.0

    def test_b_tier_priority_score(self, db_buylist):
        """Raging Bolt ex only in B-tier: avg 3 * weight 1 = 3.0."""
        result = generate_buylist(db_buylist, snapshot_id=1)
        bolt = next(r for r in result if r["card_name"] == "Raging Bolt ex")
        assert bolt["priority_score"] == 3.0

    def test_results_sorted_by_priority_score_descending(self, db_buylist):
        result = generate_buylist(db_buylist, snapshot_id=1)
        scores = [r["priority_score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_boss_orders_cross_archetype_score(self, db_buylist):
        """Boss's Orders: avg 2 copies in S + A + B archetypes.

        S: 2 * 5 = 10, A: 2 * 3 = 6, B: 2 * 1 = 2 => total 18.0
        """
        result = generate_buylist(db_buylist, snapshot_id=1)
        boss = next(r for r in result if r["card_name"] == "Boss's Orders")
        assert boss["priority_score"] == 18.0


# --- Cross-archetype aggregation ---


class TestBuylistCrossArchetypeAggregation:
    """Tests for cross-archetype max inclusion_rate and archetype lists."""

    def test_max_inclusion_rate_across_archetypes(self, db_buylist):
        """Nest Ball is in 100% of decks in all 3 archetypes -- max inclusion_rate = 1.0."""
        result = generate_buylist(db_buylist, snapshot_id=1)
        nest = next(r for r in result if r["card_name"] == "Nest Ball")
        assert nest["inclusion_rate"] == 1.0

    def test_archetype_list_completeness(self, db_buylist):
        """Nest Ball should list all 3 archetypes it appears in."""
        result = generate_buylist(db_buylist, snapshot_id=1)
        nest = next(r for r in result if r["card_name"] == "Nest Ball")
        assert set(nest["archetypes"]) == {"Charizard ex", "Dragapult ex", "Raging Bolt ex"}

    def test_single_archetype_card(self, db_buylist):
        """Charizard ex card only appears in the Charizard ex archetype."""
        result = generate_buylist(db_buylist, snapshot_id=1)
        zard = next(r for r in result if r["card_name"] == "Charizard ex")
        assert zard["archetypes"] == ["Charizard ex"]


# --- Core vs flex classification ---


class TestBuylistCoreFlex:
    """Tests for core/flex determination based on inclusion rate and avg copies."""

    def test_pokemon_core_threshold(self, db_buylist):
        """Pokemon card: core when inclusion >= 0.75 AND avg_copies >= 3."""
        result = generate_buylist(db_buylist, snapshot_id=1)
        zard = next(r for r in result if r["card_name"] == "Charizard ex")
        # inclusion_rate = 1.0 (2/2 decks), avg_copies = 3.0
        assert zard["core_flex"] == "core"
        assert zard["avg_copies"] == 3.0
        assert zard["inclusion_rate"] == 1.0

    def test_trainer_core_threshold(self, db_buylist):
        """Trainer card: core when inclusion >= 0.75 AND avg_copies >= 2."""
        result = generate_buylist(db_buylist, snapshot_id=1)
        boss = next(r for r in result if r["card_name"] == "Boss's Orders")
        # inclusion_rate = 1.0, avg_copies = 2.0 (Trainer threshold = 2)
        assert boss["core_flex"] == "core"

    def test_pokemon_flex_when_low_copies(self, db_buylist):
        """A Pokemon with high inclusion but avg_copies < 3 is flex."""
        # Add a low-copy Pokemon to both Charizard placements
        for pid in [1, 2]:
            db_buylist.execute(
                "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
                (pid, "card-tech-poke", "Tech Pokemon", 1),
            )
        db_buylist.execute(
            "INSERT INTO cards (id, name_en, name_jp, set_code, set_number, image_url, supertype, rotation_legal) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("card-tech-poke", "Tech Pokemon", "テクポケ", "sv5", "150", None, "Pokemon", 1),
        )
        db_buylist.commit()

        result = generate_buylist(db_buylist, snapshot_id=1)
        tech = next(r for r in result if r["card_name"] == "Tech Pokemon")
        # inclusion = 1.0 (2/2 in Charizard), avg_copies = 1.0, Pokemon threshold = 3
        assert tech["core_flex"] == "flex"

    def test_flex_when_low_inclusion(self, db_buylist):
        """A card in only 1 of 2 decks (50% inclusion) is flex regardless of copy count."""
        # Add a high-copy card to only one Charizard placement
        db_buylist.execute(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
            (1, "card-niche", "Niche Trainer", 4),
        )
        db_buylist.execute(
            "INSERT INTO cards (id, name_en, name_jp, set_code, set_number, image_url, supertype, rotation_legal) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("card-niche", "Niche Trainer", "ニッチ", "sv5", "160", None, "Trainer", 1),
        )
        db_buylist.commit()

        result = generate_buylist(db_buylist, snapshot_id=1)
        niche = next(r for r in result if r["card_name"] == "Niche Trainer")
        # inclusion = 0.5 (1/2 decks) < 0.75 => flex
        assert niche["core_flex"] == "flex"


# --- Result structure ---


class TestBuylistResultStructure:
    """Tests for the shape and fields of result dicts."""

    EXPECTED_KEYS = {
        "card_name",
        "card_id",
        "set_code",
        "set_number",
        "priority_score",
        "core_flex",
        "archetypes",
        "avg_copies",
        "inclusion_rate",
    }

    def test_result_dict_keys(self, db_buylist):
        result = generate_buylist(db_buylist, snapshot_id=1)
        for item in result:
            assert set(item.keys()) == self.EXPECTED_KEYS

    def test_resolved_card_has_set_info(self, db_buylist):
        """Cards present in the cards table should have set_code and set_number."""
        result = generate_buylist(db_buylist, snapshot_id=1)
        nest = next(r for r in result if r["card_name"] == "Nest Ball")
        assert nest["card_id"] == "card-nest"
        assert nest["set_code"] == "sv5"
        assert nest["set_number"] == "100"

    def test_senior_division_excluded(self, db_buylist):
        """Senior division placement (id=7) should not affect buylist results.

        The Charizard ex archetype has 2 open placements (ids 1, 2) and 1 senior (id 7).
        Decklist analysis should only see 2 decks for Charizard.
        """
        result = generate_buylist(db_buylist, snapshot_id=1)
        zard = next(r for r in result if r["card_name"] == "Charizard ex")
        # avg_copies = 3.0 (from 2 open decks each with count=3)
        # If senior were included, there would be 0 decks for pid=7 (no decklist_cards for pid=7)
        # which would still give avg 3.0 but inclusion_rate would change.
        # Since pid=7 has no decklist_cards, this validates the view filters it out.
        assert zard["inclusion_rate"] == 1.0
