"""Data validation for Scout exports and databases."""

import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Matches CJK Unified Ideographs, Katakana, Hiragana (catches untranslated JP text)
_JP_RE = re.compile(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]")

# Required files that must exist in every format export
REQUIRED_FILES = [
    "meta.json",
    "buylist.json",
    "staples.json",
    "flex.json",
    "trends.json",
    "winning-edge.json",
]

# Required directories
REQUIRED_DIRS = ["archetypes"]

# Max file size (1MB safety valve)
MAX_FILE_SIZE = 1_048_576


@dataclass
class ValidationResult:
    """Result of a validation run."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def merge(self, other: "ValidationResult") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


def validate_export(export_dir: Path) -> ValidationResult:
    """Tier 1: Validate exported JSON files in a format directory."""
    result = ValidationResult()

    if not export_dir.is_dir():
        result.errors.append(f"Export directory does not exist: {export_dir}")
        return result

    # Check required files exist
    for filename in REQUIRED_FILES:
        path = export_dir / filename
        if not path.exists():
            result.errors.append(f"Missing required file: {filename}")

    # Check required directories exist and are non-empty
    for dirname in REQUIRED_DIRS:
        dirpath = export_dir / dirname
        if not dirpath.is_dir():
            result.errors.append(f"Missing required directory: {dirname}")
        elif not any(dirpath.iterdir()):
            result.errors.append(f"Required directory is empty: {dirname}")

    # Validate all JSON files parse correctly and check sizes
    json_files = list(export_dir.rglob("*.json"))
    if not json_files:
        result.errors.append("No JSON files found in export directory")
        return result

    for json_path in json_files:
        rel = json_path.relative_to(export_dir)

        # File size check
        size = json_path.stat().st_size
        if size > MAX_FILE_SIZE:
            result.warnings.append(f"{rel}: file size {size / 1024:.0f}KB exceeds 1MB limit")

        # JSON parse check
        try:
            raw = json_path.read_text(encoding="utf-8")
            json.loads(raw)
        except json.JSONDecodeError as exc:
            result.errors.append(f"{rel}: invalid JSON — {exc}")
            continue

    # meta.json content validation
    meta_path = export_dir / "meta.json"
    if meta_path.exists():
        result.merge(_validate_meta_consistency(export_dir, meta_path))

    # JP character leak detection
    result.merge(_check_jp_leaks(export_dir))

    return result


def _validate_meta_consistency(export_dir: Path, meta_path: Path) -> ValidationResult:
    """Check meta.json has data and archetype files match."""
    result = ValidationResult()
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return result  # Already caught in main validation

    # meta.json uses a flat "archetypes" list (each entry has a "tier" field)
    archetypes = meta.get("archetypes")
    if not archetypes:
        result.errors.append("meta.json: missing or empty 'archetypes' field")
        return result

    # Check each archetype in meta has a corresponding detail file
    archetypes_dir = export_dir / "archetypes"
    if archetypes_dir.is_dir():
        for arch in archetypes:
            slug = arch.get("slug")
            if slug:
                detail_file = archetypes_dir / f"{slug}.json"
                if not detail_file.exists():
                    result.warnings.append(
                        f"meta.json references archetype '{slug}' but "
                        f"archetypes/{slug}.json is missing"
                    )

    return result


def _check_jp_leaks(export_dir: Path) -> ValidationResult:
    """Scan exported JSON for untranslated Japanese characters."""
    result = ValidationResult()
    jp_leak_count = 0
    max_reports = 10

    for json_path in export_dir.rglob("*.json"):
        rel = json_path.relative_to(export_dir)
        try:
            raw = json_path.read_text(encoding="utf-8")
        except OSError:
            continue

        # Check string values in JSON for JP characters
        if _JP_RE.search(raw):
            jp_leak_count += 1
            if jp_leak_count <= max_reports:
                result.warnings.append(f"{rel}: contains untranslated Japanese characters")

    if jp_leak_count > max_reports:
        result.warnings.append(
            f"... and {jp_leak_count - max_reports} more files with JP characters"
        )

    return result


def validate_database(conn: sqlite3.Connection) -> ValidationResult:
    """Tier 2: Validate database integrity."""
    result = ValidationResult()

    # Tournament count
    row = conn.execute("SELECT COUNT(*) as cnt FROM tournaments").fetchone()
    tournament_count = row["cnt"] if row else 0
    if tournament_count == 0:
        result.warnings.append("No tournaments in database")
        return result

    # Unknown archetype rate
    total = conn.execute("SELECT COUNT(*) as cnt FROM open_placements").fetchone()
    unknown = conn.execute(
        "SELECT COUNT(*) as cnt FROM open_placements WHERE archetype = 'Unknown'"
    ).fetchone()

    total_count = total["cnt"] if total else 0
    unknown_count = unknown["cnt"] if unknown else 0

    if total_count > 0:
        unknown_rate = unknown_count / total_count * 100
        if unknown_rate > 15:
            result.warnings.append(
                f"Unknown archetype rate is {unknown_rate:.1f}% "
                f"({unknown_count}/{total_count} placements) — exceeds 15% threshold"
            )

    # Duplicate tournaments (same name and date)
    dupes = conn.execute(
        "SELECT name, date, COUNT(*) as cnt FROM tournaments GROUP BY name, date HAVING cnt > 1"
    ).fetchall()
    for dupe in dupes:
        result.warnings.append(
            f"Duplicate tournament: '{dupe['name']}' on {dupe['date']} ({dupe['cnt']} entries)"
        )

    return result
