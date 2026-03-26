"""Tests for reports/narrative.py — context assembly and fact validation."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest.importorskip("anthropic")

from reports.model_client import ModelClient
from reports.narrative import (
    _slugify,
    assemble_report_context,
    validate_report_facts,
)

# --- Fixtures ---

META_JSON = {
    "generated_at": "2026-03-17T00:00:00",
    "tournament_count": 100,
    "deck_count": 1000,
    "date_range": {"start": "2026-01-23", "end": "2026-03-08"},
    "rotation_date": "2026-04-10",
    "tier_thresholds": {"S": 15.0, "A": 8.0},
    "format_name": "Nihil Zero",
    "archetypes": [
        {
            "archetype": "Dragapult Dusknoir",
            "slug": "dragapult-dusknoir",
            "meta_share": 9.0,
            "weighted_share": 8.9,
            "deck_count": 90,
            "best_placement": 1,
            "tier": "A",
            "trend": "down",
            "trend_delta": -6.3,
        },
        {
            "archetype": "Mega Lucario",
            "slug": "mega-lucario",
            "meta_share": 9.0,
            "weighted_share": 8.8,
            "deck_count": 90,
            "best_placement": 1,
            "tier": "A",
            "trend": "down",
            "trend_delta": -6.1,
        },
    ],
}

TRENDS_JSON = {
    "midpoint": "2026-02-14",
    "early_decks": 500,
    "late_decks": 500,
    "surging": [
        {
            "card_name": "Unfair Stamp",
            "early_count": 100,
            "late_count": 200,
            "early_pct": 20.0,
            "late_pct": 40.0,
            "delta": 20.0,
            "direction": "surging",
            "archetypes": [
                {
                    "archetype": "Dragapult Dusknoir",
                    "early_pct": 78.6,
                    "late_pct": 89.7,
                    "delta": 11.1,
                }
            ],
        }
    ],
    "declining": [],
}

WINNING_EDGE_JSON = [
    {
        "card_name": "Munkidori",
        "field_pct": 48.9,
        "win_pct": 60.4,
        "edge": 11.5,
        "winner_decks": 136,
        "field_decks": 1783,
    },
    {
        "card_name": "Budew",
        "field_pct": 52.9,
        "win_pct": 60.9,
        "edge": 8.0,
        "winner_decks": 137,
        "field_decks": 1929,
    },
]

MATCHUP_JSON = {
    "archetypes": ["Mega Lucario", "Dragapult Dusknoir", "Alakazam Dudunsparce"],
    "matrix": [
        [0.0, -0.6, -1.1],
        [0.6, 0.0, 0.1],
        [1.1, -0.1, 0.0],
    ],
}


def _write_data_files(tmp_path: Path, format_slug: str = "test-format") -> Path:
    """Write mock JSON files to a temp data directory and return data_dir."""
    fmt_dir = tmp_path / format_slug
    fmt_dir.mkdir(parents=True)
    (fmt_dir / "meta.json").write_text(json.dumps(META_JSON), encoding="utf-8")
    (fmt_dir / "trends.json").write_text(json.dumps(TRENDS_JSON), encoding="utf-8")
    (fmt_dir / "winning-edge.json").write_text(json.dumps(WINNING_EDGE_JSON), encoding="utf-8")
    (fmt_dir / "matchup.json").write_text(json.dumps(MATCHUP_JSON), encoding="utf-8")
    return tmp_path


# --- _slugify ---


class TestSlugify:
    def test_basic(self):
        assert _slugify("Dragapult Dusknoir") == "dragapult-dusknoir"

    def test_special_chars(self):
        assert _slugify("Boss's Orders") == "boss-s-orders"

    def test_already_slugified(self):
        assert _slugify("mega-lucario") == "mega-lucario"


# --- assemble_report_context ---


class TestAssembleReportContext:
    def test_returns_format_slug(self, tmp_path):
        data_dir = _write_data_files(tmp_path, "test-format")
        ctx = assemble_report_context("test-format", data_dir)
        assert ctx["format_slug"] == "test-format"

    def test_top_archetypes_present(self, tmp_path):
        data_dir = _write_data_files(tmp_path, "test-format")
        ctx = assemble_report_context("test-format", data_dir)
        assert len(ctx["top_archetypes"]) == 2
        assert ctx["top_archetypes"][0]["archetype"] == "Dragapult Dusknoir"

    def test_tournament_and_deck_counts(self, tmp_path):
        data_dir = _write_data_files(tmp_path, "test-format")
        ctx = assemble_report_context("test-format", data_dir)
        assert ctx["tournament_count"] == 100
        assert ctx["deck_count"] == 1000

    def test_surging_cards_assembled(self, tmp_path):
        data_dir = _write_data_files(tmp_path, "test-format")
        ctx = assemble_report_context("test-format", data_dir)
        assert len(ctx["surging_cards"]) == 1
        card = ctx["surging_cards"][0]
        assert card["card_name"] == "Unfair Stamp"
        assert card["delta"] == 20.0
        assert card["top_archetype"] == "Dragapult Dusknoir"

    def test_winning_edge_cards_assembled(self, tmp_path):
        data_dir = _write_data_files(tmp_path, "test-format")
        ctx = assemble_report_context("test-format", data_dir)
        assert len(ctx["winning_edge_cards"]) == 2
        assert ctx["winning_edge_cards"][0]["card_name"] == "Munkidori"
        assert ctx["winning_edge_cards"][0]["edge"] == 11.5

    def test_matchup_spotlight_assembled(self, tmp_path):
        data_dir = _write_data_files(tmp_path, "test-format")
        ctx = assemble_report_context("test-format", data_dir)
        assert len(ctx["matchup_spotlight"]) > 0
        # Largest absolute score is 1.1 (Alakazam Dudunsparce vs Mega Lucario)
        top = ctx["matchup_spotlight"][0]
        assert abs(top["score"]) == pytest.approx(1.1, abs=0.01)

    def test_handles_missing_trends(self, tmp_path):
        fmt_dir = tmp_path / "test-format"
        fmt_dir.mkdir(parents=True)
        (fmt_dir / "meta.json").write_text(json.dumps(META_JSON), encoding="utf-8")
        (fmt_dir / "winning-edge.json").write_text(json.dumps(WINNING_EDGE_JSON), encoding="utf-8")
        (fmt_dir / "matchup.json").write_text(json.dumps(MATCHUP_JSON), encoding="utf-8")
        # trends.json is missing
        ctx = assemble_report_context("test-format", tmp_path)
        assert ctx["surging_cards"] == []

    def test_handles_missing_matchup(self, tmp_path):
        fmt_dir = tmp_path / "test-format"
        fmt_dir.mkdir(parents=True)
        (fmt_dir / "meta.json").write_text(json.dumps(META_JSON), encoding="utf-8")
        (fmt_dir / "trends.json").write_text(json.dumps(TRENDS_JSON), encoding="utf-8")
        (fmt_dir / "winning-edge.json").write_text(json.dumps(WINNING_EDGE_JSON), encoding="utf-8")
        # matchup.json is missing
        ctx = assemble_report_context("test-format", tmp_path)
        assert ctx["matchup_spotlight"] == []

    def test_top_archetypes_capped_at_10(self, tmp_path):
        meta = dict(META_JSON)
        meta["archetypes"] = [
            {
                "archetype": f"Arch {i}",
                "slug": f"arch-{i}",
                "meta_share": 5.0,
                "deck_count": 50,
                "best_placement": 1,
                "tier": "B",
                "trend": "stable",
                "trend_delta": 0.0,
            }
            for i in range(15)
        ]
        fmt_dir = tmp_path / "test-format"
        fmt_dir.mkdir(parents=True)
        (fmt_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (fmt_dir / "trends.json").write_text(json.dumps(TRENDS_JSON), encoding="utf-8")
        (fmt_dir / "winning-edge.json").write_text(json.dumps(WINNING_EDGE_JSON), encoding="utf-8")
        (fmt_dir / "matchup.json").write_text(json.dumps(MATCHUP_JSON), encoding="utf-8")
        ctx = assemble_report_context("test-format", tmp_path)
        assert len(ctx["top_archetypes"]) == 10


# --- validate_report_facts ---


class TestValidateReportFacts:
    def _make_context(self):
        return {
            "top_archetypes": META_JSON["archetypes"],
            "surging_cards": [{"card_name": "Unfair Stamp"}],
            "winning_edge_cards": [{"card_name": "Munkidori"}],
        }

    def test_valid_report_returns_no_errors(self):
        ctx = self._make_context()
        errors = validate_report_facts("Dragapult Dusknoir holds 9.0% meta share.", ctx)
        assert errors == []

    def test_implausible_percentage_flagged(self):
        ctx = self._make_context()
        errors = validate_report_facts("This card is in 120% of decks.", ctx)
        assert any("120" in e for e in errors)

    def test_valid_percentages_not_flagged(self):
        ctx = self._make_context()
        errors = validate_report_facts("Win rate of 60.4% is notable.", ctx)
        assert errors == []

    def test_empty_report_text_valid(self):
        ctx = self._make_context()
        assert validate_report_facts("", ctx) == []

    def test_meta_share_mismatch_flagged(self):
        ctx = self._make_context()
        # Data says 9.0% but report says 15.0%
        errors = validate_report_facts("Dragapult Dusknoir has grown to 15.0% meta share.", ctx)
        assert any("mismatch" in e.lower() for e in errors)
        assert any("15.0" in e for e in errors)

    def test_meta_share_close_value_not_flagged(self):
        ctx = self._make_context()
        # Within 0.5% tolerance
        errors = validate_report_facts("Dragapult Dusknoir sits at 9.2% meta share.", ctx)
        assert errors == []


# --- generate_report (integration, LLM mocked) ---


def _make_mock_client(llm_response: str) -> ModelClient:
    """Create a ModelClient with a mocked generate method."""
    client = MagicMock(spec=ModelClient)
    client.model_id = "test-model"
    client.generate.return_value = llm_response
    return client


class TestGenerateReport:
    def test_writes_report_json(self, tmp_path):
        from reports.narrative import generate_report

        data_dir = _write_data_files(tmp_path, "test-format")
        output_dir = tmp_path / "output"

        llm_response = json.dumps(
            {
                "sections": [
                    {
                        "id": "meta-at-a-glance",
                        "title": "Meta at a Glance",
                        "content": "Dragapult Dusknoir leads the meta at 9.0% share.",
                        "highlights": ["Top archetype is Dragapult Dusknoir"],
                    }
                ],
                "tweets": ["Meta update: Dragapult Dusknoir leads!"],
            }
        )

        mock_client = _make_mock_client(llm_response)
        result_path = generate_report("test-format", data_dir, output_dir, model_client=mock_client)

        assert result_path.exists()
        report = json.loads(result_path.read_text(encoding="utf-8"))
        assert report["format"] == "test-format"
        assert "data_hash" in report
        assert len(report["sections"]) == 1
        assert report["sections"][0]["id"] == "meta-at-a-glance"

    def test_writes_thread_json(self, tmp_path):
        from reports.narrative import generate_report

        data_dir = _write_data_files(tmp_path, "test-format")
        output_dir = tmp_path / "output"

        llm_response = json.dumps(
            {
                "sections": [],
                "tweets": ["Tweet 1", "Tweet 2"],
            }
        )

        mock_client = _make_mock_client(llm_response)
        generate_report("test-format", data_dir, output_dir, model_client=mock_client)

        thread_path = output_dir / "test-format" / "report-thread.json"
        assert thread_path.exists()
        thread = json.loads(thread_path.read_text(encoding="utf-8"))
        assert thread["format"] == "test-format"
        assert thread["tweets"] == ["Tweet 1", "Tweet 2"]

    def test_cache_prevents_second_llm_call(self, tmp_path):
        from reports.narrative import generate_report

        data_dir = _write_data_files(tmp_path, "test-format")
        output_dir = tmp_path / "output"

        llm_response = json.dumps({"sections": [], "tweets": []})
        mock_client = _make_mock_client(llm_response)

        generate_report("test-format", data_dir, output_dir, model_client=mock_client)
        generate_report("test-format", data_dir, output_dir, model_client=mock_client)
        assert mock_client.generate.call_count == 1

    def test_extracts_json_from_markdown_fences(self, tmp_path):
        from reports.narrative import generate_report

        data_dir = _write_data_files(tmp_path, "test-format")
        output_dir = tmp_path / "output"

        # LLM wraps JSON in markdown code fences
        llm_response = '```json\n{"sections": [{"id": "s1", "title": "T", "content": "C", "highlights": []}], "tweets": ["t"]}\n```'
        mock_client = _make_mock_client(llm_response)
        result_path = generate_report("test-format", data_dir, output_dir, model_client=mock_client)

        report = json.loads(result_path.read_text(encoding="utf-8"))
        assert len(report["sections"]) == 1

    def test_raises_on_garbage_llm_response(self, tmp_path):
        from reports.narrative import generate_report

        data_dir = _write_data_files(tmp_path, "test-format")
        output_dir = tmp_path / "output"

        mock_client = _make_mock_client("This is not JSON at all, no braces here.")
        with pytest.raises(ValueError, match="did not contain valid JSON"):
            generate_report("test-format", data_dir, output_dir, model_client=mock_client)

    def test_raises_on_empty_archetypes(self, tmp_path):
        from reports.narrative import generate_report

        fmt_dir = tmp_path / "test-format"
        fmt_dir.mkdir(parents=True)
        empty_meta = dict(META_JSON)
        empty_meta["archetypes"] = []
        (fmt_dir / "meta.json").write_text(json.dumps(empty_meta), encoding="utf-8")
        (fmt_dir / "trends.json").write_text(json.dumps(TRENDS_JSON), encoding="utf-8")
        (fmt_dir / "winning-edge.json").write_text(json.dumps(WINNING_EDGE_JSON), encoding="utf-8")
        (fmt_dir / "matchup.json").write_text(json.dumps(MATCHUP_JSON), encoding="utf-8")
        output_dir = tmp_path / "output"

        mock_client = _make_mock_client("{}")
        with pytest.raises(ValueError, match="No archetype data"):
            generate_report("test-format", tmp_path, output_dir, model_client=mock_client)

    def test_generates_report_json_with_valid_shape(self, tmp_path):
        from reports.narrative import generate_report

        data_dir = _write_data_files(tmp_path, "test-format")
        output_dir = tmp_path / "output"

        sections = [
            {
                "id": f"section-{i}",
                "title": f"Section {i}",
                "content": "Some content here.",
                "highlights": ["Key point"],
            }
            for i in range(5)
        ]
        llm_response = json.dumps({"sections": sections, "tweets": ["t1", "t2"]})
        mock_client = _make_mock_client(llm_response)
        result_path = generate_report("test-format", data_dir, output_dir, model_client=mock_client)

        report = json.loads(result_path.read_text(encoding="utf-8"))
        assert len(report["sections"]) == 5
        assert "generated_at" in report
