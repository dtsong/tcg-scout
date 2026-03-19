"""Tests for analysis/matchup.py — tournament co-occurrence performance proxy."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.matchup import compute_matchup_matrix


class TestComputeMatchupMatrix:
    def test_returns_structure(self, db):
        result = compute_matchup_matrix(db, top_n=3, min_cooccurrences=1)
        assert "archetypes" in result
        assert "matrix" in result
        assert "sample_sizes" in result

    def test_matrix_dimensions(self, db):
        result = compute_matchup_matrix(db, top_n=3, min_cooccurrences=1)
        n = len(result["archetypes"])
        assert len(result["matrix"]) == n
        for row in result["matrix"]:
            assert len(row) == n

    def test_diagonal_is_zero(self, db):
        result = compute_matchup_matrix(db, top_n=3, min_cooccurrences=1)
        for i in range(len(result["archetypes"])):
            assert result["matrix"][i][i] == 0.0

    def test_antisymmetric(self, db):
        """matrix[i][j] should be -matrix[j][i] (what helps i hurts j)."""
        result = compute_matchup_matrix(db, top_n=3, min_cooccurrences=1)
        n = len(result["archetypes"])
        for i in range(n):
            for j in range(n):
                assert abs(result["matrix"][i][j] + result["matrix"][j][i]) < 0.01

    def test_sample_sizes_symmetric(self, db):
        result = compute_matchup_matrix(db, top_n=3, min_cooccurrences=1)
        n = len(result["archetypes"])
        for i in range(n):
            for j in range(n):
                assert result["sample_sizes"][i][j] == result["sample_sizes"][j][i]

    def test_min_cooccurrences_filter(self, db):
        # With high threshold, should zero out pairs with insufficient data
        result = compute_matchup_matrix(db, top_n=3, min_cooccurrences=100)
        n = len(result["archetypes"])
        for i in range(n):
            for j in range(n):
                if i != j:
                    assert result["matrix"][i][j] == 0.0

    def test_empty_db(self):
        from db import SCHEMA

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        result = compute_matchup_matrix(conn)
        assert result["archetypes"] == []
        conn.close()
