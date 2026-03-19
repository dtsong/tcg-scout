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

At export time, fetch JP card data from the tcgdex API to build a comprehensive JP-EN name mapping. Populate the `cards` table `name_jp` column (already exists, currently null). The existing `JP_CARD_NAMES` hardcoded dict in `json_export.py` serves as fallback for cards the API misses. Target: 90%+ translation coverage.

**API details:**
- Base URL: `https://api.tcgdex.net/v2/jp/sets/{set_id}` to list cards per set
- Card detail: `https://api.tcgdex.net/v2/jp/cards/{card_id}` for JP name
- Fetch only rotation-legal sets (filtered by `rotation_legal=1` in cards table)
- Rate limit: 1 request/second with retry on 429
- Error handling: log failures, skip unavailable sets, continue pipeline
- Run as a CLI step before export (`python cli.py fetch-jp-names`)

### Archetype Inference: classify_decklist

Reuse the existing `classify_decklist()` from `analysis/archetype_classifier.py` which matches decklist Pokemon cards against `ARCHETYPE_ANCHOR_CARDS` from config. This function accepts a list of dicts with `card_name`, `count`, `category` keys and returns an archetype name or "Unknown".

For CL decklists:
1. Translate each card's JP name to EN using the improved lookup
2. Build the cards list with `card_name` (EN), `count`, and `category` keys
3. Call `classify_decklist(cards)` to get the archetype name
4. Look up tier from `archetype_stats` for the matched archetype. If the archetype has no entry in `archetype_stats`, set tier to null.
5. Look up sprite filenames via `_get_sprite_filenames()` from json_export.py
6. If `classify_decklist` returns "Unknown", set archetype/tier/sprites to null

### Archetype Summary Aggregation

Group placements by inferred archetype, count occurrences, sort by count descending. Exclude "Unknown" from the summary. Include archetypes with count >= 1.

## Data Flow

```
tcgdex API -> cards.name_jp (one-time populate)
                    |
CL decklist cards --+--> JP-EN translation --> classify_decklist()
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

New top-level fields on division object:

```json
{
  "event_id": 903703,
  "event_name": "チャンピオンズリーグ2026 福岡 マスターリーグDay2",
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

Note: `event_name` remains in Japanese (from `cl_events.name`). No `event_name_en` field -- the page header already displays "Champions League" in English.

### Image URL Resolution

Join `cl_decklist_cards.card_name_en` (after translation) to `cards.name_en` to get `cards.image_url`. When multiple cards share the same name (reprints), take the first match ordered by set recency (`set_code` descending). Cards with no EN translation or no matching `cards` row get `image_url: null`.

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
  archetype?: string | null;
  tier?: Tier | null;
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
  division: string;
  date: string;
  archetype_summary?: CLArchetypeSummary[];
  placements: CLPlacement[];
}
```

All new fields are optional for backward compatibility.

## Backend Changes

### 1. tcgdex JP Card Fetcher

New function `fetch_jp_card_names(conn)` to populate `cards.name_jp`:
1. Query `SELECT DISTINCT set_code FROM cards WHERE rotation_legal = 1` to get target sets
2. For each set, fetch `https://api.tcgdex.net/v2/jp/sets/{set_code}` to get JP card list
3. Match JP cards to EN cards by set_code + set_number
4. Update `cards.name_jp` for matched records
5. Log match rate per set

Run as a CLI command before export. Results persist in DB -- only fetches sets where `name_jp` is still null.

### 2. CL Export Enhancement

Modify `export_champions_league()` in `json_export.py`:
1. Build JP-EN lookup (existing `_build_jp_en_lookup` + new `cards.name_jp` data)
2. Build EN-to-image-URL lookup from `cards` table
3. For each placement:
   a. Translate all card names JP -> EN
   b. Attach `image_url` for each card via EN name lookup
   c. Build a cards list for `classify_decklist()` and call it
   d. Look up tier from `archetype_stats` (null if not found)
   e. Look up sprite filenames via `_get_sprite_filenames()`
   f. Attach archetype, tier, sprite_filenames to placement
4. Compute `archetype_summary` by grouping placements
5. Write enriched division JSON

## Frontend Changes

### Champions Client Component

1. **Archetype summary bar** - Renders `archetype_summary` from division data. Shows sprite icons (using existing `SpriteRow` component) + archetype name + count for each archetype. Sorted by count descending.

2. **Archetype column** - Added to the placements table. Shows archetype name per row. Rows with null archetype show a dash.

3. **Image grid decklist** - Replaces the current text list when expanded. Responsive grid of card thumbnails grouped by category. Card image loaded from `image_url` with a styled fallback (card-shaped placeholder with JP name) for missing images. EN name (or JP fallback) and count displayed below each thumbnail.

## Testing

- Python: test `classify_decklist` with CL-style translated cards, test JP-EN lookup builds correctly from `cards.name_jp`, test image URL resolution with name matching, test archetype_summary aggregation
- Frontend: vitest for summary bar rendering with empty/populated data, image grid with missing images, null archetype display
