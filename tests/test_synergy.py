"""Tests for analysis/synergy.py — card synergy and co-occurrence analysis."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.synergy import compute_archetype_overlap_matrix, compute_synergy_pairs


class TestComputeSynergyPairs:
    def test_returns_pairs(self, db):
        result = compute_synergy_pairs(db, min_cooccurrences=2)
        assert "pairs" in result
        assert "per_card" in result
        assert isinstance(result["pairs"], list)

    def test_pair_has_required_fields(self, db):
        result = compute_synergy_pairs(db, min_cooccurrences=2)
        if result["pairs"]:
            pair = result["pairs"][0]
            assert "card_a" in pair
            assert "card_b" in pair
            assert "support" in pair
            assert "lift" in pair
            assert "jaccard" in pair
            assert "weighted_score" in pair

    def test_card_a_less_than_card_b(self, db):
        result = compute_synergy_pairs(db, min_cooccurrences=2)
        for pair in result["pairs"]:
            assert pair["card_a"] < pair["card_b"]

    def test_pairs_sorted_by_lift(self, db):
        result = compute_synergy_pairs(db, min_cooccurrences=2)
        pairs = result["pairs"]
        for i in range(len(pairs) - 1):
            assert pairs[i]["lift"] >= pairs[i + 1]["lift"]

    def test_per_card_partners(self, db):
        result = compute_synergy_pairs(db, min_cooccurrences=2)
        per_card = result["per_card"]
        # Nest Ball appears in all decks, should have partners
        if "Nest Ball" in per_card:
            partners = per_card["Nest Ball"]
            assert len(partners) > 0
            assert "card_name" in partners[0]
            assert "lift" in partners[0]

    def test_excludes_basic_energy(self, db):
        result = compute_synergy_pairs(db, min_cooccurrences=1)
        for pair in result["pairs"]:
            assert "Fire Energy" not in (pair["card_a"], pair["card_b"])
            assert "Basic Fire Energy" not in (pair["card_a"], pair["card_b"])

    def test_pair_archetypes(self, db):
        result = compute_synergy_pairs(db, min_cooccurrences=2)
        for pair in result["pairs"]:
            if "archetypes" in pair:
                assert isinstance(pair["archetypes"], list)

    def test_empty_db(self):
        import sqlite3

        from db import SCHEMA

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        result = compute_synergy_pairs(conn)
        assert result["pairs"] == []
        assert result["per_card"] == {}
        conn.close()


class TestComputeArchetypeOverlapMatrix:
    def test_returns_matrix(self, db):
        result = compute_archetype_overlap_matrix(db, top_n=3)
        assert "archetypes" in result
        assert "matrix" in result

    def test_matrix_dimensions(self, db):
        result = compute_archetype_overlap_matrix(db, top_n=3)
        n = len(result["archetypes"])
        assert len(result["matrix"]) == n
        for row in result["matrix"]:
            assert len(row) == n

    def test_diagonal_is_one(self, db):
        result = compute_archetype_overlap_matrix(db, top_n=3)
        for i in range(len(result["archetypes"])):
            assert result["matrix"][i][i] == 1.0

    def test_symmetric(self, db):
        result = compute_archetype_overlap_matrix(db, top_n=3)
        n = len(result["archetypes"])
        for i in range(n):
            for j in range(n):
                assert result["matrix"][i][j] == result["matrix"][j][i]

    def test_archetype_has_fields(self, db):
        result = compute_archetype_overlap_matrix(db, top_n=3)
        if result["archetypes"]:
            arch = result["archetypes"][0]
            assert "archetype" in arch
            assert "slug" in arch
            assert "weighted_share" in arch
