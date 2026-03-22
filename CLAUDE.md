# Scout

## Quick Context

- Data pipeline: Python 3.12+, SQLite
- Frontend: Next.js 16, Tailwind CSS, Recharts
- Hosting: Vercel (static export from `web/` directory)
- Domain: scout.trainerlab.io

## Key Files

- `config.py` - Rotation sets, tier thresholds, placement weights
- `db.py` - SQLite schema (cards, tournaments, placements, decklist_cards, cl_*, meta_snapshots, archetype_stats)
- `analysis/archetype.py` - Sprite-based archetype detection (`SPRITE_ARCHETYPE_MAP`, `_COMPOSITE_SPRITE_FILENAMES`)
- `analysis/meta.py` - Meta snapshot computation, tier assignment
- `analysis/buylist.py` - Priority-scored buy list for S/A/B archetypes
- `reports/json_export.py` - All JSON exports (meta, buylist, trends, archetypes, champions league, images)
- `web/app/lib/types.ts` - TypeScript types matching Python export shapes
- `web/app/lib/data.ts` - Static JSON loaders (fs.readFileSync at build time)

## Tooling

### Python

- **pytest** for testing (`python -m pytest tests/ -v`)
- No virtualenv tooling configured; uses system Python 3.12+
- SQLite with WAL journaling, row_factory = sqlite3.Row

### TypeScript (web/)

- **npm** as package manager
- **vitest** for testing (`npm test`)
- **eslint** via next lint
- Path alias: `@/` maps to `web/app/`

### Node.js / NVM

When running `node`, `npm`, `npx`, or any Node.js tools:
```bash
source ~/.nvm/nvm.sh && nvm use default --silent && <command>
```

## Databases

- `data/scout.db` (Nihil Zero format) -- **frozen**, no new tournament data will be ingested
- `data/nihil-zero.db` -- **frozen**, no new tournament data will be ingested
- `data/ninja-spinner.db` -- **active**, current rotation format receiving new data
- Tournaments have a `division` column (open/senior/junior); meta analysis filters to open only

## Architecture

### Data Flow

```
Scrapers -> SQLite -> compute_meta_snapshot -> json_export -> GCS tarball -> Vercel prebuild -> Next.js SSG
```

Cloud Build uploads exported JSON as a tarball to `gs://tcg-scout-data/`.
Vercel prebuild downloads via signed URL in `web/data-manifest.json`.
All frontend data is static JSON read at build time via `fs.readFileSync`. No runtime API calls.

For local development, run `python cli.py --format <format> export-web` to generate data on disk.

### Archetype Detection

- Primary: `SPRITE_ARCHETYPE_MAP` lookup from Limitless sprite URLs
- Fallback: Auto-derive name from sprite key (`_derive_name_from_key`)
- Last resort: HTML text label from tournament page
- Sprite key: sorted, hyphenated filename stems (e.g., "charizard-pidgeot")

### Weighted Scoring

Placements weighted by finish position (config `PLACEMENT_WEIGHTS`):
- 1st: 3.0x, 2nd: 2.5x, 3rd-4th: 2.0x, 5th-8th: 1.5x, 9th-16th: 1.2x, 17th+: 1.0x
- CL results not included in archetype scoring (cl_placements lack archetype classification)

## Testing

- All feature work should include tests
- Python: pytest with in-memory SQLite fixtures (see `tests/conftest.py`)
- Frontend: vitest with mocked fs for data loaders
- Run both before pushing: `python -m pytest tests/ -v && cd web && npm test`

## Git Workflow

- Direct pushes to main during active development
- Vercel auto-deploys from main (root directory: `web/`)

## Conventions

- Avoid emdashes in UI text
- Keep Python exports and TypeScript types in sync
- New optional fields in types (for backward compatibility with existing JSON)
- Archetype slugs: lowercase, `[^a-z0-9]+` replaced with hyphens (`_slugify`)
- All 269 archetypes get detail pages (no minimum deck count filter)
