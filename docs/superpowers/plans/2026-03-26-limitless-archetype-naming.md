# Limitless Archetype Naming Alignment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align archetype naming with Limitless TCG conventions — each sprite combo gets a unique, Limitless-style name using the `"PokemonA / PokemonB"` format derived directly from sprite filenames.

**Architecture:** Replace the manual `SPRITE_ARCHETYPE_MAP` lookup with direct sprite-filename-based naming. The new `normalize_archetype()` extracts filenames from sprite URLs, title-cases them, sorts alphabetically, and joins with `" / "`. This makes names 1:1 with Limitless and makes sprite-filename reverse-lookup trivial (split on `" / "`). The migration renames all 268 archetypes in both databases using the existing `_get_sprite_filenames()` reverse-lookup, then re-derives names.

**Tech Stack:** Python 3.12, SQLite, pytest, Next.js 16 (static export)

**Scope:** Nihil Zero (scout.db) + Ninja Spinner (ninja-spinner.db). Does NOT include optimal-60 quality fixes (separate task).

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `analysis/archetype.py` | Modify | Core naming refactor — new `normalize_archetype()`, remove SPRITE_ARCHETYPE_MAP |
| `reports/json_export.py` | Modify | Simplify `_get_sprite_filenames()` for new naming format |
| `scripts/migrate_archetype_names.py` | Create | One-time DB migration script |
| `tests/test_archetype.py` | Modify | Update all test expectations for new naming |
| `tests/test_archetype_migration.py` | Create | Tests for migration mapping |
| `tests/test_export_completeness.py` | Modify | Update slug expectations |
| `tests/test_data_contracts.py` | Modify | Update archetype name expectations |

---

### Task 1: Write migration mapping function + tests

**Files:**
- Create: `scripts/migrate_archetype_names.py`
- Create: `tests/test_archetype_migration.py`
- Read: `analysis/archetype.py` (current SPRITE_ARCHETYPE_MAP)
- Read: `reports/json_export.py` (`_get_sprite_filenames`)

- [ ] **Step 1: Write the failing test for the mapping function**

```python
# tests/test_archetype_migration.py
"""Tests for archetype name migration mapping."""
import pytest
from scripts.migrate_archetype_names import build_migration_mapping, limitless_name_from_filenames


class TestLimitlessNameFromFilenames:
    def test_single_pokemon(self):
        assert limitless_name_from_filenames(["dragapult.png"]) == "Dragapult"

    def test_two_pokemon_alphabetical(self):
        assert limitless_name_from_filenames(["dusknoir.png", "dragapult.png"]) == "Dragapult / Dusknoir"

    def test_mega_pokemon(self):
        assert limitless_name_from_filenames(["lucario-mega.png"]) == "Lucario-Mega"

    def test_mega_combo(self):
        assert limitless_name_from_filenames(["hariyama.png", "lucario-mega.png"]) == "Hariyama / Lucario-Mega"

    def test_double_mega(self):
        assert limitless_name_from_filenames(["froslass-mega.png", "starmie-mega.png"]) == "Froslass-Mega / Starmie-Mega"

    def test_hyphenated_pokemon(self):
        assert limitless_name_from_filenames(["raging-bolt.png"]) == "Raging-Bolt"

    def test_hyphenated_combo(self):
        assert limitless_name_from_filenames(["ogerpon.png", "raging-bolt.png"]) == "Ogerpon / Raging-Bolt"

    def test_form_variant(self):
        assert limitless_name_from_filenames(["noctowl.png", "ogerpon-wellspring.png"]) == "Noctowl / Ogerpon-Wellspring"


class TestBuildMigrationMapping:
    def test_returns_dict(self):
        mapping = build_migration_mapping()
        assert isinstance(mapping, dict)
        assert len(mapping) > 0

    def test_known_renames(self):
        mapping = build_migration_mapping()
        assert mapping["Mega Lucario"] == "Hariyama / Lucario-Mega"
        assert mapping["Dragapult Dusknoir"] == "Dragapult / Dusknoir"
        assert mapping["Dragapult ex"] == "Dragapult"
        assert mapping["Raging Bolt ex"] == "Ogerpon / Raging-Bolt"
        assert mapping["Mega Venusaur"] == "Ogerpon / Venusaur-Mega"
        assert mapping["Mega Meganium"] == "Meganium-Mega / Ogerpon"
        assert mapping["Tera Box"] == "Noctowl / Ogerpon-Wellspring"
        assert mapping["Mega Absol Box"] == "Absol-Mega / Kangaskhan-Mega"
        assert mapping["Zoroark ex"] == "Zoroark"
        assert mapping["Archaludon ex"] == "Archaludon"

    def test_auto_derived_renames(self):
        mapping = build_migration_mapping()
        assert mapping["Alakazam Dudunsparce"] == "Alakazam / Dudunsparce"
        assert mapping["Garchomp Roserade"] == "Garchomp / Roserade"
        assert mapping["Clefairy Ogerpon"] == "Clefairy / Ogerpon"

    def test_unknown_preserved(self):
        mapping = build_migration_mapping()
        assert mapping["Unknown"] == "Unknown"

    def test_no_collisions(self):
        mapping = build_migration_mapping()
        new_names = list(mapping.values())
        # Exclude "Unknown" from collision check
        non_unknown = [n for n in new_names if n != "Unknown"]
        assert len(non_unknown) == len(set(non_unknown)), "Collision detected in new names"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_archetype_migration.py -v`
Expected: FAIL — module `scripts.migrate_archetype_names` not found

- [ ] **Step 3: Write the migration mapping module**

```python
# scripts/migrate_archetype_names.py
"""Build old->new archetype name mapping for Limitless-style naming.

Usage:
    python -m scripts.migrate_archetype_names [--dry-run] [--db PATH]
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.archetype import SPRITE_ARCHETYPE_MAP, _COMPOSITE_SPRITE_FILENAMES
from reports.json_export import _get_sprite_filenames


def limitless_name_from_filenames(png_filenames: list[str]) -> str:
    """Convert sprite filenames to Limitless-style archetype name.

    ['lucario-mega.png', 'hariyama.png'] -> 'Hariyama / Lucario-Mega'
    ['dragapult.png'] -> 'Dragapult'
    """
    parts = []
    for fn in png_filenames:
        stem = fn.removesuffix(".png")
        titled = "-".join(p.capitalize() for p in stem.split("-"))
        parts.append(titled)
    parts.sort()
    if len(parts) > 1:
        return " / ".join(parts)
    return parts[0] if parts else "Unknown"


def build_migration_mapping() -> dict[str, str]:
    """Build complete old_name -> new_name mapping for all archetypes."""
    mapping: dict[str, str] = {}

    # Collect all archetype names from SPRITE_ARCHETYPE_MAP
    mapped_names = set(SPRITE_ARCHETYPE_MAP.values())

    # For mapped names: use known sprite key -> filenames -> new name
    # Handle merges (multiple keys -> same old name) by picking the
    # most specific key (most filenames).
    from collections import defaultdict

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
    """Build mapping for all archetypes in a database."""
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
        print(f"\nDry run — no changes applied. Use --apply to execute.")

    conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate archetype names to Limitless style")
    parser.add_argument("--db", default="data/scout.db", help="Database path")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry run)")
    args = parser.parse_args()

    apply_migration(args.db, dry_run=not args.apply)
```

- [ ] **Step 4: Create `scripts/__init__.py` if missing**

```bash
touch scripts/__init__.py
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_archetype_migration.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run dry run on both databases to verify mapping**

```bash
python -m scripts.migrate_archetype_names --db data/scout.db
python -m scripts.migrate_archetype_names --db data/ninja-spinner.db
```

Expected: See rename preview with no collisions, all 257+ names change.

- [ ] **Step 7: Commit**

```bash
git add scripts/migrate_archetype_names.py scripts/__init__.py tests/test_archetype_migration.py
git commit -m "feat: add archetype name migration script for Limitless alignment"
```

---

### Task 2: Handle Mega Venusaur Meganium re-split

The earlier merge (Task from previous conversation turn) needs to be undone since the two variants have different sprites on Limitless.

**Files:**
- Modify: `data/scout.db` (placements table)

- [ ] **Step 1: Re-split using decklist analysis**

```bash
sqlite3 data/scout.db "
-- 34 placements have Mega Meganium ex -> Meganium-Mega / Venusaur-Mega
-- 2 placements have regular Meganium only -> Meganium / Venusaur-Mega
UPDATE placements SET archetype = 'Meganium-Mega / Venusaur-Mega'
WHERE archetype = 'Mega Venusaur Meganium'
  AND id IN (
    SELECT DISTINCT p.id FROM placements p
    JOIN decklist_cards dc ON dc.placement_id = p.id
    WHERE p.archetype = 'Mega Venusaur Meganium'
      AND dc.card_name LIKE '%Mega Meganium%'
  );

UPDATE placements SET archetype = 'Meganium / Venusaur-Mega'
WHERE archetype = 'Mega Venusaur Meganium';
"
```

- [ ] **Step 2: Verify the split**

```bash
sqlite3 data/scout.db "
SELECT archetype, COUNT(*) FROM placements
WHERE archetype LIKE '%Meganium%Venusaur%' OR archetype LIKE '%Venusaur%Meganium%'
GROUP BY archetype;
"
```

Expected:
```
Meganium-Mega / Venusaur-Mega|34
Meganium / Venusaur-Mega|2
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "fix: re-split Mega Venusaur Meganium into Limitless sprite variants"
```

---

### Task 3: Apply full migration to both databases

**Files:**
- Modify: `data/scout.db`
- Modify: `data/ninja-spinner.db`

- [ ] **Step 1: Apply migration to scout.db**

```bash
python -m scripts.migrate_archetype_names --db data/scout.db --apply
```

Expected: ~255 renames applied (Mega Venusaur Meganium variants already done in Task 2).

- [ ] **Step 2: Verify scout.db migration**

```bash
sqlite3 data/scout.db "SELECT archetype FROM placements WHERE archetype NOT LIKE '%/%' AND archetype != 'Unknown' ORDER BY archetype LIMIT 20;"
```

Expected: Only single-sprite archetypes remain without `/` (e.g., `Archaludon`, `Ceruledge`, `Dragapult`, `Zoroark`).

- [ ] **Step 3: Apply migration to ninja-spinner.db**

```bash
python -m scripts.migrate_archetype_names --db data/ninja-spinner.db --apply
```

- [ ] **Step 4: Commit**

```bash
git add data/scout.db data/ninja-spinner.db
git commit -m "data: migrate archetype names to Limitless naming convention"
```

---

### Task 4: Refactor `normalize_archetype()` for Limitless-style naming

**Files:**
- Modify: `analysis/archetype.py`
- Modify: `tests/test_archetype.py`

- [ ] **Step 1: Write failing tests for new naming behavior**

Replace the existing test expectations in `tests/test_archetype.py`:

```python
# tests/test_archetype.py — updated test expectations

class TestNormalizeArchetype:
    """Test the full normalize_archetype pipeline with Limitless-style output."""

    def test_single_sprite(self):
        urls = ["https://r2.limitlesstcg.net/pokemon/gen9/dragapult.png"]
        assert normalize_archetype(urls) == "Dragapult"

    def test_two_sprites_alphabetical(self):
        urls = [
            "https://r2.limitlesstcg.net/pokemon/gen9/dusknoir.png",
            "https://r2.limitlesstcg.net/pokemon/gen9/dragapult.png",
        ]
        assert normalize_archetype(urls) == "Dragapult / Dusknoir"

    def test_mega_sprite(self):
        urls = ["https://r2.limitlesstcg.net/pokemon/gen9/lucario-mega.png"]
        assert normalize_archetype(urls) == "Lucario-Mega"

    def test_mega_combo(self):
        urls = [
            "https://r2.limitlesstcg.net/pokemon/gen9/hariyama.png",
            "https://r2.limitlesstcg.net/pokemon/gen9/lucario-mega.png",
        ]
        assert normalize_archetype(urls) == "Hariyama / Lucario-Mega"

    def test_double_mega(self):
        urls = [
            "https://r2.limitlesstcg.net/pokemon/gen9/starmie-mega.png",
            "https://r2.limitlesstcg.net/pokemon/gen9/froslass-mega.png",
        ]
        assert normalize_archetype(urls) == "Froslass-Mega / Starmie-Mega"

    def test_hyphenated_pokemon(self):
        urls = ["https://r2.limitlesstcg.net/pokemon/gen9/raging-bolt.png"]
        assert normalize_archetype(urls) == "Raging-Bolt"

    def test_hyphenated_combo(self):
        urls = [
            "https://r2.limitlesstcg.net/pokemon/gen9/ogerpon.png",
            "https://r2.limitlesstcg.net/pokemon/gen9/raging-bolt.png",
        ]
        assert normalize_archetype(urls) == "Ogerpon / Raging-Bolt"

    def test_underscore_in_url(self):
        urls = ["https://r2.limitlesstcg.net/pokemon/gen9/Iron_Hands.png"]
        assert normalize_archetype(urls) == "Iron-Hands"

    def test_html_fallback(self):
        assert normalize_archetype([], html_archetype="Custom Deck") == "Custom Deck"

    def test_unknown_fallback(self):
        assert normalize_archetype([]) == "Unknown"

    def test_empty_urls_with_html(self):
        assert normalize_archetype([], html_archetype="  Rogue  ") == "Rogue"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_archetype.py::TestNormalizeArchetype -v`
Expected: FAIL — old naming produces "Dragapult ex" instead of "Dragapult", etc.

- [ ] **Step 3: Rewrite `normalize_archetype()` and simplify archetype.py**

Replace the core of `analysis/archetype.py`:

```python
"""Limitless-style archetype normalizer.

Produces archetype names directly from sprite URLs, matching Limitless TCG
conventions: "PokemonA / PokemonB" with title-cased filenames sorted
alphabetically.
"""

import re

LIMITLESS_SPRITE_CDN = "https://r2.limitlesstcg.net/pokemon/gen9"

_FILENAME_RE = re.compile(r"/([a-zA-Z0-9_-]+)\.png")


def build_sprite_key(sprite_urls: list[str]) -> str:
    """Build a canonical sprite key from image URLs.

    Extracts filename stems, lowercases, sorts alphabetically, joins with hyphens.
    """
    names: list[str] = []
    for url in sprite_urls:
        match = _FILENAME_RE.search(url)
        if match:
            name = match.group(1).lower().replace("_", "-")
            names.append(name)
    names.sort()
    return "-".join(names)


def normalize_archetype(sprite_urls: list[str], html_archetype: str = "") -> str:
    """Resolve archetype name from sprite URLs with optional HTML text fallback.

    Produces Limitless-style names: "PokemonA / PokemonB" from sprite filenames,
    sorted alphabetically. Single sprites produce just "Pokemon".
    """
    if sprite_urls:
        filenames: list[str] = []
        for url in sprite_urls:
            match = _FILENAME_RE.search(url)
            if match:
                name = match.group(1).lower().replace("_", "-")
                filenames.append(name)
        if filenames:
            filenames.sort()
            parts = [
                "-".join(p.capitalize() for p in fn.split("-"))
                for fn in filenames
            ]
            return " / ".join(parts) if len(parts) > 1 else parts[0]

    if html_archetype and html_archetype.strip():
        return html_archetype.strip()

    return "Unknown"
```

Keep `build_sprite_key()` (still used for dedup/comparison), remove:
- `SPRITE_ARCHETYPE_MAP`
- `_COMPOSITE_SPRITE_FILENAMES`
- `_sprite_key_to_filenames()`
- `_split_mega_aware()`
- `_derive_name_from_key()`

Preserve `classify_from_decklist()` and `classify_jp_decklist()` if they exist — update their return values to use Limitless-style names by calling a shared helper.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_archetype.py -v`
Expected: All new tests PASS

- [ ] **Step 5: Commit**

```bash
git add analysis/archetype.py tests/test_archetype.py
git commit -m "refactor: simplify normalize_archetype to produce Limitless-style names"
```

---

### Task 5: Simplify `_get_sprite_filenames()` in export

**Files:**
- Modify: `reports/json_export.py`
- Modify: `tests/test_data_contracts.py` (if sprite filename tests exist)

- [ ] **Step 1: Rewrite `_get_sprite_filenames()`**

With the new naming format, reverse-lookup is trivial:

```python
def _get_sprite_filenames(archetype_name: str) -> list[str]:
    """Get sprite filenames from a Limitless-style archetype name.

    "Hariyama / Lucario-Mega" -> ["hariyama.png", "lucario-mega.png"]
    "Dragapult" -> ["dragapult.png"]
    """
    if not archetype_name or archetype_name == "Unknown":
        return []
    if " / " in archetype_name:
        parts = archetype_name.split(" / ")
        return [f"{p.lower()}.png" for p in parts]
    return [f"{archetype_name.lower()}.png"]
```

- [ ] **Step 2: Run all Python tests**

Run: `python -m pytest tests/ -v`
Expected: PASS (may need to update test expectations for new archetype names in various test files)

- [ ] **Step 3: Fix any failing tests**

Update hardcoded archetype name expectations in:
- `tests/test_data_contracts.py`
- `tests/test_export_completeness.py`
- `tests/test_meta.py`
- Any other test files with archetype name assertions

The pattern: replace old names with Limitless-style names in all test fixtures and assertions.

- [ ] **Step 4: Commit**

```bash
git add reports/json_export.py tests/
git commit -m "refactor: simplify sprite filename lookup for Limitless-style names"
```

---

### Task 6: Update `classify_from_decklist()` and anchor card config

The decklist-based classifier in `config.py` (`ARCHETYPE_ANCHOR_CARDS`) and `analysis/archetype.py` (`classify_from_decklist`) returns old-style names. Update to return Limitless-style names.

**Files:**
- Modify: `config.py` (ARCHETYPE_ANCHOR_CARDS values)
- Modify: `analysis/archetype.py` (`classify_from_decklist`, `classify_jp_decklist`)

- [ ] **Step 1: Update ARCHETYPE_ANCHOR_CARDS in config.py**

Change all archetype name values to Limitless-style:

```python
# Example changes in ARCHETYPE_ANCHOR_CARDS:
# Old: "Charizard ex": {"Pidgeot ex": "Charizard ex", "_default": "Charizard ex"}
# New: "Charizard ex": {"Pidgeot ex": "Charizard / Pidgeot", "_default": "Charizard"}
```

Go through every entry and update the archetype name values. Keep card names as-is (those are card names, not archetype names).

- [ ] **Step 2: Update classify functions**

Ensure `classify_from_decklist()` and `classify_jp_decklist()` return Limitless-style names. If they reference `SPRITE_ARCHETYPE_MAP` (now removed), update to use the new naming directly.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add config.py analysis/archetype.py
git commit -m "refactor: update decklist classifier to return Limitless-style archetype names"
```

---

### Task 7: Recompute meta snapshots + re-export

**Files:**
- Modify: `data/scout.db` (meta_snapshots, archetype_stats)
- Modify: `web/public/data/` (all exported JSON)

- [ ] **Step 1: Recompute meta for nihil-zero**

```bash
python cli.py --format nihil-zero meta
```

- [ ] **Step 2: Re-export nihil-zero web data**

```bash
python cli.py --format nihil-zero export-web
```

- [ ] **Step 3: Clean up stale archetype JSON files**

The export creates new files with new slugs but doesn't remove old ones. Remove stale files:

```bash
# List files in archetypes dir that don't match any archetype in the latest export
python3 -c "
import json, os
meta = json.load(open('web/public/data/nihil-zero/meta.json'))
valid_slugs = {a['slug'] for a in meta['archetypes']}
arch_dir = 'web/public/data/nihil-zero/archetypes'
for f in os.listdir(arch_dir):
    slug = f.removesuffix('.json')
    if slug not in valid_slugs and slug != 'index':
        print(f'Removing stale: {f}')
        os.remove(os.path.join(arch_dir, f))
"
```

Do the same for `archetype-reports/`, `optimal-60/`, and `trends/` directories.

- [ ] **Step 4: Recompute + re-export ninja-spinner**

```bash
python cli.py --format ninja-spinner meta
python cli.py --format ninja-spinner export-web
```

Clean up stale files for ninja-spinner too.

- [ ] **Step 5: Verify exported data**

```bash
python3 -c "
import json
meta = json.load(open('web/public/data/nihil-zero/meta.json'))
# Check top archetype has Limitless-style name
top = meta['archetypes'][0]
print(f'Top archetype: {top[\"archetype\"]} (slug: {top[\"slug\"]})')
print(f'Sprites: {top.get(\"sprite_filenames\", [])}')
assert '/' in top['archetype'] or top['archetype'][0].isupper()
# Check a known rename
venusaur = [a for a in meta['archetypes'] if 'Venusaur' in a['archetype']]
for v in venusaur:
    print(f'{v[\"archetype\"]}: {v[\"deck_count\"]} decks, slug={v[\"slug\"]}')
"
```

- [ ] **Step 6: Commit**

```bash
git add data/ web/public/data/
git commit -m "data: recompute meta and re-export with Limitless archetype names"
```

---

### Task 8: Run frontend tests + fix

**Files:**
- Modify: various `tests/` and `web/` test files

- [ ] **Step 1: Run frontend tests**

```bash
cd web && npm test
```

- [ ] **Step 2: Fix any failures**

Update hardcoded archetype slugs/names in:
- `web/app/__tests__/` files
- Any component test fixtures

The slug format changes significantly:
- `mega-lucario` → `hariyama-lucario-mega`
- `dragapult-ex` → `dragapult`
- `mega-venusaur` → `ogerpon-venusaur-mega`

- [ ] **Step 3: Run full test suite**

```bash
python -m pytest tests/ -v && cd web && npm test
```

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "test: update test expectations for Limitless archetype naming"
```

---

### Task 9: End-to-end verification

- [ ] **Step 1: Verify slug consistency**

```bash
python3 -c "
import json, re
meta = json.load(open('web/public/data/nihil-zero/meta.json'))
for a in meta['archetypes']:
    name = a['archetype']
    slug = a['slug']
    # Verify slug matches what _slugify would produce
    expected_slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    assert slug == expected_slug, f'Slug mismatch: {name} -> {slug} (expected {expected_slug})'
print(f'All {len(meta[\"archetypes\"])} slugs consistent')
"
```

- [ ] **Step 2: Verify sprite filenames in export**

```bash
python3 -c "
import json
meta = json.load(open('web/public/data/nihil-zero/meta.json'))
for a in meta['archetypes']:
    name = a['archetype']
    sprites = a.get('sprite_filenames', [])
    if ' / ' in name:
        parts = name.split(' / ')
        expected = sorted([p.lower() + '.png' for p in parts])
        actual = sorted(sprites)
        assert actual == expected, f'{name}: expected {expected}, got {actual}'
    elif name != 'Unknown':
        assert sprites == [name.lower() + '.png'], f'{name}: expected [{name.lower()}.png], got {sprites}'
print('All sprite filenames correct')
"
```

- [ ] **Step 3: Spot-check detail pages**

```bash
python3 -c "
import json
# Check a few specific archetype detail files
for slug in ['hariyama-lucario-mega', 'dragapult-dusknoir', 'ogerpon-venusaur-mega']:
    d = json.load(open(f'web/public/data/nihil-zero/archetypes/{slug}.json'))
    print(f'{d[\"archetype\"]}: {d[\"deck_count\"]} decks, best={d[\"best_placement\"]}')
"
```

Expected:
```
Hariyama / Lucario-Mega: 611 decks, best=1
Dragapult / Dusknoir: 608 decks, best=1
Ogerpon / Venusaur-Mega: 214 decks, best=1
```

- [ ] **Step 4: Build Next.js to verify static generation**

```bash
cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npm run build
```

Expected: Build succeeds, generates pages for all archetypes with new slugs.

- [ ] **Step 5: Final commit if any cleanup needed**

```bash
git add -A && git commit -m "chore: verification cleanup for Limitless naming migration"
```
