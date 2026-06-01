# TPCI Phase 1a — Current-Window Backfill: Execution Plan

**Date:** 2026-05-31
**Spec:** `2026-05-26-tpci-data-completeness-design.md` (workstream 1a)
**Scope:** Backfill the missing `tpci-standard` majors (dataset_start 2025-09-12+), compute meta, ship live. Pure pipeline.
**Status:** Ready to execute. Primary risk pre-cleared.

## What discovery established (2026-05-31)

- `limitlesstcg.com` STANDARD/major listing: **37 majors since 2025-09-12**; **4 ingested**, **33 missing**.
- **EN archetype gate: PASSED.** The 4 ingested majors classify at **100% (128/128, 0 `other`)**. Sprite-based `SPRITE_ARCHETYPE_MAP` is host-agnostic and carries EN events. → The spec's "EN-label reconciliation pass" branch is **dropped**.
- Current ingest depth is **top-32 per major** (a decision point below).
- **Indianapolis is not yet posted** on Limitless (latest major = Regional Melbourne 2026-05-23). The backfill includes it automatically once standings appear.
- **Scope is TPCI-only** (Americas/Europe/Oceania/Africa). The 6 unfetched majors are 5 TPC-region (Korean Leagues ×3, Malaysia + Indonesia PBL — out of scope by design) + 1 TPCI (Cape Town, 88p, no published standings). Final set = 31 TPCI majors, 0 TPC. See `2026-05-31-tpci-historical-formats-scope.md` for the TPCI/TPC inclusion rule.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Ship order | **Standings first, decklists later** | Standings give archetype-based meta (the "format history" goal) in ~minutes at 20 RPM. Decklists (~1000+ requests, ~1h) enable card-level buylist — defer to a second pass. |
| Ingest depth | **Full standings** (`--max-placements` unset), not top-32 | Richer meta + placement-weight curve goes to 17th+. Re-running upgrades the existing 4. Revisit if request budget bites. |
| Where it runs | **Local validation → GCS cache upload** | One-time backfill. Cloud Build path documented as the durable option for ongoing monthly majors. |
| EN reconciliation pass | **Not needed** | Gate passed at 100%. |

## Phases

### Phase 0 — Smoke test (1 major, end-to-end)
```
uv run scout --format tpci-standard scrape-tpci --since 2025-09-12 \
  --no-decklists --max-tournaments 1
```
Verify: 1 new tournament + standings ingested, archetype coverage >=95%, no parser errors.

### Phase 1 — Full standings backfill (33 majors, no decklists)
```
uv run scout --format tpci-standard scrape-tpci --since 2025-09-12 --no-decklists
```
- Idempotent: skips the 4 already ingested.
- Gate: overall archetype coverage >=95% across all majors (measure before proceeding).

### Phase 2 — Meta + export
```
uv run scout --format tpci-standard meta
uv run scout --format tpci-standard export-web --strict
uv run scout --format tpci-standard validate
```
Verify: `tpci-standard` in `web/public/data/formats.json` with status `active`, tournament_count ~37, non-zero deck_count, meta_snapshot present.

### Phase 3 — Ship to production
The 3-hourly `cloudbuild-scrape.yaml` restores **all** `*.db` from `gs://tcg-scout-cache/scout-dbs/` and `export-web` includes every registered format. So tpci-standard goes live by landing its DB in that cache:
```
gsutil cp data/tpci-standard.db gs://tcg-scout-cache/scout-dbs/
```
**Blocker:** the agent's `gcloud` is authed to the wrong project (`appraisehq-prod`) with stale tokens. **User must run the upload** (or `gcloud auth login` + set the tcg-scout project for the agent). Next scrape run (~3h) publishes it; Vercel redeploys.

### Phase 4 (follow-on) — Decklists
Re-run without `--no-decklists` (full or `--since`-bounded), or add a `cloudbuild-tpci.yaml` modeled on `cloudbuild-decklists.yaml` for ongoing majors.

## Verification checklist
- [ ] Phase 0 smoke: 1 major, coverage >=95%
- [ ] Phase 1: 33 majors ingested, idempotent re-run adds 0
- [ ] Phase 2: `tpci-standard` exported, meta computed, `validate` clean
- [ ] `uv run pytest tests/ -v` green; `uv run ruff check . && uv run ruff format --check .` clean
- [ ] Phase 3: DB in GCS cache; format live on scout.trainerlab.io after next scrape

## Open questions
- Full-standings request volume vs 20 RPM — acceptable for one-time run? (Estimate after Phase 0.)
- Ongoing freshness: scheduled `cloudbuild-tpci.yaml` vs manual monthly re-run? (Defer to post-ship.)
