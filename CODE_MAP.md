# CODE_MAP.md

Quick-reference architecture map for coding agents navigating the Scout codebase.

## Data Flow

```
Scrapers (limitless.py, pokemon_jp.py, tcgdex.py)
  -> SQLite (db.py schema, one DB per format)
    -> Analysis (meta.py, archetype.py, card_stats.py, etc.)
      -> JSON Export (json_export.py -> web/public/data/)
        -> Next.js SSG (fs.readFileSync at build time)
          -> Vercel static deploy
```

## Directory Layout

```
├── config.py                        # Rotation sets, formats, tier thresholds, placement weights
├── db.py                            # SQLite schema (10 tables), connection management
├── cli.py                           # Click CLI: scrape, compute, export-web, cl-scrape
├── analysis/
│   ├── archetype.py                 # SPRITE_ARCHETYPE_MAP, normalize_archetype()
│   ├── archetype_classifier.py      # classify_decklist() from card contents
│   ├── meta.py                      # compute_meta_snapshot(), tier assignment
│   ├── buylist.py                   # generate_buylist(), priority scoring
│   ├── card_stats.py                # compute_card_stats(), _classify_card()
│   ├── evolution.py                 # compute_archetype_evolution(), weekly tracking
│   ├── matchup.py                   # compute_matchup_matrix(), co-tournament performance
│   └── synergy.py                   # compute_synergy_pairs(), card co-occurrence
├── scraper/
│   ├── limitless.py                 # LimitlessClient: City League scraper (httpx)
│   ├── pokemon_jp_api.py            # PokemonJPAPIClient: players.pokemon-card.com HTTP API
│   ├── pokemon_jp.py                # PokemonJPClient: Playwright browser scraper (CL decklists)
│   ├── tcgdex.py                    # TCGdexClient: rotation-legal card catalog
│   └── card_mappings.py             # JP->EN card ID mapping scraper
├── reports/
│   ├── json_export.py               # All JSON exports, JP_CARD_NAMES dict, _build_jp_en_lookup()
│   ├── csv_export.py                # CSV export (legacy)
│   └── markdown.py                  # Markdown reports
├── scripts/
│   ├── populate_supertypes.py       # Fetch card supertypes from TCGdex API
│   └── validate_classifier.py       # Test archetype classifier accuracy
├── tests/
│   ├── conftest.py                  # In-memory SQLite fixture (3 tournaments, 6 placements, 1 CL event)
│   ├── test_archetype.py            # Sprite detection
│   ├── test_archetype_classifier.py # Content classification
│   ├── test_meta.py                 # Meta snapshot
│   ├── test_card_stats.py           # Card stats + supertype override
│   ├── test_json_export.py          # JSON export end-to-end
│   ├── test_populate_supertypes.py  # populate_supertypes with mocked API
│   ├── test_evolution.py            # Evolution tracking
│   ├── test_matchup.py              # Matchup matrix
│   ├── test_synergy.py              # Synergy pairs
│   ├── test_pokemon_jp_api.py       # API client
│   └── test_integration.py          # Full pipeline
├── web/
│   ├── app/
│   │   ├── page.tsx                 # Root: format selector
│   │   ├── layout.tsx               # Root layout
│   │   ├── [format]/
│   │   │   ├── page.tsx + dashboard-client.tsx    # Dashboard overview
│   │   │   ├── layout.tsx                         # Format layout (nav, date filter)
│   │   │   ├── archetypes/
│   │   │   │   ├── page.tsx + archetypes-client.tsx
│   │   │   │   └── [slug]/page.tsx + results-table.tsx
│   │   │   ├── cards/
│   │   │   │   ├── page.tsx + cards-client.tsx
│   │   │   │   └── [slug]/page.tsx + card-detail-client.tsx
│   │   │   ├── buylist/page.tsx + buylist-client.tsx
│   │   │   ├── trends/page.tsx + trends-client.tsx
│   │   │   └── champions/page.tsx + champions-client.tsx
│   │   ├── components/              # Shared UI (see Components section)
│   │   └── lib/
│   │       ├── types.ts             # All TypeScript interfaces
│   │       ├── data.ts              # Static JSON loaders (fs.readFileSync)
│   │       └── utils.ts             # cn(), formatPlacement(), formatPct()
│   └── public/data/{format}/        # Exported JSON (meta, buylist, archetypes/, cards/, etc.)
└── data/                            # SQLite databases (one per format)
```

## Database Tables (db.py)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `cards` | Rotation-legal card catalog (TCGdex) | id, name_en, name_jp, set_code, supertype, regulation_mark |
| `tournaments` | City League events | id, name, date, player_count |
| `placements` | Tournament results | tournament_id, standing, archetype, player_name |
| `decklist_cards` | Per-placement card counts | placement_id, card_id, card_name, count |
| `card_mappings` | JP-EN card ID mappings | jp_card_id, en_card_id, card_name_jp, card_name_en |
| `cl_events` | Champions League events | id, name, division, date |
| `cl_placements` | CL results | event_id, standing, player_name, region, deck_code |
| `cl_decklist_cards` | CL decklists (JP names) | placement_id, card_name_jp, card_name_en, count, category |
| `meta_snapshots` | Computed meta state | id, generated_at, tournament_count, deck_count |
| `archetype_stats` | Per-snapshot archetype metrics | snapshot_id, archetype, meta_share, tier, deck_count |

## Key Config Constants (config.py)

| Constant | Value | Purpose |
|----------|-------|---------|
| `TIER_THRESHOLDS` | S: 15%, A: 8%, B: 3%, C: 1% | Assign archetype tiers |
| `PLACEMENT_WEIGHTS` | 1st: 3.0, 2nd: 2.5, ... 17th+: 1.0 | Weight tournament finishes |
| `ARCHETYPE_ANCHOR_CARDS` | dict | Primary/secondary Pokemon -> archetype name |
| `ROTATION_LEGAL_REGULATION_MARKS` | {H, I} | Filter TCGdex cards |
| `CORE_INCLUSION_RATE` | 75% | Buy list core threshold |

## Archetype Detection Pipeline

1. **Primary**: derive archetype names directly from Limitless sprite URL filenames (`analysis/archetype.py`)
2. **Fallback**: HTML text label from tournament page, then `Unknown`
3. **Content-based**: `classify_decklist()` matches Pokemon anchor cards for sources without sprites (`analysis/archetype_classifier.py`)

## JSON Export Outputs (json_export.py)

All exports land in `web/public/data/{format}/` locally, then Cloud Build packages them into a GCS data tarball referenced by `web/data-manifest.json`:

| File | Function | Content |
|------|----------|---------|
| `meta.json` | `export_meta()` | Archetype list with meta_share, tier, trend |
| `buylist.json` | `export_buylist()` | Priority-scored cards with urgency |
| `staples.json` | `export_staples()` | High-inclusion cards |
| `flex.json` | `export_flex()` | Medium-inclusion cards |
| `trends.json` | `export_trends()` | Surging/declining cards |
| `winning-edge.json` | `export_winning_edge()` | 1st-place advantage cards |
| `ace-specs.json` | `export_ace_specs()` | ACE SPEC card usage |
| `timeline.json` | `export_timeline()` | Weekly meta share history |
| `evolution.json` | `export_meta_evolution()` | Archetype adoption/drop events |
| `matchup.json` | `export_matchup_matrix()` | Pairwise performance matrix |
| `overlap.json` | `export_overlap_matrix()` | Archetype similarity matrix |
| `archetypes/{slug}.json` | `export_archetype_details()` | Per-archetype detail pages |
| `cards/{slug}.json` | `export_card_details()` | Per-card detail pages |
| `champions-league/{div}.json` | `export_champions_league()` | CL division results |

## Frontend Components (web/app/components/)

**Charts**: meta-bar-chart, meta-timeline, evolution-timeline, archetype-radar, archetype-heat-matrix, matchup-heat-matrix, performance-trendline

**Data**: data-table (sortable/filterable), sprite-row, variant-breakdown

**UI**: nav, stat-card, tier-badge, date-filter, date-filter-provider, welcome-guide

## TypeScript Types (web/app/lib/types.ts)

Core types: `Tier`, `FormatInfo`, `ArchetypeSummary`, `MetaData`, `BuylistCard`, `ArchetypeDetail`, `CardDetail`, `CLDivision`, `CLPlacement`, `CLDecklistCard`, `CLArchetypeSummary`, `MatchupMatrixData`, `OverlapMatrixData`, `TrendsData`, `EvolutionEvent`

## Test Commands

```bash
python -m pytest tests/ -v                    # All Python tests
python -m pytest tests/test_meta.py -v        # Single module
cd web && source ~/.nvm/nvm.sh && npm test    # Frontend tests
```

## CLI Commands (cli.py)

```bash
scout init [--reset]                          # Initialize DB
scout cards                                   # Fetch card catalog from TCGdex
scout scrape [--start] [--end]                # Scrape City Leagues from Limitless
scout compute                                 # Compute meta snapshot
scout export-web                              # Export all JSON to web/public/data/
scout cl-scrape                               # Scrape Champions League events
scout cl-classify                             # Classify CL decklists
```
