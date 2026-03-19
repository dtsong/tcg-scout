# Champions League Page Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add English translations, card images, and archetype detection to the Champions League page.

**Architecture:** Populate the existing `card_mappings` table via the Limitless scraper, use those mappings to translate CL decklists JP->EN, then classify each placement's archetype via `classify_decklist()`. Enrich the CL JSON export with archetype, tier, sprite filenames, and card image URLs. Update the frontend with an archetype summary bar, archetype column, and card image grid.

**Tech Stack:** Python 3.12+, SQLite, Next.js, Tailwind CSS, existing Limitless scraper infrastructure

---

### Task 1: Populate card_mappings and integrate into CL export

**Files:**
- Modify: `reports/json_export.py` (export_champions_league function, ~line 1648)
- Modify: `reports/json_export.py` (_build_jp_en_lookup function, ~line 1636)

**Context:**
- `scraper/card_mappings.py` has `sync_card_mappings()` to scrape Limitless JP-EN mappings
- `card_mappings` table exists in schema (`db.py:68`) but has no data
- `_build_jp_en_lookup()` currently only uses `JP_CARD_NAMES` dict + `cards` table
- CL cards have `set_code` column that maps to JP set codes used in `card_mappings`

- [ ] **Step 1: Run sync_card_mappings to populate the mappings table**

This is a one-time CLI operation. The `card_mappings` table must have data before the export can use it.

```bash
python -c "
from db import get_format_connection
from scraper.card_mappings import sync_card_mappings
conn = get_format_connection('nihil-zero')
sync_card_mappings(conn)
conn.close()
"
```

Expected: Populates `card_mappings` with JP-EN name pairs scraped from Limitless.

- [ ] **Step 2: Verify mappings cover CL cards**

```bash
python -c "
import sqlite3
db = sqlite3.connect('data/nihil-zero.db')
db.row_factory = sqlite3.Row
total = db.execute('SELECT COUNT(*) FROM card_mappings').fetchone()[0]
print(f'Total mappings: {total}')
# Check coverage of CL untranslated cards
matched = db.execute('''
    SELECT COUNT(DISTINCT cl.card_name_jp)
    FROM cl_decklist_cards cl
    JOIN card_mappings cm ON cm.card_name_jp = cl.card_name_jp
    WHERE cl.card_name_en IS NULL
''').fetchone()[0]
unmatched = db.execute('''
    SELECT COUNT(DISTINCT cl.card_name_jp)
    FROM cl_decklist_cards cl
    WHERE cl.card_name_en IS NULL
    AND NOT EXISTS (SELECT 1 FROM card_mappings cm WHERE cm.card_name_jp = cl.card_name_jp)
''').fetchone()[0]
print(f'CL cards matched via card_mappings: {matched}')
print(f'CL cards still unmatched: {unmatched}')
db.close()
"
```

Expected: High match rate. Note any remaining unmatched cards -- they'll fall back to `JP_CARD_NAMES` dict or show as JP.

- [ ] **Step 3: Update _build_jp_en_lookup to include card_mappings**

In `reports/json_export.py`, modify `_build_jp_en_lookup()` to also query `card_mappings`:

```python
def _build_jp_en_lookup(conn: sqlite3.Connection) -> dict[str, str]:
    """Build a comprehensive JP-to-EN card name lookup."""
    lookup = dict(JP_CARD_NAMES)

    # From cards table (name_jp -> name_en)
    for row in conn.execute(
        "SELECT name_jp, name_en FROM cards WHERE name_jp IS NOT NULL AND name_jp != ''"
    ):
        lookup[row["name_jp"]] = row["name_en"]

    # From card_mappings table (scraped from Limitless)
    try:
        for row in conn.execute(
            "SELECT card_name_jp, card_name_en FROM card_mappings "
            "WHERE card_name_jp IS NOT NULL AND card_name_en IS NOT NULL"
        ):
            lookup[row["card_name_jp"]] = row["card_name_en"]
    except Exception:
        pass  # Table may not exist in test DBs

    logger.info("JP-EN lookup: %d entries", len(lookup))
    return lookup
```

- [ ] **Step 4: Write test for updated _build_jp_en_lookup**

In `tests/test_json_export.py`, add a test:

```python
class TestBuildJpEnLookupWithMappings:
    def test_includes_card_mappings(self, db):
        # Create card_mappings table and insert a test mapping
        db.execute("""
            CREATE TABLE IF NOT EXISTS card_mappings (
                jp_card_id TEXT PRIMARY KEY,
                en_card_id TEXT NOT NULL,
                card_name_jp TEXT,
                card_name_en TEXT,
                jp_set_id TEXT,
                en_set_id TEXT
            )
        """)
        db.execute(
            "INSERT INTO card_mappings VALUES (?, ?, ?, ?, ?, ?)",
            ("SV8a-221", "me02.5-100", "ドラパルトex", "Dragapult ex", "SV8a", "me02.5"),
        )
        db.commit()
        lookup = _build_jp_en_lookup(db)
        assert lookup["ドラパルトex"] == "Dragapult ex"
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_json_export.py -v -k "test_includes_card_mappings"
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add reports/json_export.py tests/test_json_export.py
git commit -m "feat: integrate card_mappings into JP-EN lookup for CL translations"
```

---

### Task 2: Add archetype inference and enriched CL export

**Files:**
- Modify: `reports/json_export.py` (export_champions_league function)
- Create: `tests/test_cl_archetype.py`

**Context:**
- `classify_decklist(cards)` in `analysis/archetype_classifier.py` takes `[{card_name, count, category}]` and returns archetype name or "Unknown"
- `_get_sprite_filenames(archetype_name)` returns sprite filenames for an archetype
- `archetype_stats` table has tier data per archetype
- `cards` table has `image_url` for EN card names
- CL decklist cards have `card_name_jp`, `card_name_en` (after translation), `count`, `category`

- [ ] **Step 1: Write test for CL archetype inference**

Create `tests/test_cl_archetype.py`:

```python
"""Tests for CL archetype inference via classify_decklist."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.archetype_classifier import classify_decklist


class TestCLArchetypeInference:
    def test_dragapult_dusknoir(self):
        cards = [
            {"card_name": "Dragapult ex", "count": 2, "category": "Pokemon"},
            {"card_name": "Drakloak", "count": 2, "category": "Pokemon"},
            {"card_name": "Dreepy", "count": 4, "category": "Pokemon"},
            {"card_name": "Dusknoir", "count": 1, "category": "Pokemon"},
            {"card_name": "Dusclops", "count": 1, "category": "Pokemon"},
            {"card_name": "Duskull", "count": 2, "category": "Pokemon"},
            {"card_name": "Nest Ball", "count": 4, "category": "Trainer"},
        ]
        assert classify_decklist(cards) == "Dragapult Dusknoir"

    def test_unknown_archetype(self):
        cards = [
            {"card_name": "Pikachu", "count": 4, "category": "Pokemon"},
            {"card_name": "Raichu", "count": 2, "category": "Pokemon"},
        ]
        assert classify_decklist(cards) == "Unknown"

    def test_empty_decklist(self):
        assert classify_decklist([]) == "Unknown"
```

- [ ] **Step 2: Run test to verify it passes**

```bash
python -m pytest tests/test_cl_archetype.py -v
```

Expected: PASS (classify_decklist already exists)

- [ ] **Step 3: Modify export_champions_league to add archetype + image enrichment**

In `reports/json_export.py`, update `export_champions_league()`:

```python
def export_champions_league(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export Champions League data with archetype inference and card images."""
    from analysis.archetype_classifier import classify_decklist

    cl_dir = output_dir / "champions-league"
    cl_dir.mkdir(parents=True, exist_ok=True)

    lookup = _build_jp_en_lookup(conn)

    # Build EN name -> image_url lookup from cards table
    image_lookup: dict[str, str] = {}
    for row in conn.execute(
        "SELECT name_en, image_url FROM cards WHERE image_url IS NOT NULL ORDER BY set_code DESC"
    ):
        if row["name_en"] not in image_lookup:
            image_lookup[row["name_en"]] = row["image_url"]

    # Get tier data from latest snapshot
    tier_lookup: dict[str, str] = {}
    for row in conn.execute(
        """SELECT archetype, tier FROM archetype_stats
           WHERE snapshot_id = (SELECT MAX(id) FROM meta_snapshots)"""
    ):
        tier_lookup[row["archetype"]] = row["tier"]

    # Query CL events grouped by division
    events = conn.execute(
        "SELECT DISTINCT id, name, division, date FROM cl_events ORDER BY division"
    ).fetchall()

    for event in events:
        placements = conn.execute(
            """SELECT DISTINCT standing, player_name, region, deck_code
               FROM cl_placements WHERE event_id = ? ORDER BY standing""",
            (event["id"],),
        ).fetchall()

        placement_list = []
        for p in placements:
            # Fetch decklist
            cards_rows = conn.execute(
                """SELECT DISTINCT c.card_name_jp, c.card_name_en, c.count, c.category
                   FROM cl_placements cp
                   JOIN cl_decklist_cards c ON c.placement_id = cp.id
                   WHERE cp.event_id = ? AND cp.standing = ? AND cp.player_name = ?
                   ORDER BY c.category, c.card_name_jp""",
                (event["id"], p["standing"], p["player_name"]),
            ).fetchall()

            decklist = []
            classify_input = []
            for c in cards_rows:
                en_name = c["card_name_en"] or lookup.get(c["card_name_jp"])
                card_entry = {
                    "card_name_jp": c["card_name_jp"],
                    "card_name_en": en_name,
                    "count": c["count"],
                    "category": c["category"],
                    "image_url": image_lookup.get(en_name) if en_name else None,
                }
                decklist.append(card_entry)

                if en_name:
                    classify_input.append({
                        "card_name": en_name,
                        "count": c["count"],
                        "category": c["category"],
                    })

            # Classify archetype
            archetype = classify_decklist(classify_input)
            if archetype == "Unknown":
                archetype = None

            placement_entry = {
                "standing": p["standing"],
                "player_name": p["player_name"],
                "region": p["region"],
                "deck_code": p["deck_code"],
                "archetype": archetype,
                "tier": tier_lookup.get(archetype) if archetype else None,
                "sprite_filenames": _get_sprite_filenames(archetype) if archetype else None,
                "decklist": decklist,
            }
            placement_list.append(placement_entry)

        # Compute archetype summary
        arch_counts: dict[str, int] = {}
        arch_sprites: dict[str, list[str]] = {}
        for pl in placement_list:
            if pl["archetype"]:
                arch_counts[pl["archetype"]] = arch_counts.get(pl["archetype"], 0) + 1
                if pl["archetype"] not in arch_sprites:
                    arch_sprites[pl["archetype"]] = pl["sprite_filenames"] or []

        archetype_summary = sorted(
            [
                {
                    "archetype": name,
                    "count": count,
                    "sprite_filenames": arch_sprites.get(name, []),
                }
                for name, count in arch_counts.items()
            ],
            key=lambda x: x["count"],
            reverse=True,
        )

        division_data = {
            "event_id": event["id"],
            "event_name": event["name"],
            "division": event["division"],
            "date": event["date"],
            "archetype_summary": archetype_summary,
            "placements": placement_list,
        }

        _write_json(division_data, cl_dir / f"{event['division']}.json")

    logger.info("Exported Champions League data (%d divisions)", len(events))
```

- [ ] **Step 4: Write test for enriched CL export**

Add to `tests/test_json_export.py`:

```python
class TestExportChampionsLeagueEnriched:
    def test_placements_have_archetype_fields(self, db, tmp_path):
        export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        for p in data["placements"]:
            assert "archetype" in p
            assert "tier" in p
            assert "sprite_filenames" in p

    def test_decklist_cards_have_image_url(self, db, tmp_path):
        export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        p = data["placements"][0]
        for card in p["decklist"]:
            assert "image_url" in card

    def test_has_archetype_summary(self, db, tmp_path):
        export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        assert "archetype_summary" in data
        assert isinstance(data["archetype_summary"], list)
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_json_export.py -v -k "ChampionsLeagueEnriched or test_cl_archetype"
python -m pytest tests/test_cl_archetype.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add reports/json_export.py tests/test_json_export.py tests/test_cl_archetype.py
git commit -m "feat: add archetype inference, image URLs, and archetype summary to CL export"
```

---

### Task 3: Update TypeScript types

**Files:**
- Modify: `web/app/lib/types.ts`

- [ ] **Step 1: Update CL types**

```typescript
// Add CLArchetypeSummary after CLDivision
export interface CLArchetypeSummary {
  archetype: string;
  count: number;
  sprite_filenames?: string[];
}

// Update CLDecklistCard - add image_url
export interface CLDecklistCard {
  card_name_jp: string;
  card_name_en: string | null;
  count: number;
  category: string;
  image_url?: string | null;
}

// Update CLPlacement - add archetype fields
export interface CLPlacement {
  standing: number;
  player_name: string;
  region: string;
  deck_code: string;
  archetype?: string | null;
  tier?: Tier | null;
  sprite_filenames?: string[];
  decklist: CLDecklistCard[];
}

// Update CLDivision - add archetype_summary
export interface CLDivision {
  event_id: number;
  event_name: string;
  division: string;
  date: string;
  archetype_summary?: CLArchetypeSummary[];
  placements: CLPlacement[];
}
```

- [ ] **Step 2: Run typecheck**

```bash
cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add web/app/lib/types.ts
git commit -m "feat: update CL types with archetype, image_url, and summary fields"
```

---

### Task 4: Build the Champions League frontend

**Files:**
- Modify: `web/app/[format]/champions/champions-client.tsx`

**Context:**
- Existing `SpriteRow` component renders archetype sprites from filenames
- Existing `TierBadge` component renders tier badges (S/A/B/C/Rogue)
- Follow existing styling conventions (bg-surface-800, border-surface-600, etc.)

- [ ] **Step 1: Add archetype summary bar**

At the top of the component, after the division tabs, render the `archetype_summary` from the active division. Use `SpriteRow` for sprites and show counts.

- [ ] **Step 2: Add archetype column to placements table**

Add an "Archetype" column header and show the archetype name in each row. Show a dash for null archetypes.

- [ ] **Step 3: Replace text decklist with image grid**

In the expanded `PlacementRow`, replace the current text list with a responsive grid of card thumbnails. For each card:
- Show `image_url` as an `<img>` with a card-shaped fallback for missing images
- Show EN name (or JP fallback) below
- Show count

Group by category (Pokemon, Trainer, Energy) with category headers.

- [ ] **Step 4: Full component rewrite**

Replace `champions-client.tsx` with the updated version incorporating all three changes above. Import `SpriteRow` and `TierBadge`. Import new types `CLArchetypeSummary`.

Key implementation details:
- Summary bar: `division.archetype_summary?.map(...)` with `SpriteRow` + name + count
- Archetype column: Add `<th>` and `<td>` for archetype, hidden on mobile via `hidden sm:table-cell`
- Image grid: `grid grid-cols-4 sm:grid-cols-6 lg:grid-cols-8 gap-3` with card thumbnails
- Card image: `<img>` with `w-[72px] h-[100px] object-cover rounded` and `onError` fallback
- Fallback: card-shaped div with JP name in small text

- [ ] **Step 5: Run frontend tests and build**

```bash
cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npm test && npx next build
```

Expected: Tests pass, build succeeds

- [ ] **Step 6: Commit**

```bash
git add web/app/[format]/champions/champions-client.tsx
git commit -m "feat: add archetype summary, archetype column, and card image grid to CL page"
```

---

### Task 5: Re-export CL data with enrichments

**Files:**
- Modify: `web/public/data/nihil-zero/champions-league/*.json` (re-generated)

- [ ] **Step 1: Re-run CL export with enriched data**

```bash
python -c "
from db import get_format_connection
from reports.json_export import export_champions_league
from pathlib import Path
conn = get_format_connection('nihil-zero')
out = Path('web/public/data/nihil-zero')
export_champions_league(conn, out)
conn.close()
"
```

- [ ] **Step 2: Verify enriched JSON**

```bash
python -c "
import json
with open('web/public/data/nihil-zero/champions-league/masters.json') as f:
    data = json.load(f)
print(f'Archetype summary: {len(data.get(\"archetype_summary\", []))} entries')
p = data['placements'][0]
print(f'First placement archetype: {p.get(\"archetype\")}')
translated = sum(1 for c in p['decklist'] if c.get('card_name_en'))
with_images = sum(1 for c in p['decklist'] if c.get('image_url'))
total = len(p['decklist'])
print(f'Translation: {translated}/{total}, Images: {with_images}/{total}')
"
```

- [ ] **Step 3: Build and verify**

```bash
cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npx next build
```

- [ ] **Step 4: Commit**

```bash
git add web/public/data/nihil-zero/champions-league/
git commit -m "feat: re-export CL data with translations, archetypes, and image URLs"
```

---

### Task 6: Run full test suite and final verification

- [ ] **Step 1: Run all Python tests**

```bash
python -m pytest tests/ -v
```

Expected: All tests pass (168+ tests)

- [ ] **Step 2: Run all frontend tests**

```bash
cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npm test
```

Expected: All tests pass

- [ ] **Step 3: Verify dev server**

```bash
cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npx next dev &
# Open http://localhost:3000/nihil-zero/champions
# Verify: archetype summary bar, archetype column, card images in expanded decklist
```

- [ ] **Step 4: Final commit if any adjustments**

```bash
git add -A && git commit -m "fix: address final CL page adjustments"
```
