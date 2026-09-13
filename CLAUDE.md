# Scout

## Quick Context

- Data pipeline: Python 3.12+, SQLite
- Frontend: Next.js 16, Tailwind CSS, Recharts
- Hosting: Vercel (static export from `web/` directory)
- Domain: scout.trainerlab.io

## Key Files

- `config.py` - Rotation sets, tier thresholds, placement weights
- `db.py` - SQLite schema (cards, tournaments, placements, decklist_cards, cl_*, meta_snapshots, archetype_stats)
- `analysis/archetype.py` - Sprite-filename archetype derivation (`normalize_archetype`, `build_sprite_key`); content-based fallback lives in `analysis/archetype_classifier.py` (`ARCHETYPE_ANCHOR_CARDS` in `config.py`)
- `analysis/meta.py` - Meta snapshot computation, tier assignment
- `analysis/buylist.py` - Priority-scored buy list for S/A/B archetypes
- `reports/json_export.py` - All JSON exports (meta, buylist, trends, archetypes, champions league, images)
- `web/app/lib/types.ts` - TypeScript types matching Python export shapes
- `web/app/lib/data.ts` - Static JSON loaders (fs.readFileSync at build time)

## Tooling

### Python

- **uv** for env + dependency management (Python 3.12, pinned in `.python-version`)
  - `uv sync` installs runtime + the `dev` dependency group (PEP 735; `dev` includes `test`)
  - `uv run pytest tests/ -v` to test; `uv run scout <cmd>` (or `uv run python cli.py ...`) to run the CLI
  - `uv lock` after editing `pyproject.toml`; commit `uv.lock`
  - Deps live in `pyproject.toml` (`[project].dependencies` + `[dependency-groups]`); the top-level `requirements.txt` is the pinned export used by Cloud Build deploy
- **pytest** for testing, **ruff** for lint + format (`uv run ruff check . && uv run ruff format .`)
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

- One SQLite DB per format slug in `config.FORMATS` (`data/<slug>.db`); status derives from `dataset_end` via `is_format_frozen`
- **Active (2026-27 season, from 2026-09):** `storm-emeralda.db` (JP, M6 Storm Emeralda legal 2026-08-14, until M7 Hadou Seeker legality 2026-12-11), `tpci-standard-2027.db` (TPCi 2026-27 season, regulation H-I-J; end date is a placeholder until the 2027 rotation is announced)
- **Frozen:** `nihil-zero.db`, `ninja-spinner.db`, `abyss-eye.db` (JP, ended 2026-08-13), `tpci-standard.db` (2025-26 season incl. Worlds 2026), `tpci-standard-2025.db`, `tpci-standard-2024.db`, plus legacy `scout.db`
- Cloud Build reads the active/frozen split from `_SCRAPE_FORMATS` / `_FROZEN_FORMATS` in `cloudbuild-scrape.yaml`; `tests/test_jp_event_metadata.py` guards that they match `config.FORMATS`. Empty active formats (no placements yet) export nothing and appear as `"upcoming"` in `formats.json`.
- JP set legality convention: a JP set is tournament-legal two weeks after release; format boundaries follow that date
- `scraper/pokemon_jp_api.py` must use `curl_cffi` with Chrome impersonation (Cloudflare fingerprints TLS; plain httpx gets 403)
- Tournaments have a `division` column (open/senior/junior); meta analysis filters to open only

## Architecture

### Data Flow

```
Scrapers -> SQLite -> compute_meta_snapshot -> json_export -> GCS tarball -> Vercel prebuild -> Next.js SSG
```

Cloud Build uploads exported JSON as a tarball to `gs://tcg-scout-data/`.
Vercel prebuild downloads via signed URL in `web/data-manifest.json`.
All frontend data is static JSON read at build time via `fs.readFileSync`. No runtime API calls.

For local development, run `uv run scout --format <format> export-web` to generate data on disk.

### Archetype Detection

- Primary (`normalize_archetype`): derive the name directly from Limitless sprite-URL
  filenames, no lookup table. Single sprite -> titled stem ("Dragapult"); multiple ->
  alphabetical, " / "-joined ("Dragapult / Dusknoir"). This is host- and era-agnostic.
- Fallback: HTML text label from the tournament page, then "Unknown".
- Content-based (`classify_from_decklist` -> `archetype_classifier.classify_decklist`):
  classifies from decklist contents via `ARCHETYPE_ANCHOR_CARDS` (config) for JP City
  League / CL placements that have no sprite icons (`JP_CARD_NAME_MAP` maps JP names).
- Sprite key (`build_sprite_key`): sorted, lowercased, hyphenated filename stems
  (e.g., "charizard-pidgeot").

### Weighted Scoring

Placements weighted by finish position (config `PLACEMENT_WEIGHTS`):
- 1st: 3.0x, 2nd: 2.5x, 3rd-4th: 2.0x, 5th-8th: 1.5x, 9th-16th: 1.2x, 17th+: 1.0x
- CL results not included in archetype scoring (cl_placements lack archetype classification)

## Testing

- All feature work should include tests
- Python: pytest with in-memory SQLite fixtures (see `tests/conftest.py`)
- Frontend: vitest with mocked fs for data loaders
- Run both before pushing: `uv run pytest tests/ -v && cd web && npm test`

## Git Workflow

- Direct pushes to main during active development
- Vercel auto-deploys from main (root directory: `web/`)

## Session Guidelines

This project is the highest-friction project in the workspace (135 friction events, 7 cost-sink sessions). To avoid context decay:
- **Split by layer:** Separate sessions for Python pipeline work vs Next.js frontend work. Do not mix both in one session.
- **Session cap:** If a session exceeds 100 tool calls, wrap up current work and suggest starting a new session.
- **Key files first:** Read `config.py`, `db.py`, and `web/app/lib/types.ts` early, these are re-read most often.

## Conventions

- Avoid emdashes in UI text
- Keep Python exports and TypeScript types in sync
- New optional fields in types (for backward compatibility with existing JSON)
- Archetype slugs: lowercase, `[^a-z0-9]+` replaced with hyphens (`_slugify`)
- All 269 archetypes get detail pages (no minimum deck count filter)
