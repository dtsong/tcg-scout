# Main-Site Standings Scraper (pre-Labs international backfill)

Status: **planned** (investigation done; build not started)
Date: 2026-06-01
Motivates: completing `tpci-standard-2024` (2024-25 season incl. Worlds 2024)

## Problem

Limitless **Labs** standings (`labs.limitlesstcg.com/<id>/standings`, the
server-rendered blob the current `LabsLimitlessClient.fetch_standings` reads)
only indexed events from **~Sept 2024**. Every pre-Labs international major has
its standings + decklists on the **main** site (`limitlesstcg.com/tournaments/<id>`)
in a different HTML layout, with NO `/standings` sub-page (that path 404s).

Empirically (scrape of 2024-04-05 → 2025-04-10, `--max-pages 2`, 53 majors found):
- **24 ingested** via Labs: 2024-09-14 → 2025-03-29, 31,469 placements, archetype
  coverage **99.57%**. Solid back-half-of-season data (partial DB already on disk
  at `data/tpci-standard-2024.db`, gitignored).
- **29 skipped** "No Labs standings link yet" — a clean cliff at 2024-08-16 and
  older, including the marquee targets: **Worlds 2024 (id 420, 1147 players),
  NAIC 2024 (id 406), EUIC 2024 (id 405)**, plus all spring/summer 2024 Regionals
  and SE-Asia PBLs.

## Key finding (de-risks the build)

`scraper/limitless.py` `LimitlessClient.fetch_jp_city_league_placements` **already
parses the main-site standings table** and its own comments handle the
international layout: "JP City Leagues have deck in col 2; international tournaments
may have Country in col 2, Deck in col 3, List in col 4." It extracts rank,
player name, sprite-normalized archetype, and `/decks/list/<id>` decklist URL.
So this is **extend + integrate**, not a net-new parser.

## Open question to resolve FIRST (Phase 1)

The main page `/tournaments/420` exposes only the **top ~127** of 1147 Worlds-2024
players (the `/standings` sub-page is 404). Determine how to get the full field:
a query param (`?players=all`?), a separate results endpoint, or whether top-cut
is all the main site exposes. For weighted meta share, top-N of a major is still
usable (placements are finish-weighted), but confirm before scraping. Capture a
real HTML fixture of an international main-site standings table for tests.

## Plan (phased, TDD)

1. **Investigate + fixture**: nail the full-field URL/param; save a main-site
   standings HTML fixture (international layout) + a `/decks/list/<id>` fixture.
2. **Parser + integration** (TDD, ≤5 files): generalize the main-site standings
   fetch (rename off the `jp_city_league` name or add a sibling
   `fetch_main_site_standings(tournament_id)`); add a fallback in `cli.py`
   `scrape-tpci` — when `metadata.labs_tournament_id is None`, ingest via the
   main-site path instead of skipping. Reconcile `LimitlessPlacement` →
   placements insert (player_name/archetype/decklist_url; no country/W-L-T from
   this source — leave nullable). Keep the JP-region exclusion working.
3. **Re-scrape** `tpci-standard-2024` full window (`--since 2024-04-05 --until
   2025-04-10 --max-pages 2`). scrape-tpci skips existing rows, so this ADDS the
   29 pre-Labs events to the existing 24. Expect Worlds/NAIC/EUIC 2024 ingested.
4. **Gate**: archetype Unknown < 10% on the combined DB (Labs back-half is 0.43%;
   main-site rows should be similar — sprite-based).
5. **Decklists**: `backfill-decklists --source labs --max-standing 32` (the labs
   source path also handles main-site `/decks/list/` URLs — verify) + export
   (`meta` + `export-web --strict`) + `validate`.
6. **Publish**: upload `tpci-standard-2024.db` to `gs://tcg-scout-cache/scout-dbs/`
   **BEFORE** committing the config entry; add the config entry + tests; wire
   both cloudbuild yamls. Frozen Archives grouping is already generic (frontend
   needs no change — it auto-classified tpci-standard-2025).

## Verified boundaries (already researched — do not re-derive)

- 2024 Standard rotation (in-person): **2024-04-05**, reg mark E out, **F-G-H legal**.
- 2025 Standard rotation (in-person): **2025-04-11**, reg F out → window ends 2025-04-10.
- Worlds 2024: **Aug 16-18, 2024** (Honolulu); NAIC 2024: 2024-06-07 New Orleans.
- Adjacent to `tpci-standard-2025` (2025-04-11+); no gap/overlap.
- Sources: pokemon.com + PokeGuardian rotation announcements; Bulbapedia 2024-25 Standard.

## Config entry to add (Phase 6, NOT before GCS upload)

```python
"tpci-standard-2024": {
    "name": "TPCi Standard 2024",
    "name_en": "2024-25 Standard (post-E rotation)",
    "dataset_start": "2024-04-05",
    "dataset_end": "2025-04-10",
    "rotation_date": "2025-04-11",
    "description": "International Standard, 2024-25 season (regulation F-G-H): "
    "NAIC 2024, Worlds 2024, and the 2024-25 Regional/IC circuit",
    "db_name": "tpci-standard-2024.db",
},
```
Tests (drafted this session, reverted with the config): assert the 2024-04-05 →
2025-04-10 window and 1-day adjacency to tpci-standard-2025.

## Gotcha

Registering a format in `FORMATS` makes `export-web` try to export it. Do NOT
push the config entry until its DB is in the GCS cache, or a strict export run
risks an empty/failed export (per the tpci-standard-2025 publish lesson).
