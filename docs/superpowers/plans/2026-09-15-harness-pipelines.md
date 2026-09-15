# Harness Pipelines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Cloud Build scrape and CI pipelines with two Harness CI pipelines that keep state in Harness cache and a GitHub Release, with no GCP dependency.

**Architecture:** A stdlib-only script (`scripts/publish_data_release.py`) owns every interaction with the GitHub Release (restore fallback, tarball publish, manifest write, DB backup). Two v0 Harness pipeline YAML files under `.harness/` call the CLI and that script; cache steps carry `data/*.db` and `web/public/data/` between runs. Tests parse the YAML and exercise the script against a fake HTTP layer.

**Tech Stack:** Python 3.12 (stdlib urllib/tarfile/hashlib), pytest, pyyaml (test group only), Harness CI v0 YAML on Harness Cloud, Harness MCP tools for apply.

**Spec:** `docs/superpowers/specs/2026-09-15-harness-pipelines-design.md`

## Global Constraints

- Harness account `jKE_O7LaTmaV8BCJt1ic7w`, org `default`, project `default_project`; codebase connector `account.Github_OAuth_1784959546725`; token secret `account.harnessoauthaccesstoken_github_1784959546428`. No new secrets.
- Pipelines are v0 YAML; identifiers are literal strings.
- Cron `0 6 * * *` UTC; runner `Linux/Amd64`, `runtime: Cloud`, default size.
- Release tag `data`, prerelease; keep the newest 8 `data-*.tar.gz` assets; DB backup asset name `dbs.tar.gz`.
- `web/data-manifest.json` format is unchanged: `{"version":1,"archives":[{"url","sha256","created_at"}]}`.
- No em dashes anywhere. Ruff clean (`uv run ruff check . && uv run ruff format .`). Tests via `.venv/bin/python -m pytest tests/ -q`.

---

### Task 1: Release client and restore/publish script

**Files:**
- Create: `scripts/publish_data_release.py`
- Create: `tests/test_publish_data_release.py`
- Modify: `pyproject.toml` (add `pyyaml>=6` to the `test` group for Task 2; run `uv lock`)

**Interfaces:**
- Produces: `class GitHubRelease(repo: str, tag: str, token: str, http: Http)` with `ensure() -> dict`, `assets() -> list[dict]`, `upload_asset(path: Path, name: str) -> dict`, `delete_asset(asset_id: int) -> None`, `download_asset(name: str, dest: Path) -> bool`.
- Produces: `restore(release, data_dir, export_dir, fallback_url, http) -> list[str]` (what was restored).
- Produces: `publish(release, export_dir, data_dir, manifest_path, now, keep=8) -> dict` (manifest).
- Produces: `upload_dbs(release, data_dir) -> dict`.
- CLI: `python scripts/publish_data_release.py {restore|publish|upload-dbs}`; env `GITHUB_TOKEN`, `GITHUB_REPO` (default `dtsong/tcg-scout`), `DATA_RELEASE_TAG` (default `data`).

- [x] **Step 1: Write the failing tests** (fake `Http` records requests; release JSON fixtures)

Tests: `ensure` creates the release when GET 404s and marks `prerelease: true`; `publish` uploads `data-<ts>.tar.gz` and `dbs.tar.gz`, deletes the oldest data assets beyond 8, writes the manifest with the browser download URL and the sha256 of the tarball on disk; `restore` skips when both dirs are populated, downloads `dbs.tar.gz` when `data/` has no DBs, downloads the newest `data-*.tar.gz` when `formats.json` is missing, and falls back to `fallback_url` when the release has no data asset; the token never appears in any URL.

- [x] **Step 2: Run tests, expect ImportError**
- [x] **Step 3: Implement the script** (stdlib only; `Http` protocol with `request(method, url, data, headers) -> (status, body)`; upload via `uploads.github.com` with `Content-Type: application/gzip`; asset ordering by name, which sorts by timestamp)
- [x] **Step 4: Tests pass; ruff clean**
- [x] **Step 5: Commit** `feat: GitHub Release publisher for exported data and DB backups`

### Task 2: Scrape pipeline YAML, trigger, and guards

**Files:**
- Create: `.harness/pipelines/scrape.yaml`, `.harness/triggers/scrape-cron.yaml`
- Create: `tests/test_harness_pipelines.py`
- Modify: `cli.py` `formats_list` (add `--region` filter so the pipeline can select JP active formats)

**Interfaces:**
- Consumes: `scout formats-list --status active --region jp`, `python scripts/publish_data_release.py restore|publish`.

- [x] **Step 1: Failing tests**: YAML parses; `pipeline.identifier == "scout_scrape"`; steps in order `RestoreCache x2, Run bootstrap, Run scrape, Run validate, SaveCache x2, Run publish`; both SaveCache `override: true`; scrape command contains `formats-list --status active --region jp` and no literal format slug; publish step guards on `main`; trigger cron is `0 6 * * *` and pins branch `main`; `formats-list --region jp` returns only JP slugs.
- [x] **Step 2: Run, expect failures**
- [x] **Step 3: Write YAML and the CLI option**
- [x] **Step 4: Tests pass; ruff clean**
- [x] **Step 5: Commit** `ci: Harness scrape pipeline and daily trigger`

### Task 3: Verify pipeline YAML and push trigger

**Files:**
- Create: `.harness/pipelines/verify.yaml`, `.harness/triggers/verify-on-push.yaml`
- Modify: `tests/test_harness_pipelines.py`

- [x] **Step 1: Failing tests**: identifier `scout_verify`; python step runs `ruff check`, `ruff format --check`, `pytest`; web step runs `npm ci`, `tsc --noEmit`, `eslint . --quiet`, `vitest run`; no `playwright` anywhere; trigger is Github Push to `main` with `autoAbortPreviousExecutions: true`.
- [x] **Step 2: Run, expect failures**
- [x] **Step 3: Write YAML** (Node 22 curl+tar recipe from vgc-trainerlab)
- [x] **Step 4: Tests pass**
- [x] **Step 5: Commit** `ci: Harness verify pipeline and push trigger`

### Task 4: Apply to Harness and run

- [x] **Step 1:** `harness_create` pipeline `scout_scrape` and `scout_verify` from the YAML files; `harness_create` both triggers.
- [x] **Step 2:** `harness_execute` `scout_verify` on `main`; confirm success.
- [x] **Step 3:** `harness_execute` `scout_scrape` on `main`; confirm the `data` release exists, the manifest commit landed, and Vercel redeployed (check `scout.trainerlab.io/data/formats.json` matches).
- [x] **Step 4:** Record execution URLs and durations in the handover.

### Task 5: Cutover documentation and Cloud Build removal

**Files:**
- Delete: `cloudbuild-scrape.yaml`, `cloudbuild-decklists.yaml`, `cloudbuild-ci.yaml`
- Modify: `tests/test_jp_event_metadata.py` (remove the substitutions guard class), `CLAUDE.md` (Databases and Data Flow sections), `web/scripts/prebuild.mjs` (error text), `memory/HANDOVER-*.md`

- [x] **Step 1:** Edit files; run full pytest and `cd web && npm test`.
- [x] **Step 2:** Commit `ci: retire Cloud Build in favour of Harness`.
- [x] **Step 3:** Owner actions listed in the final message: `gcloud auth login`; seed DBs to the release; pause then delete Cloud Scheduler job `tcg-scout-scrape` and the Cloud Build triggers; the `functions/poll_tournaments` Cloud Function still references `cloudbuild-scrape.yaml` and must be disabled or retargeted.
