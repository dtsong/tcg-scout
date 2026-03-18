"""Tests for analysis/meta.py — meta snapshot computation and tier assignment."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.meta import _assign_tier, compute_meta_snapshot, get_latest_snapshot


# --- _assign_tier ---

class TestAssignTier:
    def test_s_tier(self):
        assert _assign_tier(15.0) == "S"
        assert _assign_tier(20.0) == "S"

    def test_a_tier(self):
        assert _assign_tier(8.0) == "A"
        assert _assign_tier(14.9) == "A"

    def test_b_tier(self):
        assert _assign_tier(3.0) == "B"
        assert _assign_tier(7.9) == "B"

    def test_c_tier(self):
        assert _assign_tier(1.0) == "C"
        assert _assign_tier(2.9) == "C"

    def test_rogue(self):
        assert _assign_tier(0.5) == "Rogue"
        assert _assign_tier(0.0) == "Rogue"


# --- compute_meta_snapshot ---

class TestComputeMetaSnapshot:
    def test_creates_snapshot(self, db):
        # Delete the pre-seeded snapshot so we start fresh
        db.execute("DELETE FROM archetype_stats")
        db.execute("DELETE FROM meta_snapshots")
        db.commit()

        snapshot_id = compute_meta_snapshot(db)
        assert snapshot_id is not None

        # Verify snapshot row
        snap = db.execute(
            "SELECT * FROM meta_snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
        assert snap["tournament_count"] == 3
        assert snap["deck_count"] == 6

    def test_assigns_correct_tiers(self, db):
        db.execute("DELETE FROM archetype_stats")
        db.execute("DELETE FROM meta_snapshots")
        db.commit()

        snapshot_id = compute_meta_snapshot(db)

        stats = db.execute(
            "SELECT archetype, meta_share, tier FROM archetype_stats WHERE snapshot_id = ? ORDER BY meta_share DESC",
            (snapshot_id,),
        ).fetchall()

        tier_map = {row["archetype"]: row["tier"] for row in stats}
        # Charizard ex: 3/6 = 50% -> S
        assert tier_map["Charizard ex"] == "S"
        # Dragapult ex: 2/6 = 33.33% -> S
        assert tier_map["Dragapult ex"] == "S"
        # Raging Bolt ex: 1/6 = 16.67% -> S
        assert tier_map["Raging Bolt ex"] == "S"


# --- get_latest_snapshot ---

class TestGetLatestSnapshot:
    def test_returns_correct_structure(self, db):
        result = get_latest_snapshot(db)
        assert result is not None
        assert "id" in result
        assert "generated_at" in result
        assert "tournament_count" in result
        assert "deck_count" in result
        assert "archetypes" in result
        assert isinstance(result["archetypes"], list)

    def test_archetypes_sorted_by_share_desc(self, db):
        result = get_latest_snapshot(db)
        shares = [a["meta_share"] for a in result["archetypes"]]
        assert shares == sorted(shares, reverse=True)

    def test_returns_none_when_empty(self, db):
        db.execute("DELETE FROM archetype_stats")
        db.execute("DELETE FROM meta_snapshots")
        db.commit()
        assert get_latest_snapshot(db) is None
