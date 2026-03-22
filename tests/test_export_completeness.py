"""Integration test: verify export_all completes without silent failures."""

import logging
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

        # Drop a table that optional exports depend on to force an error
        db.execute("DROP VIEW IF EXISTS open_placements")
        db.commit()

        with pytest.raises(Exception):
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

        out = export_all(db, output_dir=tmp_path, format_slug="nihil-zero")
        result = validate_export(out)

        assert result.ok, f"Validation errors: {result.errors}"
