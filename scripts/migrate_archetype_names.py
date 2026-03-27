"""Build old->new archetype name mapping for Limitless-style naming.

Usage:
    python -m scripts.migrate_archetype_names [--dry-run] [--db PATH]
"""

import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.archetype import _COMPOSITE_SPRITE_FILENAMES, SPRITE_ARCHETYPE_MAP
from reports.json_export import _get_sprite_filenames


def limitless_name_from_filenames(png_filenames: list[str]) -> str:
    """Convert sprite filenames to Limitless-style archetype name.

    ['lucario-mega.png', 'hariyama.png'] -> 'Hariyama / Lucario-Mega'
    ['dragapult.png'] -> 'Dragapult'
    [] -> 'Unknown'
    """
    if not png_filenames:
        return "Unknown"
    parts = []
    for fn in png_filenames:
        stem = fn.removesuffix(".png")
        titled = "-".join(p.capitalize() for p in stem.split("-"))
        parts.append(titled)
    parts.sort()
    if len(parts) > 1:
        return " / ".join(parts)
    return parts[0]


def build_migration_mapping() -> dict[str, str]:
    """Build old_name -> new_name mapping for all archetypes in SPRITE_ARCHETYPE_MAP.

    For merged names (multiple sprite keys -> same old name), picks the key with
    the most sprite components (most filenames).
    """
    mapping: dict[str, str] = {}

    # Group keys by old name
    name_to_keys: dict[str, list[str]] = defaultdict(list)
    for key, name in SPRITE_ARCHETYPE_MAP.items():
        name_to_keys[name].append(key)

    for old_name, keys in name_to_keys.items():
        # For merged names, pick the key with the most sprite components
        best_key = max(keys, key=lambda k: len(_COMPOSITE_SPRITE_FILENAMES.get(k, [k])))
        filenames = _COMPOSITE_SPRITE_FILENAMES.get(best_key, [best_key])
        png_fns = [f"{fn}.png" for fn in filenames]
        mapping[old_name] = limitless_name_from_filenames(png_fns)

    return mapping


def build_full_mapping(db_path: str) -> dict[str, str]:
    """Build mapping for ALL archetypes in a database.

    For mapped names: uses build_migration_mapping().
    For auto-derived names: uses _get_sprite_filenames() to reverse the name to
    filenames, then converts to Limitless style.
    'Unknown' stays 'Unknown'.
    """
    conn = sqlite3.connect(db_path)
    archetypes = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT archetype FROM placements ORDER BY archetype"
        ).fetchall()
    ]
    conn.close()

    base_mapping = build_migration_mapping()
    full: dict[str, str] = {}

    for old_name in archetypes:
        if old_name == "Unknown":
            full[old_name] = "Unknown"
        elif old_name in base_mapping:
            full[old_name] = base_mapping[old_name]
        else:
            # Auto-derived: reverse via _get_sprite_filenames
            sprite_fns = _get_sprite_filenames(old_name)
            if sprite_fns:
                full[old_name] = limitless_name_from_filenames(sprite_fns)
            else:
                full[old_name] = old_name  # Keep as-is

    return full


def apply_migration(db_path: str, dry_run: bool = True) -> None:
    """Apply archetype name migration to a database."""
    mapping = build_full_mapping(db_path)
    conn = sqlite3.connect(db_path)

    changes = {old: new for old, new in mapping.items() if old != new}
    print(f"Database: {db_path}")
    print(f"Total archetypes: {len(mapping)}, changing: {len(changes)}")

    for old_name, new_name in sorted(changes.items()):
        count = conn.execute(
            "SELECT COUNT(*) FROM placements WHERE archetype = ?", (old_name,)
        ).fetchone()[0]
        print(f"  {old_name:<40} -> {new_name:<40} ({count})")

        if not dry_run:
            conn.execute(
                "UPDATE placements SET archetype = ? WHERE archetype = ?",
                (new_name, old_name),
            )

    if not dry_run:
        conn.commit()
        print(f"\nApplied {len(changes)} renames.")
    else:
        print("\nDry run -- no changes applied. Use --apply to execute.")

    conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate archetype names to Limitless style")
    parser.add_argument("--db", default="data/scout.db", help="Database path")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry run)")
    args = parser.parse_args()

    apply_migration(args.db, dry_run=not args.apply)
