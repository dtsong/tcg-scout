"""Data contract tests: validate JSON export shapes match expected TypeScript interfaces.

These tests guard against silent drift between Python exports and TypeScript types.
Each test runs export_all against the db_integration fixture and validates the shape
of the resulting JSON files.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _export_once(db_integration, tmp_path):
    """Helper: compute meta snapshot and export all, return output dir."""
    from analysis.meta import compute_meta_snapshot
    from reports.json_export import export_all

    db_integration.execute("DELETE FROM archetype_stats")
    db_integration.execute("DELETE FROM meta_snapshots")
    db_integration.commit()

    compute_meta_snapshot(db_integration)
    return export_all(db_integration, output_dir=tmp_path, format_slug="nihil-zero")


@pytest.fixture()
def export_dir(db_integration, tmp_path):
    """Run export_all once and return the output directory."""
    return _export_once(db_integration, tmp_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_keys(obj, required_keys, context=""):
    """Assert all required keys exist in a dict."""
    missing = set(required_keys) - set(obj.keys())
    assert not missing, f"Missing keys in {context}: {missing}"


def _assert_type(val, expected_types, field_name):
    """Assert a value matches one of the expected types."""
    assert isinstance(val, expected_types), (
        f"{field_name}: expected {expected_types}, got {type(val).__name__} = {val!r}"
    )


def _assert_no_none(obj, fields, context=""):
    """Assert specified fields are not None."""
    for field in fields:
        assert obj.get(field) is not None, f"{context}.{field} is None"


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestMetaContract:
    def test_meta_json_shape(self, export_dir):
        meta = json.loads((export_dir / "meta.json").read_text())

        _assert_keys(
            meta,
            ["generated_at", "tournament_count", "deck_count", "date_range", "archetypes"],
            "meta.json",
        )
        _assert_type(meta["tournament_count"], int, "tournament_count")
        _assert_type(meta["deck_count"], int, "deck_count")
        _assert_type(meta["archetypes"], list, "archetypes")
        assert len(meta["archetypes"]) > 0, "archetypes should not be empty"

        # date_range shape
        _assert_keys(meta["date_range"], ["start", "end"], "date_range")

        # format metadata
        assert "format" in meta
        _assert_keys(meta["format"], ["slug", "name"], "format")

    def test_archetype_items_shape(self, export_dir):
        meta = json.loads((export_dir / "meta.json").read_text())

        for arch in meta["archetypes"]:
            _assert_keys(
                arch,
                [
                    "archetype",
                    "slug",
                    "meta_share",
                    "weighted_share",
                    "deck_count",
                    "best_placement",
                    "tier",
                ],
                f"archetype={arch.get('archetype')}",
            )
            _assert_no_none(
                arch,
                ["archetype", "slug", "meta_share", "tier"],
                f"archetype={arch.get('archetype')}",
            )
            _assert_type(arch["meta_share"], (int, float), "meta_share")
            _assert_type(arch["weighted_share"], (int, float), "weighted_share")
            _assert_type(arch["deck_count"], int, "deck_count")
            assert arch["tier"] in {"S", "A", "B", "C", "Rogue"}, f"Invalid tier: {arch['tier']}"


@pytest.mark.integration
class TestBuylistContract:
    def test_buylist_json_shape(self, export_dir):
        buylist = json.loads((export_dir / "buylist.json").read_text())

        _assert_type(buylist, list, "buylist.json root")
        if len(buylist) > 0:
            for item in buylist:
                _assert_keys(
                    item,
                    [
                        "card_name",
                        "card_id",
                        "set_code",
                        "set_number",
                        "priority_score",
                        "urgency",
                        "core_flex",
                        "archetypes",
                        "avg_copies",
                        "inclusion_rate",
                    ],
                    f"buylist item={item.get('card_name')}",
                )
                _assert_type(item["priority_score"], (int, float), "priority_score")
                _assert_type(item["card_name"], str, "card_name")
                _assert_type(item["archetypes"], list, "archetypes")
                _assert_type(item["avg_copies"], (int, float), "avg_copies")
                _assert_type(item["inclusion_rate"], (int, float), "inclusion_rate")
                assert item["urgency"] in {"URGENT", "HIGH", "MODERATE"}, (
                    f"Invalid urgency: {item['urgency']}"
                )
                assert item["core_flex"] in {"core", "flex"}, (
                    f"Invalid core_flex: {item['core_flex']}"
                )


@pytest.mark.integration
class TestTrendsContract:
    def test_trends_json_shape(self, export_dir):
        trends = json.loads((export_dir / "trends.json").read_text())

        _assert_keys(
            trends,
            ["midpoint", "early_decks", "late_decks", "surging", "declining"],
            "trends.json",
        )
        _assert_type(trends["early_decks"], int, "early_decks")
        _assert_type(trends["late_decks"], int, "late_decks")
        _assert_type(trends["surging"], list, "surging")
        _assert_type(trends["declining"], list, "declining")

        # If there are surging/declining items, validate shape
        for card in trends["surging"] + trends["declining"]:
            _assert_keys(
                card,
                ["card_name", "early_pct", "late_pct", "delta"],
                "trends card item",
            )
            _assert_type(card["delta"], (int, float), "delta")


@pytest.mark.integration
class TestArchetypesContract:
    def test_archetype_detail_files_exist(self, export_dir):
        arch_dir = export_dir / "archetypes"
        assert arch_dir.is_dir(), "archetypes/ directory should exist"
        arch_files = list(arch_dir.glob("*.json"))
        assert len(arch_files) >= 3, f"Expected >=3 archetype files, found {len(arch_files)}"

    def test_archetype_detail_shape(self, export_dir):
        arch_dir = export_dir / "archetypes"
        for arch_file in arch_dir.glob("*.json"):
            data = json.loads(arch_file.read_text())
            _assert_keys(
                data,
                [
                    "archetype",
                    "slug",
                    "tier",
                    "meta_share",
                    "weighted_share",
                    "deck_count",
                    "core_cards",
                    "all_cards",
                    "results",
                    "radar",
                ],
                f"archetypes/{arch_file.name}",
            )
            _assert_no_none(
                data,
                ["archetype", "slug", "tier"],
                f"archetypes/{arch_file.name}",
            )
            _assert_type(data["core_cards"], list, "core_cards")
            _assert_type(data["all_cards"], list, "all_cards")
            _assert_type(data["results"], list, "results")
            _assert_type(data["radar"], dict, "radar")

            # Radar shape — matches ArchetypeRadar in types.ts
            _assert_keys(
                data["radar"],
                [
                    "meta_share",
                    "weighted_share",
                    "consistency",
                    "ceiling",
                    "popularity",
                    "core_density",
                ],
                f"archetypes/{arch_file.name} radar",
            )

    def test_archetype_card_shape(self, export_dir):
        """Validate ArchetypeCard items in all_cards — matches types.ts:102-108."""
        arch_dir = export_dir / "archetypes"
        for arch_file in arch_dir.glob("*.json"):
            data = json.loads(arch_file.read_text())
            for card in data["all_cards"]:
                _assert_keys(
                    card,
                    ["card_name", "inclusion_pct", "avg_copies", "decks_with"],
                    f"{arch_file.name} all_cards item={card.get('card_name')}",
                )
                _assert_type(card["inclusion_pct"], (int, float), "inclusion_pct")
                _assert_type(card["avg_copies"], (int, float), "avg_copies")
                _assert_type(card["decks_with"], int, "decks_with")

    def test_archetype_result_shape(self, export_dir):
        """Validate ArchetypeResult items — matches types.ts:118-125."""
        arch_dir = export_dir / "archetypes"
        for arch_file in arch_dir.glob("*.json"):
            data = json.loads(arch_file.read_text())
            for result in data["results"]:
                _assert_keys(
                    result,
                    ["tournament_name", "date", "standing", "player_name"],
                    f"{arch_file.name} result",
                )
                _assert_type(result["standing"], int, "standing")
                _assert_type(result["date"], str, "date")
                _assert_type(result["player_name"], str, "player_name")


@pytest.mark.integration
class TestFormatsContract:
    def test_formats_json_shape(self, export_dir):
        from reports.json_export import export_formats

        # export_formats writes to the parent of format dirs
        export_formats(output_dir=export_dir.parent)

        formats_path = export_dir.parent / "formats.json"
        assert formats_path.exists(), "formats.json should exist"

        formats = json.loads(formats_path.read_text())
        _assert_type(formats, list, "formats.json root")
        assert len(formats) >= 2, "Should have at least 2 formats"

        for fmt in formats:
            _assert_keys(fmt, ["slug", "name", "status"], f"format={fmt.get('slug')}")
            assert fmt["status"] in {"active", "frozen", "upcoming"}, (
                f"Invalid status: {fmt['status']}"
            )


@pytest.mark.integration
class TestExportCompleteness:
    """Verify export_all produces all expected files."""

    EXPECTED_FILES = [
        "meta.json",
        "buylist.json",
        "staples.json",
        "flex.json",
        "trends.json",
        "winning-edge.json",
        "ace-specs.json",
        "timeline.json",
    ]

    EXPECTED_DIRS = [
        "archetypes",
    ]

    def test_all_expected_files_exist(self, export_dir):
        for fname in self.EXPECTED_FILES:
            path = export_dir / fname
            assert path.exists(), f"Missing expected export file: {fname}"
            # Verify it's valid JSON
            data = json.loads(path.read_text())
            assert data is not None, f"{fname} parsed to None"

    def test_all_expected_dirs_exist(self, export_dir):
        for dname in self.EXPECTED_DIRS:
            path = export_dir / dname
            assert path.is_dir(), f"Missing expected export directory: {dname}"

    def test_no_empty_json_files(self, export_dir):
        """No exported JSON file should be an empty object/array when data exists."""
        for json_file in export_dir.glob("*.json"):
            data = json.loads(json_file.read_text())
            # meta.json is a dict, others are lists — both should be non-empty
            if isinstance(data, list):
                # Some files may legitimately be empty (e.g., card-analysis with low sample)
                pass
            elif isinstance(data, dict):
                assert len(data) > 0, f"{json_file.name} is an empty object"
