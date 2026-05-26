# TPCI Data Completeness — Phase 1 Design

**Date:** 2026-05-26
**Scope:** Pure Python pipeline. No frontend work. (Phase 2 trends/evolution + UI is a separate brainstorm.)
**Status:** Approved design, ready for implementation plan.

## Problem

Scout's international (TPCI) Standard coverage is shallow and disconnected:

1. **Majors are incomplete.** `data/tpci-standard.db` holds only 4 regionals
   (Prague, LA, Campinas, Utrecht — the labs H2H backfill seed). Many TPCI majors
   (Regionals, ICs, Worlds, Special Events) have occurred since the format's
   `dataset_start` of 2025-09-12 and are not ingested. `meta_snapshots` = 0;
   nothing is exported; `tpci-standard` is absent from `formats.json`.
2. **The days between majors are dark.** Majors fire roughly monthly. Between
   them, the competitive meta moves on `play.limitlesstcg.com` online events —
   a separate site Scout does not scrape at all.

The between-majors online data is not merely "more rows." Grassroots/online
events are low-stakes, so they surface **speculative and experimental lists
before they reach high-pressure majors**. Online is therefore a *leading
indicator* of the meta; majors are *confirmed* meta. Phase 1 captures both as
distinct, well-labelled datasets so Phase 2 can study the adoption pipeline
(a card/deck appears online → later wins a regional).

## Goals (Phase 1)

- Backfill **all** TPCI majors since `dataset_start`, compute meta, export so
  `tpci-standard` is live on the frontend.
- Add a new **`tpci-online`** format sourced from `play.limitlesstcg.com`,
  ingested broadly and labelled richly, with inclusion governed by a tunable
  config filter (not a scrape-time gate).
- Keep the two datasets **distinct** (separate formats / DBs). No blending.

## Non-Goals (deferred to Phase 2)

- Time-series / trends analysis (`analysis/trends.py`), `trends.json` export.
- Any frontend work, including a trends/evolution view.
- The "online-leads-majors" tech-adoption pipeline analysis.
- Backfilling online history beyond what the survey deems worthwhile.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Online vs majors data model | **Two distinct formats** (`tpci-standard`, `tpci-online`) | Online meta diverges from IRL (BO1 vs BO3, ladder vs Swiss+cut). Separate tier lists avoid one swamping the other; matches the established per-format-DB pattern. |
| Inclusion threshold | **Label-rich, filter-late** | Ingesting broadly + labelling means re-tuning inclusion is a config change, not a re-scrape. Cannot study data never scraped. |
| Ingest floor | **>=32 players (config-tunable)** | A volume bound only — crawling 8-person pods is not worth the rate budget. Not a meta-inclusion decision. |
| New label column | **`best_of` only** | Captures the "pressure" dimension (BO1 online vs BO3 majors). `size_tier` derived at query time from existing `player_count`; `tournament_type` reused for online subtypes. |
| Scraper structure | **New `PlayLimitlessClient`** | `play.limitlesstcg.com` is a net-new host; `LabsLimitlessClient` is already ~1200 LOC across two hosts. Clean boundary, reuses `RateLimitedHTTPClient`. |
| Storage | SQLite format DBs (`tpci-standard.db`, `tpci-online.db`) | Existing `get_format_connection` pattern. Postgres `labs` schema stays the H2H matchup store (separate concern, already built). |

## Architecture

Three workstreams, runnable largely independently.

### 1a — Majors completeness (mostly existing code)

`scrape-tpci` already discovers majors via
`LabsLimitlessClient.list_tournaments(type_filter="major")`
(`scraper/labs_limitless.py:476`) and ingests standings + decklists into the
format DB (`cli.py:2077`). Work:

1. Run `scout --format tpci-standard scrape-tpci --type-filter major --since 2025-09-12`
   to backfill every major since dataset start.
2. **Validate EN archetype classification.** `ARCHETYPE_ANCHOR_CARDS` is
   JP-name oriented. Sprite-based detection (`SPRITE_ARCHETYPE_MAP`) is primary
   and host-agnostic, so it should carry EN events — but coverage must be
   measured against the loaded decks. If sprite coverage is gappy, add an
   EN-label → Scout-slug reconciliation pass. Surface a coverage metric
   (% placements with a non-`other` archetype) as the gate.
3. `scout --format tpci-standard meta` then `export-web` →
   `tpci-standard` appears in `formats.json`.

### 1b — Online landscape survey (new, cheap)

New CLI `scout survey-online`:
- Listings-only (no decklists, no standings detail). Low request count.
- Emits a landscape report to stdout/stderr: events per week, player-count
  histogram, cadence relative to majors, BO1 vs BO3 split, format mix.
- Writes nothing to a published DB (metadata-only; may persist to a scratch
  table or just report). Purpose: set the **default inclusion filter** values
  in `config.py` from real distribution data.

### 1c — Online ingestion (new)

- `scraper/play_limitless.py` → `PlayLimitlessClient(RateLimitedHTTPClient)`:
  `list_events()`, `fetch_standings()`, `fetch_decklist()` for
  `play.limitlesstcg.com`. Own parsers; reuses the rate-limit base and
  `analysis/archetype.normalize_archetype`.
- `scout --format tpci-online scrape-play`:
  - Ingest all Standard events at/above the config floor (`>=32`).
  - **Resumable + idempotent** — skip already-ingested event IDs.
  - Populate `best_of`, `player_count`, `tournament_type` (online subtypes),
    `division`, `country`, `date`.
- Inclusion filter lives in `config.py` and is applied in `analysis/meta.py`
  (e.g. min player count, allowed `best_of`, allowed subtypes). Defaults seeded
  from the 1b survey.
- `scout --format tpci-online meta` then `export-web` → `tpci-online` in
  `formats.json`.

## Data Model

`tournaments` schema (shared across format DBs) today:

```
id, name, date, player_count, country, division,
tournament_type, prefecture, store_name, capacity
```

**Change:** add `best_of INTEGER` (nullable; NULL = unknown). Migration applied
to all format DBs (schema is shared). No `size_tier` column — derived from
`player_count` at query time. `source` is implicit per format DB.

Inclusion-filter config shape (illustrative, in `config.py`):

```python
TPCI_ONLINE_INCLUSION = {
    "min_player_count": 64,    # default for meta; ingest floor is lower (32)
    "allowed_best_of": [3],    # tune after survey
    "allowed_subtypes": None,  # None = all
}
SIZE_TIERS = [(256, "large"), (64, "medium"), (32, "small")]
```

## Components & Isolation

| File | Change | Responsibility |
|------|--------|----------------|
| `scraper/play_limitless.py` | NEW | `PlayLimitlessClient` + dataclasses + parsers for play.* |
| `cli.py` | NEW commands | `scrape-play`, `survey-online` |
| `config.py` | NEW | `tpci-online` format entry; `TPCI_ONLINE_INCLUSION`; `SIZE_TIERS` |
| `db.py` | migration | add `best_of` column to `tournaments` |
| `analysis/meta.py` | edit | honor inclusion filter when computing online meta |
| `reports/json_export.py` | none expected | format-agnostic loop already exports any registered format |
| `web/app/lib/*` | none | frontend discovers formats from `formats.json`; no code change |
| `tests/` | NEW | play fixtures, parser/label/inclusion tests, integration |

## Error Handling & Ops

- 20 RPM rate limit (`config.LABS_REQUESTS_PER_MINUTE` or a play-specific value);
  reuse backoff/retry from `RateLimitedHTTPClient`.
- Ingestion idempotent (`INSERT ... ON CONFLICT`/`INSERT OR IGNORE` on event id),
  resumable by skipping ingested ids; commit per event or small batch.
- Archetype fallback chain unchanged: sprite map → derived-from-key → HTML label
  → `other`.
- Survey is read-only and side-effect-free on published data.

## Testing

Mirror the labs spike pattern (offline-first):
- Snapshot `play.limitlesstcg.com` fixtures (listing page, a standings page, a
  decklist) into `tests/fixtures/play/`; parser unit tests run against fixtures
  with zero network.
- `best_of` / label-derivation unit tests.
- Inclusion-filter unit tests (rows in/out for given config).
- EN archetype coverage test on a majors sample (asserts coverage above an
  agreed threshold; this is the 1a gate).
- Integration: mocked `scrape-play` → `meta` → `export-web` asserts
  `tpci-online` present in `formats.json` with non-zero counts.

## Verification

1. `tpci-standard.db` tournament count >> 4 after 1a; meta computed; archetype
   coverage above gate; `tpci-standard` in `formats.json`.
2. Survey report produced; inclusion defaults set in `config.py` from it.
3. `tpci-online.db` populated above floor; re-running `scrape-play` adds 0 rows
   (idempotent); `tpci-online` in `formats.json`.
4. `uv run pytest tests/ -v` green; `uv run ruff check . && uv run ruff format --check .` clean.

## Open Questions

- Exact `play.limitlesstcg.com` page structure (HTML vs SvelteKit JSON, where
  `best_of` is exposed, how decklist links are formed) — resolved during the
  fixture-snapshot step of 1c.
- Whether the survey persists a scratch table or only reports — decide during
  1b; default to report-only.
