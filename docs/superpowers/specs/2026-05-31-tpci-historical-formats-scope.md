# TPCI Historical Multi-Format Backfill — Scope Note

**Date:** 2026-05-31 (updated 2026-06-01)
**Status:** First rotation SHIPPED. `tpci-standard-2025` (2025 spring rotation) is
backfilled, exported, and wired to publish. See "2026-06-01 — Spike shipped" below.
**Trigger:** "Leverage labs.limitlesstcg.com as source of truth — there's a ton of historical data across formats."

## 2026-06-01 — Spike shipped (tpci-standard-2025)

One-rotation spike taken through full publish (commits `94f7a97`, `b012852`, `a8fcd7e`).

- **Window:** 2025-04-11 → 2025-09-11 (F rotated out, G+H legal; pre-Mega Evolution).
- **Data:** 11 majors (incl. NAIC 2025, Worlds 2025), 16,998 placements, 352 top-32 decklists.
- **Quality gate PASSED:** archetype coverage **99.65%** (59 Unknown). The Q4 fear below is
  empirically moot for this era — `normalize_archetype` derives names from sprite-URL
  filenames (era-agnostic), NOT a `SPRITE_ARCHETYPE_MAP` lookup (Q4 / CLAUDE.md are stale).
- **Tooling added:** `--until` upper bound on `scrape-tpci` (meta.py doesn't filter by
  `dataset_end`, so a per-format DB must be window-bounded at scrape time).
- **Frontend (Q5 resolved):** frozen formats now group under an "Archives" heading; no new
  status needed (`status:"frozen"` already derives from `dataset_end < today`). Frozen banner
  copy made format-aware (was JP-City-League-hardcoded).
- **Floor (Q1):** stopped at the 2025 spring rotation. Deeper history (Worlds 2024 etc.)
  blocked on `list_tournaments` pagination (single 100-row page; 2025 window fit, older won't).

### Original scope (preserved below for the remaining open questions)

## What's available (discovery 2026-05-31)

`limitlesstcg.com` STANDARD/major listing returns **100+ majors back to at least 2024-05-11**, page-capped at 100 (more behind it). Examples beyond the current window:
- World Championships 2024 (US), NAIC 2024 New Orleans, EUIC/LAIC 2024–25
- Full Regional/Special-Event circuit across NA / EU / LATAM / APAC / Korea

Everything **before 2025-09-12** belongs to **earlier Standard rotations** (different cardpools) than `tpci-standard` (2025-09-12 → 2026-09-04).

## Region scope: TPCI primary, TPC only if format-matched

Inclusion rule (set 2026-05-31):

- **TPCI regions are primary** — Americas (US/CA/MX/BR/AR/CL/PR…), Europe (GB/DE/FR/ES/PL/NL/CZ…), Oceania (AU/NZ), Africa (ZA). These are the default ingest set.
- **TPC regions (JP/KR + Asian Premier Ball Leagues: MY/ID/SG/PH/TW/TH) are skipped by default.** They run on separate org structures and largely don't publish to `labs.limitlesstcg.com`.
- **Exception:** TPC-region events are includable **iff the format is the same** (Temporal Forces → Perfect Order Standard) **and** standings are actually available. Same cardpool = comparable meta.

Current-window effect: the 6 unfetched majors are 5 TPC-region (Korean Leagues ×3, Malaysia + Indonesia PBL — out of scope) and 1 TPCI (Special Event Cape Town, 88p, no published standings). The 31 ingested are 100% TPCI. No filtering code needed yet — the "no Labs link" skip already excludes the TPC events; an explicit region filter only becomes necessary if/when TPC events start publishing standings.

## The core problem

`tpci-standard` is a single rotation window. Capturing pre-2025-09-12 majors means **defining new historical format entries** in `config.py` (one per rotation), each with its own DB, meta, and tier list — not widening one backfill. The scraper (`LabsLimitlessClient`) and ingest (`scrape-tpci --format <historical>`) already work across all of them; the missing pieces are format definitions and rotation boundaries.

## Open questions for the brainstorm

1. **How far back?** Worlds 2024 (2024-08) as the floor? Earlier? ROI drops as cardpools age out of relevance.
2. **Rotation boundaries.** Need the exact set-release/rotation dates that delimit each prior international Standard format (the analog of `tpci-standard`'s 2025-09-12 start).
3. **Format naming.** Mirror the JP-style codenames, or plain rotation labels (e.g. `tpci-standard-2024`)?
4. **Archetype validity across eras.** Sprite map is host-agnostic (100% on current EN majors), but older archetypes may not exist in today's `SPRITE_ARCHETYPE_MAP` — needs a coverage check per era.
5. **Frontend.** Multiple historical formats in `formats.json` — does the format switcher need a "historical/archived" grouping?
6. **Relationship to Phase 2 (online).** Does historical majors data feed the eventual trends/adoption analysis, or stand alone?

## Dependencies
- Current-window Phase 1a should ship first (proves the pipeline end-to-end on EN majors).
- No code change to the scraper expected; this is config + ops + (maybe) frontend grouping.
