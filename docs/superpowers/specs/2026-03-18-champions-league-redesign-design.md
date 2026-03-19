# Champions League Page Redesign

**Date:** 2026-03-18
**Status:** Approved

## Goal

Improve the Champions League page (`/[format]/champions`) with English translations, card images, and archetype information visible at the top-level view.

## Current State

- CL placements show: standing, player name, region
- Expanded decklists show text-only card lists grouped by category
- Only 4% of CL card names have English translations
- No archetype data on CL placements
- No card images displayed

## Design

### Top-Level View: Summary Bar + Archetype Column

Above the placements table, add an archetype distribution bar showing each archetype with sprite icons and occurrence count (e.g., "Dragapult Dusknoir x4"). The placements table gains an archetype column showing the inferred archetype name per row.

### Expanded Decklist: Image Grid

When a row is expanded, show card thumbnails in a responsive grid grouped by Pokemon/Trainer/Energy. Each card shows: thumbnail image, EN name (or JP if untranslated), and copy count. Cards without images show a styled placeholder.

### Translation: tcgdex API + Hardcoded Fallback

At export time, fetch JP card data from the tcgdex API to build a comprehensive JP-EN name mapping. Populate the `cards` table with `name_jp` values. The existing `JP_CARD_NAMES` hardcoded dict in `json_export.py` serves as fallback for cards the API misses. Target: 90%+ translation coverage.

### Archetype Inference: Key Pokemon Matching

Extract Pokemon ex/V names from each CL decklist. Translate them to EN via the improved lookup. Match the combination against `SPRITE_ARCHETYPE_MAP` entries by generating a sprite key (sorted, hyphenated stems). Falls back to "Unknown" if no confident match. The inferred archetype name, tier, and sprite filenames are included in the CL JSON export.

## Data Flow

```
tcgdex API -> cards.name_jp (one-time populate)
                    |
CL decklist cards --+--> JP-EN translation --> archetype inference
                    |                               |
                    v                               v
            export_champions_league() -----> {division}.json
                                                    |
                                                    v
                                        Champions client component
                                        (summary bar, archetype col,
                                         image grid decklist)
```

## Schema Changes

### CL JSON Export Shape (per placement)

New fields added to each placement object:

```json
{
  "standing": 1,
  "player_name": "Taka",
  "region": "Aichi",
  "deck_code": "...",
  "archetype": "Dragapult Dusknoir",
  "tier": "A",
  "sprite_filenames": ["dragapult.png", "dusknoir.png"],
  "decklist": [
    {
      "card_name_jp": "ドラパルトex",
      "card_name_en": "Dragapult ex",
      "count": 2,
      "category": "Pokemon",
      "image_url": "https://assets.tcgdex.net/en/me/me02.5/123/high.png"
    }
  ]
}
```

New top-level field on division object:

```json
{
  "event_id": 903703,
  "event_name": "...",
  "event_name_en": "Champions League 2026 Fukuoka Masters Day2",
  "archetype_summary": [
    {
      "archetype": "Dragapult Dusknoir",
      "count": 4,
      "sprite_filenames": ["dragapult.png", "dusknoir.png"]
    }
  ],
  "placements": [...]
}
```

### TypeScript Type Changes

```typescript
// Updated CLDecklistCard
export interface CLDecklistCard {
  card_name_jp: string;
  card_name_en: string | null;
  count: number;
  category: string;
  image_url?: string | null;
}

// Updated CLPlacement
export interface CLPlacement {
  standing: number;
  player_name: string;
  region: string;
  deck_code: string;
  archetype?: string;
  tier?: Tier;
  sprite_filenames?: string[];
  decklist: CLDecklistCard[];
}

// New type for archetype summary
export interface CLArchetypeSummary {
  archetype: string;
  count: number;
  sprite_filenames?: string[];
}

// Updated CLDivision
export interface CLDivision {
  event_id: number;
  event_name: string;
  event_name_en?: string;
  division: string;
  date: string;
  archetype_summary?: CLArchetypeSummary[];
  placements: CLPlacement[];
}
```

All new fields are optional for backward compatibility.

## Backend Changes

### 1. tcgdex JP Card Fetcher

New function to populate `cards.name_jp` from the tcgdex JP API. Fetches card data for current rotation sets, maps JP names to existing EN card records. Run once during data pipeline, results cached in DB.

### 2. CL Archetype Inference

New function in `analysis/` or within `json_export.py`:

1. For each CL placement, get the decklist Pokemon cards
2. Translate JP names to EN using the improved lookup
3. Generate a sprite key from the EN Pokemon names (lowercase stems, sorted, hyphenated)
4. Look up the sprite key in `SPRITE_ARCHETYPE_MAP`
5. If matched, attach archetype name, tier (from latest `archetype_stats`), and sprite filenames
6. If no match, set archetype to null

### 3. Image URL Resolution

During CL export, for each translated card name, look up the `image_url` from the `cards` table. Attach to the exported decklist card object.

## Frontend Changes

### Champions Client Component

1. **Archetype summary bar** - Renders `archetype_summary` from division data. Shows sprite icons + archetype name + count for each archetype present.

2. **Archetype column** - Added to the placements table. Shows archetype name per row. Rows with unknown archetype show a dash.

3. **Image grid decklist** - Replaces the current text list when expanded. Responsive grid of card thumbnails grouped by category. Card image loaded from `image_url`, with a styled fallback for missing images. EN name and count displayed below each thumbnail.

## Testing

- Python: test archetype inference with known decklists, test JP-EN lookup coverage, test image URL resolution
- Frontend: test summary bar rendering, test image grid with missing images, test unknown archetype display
