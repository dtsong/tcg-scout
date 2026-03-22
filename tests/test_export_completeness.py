"""Integration tests: verify export_all completes without silent failures and handles edge cases."""

import json
import logging
import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.mark.integration
class TestExportCompleteness:
    def test_export_all_no_skipped_exports(self, db, tmp_path, caplog):
        """export_all should not silently skip any exports on a healthy DB."""
        from analysis.meta import compute_meta_snapshot
        from reports.json_export import export_all

        # Fresh snapshot
        db.execute("DELETE FROM archetype_stats")
        db.execute("DELETE FROM meta_snapshots")
        db.commit()
        compute_meta_snapshot(db)

        # Run export with log capture
        with caplog.at_level(logging.WARNING, logger="reports.json_export"):
            export_all(db, output_dir=tmp_path, format_slug="nihil-zero")

        # Check no "Skipping" warnings were emitted
        skip_messages = [r.message for r in caplog.records if "Skipping" in r.message]
        assert skip_messages == [], f"Exports were silently skipped: {skip_messages}"

    def test_export_strict_propagates_errors(self, db, tmp_path):
        """strict=True should raise instead of swallowing errors."""
        from analysis.meta import compute_meta_snapshot
        from reports.json_export import export_all

        # Fresh snapshot
        db.execute("DELETE FROM archetype_stats")
        db.execute("DELETE FROM meta_snapshots")
        db.commit()
        compute_meta_snapshot(db)

        # Drop a view that optional exports depend on to force an error
        db.execute("DROP VIEW IF EXISTS open_placements")
        db.commit()

        with pytest.raises((sqlite3.OperationalError, ValueError)):
            export_all(db, output_dir=tmp_path, format_slug="nihil-zero", strict=True)

    def test_validation_passes_on_exported_data(self, db, tmp_path):
        """Exported data should pass Tier 1 validation."""
        from analysis.meta import compute_meta_snapshot
        from reports.json_export import export_all
        from validation import validate_export

        # Fresh snapshot
        db.execute("DELETE FROM archetype_stats")
        db.execute("DELETE FROM meta_snapshots")
        db.commit()
        compute_meta_snapshot(db)

        out, _skipped = export_all(db, output_dir=tmp_path, format_slug="nihil-zero")
        result = validate_export(out)

        assert result.ok, f"Validation errors: {result.errors}"


def _export_fresh(conn, tmp_path, format_slug="nihil-zero"):
    """Helper: clear stale snapshots, recompute, and export."""
    from analysis.meta import compute_meta_snapshot
    from reports.json_export import export_all

    conn.execute("DELETE FROM archetype_stats")
    conn.execute("DELETE FROM meta_snapshots")
    conn.commit()
    compute_meta_snapshot(conn)
    out, _skipped = export_all(conn, output_dir=tmp_path, format_slug=format_slug)
    return out


@pytest.mark.integration
class TestPipelineEdgeCases:
    """Test pipeline behavior with degenerate or edge-case data."""

    def test_empty_db_raises_cleanly(self, db_empty):
        """compute_meta_snapshot on empty DB should raise ValueError, not a SQL error."""
        from analysis.meta import compute_meta_snapshot

        with pytest.raises(ValueError, match="No placement data"):
            compute_meta_snapshot(db_empty)

    def test_single_tournament_exports(self, db_single_tournament, tmp_path):
        """Pipeline should handle a single tournament with minimal placements."""
        out = _export_fresh(db_single_tournament, tmp_path)
        meta = json.loads((out / "meta.json").read_text())
        assert meta["tournament_count"] >= 1
        assert meta["deck_count"] >= 2
        assert len(meta["archetypes"]) >= 2

    def test_no_nan_or_infinity_in_exports(self, db_integration, tmp_path):
        """JSON exports must never contain NaN or Infinity values."""
        out = _export_fresh(db_integration, tmp_path)
        nan_inf_re = re.compile(r"(?<![a-zA-Z])(?:NaN|-?Infinity)(?![a-zA-Z])")
        for json_file in out.rglob("*.json"):
            text = json_file.read_text()
            match = nan_inf_re.search(text)
            assert match is None, f"{json_file.name} contains {match.group()}"
            json.loads(text)  # also verify it parses cleanly

    def test_meta_tier_assignments_valid(self, db_integration, tmp_path):
        """Every archetype must have a valid tier."""
        out = _export_fresh(db_integration, tmp_path)
        meta = json.loads((out / "meta.json").read_text())
        valid_tiers = {"S", "A", "B", "C", "Rogue"}
        for arch in meta["archetypes"]:
            assert arch["tier"] in valid_tiers, (
                f"{arch['archetype']} has invalid tier: {arch['tier']}"
            )
            assert arch["meta_share"] > 0
            assert arch["deck_count"] > 0

    def test_archetype_detail_files_match_meta(self, db_integration, tmp_path):
        """Every archetype in meta.json must have a detail file, and vice versa."""
        out = _export_fresh(db_integration, tmp_path)
        meta = json.loads((out / "meta.json").read_text())
        meta_slugs = {a["slug"] for a in meta["archetypes"]}

        archetypes_dir = out / "archetypes"
        detail_slugs = {f.stem for f in archetypes_dir.glob("*.json")}

        missing_details = meta_slugs - detail_slugs
        assert not missing_details, f"Meta archetypes missing detail files: {missing_details}"

        orphan_details = detail_slugs - meta_slugs
        assert not orphan_details, f"Detail files without meta entry: {orphan_details}"

        # Verify key fields match
        for arch in meta["archetypes"]:
            detail = json.loads((archetypes_dir / f"{arch['slug']}.json").read_text())
            assert detail["archetype"] == arch["archetype"]
            assert detail["tier"] == arch["tier"]

    def test_card_index_fields_valid(self, db_integration, tmp_path):
        """Card index entries must have required fields with valid values."""
        out = _export_fresh(db_integration, tmp_path)
        index_path = out / "cards" / "index.json"
        if not index_path.exists():
            pytest.skip("cards/index.json not exported (optional)")

        cards = json.loads(index_path.read_text())
        required_fields = ["card_name", "card_slug", "usage_pct", "avg_copies", "category"]
        for card in cards:
            for field in required_fields:
                assert field in card, f"Card '{card.get('card_name', '?')}' missing: {field}"
            assert 0 <= card["usage_pct"] <= 100, (
                f"{card['card_name']} usage_pct out of range: {card['usage_pct']}"
            )
            assert card["avg_copies"] > 0, (
                f"{card['card_name']} avg_copies must be positive: {card['avg_copies']}"
            )
