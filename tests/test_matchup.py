"""Tests for analysis/matchup.py — tournament co-occurrence performance proxy."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.matchup import compute_matchup_matrix, extract_archetype_matchups


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


class TestExtractArchetypeMatchups:
    def test_returns_favorable_and_unfavorable(self, labs_db):
        from analysis.matchup import compute_labs_matchup_matrix

        matrix_result = compute_labs_matchup_matrix(labs_db, top_n=3, min_matches=1)
        result = extract_archetype_matchups(matrix_result, "Dragapult ex", top_n=5)

        assert "favorable" in result
        assert "unfavorable" in result
        assert isinstance(result["favorable"], list)
        assert isinstance(result["unfavorable"], list)

    def test_each_entry_has_required_fields(self, labs_db):
        from analysis.matchup import compute_labs_matchup_matrix

        matrix_result = compute_labs_matchup_matrix(labs_db, top_n=3, min_matches=1)
        result = extract_archetype_matchups(matrix_result, "Dragapult ex", top_n=5)

        for entry in result["favorable"] + result["unfavorable"]:
            assert "archetype" in entry
            assert "win_rate" in entry
            assert "sample_size" in entry
            assert "ci_lower" in entry
            assert "ci_upper" in entry

    def test_favorable_sorted_descending(self, labs_db):
        from analysis.matchup import compute_labs_matchup_matrix

        matrix_result = compute_labs_matchup_matrix(labs_db, top_n=3, min_matches=1)
        result = extract_archetype_matchups(matrix_result, "Dragapult ex", top_n=5)

        rates = [e["win_rate"] for e in result["favorable"]]
        assert rates == sorted(rates, reverse=True)

    def test_unfavorable_sorted_ascending(self, labs_db):
        from analysis.matchup import compute_labs_matchup_matrix

        matrix_result = compute_labs_matchup_matrix(labs_db, top_n=3, min_matches=1)
        result = extract_archetype_matchups(matrix_result, "Dragapult ex", top_n=5)

        rates = [e["win_rate"] for e in result["unfavorable"]]
        assert rates == sorted(rates)

    def test_unknown_archetype_returns_empty(self, labs_db):
        from analysis.matchup import compute_labs_matchup_matrix

        matrix_result = compute_labs_matchup_matrix(labs_db, top_n=3, min_matches=1)
        result = extract_archetype_matchups(matrix_result, "Nonexistent Deck", top_n=5)

        assert result["favorable"] == []
        assert result["unfavorable"] == []

    def test_empty_matrix_returns_empty(self):
        empty_result = {
            "archetypes": [],
            "matrix": [],
            "sample_sizes": [],
            "confidence": [],
            "source": "labs-h2h",
        }
        result = extract_archetype_matchups(empty_result, "Anything", top_n=5)
        assert result["favorable"] == []
        assert result["unfavorable"] == []

    def test_respects_top_n_limit(self, labs_db):
        from analysis.matchup import compute_labs_matchup_matrix

        matrix_result = compute_labs_matchup_matrix(labs_db, top_n=3, min_matches=1)
        result = extract_archetype_matchups(matrix_result, "Dragapult ex", top_n=1)

        assert len(result["favorable"]) <= 1
        assert len(result["unfavorable"]) <= 1
