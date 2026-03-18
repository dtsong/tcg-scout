# Scout

Competitive intelligence for Japan's post-rotation Pokemon TCG format. Tracks City League and Champions League tournament results, generates meta tier lists, buy lists, and trend analysis.

Live at [scout.trainerlab.io](https://scout.trainerlab.io)

## Stack

- **Data Pipeline:** Python 3.12+, SQLite (WAL mode)
- **Frontend:** Next.js 16, Tailwind CSS, Recharts
- **Hosting:** Vercel (static export)
- **Data Sources:** LimitlessTCG (City Leagues), pokemon-card.com (Champions League)

## Project Structure

```
trainerlab-scout/
  config.py              # Rotation rules, tier thresholds, placement weights
  db.py                  # SQLite schema and connection helpers
  cli.py                 # CLI entrypoint (scrape, compute, export)
  analysis/
    archetype.py         # Sprite-based archetype detection
    meta.py              # Meta snapshot computation and tier assignment
    buylist.py           # Priority-scored buy list generation
  reports/
    json_export.py       # Static JSON export for Next.js
  scrapers/              # Limitless and pokemon-card.com scrapers
  tests/                 # Python test suite (pytest)
  web/                   # Next.js frontend (deployed to Vercel)
    app/
      page.tsx           # Dashboard
      archetypes/        # Archetype list + detail pages
      buylist/           # Buy list with TCGPlayer links
      trends/            # Surging/declining card trends
      champions/         # Champions League decklists
      lib/
        types.ts         # TypeScript type definitions
        data.ts          # Static JSON data loaders
        utils.ts         # Formatting utilities
      components/        # Shared UI components
    public/
      data/              # Exported JSON (meta, buylist, trends, etc.)
      images/            # Pokemon sprites and card images
```

## Data Pipeline

```
Scrape (Limitless/pokemon-card.com)
  -> SQLite (tournaments, placements, decklist_cards, cl_*)
  -> compute_meta_snapshot (tier assignment)
  -> json_export (static JSON to web/public/data/)
  -> Next.js build (static HTML)
  -> Vercel deploy
```

### Key Commands

```bash
# Scrape latest City League results
python cli.py scrape

# Compute meta snapshot
python cli.py compute

# Export all data for the web frontend
python cli.py export-web

# Or use make
make export-web
```

## Frontend Development

```bash
cd web
npm install
npm run dev       # Dev server on localhost:3000
npm run build     # Production build (276 static pages)
npm test          # Run vitest
```

## Testing

```bash
# Python tests (55 tests)
python -m pytest tests/ -v

# Frontend tests (20 tests)
cd web && npm test
```

## Format Context

**Nihil Zero** is Japan's post-rotation format covering Temporal Forces (SV5) through Perfect Order, plus Mega Evolution sets (ME01-02.5). Japan plays this format months ahead of the international release, which goes live on April 10, 2026.

## Meta Analysis

- **Weighted scoring:** Tournament placements weighted by finish position (1st = 3.0x through top 16 = 1.2x, others = 1.0x)
- **Tier assignment:** S (15%+), A (8%+), B (3%+), C (1%+), Rogue (<1%)
- **Archetype detection:** Sprite-based from Limitless CDN URLs, with canonical name mapping
- **Trend analysis:** Early vs late period comparison with per-archetype breakdowns
