"""Tests for evaluation/harness.py — eval harness skeleton."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest.importorskip("anthropic")

from evaluation.harness import (
    ContainsKeywordsScorer,
    EvalHarness,
    ExactMatchScorer,
    GoldenExample,
    JSONSchemaScorer,
    load_golden_dataset,
)
from reports.model_client import ModelClient

# --- Helpers ---

SAMPLE_DATASET = {
    "name": "test-dataset",
    "examples": [
        {
            "id": "ex-001",
            "input_prompt": "What is the top archetype?",
            "expected": {"text": "Dragapult Dusknoir", "keywords": ["Dragapult"]},
            "metadata": {"category": "meta"},
        },
        {
            "id": "ex-002",
            "input_prompt": "List top cards.",
            "expected": {"text": "Munkidori, Unfair Stamp", "keywords": ["Munkidori", "Stamp"]},
            "metadata": {},
        },
    ],
}


def _write_dataset(tmp_path: Path, data: dict | None = None) -> Path:
    """Write a golden dataset JSON and return the path."""
    path = tmp_path / "test-dataset.json"
    path.write_text(json.dumps(data or SAMPLE_DATASET), encoding="utf-8")
    return path


# --- load_golden_dataset ---


class TestLoadGoldenDataset:
    def test_loads_examples(self, tmp_path):
        path = _write_dataset(tmp_path)
        examples = load_golden_dataset(path)
        assert len(examples) == 2
        assert isinstance(examples[0], GoldenExample)

    def test_example_fields(self, tmp_path):
        path = _write_dataset(tmp_path)
        examples = load_golden_dataset(path)
        ex = examples[0]
        assert ex.id == "ex-001"
        assert ex.input_prompt == "What is the top archetype?"
        assert ex.expected["text"] == "Dragapult Dusknoir"
        assert ex.metadata["category"] == "meta"

    def test_empty_dataset(self, tmp_path):
        path = _write_dataset(tmp_path, {"name": "empty", "examples": []})
        examples = load_golden_dataset(path)
        assert examples == []


# --- ExactMatchScorer ---


class TestExactMatchScorer:
    def test_exact_match(self):
        scorer = ExactMatchScorer()
        result = scorer.score("Dragapult Dusknoir", {"text": "Dragapult Dusknoir"})
        assert result.passed
        assert result.score == 1.0

    def test_mismatch(self):
        scorer = ExactMatchScorer()
        result = scorer.score("Charizard ex", {"text": "Dragapult Dusknoir"})
        assert not result.passed
        assert result.score == 0.0

    def test_strips_whitespace(self):
        scorer = ExactMatchScorer()
        result = scorer.score("  hello  ", {"text": "hello"})
        assert result.passed


# --- ContainsKeywordsScorer ---


class TestContainsKeywordsScorer:
    def test_all_keywords_present(self):
        scorer = ContainsKeywordsScorer()
        result = scorer.score(
            "Dragapult Dusknoir leads the meta", {"keywords": ["Dragapult", "meta"]}
        )
        assert result.passed
        assert result.score == 1.0

    def test_missing_keyword(self):
        scorer = ContainsKeywordsScorer()
        result = scorer.score("Charizard leads", {"keywords": ["Dragapult", "leads"]})
        assert not result.passed
        assert result.score == pytest.approx(0.5)
        assert "Dragapult" in result.details["missing"]

    def test_empty_keywords(self):
        scorer = ContainsKeywordsScorer()
        result = scorer.score("anything", {"keywords": []})
        assert result.passed

    def test_case_insensitive(self):
        scorer = ContainsKeywordsScorer()
        result = scorer.score("DRAGAPULT is strong", {"keywords": ["dragapult"]})
        assert result.passed


# --- JSONSchemaScorer ---


class TestJSONSchemaScorer:
    def test_valid_json_with_keys(self):
        scorer = JSONSchemaScorer()
        output = json.dumps({"sections": [], "tweets": []})
        result = scorer.score(output, {"required_keys": ["sections", "tweets"]})
        assert result.passed
        assert result.score == 1.0

    def test_missing_keys(self):
        scorer = JSONSchemaScorer()
        output = json.dumps({"sections": []})
        result = scorer.score(output, {"required_keys": ["sections", "tweets"]})
        assert not result.passed
        assert "tweets" in result.details["missing_keys"]

    def test_invalid_json(self):
        scorer = JSONSchemaScorer()
        result = scorer.score("not json", {"required_keys": ["sections"]})
        assert not result.passed
        assert result.score == 0.0

    def test_no_required_keys(self):
        scorer = JSONSchemaScorer()
        result = scorer.score("{}", {"required_keys": []})
        assert result.passed


# --- EvalHarness ---


class TestEvalHarness:
    def _make_mock_client(self, responses: list[str]) -> ModelClient:
        client = MagicMock(spec=ModelClient)
        client.generate.side_effect = responses
        return client

    def test_runs_all_examples(self, tmp_path):
        path = _write_dataset(tmp_path)
        mock_client = self._make_mock_client(["Dragapult Dusknoir", "Munkidori, Unfair Stamp"])
        harness = EvalHarness(mock_client, ExactMatchScorer())
        report = harness.run(path)
        assert report.total == 2
        assert report.dataset_name == "test-dataset"
        assert mock_client.generate.call_count == 2

    def test_all_pass(self, tmp_path):
        path = _write_dataset(tmp_path)
        mock_client = self._make_mock_client(["Dragapult Dusknoir", "Munkidori, Unfair Stamp"])
        harness = EvalHarness(mock_client, ExactMatchScorer())
        report = harness.run(path)
        assert report.passed == 2
        assert report.failed == 0
        assert report.mean_score == 1.0

    def test_partial_pass(self, tmp_path):
        path = _write_dataset(tmp_path)
        mock_client = self._make_mock_client(["Dragapult Dusknoir", "wrong answer"])
        harness = EvalHarness(mock_client, ExactMatchScorer())
        report = harness.run(path)
        assert report.passed == 1
        assert report.failed == 1

    def test_empty_dataset(self, tmp_path):
        path = _write_dataset(tmp_path, {"name": "empty", "examples": []})
        mock_client = self._make_mock_client([])
        harness = EvalHarness(mock_client, ExactMatchScorer())
        report = harness.run(path)
        assert report.total == 0
        assert report.mean_score == 0.0

    def test_pass_threshold(self, tmp_path):
        dataset = {
            "name": "threshold-test",
            "examples": [
                {
                    "id": "ex-001",
                    "input_prompt": "test",
                    "expected": {"keywords": ["alpha", "beta"]},
                }
            ],
        }
        path = _write_dataset(tmp_path, dataset)
        # Output contains only one of two keywords -> score 0.5
        mock_client = self._make_mock_client(["alpha only"])
        harness = EvalHarness(mock_client, ContainsKeywordsScorer())

        # Default threshold 0.8 -> fail
        report = harness.run(path, pass_threshold=0.8)
        assert report.failed == 1

        # Lower threshold -> pass
        mock_client = self._make_mock_client(["alpha only"])
        harness = EvalHarness(mock_client, ContainsKeywordsScorer())
        report = harness.run(path, pass_threshold=0.4)
        assert report.passed == 1

    def test_system_prompt_forwarded(self, tmp_path):
        dataset = {
            "name": "sys-prompt",
            "examples": [
                {"id": "ex-001", "input_prompt": "test", "expected": {"text": "ok"}},
            ],
        }
        path = _write_dataset(tmp_path, dataset)
        mock_client = self._make_mock_client(["ok"])
        harness = EvalHarness(mock_client, ExactMatchScorer())
        harness.run(path, system_prompt="Be concise.")

        call_kwargs = mock_client.generate.call_args[1]
        assert call_kwargs["system_prompt"] == "Be concise."
