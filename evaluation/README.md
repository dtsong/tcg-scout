# Evaluation Harness

Framework for running golden dataset tests against Scout model outputs.

## Golden Dataset Format

Create a JSON file with the following structure:

```json
{
  "name": "my-eval-dataset",
  "examples": [
    {
      "id": "example-001",
      "input_prompt": "Summarize the meta for Dragapult Dusknoir at 9% share.",
      "expected": {
        "keywords": ["Dragapult", "Dusknoir", "9%"],
        "required_keys": ["sections"]
      },
      "metadata": {
        "category": "meta-summary",
        "difficulty": "easy"
      }
    }
  ]
}
```

## Built-in Scorers

- **ExactMatchScorer** -- checks if output exactly matches `expected.text`
- **ContainsKeywordsScorer** -- checks if output contains all `expected.keywords`
- **JSONSchemaScorer** -- checks if output is valid JSON with `expected.required_keys`

## Adding a Custom Scorer

Subclass `evaluation.harness.Scorer` and implement the `score()` method:

```python
from evaluation.harness import Scorer, ScoredResult

class MyScorer(Scorer):
    def score(self, model_output: str, expected: dict) -> ScoredResult:
        # Custom scoring logic
        return ScoredResult(
            example_id="",
            score=1.0,
            passed=True,
            model_output=model_output,
            details={},
        )
```

## Running Evaluations

```python
from reports.model_client import ModelClient
from evaluation.harness import EvalHarness, ContainsKeywordsScorer

client = ModelClient(model_id="claude-haiku-4-5-20251001")
harness = EvalHarness(client, ContainsKeywordsScorer())
report = harness.run(Path("evaluation/datasets/my-dataset.json"))
print(f"Passed: {report.passed}/{report.total}")
```

## Directory Structure

```
evaluation/
  __init__.py
  harness.py           # Core framework
  README.md            # This file
  datasets/            # Golden dataset JSON files (add yours here)
```
