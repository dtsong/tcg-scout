"""Tests for the validation module."""

import json
import sqlite3

import pytest

from validation import ValidationResult, validate_database, validate_export


@pytest.fixture()
def export_dir(tmp_path):
    """Create a valid export directory structure."""
    fmt_dir = tmp_path / "test-format"
    fmt_dir.mkdir()

    # Required files
    meta = {
        "generated_at": "2026-03-20T12:00:00Z",
        "tournament_count": 10,
        "deck_count": 50,
        "archetypes": [
            {"slug": "charizard-ex", "archetype": "Charizard ex", "meta_share": 20.0, "tier": "S"},
        ],
    }
    (fmt_dir / "meta.json").write_text(json.dumps(meta))
    (fmt_dir / "buylist.json").write_text(json.dumps([]))
    (fmt_dir / "staples.json").write_text(json.dumps([]))
    (fmt_dir / "flex.json").write_text(json.dumps([]))
    (fmt_dir / "trends.json").write_text(json.dumps({}))
    (fmt_dir / "winning-edge.json").write_text(json.dumps([]))

    # Required directory with content
    archetypes_dir = fmt_dir / "archetypes"
    archetypes_dir.mkdir()
    (archetypes_dir / "charizard-ex.json").write_text(json.dumps({"slug": "charizard-ex"}))

    return fmt_dir


class TestValidateExport:
    def test_valid_export_passes(self, export_dir):
        result = validate_export(export_dir)
        assert result.ok
        assert len(result.errors) == 0

    def test_missing_directory(self, tmp_path):
        result = validate_export(tmp_path / "nonexistent")
        assert not result.ok
        assert any("does not exist" in e for e in result.errors)

    def test_missing_required_file(self, export_dir):
        (export_dir / "meta.json").unlink()
        result = validate_export(export_dir)
        assert not result.ok
        assert any("meta.json" in e for e in result.errors)

    def test_empty_archetypes_dir(self, export_dir):
        for f in (export_dir / "archetypes").iterdir():
            f.unlink()
        result = validate_export(export_dir)
        assert not result.ok
        assert any("empty" in e for e in result.errors)

    def test_invalid_json(self, export_dir):
        (export_dir / "buylist.json").write_text("{invalid json")
        result = validate_export(export_dir)
        assert not result.ok
        assert any("invalid JSON" in e for e in result.errors)

    def test_empty_archetypes_is_error(self, export_dir):
        meta = {"archetypes": []}
        (export_dir / "meta.json").write_text(json.dumps(meta))
        result = validate_export(export_dir)
        assert not result.ok
        assert any("empty 'archetypes'" in e for e in result.errors)

    def test_missing_archetype_file_is_warning(self, export_dir):
        meta = json.loads((export_dir / "meta.json").read_text())
        meta["archetypes"].append({"slug": "missing-deck", "archetype": "Missing", "tier": "B"})
        (export_dir / "meta.json").write_text(json.dumps(meta))
        result = validate_export(export_dir)
        assert result.ok  # Warning, not error
        assert any("missing-deck" in w for w in result.warnings)

    def test_jp_characters_are_warning(self, export_dir):
        (export_dir / "archetypes" / "charizard-ex.json").write_text(
            json.dumps({"card": "\u30ea\u30b6\u30fc\u30c9\u30f3"}, ensure_ascii=False)
        )
        result = validate_export(export_dir)
        assert result.ok  # Warning, not error
        assert any("Japanese" in w for w in result.warnings)

    def test_oversized_file_is_warning(self, export_dir):
        # Create a file slightly over 1MB
        big_data = json.dumps({"data": "x" * (1024 * 1024 + 100)})
        (export_dir / "buylist.json").write_text(big_data)
        result = validate_export(export_dir)
        assert result.ok  # Warning, not error
        assert any("exceeds" in w for w in result.warnings)


class TestValidateDatabase:
    @pytest.fixture()
    def conn(self, db):
        return db

    def test_valid_db_passes(self, conn):
        result = validate_database(conn)
        assert result.ok

    def test_empty_db_warns(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        from db import SCHEMA

        conn.executescript(SCHEMA)
        result = validate_database(conn)
        assert result.ok  # Warning, not error
        assert any("No tournaments" in w for w in result.warnings)

    def test_high_unknown_rate_warns(self, conn):
        # Add many Unknown placements
        for i in range(100, 120):
            conn.execute(
                "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
                "VALUES (?, 't1', ?, 'Unknown Player', 'Unknown')",
                (i, i),
            )
        conn.commit()
        result = validate_database(conn)
        assert any("Unknown archetype rate" in w for w in result.warnings)

    def test_duplicate_tournaments_warns(self, conn):
        conn.execute(
            "INSERT INTO tournaments (id, name, date, player_count, division) "
            "VALUES ('t99', 'Osaka CL Jan', '2026-01-25', 64, 'open')"
        )
        conn.commit()
        result = validate_database(conn)
        assert any("Duplicate tournament" in w for w in result.warnings)


class TestValidationResult:
    def test_ok_when_no_errors(self):
        result = ValidationResult()
        assert result.ok

    def test_not_ok_with_errors(self):
        result = ValidationResult(errors=["something broke"])
        assert not result.ok

    def test_ok_with_only_warnings(self):
        result = ValidationResult(warnings=["heads up"])
        assert result.ok

    def test_merge(self):
        a = ValidationResult(errors=["e1"], warnings=["w1"])
        b = ValidationResult(errors=["e2"], warnings=["w2"])
        a.merge(b)
        assert len(a.errors) == 2
        assert len(a.warnings) == 2
