# Harness Pipelines Replace Cloud Build

Status: approved in chat 2026-09-15 (approach A, daily cadence, lean CI).
Supersedes `2026-07-29-harness-ci-spike-design.md`, which concluded that the
3-hourly scrape could not fit Harness Free. It still cannot. What changed is
the cadence (daily) and the caching (frozen exports restored, not recomputed),
which together fit the budget.

## Decision

Move both pipelines (scheduled scrape and CI) from Google Cloud Build to
Harness CI on Harness Cloud runners, and remove every GCP dependency: no GCS
buckets, no Secret Manager, no Cloud Scheduler. Durable state lives in
Harness-hosted cache with a GitHub Release as the backup and as the public
download for Vercel.

## Budget

| Item | Per run | Per month |
|---|---|---|
| Free plan allowance | | 2000 credits, no rollover |
| Linux runner (8 core default) | 2 credits/min | |
| vgc-trainerlab nightly (same account) | ~11 min | ~660 credits |
| scout_scrape, 1 run/day, early season | ~2 min | ~120 credits |
| scout_scrape, 1 run/day, peak season | ~15 min | ~900 credits |
| scout_verify, ~30 runs/month | ~4 min | ~240 credits |

Peak total ~1800 credits. Twice-daily scraping is a one-line trigger change
that is affordable only while runs stay under ~7 min. Playwright e2e is not
run on Harness for this reason.

## Harness objects (account `jKE_O7LaTmaV8BCJt1ic7w`, org `default`, project `default_project`)

| Object | Identifier | Notes |
|---|---|---|
| Pipeline | `scout_scrape` | Source of truth `.harness/pipelines/scrape.yaml`, applied with the Harness MCP tools like vgc-trainerlab. Tag `app: tcg-scout`. |
| Pipeline | `scout_verify` | `.harness/pipelines/verify.yaml`. |
| Trigger | `scout_scrape_daily` | Cron `0 6 * * *` UTC, branch `main`. `.harness/triggers/scrape-cron.yaml`. |
| Trigger | `scout_verify_on_push` | GitHub push to `main`, aborts previous. `.harness/triggers/verify-on-push.yaml`. |
| Connector (existing) | `account.Github_OAuth_1784959546725` | Codebase clone. |
| Secret (existing) | `account.harnessoauthaccesstoken_github_1784959546428` | Write-scoped OAuth token used for the manifest push and release uploads. No new secrets. |

Pipelines are v0 YAML (`pipeline:` root, `<+...>` expressions). Identifiers
are literal strings (Harness treats them as primary keys).

## Storage

| Data | Where | Why |
|---|---|---|
| `data/*.db` (16 MB compressed) | Harness cache key `scout-dbs`, `override: true`; backed up every run to the release asset `dbs.tar.gz` | Cache is fast; the release survives the 15-day cache retention and eviction. |
| `web/public/data/` (31 MB compressed) | Harness cache key `scout-export` | Frozen formats are byte-stable and cost ~20 min each to recompute. Active formats are re-exported every run over the top. |
| Data tarball for Vercel | GitHub Release tagged `data` (prerelease, so it never becomes "Latest"), asset `data-<ts>.tar.gz`, last 8 kept | Public URL, `fetch` in `prebuild.mjs` follows the redirect and verifies sha256. Manifest format unchanged. |

## scout_scrape stage steps

1. `RestoreCache` key `scout-dbs` and `RestoreCache` key `scout-export`
   (a missing key is not an error).
2. `Run` **bootstrap**: `python scripts/publish_data_release.py restore`.
   If `data/` has no `.db` files, download `dbs.tar.gz` from the release
   (skip if the asset does not exist yet). If `web/public/data/formats.json`
   is missing, download the newest `data-*.tar.gz` from the release, or, when
   the release has none, `https://storage.googleapis.com/tcg-scout-data/data-latest.tar.gz`
   (public, one-time migration path).
3. `Run` **scrape and export**: install uv with the official installer,
   `uv sync --locked --no-dev`, then for each `formats-list --status active`
   slug with region `jp`: init, scrape, scrape-jp, backfill-archetypes,
   translate-cards, meta. tpci-standard-2027 stays export-only, as today.
   Export every active format with `--strict`. For each frozen slug, export
   only if `web/public/data/<slug>/meta.json` is missing. `timeout: 45m`.
4. `Run` **validate**: `scout --format <slug> validate` for every slug whose
   DB file exists (today's list is hard-coded and stale).
5. `SaveCache` `scout-dbs` and `SaveCache` `scout-export`, both `override: true`.
6. `Run` **publish**: `python scripts/publish_data_release.py publish`
   tars `web/public/data`, uploads it and `dbs.tar.gz` to the `data` release
   (creating the release if absent), prunes data tarballs beyond the newest
   8, writes `web/data-manifest.json`, and pushes the manifest commit to
   `main` with the vgc credential pattern (token in the URL is masked by
   Harness; no credential helper needed). Guard: only on branch `main`; no-op
   on an empty diff; rebase-and-retry three times on a rejected push.

`scripts/publish_data_release.py` is stdlib-only (urllib, tarfile, hashlib,
json) so it runs before `uv sync`. It reads `GITHUB_TOKEN` from the
environment and never prints it. Unit tests cover manifest writing,
asset pruning, and the restore fallback order with a fake HTTP layer.

## scout_verify stage steps

One `Run` step: install uv, `uv sync --locked`, `ruff check`,
`ruff format --check`, `pytest tests/`. A second `Run` step: install Node 22
with the vgc curl+tar recipe, `npm ci`, `tsc --noEmit`, `eslint . --quiet`,
`vitest run`. Cache Intelligence enabled for the uv and npm caches.

## Tests and guards

- `tests/test_harness_pipelines.py`: both YAML files parse, identifiers are
  literal, the scrape pipeline uses `formats-list` rather than a hard-coded
  slug list, the cron expression is daily, and no step embeds a secret in
  plain text.
- `tests/test_publish_data_release.py`: as above.
- `tests/test_jp_event_metadata.py`: the `_SCRAPE_FORMATS` guard is removed
  with the Cloud Build file.

## Cutover

1. Commit `.harness/`, the script, and tests. Apply pipelines and triggers
   through the Harness MCP tools.
2. Owner, once, after `gcloud auth login`: copy the production DBs and
   seed the release, so the first Harness run starts from real data:
   `gsutil -m cp 'gs://tcg-scout-cache/scout-dbs/*.db' data/ && GITHUB_TOKEN=$(gh auth token) .venv/bin/python scripts/publish_data_release.py upload-dbs`.
   Without this step the first run still succeeds: frozen exports come from
   the public `data-latest.tar.gz`, but tpci-standard-2027's operator-ingested
   DB would be lost, so do this before the first run.
3. Run `scout_scrape` manually; confirm the manifest commit and the Vercel
   deploy.
4. Pause the Cloud Scheduler job, then delete it and the Cloud Build
   triggers. Delete `cloudbuild-*.yaml`. Update `CLAUDE.md` and
   `requirements.txt` notes. The GCS buckets stay untouched for 30 days as a
   rollback, then can be deleted.

## Rollback

Re-enable the Cloud Scheduler job; the Cloud Build YAML is in git history.
`web/data-manifest.json` accepts either host, so Vercel is unaffected either
way.
