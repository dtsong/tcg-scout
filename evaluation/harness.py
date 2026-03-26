"""Eval harness for running golden dataset tests against model outputs.

Usage
-----
1. Create a golden dataset JSON file (see ``evaluation/README.md``).
2. Implement a ``Scorer`` subclass for your evaluation criteria.
3. Run the harness via ``EvalHarness.run()``.

The harness loads golden examples, calls the model for each, and
scores the output against expected values.
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import anthropic

from reports.model_client import ModelClient

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------


@dataclass
class GoldenExample:
    """A single test case from a golden dataset."""

    id: str
    input_prompt: str
    expected: dict
    metadata: dict = field(default_factory=dict)


@dataclass
class ScoredResult:
    """Result of evaluating a single example."""

    example_id: str
    score: float  # 0.0 to 1.0
    passed: bool
    model_output: str
    details: dict = field(default_factory=dict)


@dataclass
class EvalReport:
    """Aggregate report from an evaluation run."""

    dataset_name: str
    total: int
    passed: int
    failed: int
    mean_score: float
    results: list[ScoredResult]


# ------------------------------------------------------------------
# Scorer interface
# ------------------------------------------------------------------


class Scorer(ABC):
    """Base class for scoring model outputs against expected values."""

    @abstractmethod
    def score(self, model_output: str, expected: dict) -> ScoredResult:
        """Score a single model output.

        Parameters
        ----------
        model_output:
            Raw text from the model.
        expected:
            Expected values from the golden dataset.

        Returns
        -------
        ScoredResult
            Must set example_id to "" (harness overwrites example_id
            and passed based on pass_threshold).
        """
        ...


class ExactMatchScorer(Scorer):
    """Scorer that checks if model output exactly matches expected text."""

    def score(self, model_output: str, expected: dict) -> ScoredResult:
        expected_text = expected.get("text", "")
        match = model_output.strip() == expected_text.strip()
        return ScoredResult(
            example_id="",
            score=1.0 if match else 0.0,
            passed=match,
            model_output=model_output,
            details={"expected": expected_text, "match": match},
        )


class ContainsKeywordsScorer(Scorer):
    """Scorer that checks if model output contains required keywords."""

    def score(self, model_output: str, expected: dict) -> ScoredResult:
        keywords = expected.get("keywords", [])
        if not keywords:
            return ScoredResult(
                example_id="",
                score=1.0,
                passed=True,
                model_output=model_output,
                details={"keywords": [], "missing": []},
            )

        output_lower = model_output.lower()
        missing = [kw for kw in keywords if kw.lower() not in output_lower]
        hit_ratio = 1.0 - (len(missing) / len(keywords))
        return ScoredResult(
            example_id="",
            score=hit_ratio,
            passed=len(missing) == 0,
            model_output=model_output,
            details={"keywords": keywords, "missing": missing},
        )


class JSONSchemaScorer(Scorer):
    """Scorer that checks if model output is valid JSON with required keys."""

    def score(self, model_output: str, expected: dict) -> ScoredResult:
        required_keys = expected.get("required_keys", [])
        try:
            parsed = json.loads(model_output)
        except (json.JSONDecodeError, TypeError):
            return ScoredResult(
                example_id="",
                score=0.0,
                passed=False,
                model_output=model_output,
                details={"error": "Invalid JSON"},
            )

        if not isinstance(parsed, dict):
            return ScoredResult(
                example_id="",
                score=0.0,
                passed=False,
                model_output=model_output,
                details={"error": "Expected JSON object"},
            )

        missing = [k for k in required_keys if k not in parsed]
        hit_ratio = 1.0 - (len(missing) / len(required_keys)) if required_keys else 1.0
        return ScoredResult(
            example_id="",
            score=hit_ratio,
            passed=len(missing) == 0,
            model_output=model_output,
            details={"required_keys": required_keys, "missing_keys": missing},
        )


# ------------------------------------------------------------------
# Harness
# ------------------------------------------------------------------


def _parse_golden_examples(data: dict, source: str) -> list[GoldenExample]:
    """Parse golden examples from already-loaded JSON data.

    Parameters
    ----------
    data:
        Parsed JSON dictionary with an ``examples`` key.
    source:
        Label for error messages (typically the file path).
    """
    if "examples" not in data:
        raise ValueError(
            f"Golden dataset {source} is missing 'examples' key. Available keys: {list(data.keys())}"
        )
    examples = []
    for i, item in enumerate(data["examples"]):
        for required_key in ("id", "input_prompt"):
            if required_key not in item:
                raise ValueError(
                    f"Example at index {i} in {source} is missing required key '{required_key}'"
                )
        examples.append(
            GoldenExample(
                id=item["id"],
                input_prompt=item["input_prompt"],
                expected=item.get("expected", {}),
                metadata=item.get("metadata", {}),
            )
        )
    return examples


def load_golden_dataset(path: Path) -> list[GoldenExample]:
    """Load golden examples from a JSON file.

    Expected format::

        {
            "name": "dataset-name",
            "examples": [
                {
                    "id": "example-001",
                    "input_prompt": "...",
                    "expected": { ... },
                    "metadata": { ... }
                }
            ]
        }
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    return _parse_golden_examples(data, str(path))


class EvalHarness:
    """Run golden dataset evaluations against a ModelClient."""

    def __init__(self, client: ModelClient, scorer: Scorer) -> None:
        self.client = client
        self.scorer = scorer

    def run(
        self,
        dataset_path: Path,
        *,
        system_prompt: str | None = None,
        pass_threshold: float = 0.8,
    ) -> EvalReport:
        """Execute evaluation against a golden dataset.

        Parameters
        ----------
        dataset_path:
            Path to the golden dataset JSON file.
        system_prompt:
            Optional system prompt passed to the model for every example.
        pass_threshold:
            Minimum score for an example to be considered passing.
        """
        data = json.loads(dataset_path.read_text(encoding="utf-8"))
        dataset_name = data.get("name", dataset_path.stem)
        examples = _parse_golden_examples(data, str(dataset_path))

        results: list[ScoredResult] = []
        for example in examples:
            logger.info("Evaluating example %s", example.id)
            try:
                model_output = self.client.generate(
                    example.input_prompt,
                    system_prompt=system_prompt,
                )
            except (anthropic.APIError, ValueError, TypeError) as exc:
                logger.error("Model call failed for example %s: %s", example.id, exc)
                results.append(
                    ScoredResult(
                        example_id=example.id,
                        score=0.0,
                        passed=False,
                        model_output="",
                        details={"error": str(exc)},
                    )
                )
                continue
            result = self.scorer.score(model_output, example.expected)
            result.example_id = example.id
            result.passed = result.score >= pass_threshold
            results.append(result)

        passed = sum(1 for r in results if r.passed)
        mean_score = sum(r.score for r in results) / len(results) if results else 0.0

        report = EvalReport(
            dataset_name=dataset_name,
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            mean_score=mean_score,
            results=results,
        )
        logger.info(
            "Eval complete: %s — %d/%d passed (mean score: %.2f)",
            dataset_name,
            passed,
            len(results),
            mean_score,
        )
        return report
