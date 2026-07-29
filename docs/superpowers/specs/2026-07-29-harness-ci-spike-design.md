# Harness CI Spike Design

Date: 2026-07-29
Status: Approved, pending implementation plan

## Motivation

A Harness Cloud port was requested and deferred in the 2026-07-26 session
(`memory/HANDOVER-2026-07-26-1835.md:113`). This spec revisits it.

The original motivation does not survive contact with the facts. Two findings,
established before any design work:

1. **`dtsong/tcg-scout` is a public repository.** GitHub Actions is free and
   unlimited on public repos. The comment in `.github/workflows/scrape.yml:3`
   ("Disabled while GitHub Actions minutes are exhausted") is stale and should
   not be cited as a reason to move CI anywhere.

2. **Harness Free is a smaller budget than what the project already has for
   free.** 2000 credits per month, no rollover. Linux Medium (8 cores, the
   default resource class) burns 2 credits per minute, so the allowance is
   1000 build-minutes per month. Cache storage caps at 2 GB account-wide.

So this is not a cost-saving migration. It is an evaluation, undertaken on its
merits, of whether Harness is a platform worth adopting later. The spike is
sized to answer that at roughly 1% of the monthly credit allowance.

## Credit arithmetic

Measured against real runs, not estimates. Source: GitHub Actions run
`30336021619`, 2026-07-28, commit "test: verify ANALYZE is called during init_db
with seeded data".

| Leg | Measured duration | Billable credits/run |
|---|---|---|
| `python` (uv sync, ruff lint, ruff format, 888 tests) | 21s | 2 |
| `frontend` (npm ci, tsc, eslint, vitest, build, 2 E2E suites) | 6m 09s | 14 |
| `frontend` at `cloudbuild-ci.yaml` parity (+`test:export`, +`e2e:assets`, +`e2e:performance`) | est. ~10m | ~20 |

Full-parity CI is therefore ~22 credits/run, or **~90 runs/month** against the
2000-credit ceiling.

Observed run volume on `ci.yml`: **174 runs in June 2026**, 19 in July. June is
renovate-driven. A renovate-heavy month is roughly 2x over the free ceiling, and
unused credits do not roll over to absorb a quiet month.

The frontend leg is 95% of that spend. The python leg is effectively free.

### Consequence for the data pipelines

A 45-minute daily scrape costs `45 x 2 x 30 = 2,700 credits/month`, exceeding
the entire monthly allowance before any CI runs at all. `cloudbuild-scrape.yaml`
and `cloudbuild-decklists.yaml` are **structurally impossible on Harness Free**,
independent of whether they would work technically. This is a firmer conclusion
than the handover's note that Harness "would hit its own wall" on the timeout:
the wall is billing, not runtime.

### Consequence for caching

`web/node_modules` is 598 MB against a 2 GB account-wide cap. Adding the npm and
uv caches lands near 1.3 GB. It fits, with no room for a second project. Not a
constraint for this spike (python only) but a hard limit on any later expansion.

## Scope

Port **the python leg only**. One CI stage, ~2 credits per run, ~1000 runs of
headroom per month.

This is the cheapest workload in the repo that still exercises everything worth
evaluating: the GitHub connector, Git Experience, Harness Cloud runners, custom
caching, JUnit reporting, and the execution UI.

### Explicitly not in scope

- The frontend leg and its four Playwright suites
- `cloudbuild-scrape.yaml`, `cloudbuild-decklists.yaml`
- Vercel deploy orchestration
- The `smoke-test.yml` and `freshness-check.yml` workflows
- Removing or disabling any existing CI

`.github/workflows/ci.yml` and both Cloud Build pipelines continue running
untouched throughout. The spike is purely additive.

## Harness objects

| Object | Identifier | Notes |
|---|---|---|
| Project | `tcg_scout` (org `default`) | Isolates the spike. `harness delete project tcg_scout` reverses everything on a no-go. The existing `default_project` is left alone. |
| Secret | `github_pat` | Classic PAT, scopes `repo` + `admin:repo_hook`, stored in the built-in Harness secret manager (`harnessSecretManager`, already present). |
| Connector | `github_tcg_scout` | Account-level, HTTP auth via `github_pat`, **API access enabled**. Required for both codebase clone and Git Experience. |
| Pipeline | `python_ci` | **Remote**, stored at `.harness/python-ci.yaml` on branch `main`. |
| Trigger | `on_pr_and_main` | PR opened/reopened/updated, plus push to `main`. Affordable at 2 credits/run. |

Account context: `jKE_O7LaTmaV8BCJt1ic7w` (`xdtsong`), org `default`. Verified
2026-07-29 to contain 1 project, 0 pipelines, 0 delegates, 0 secrets, and only
the built-in GCP KMS secret manager. Clean slate.

**No Docker registry connector is required.** uv is installed with the official
shell installer rather than pulling `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`,
which eliminates a connector and an anonymous-pull configuration from the setup.

## Pipeline definition

One CI stage on Harness Cloud, `platform: {os: Linux, arch: Amd64}`,
`runtime: {type: Cloud, spec: {}}`. Default Medium resource class; upsizing is
not viable on free tier (Large is 10 credits/min, a 5x multiplier).

Steps mirror `.github/workflows/ci.yml:12-36`:

1. **Install uv** — `curl -LsSf https://astral.sh/uv/install.sh | sh`.
   uv reads `.python-version` and provisions Python 3.12 itself.
2. **Sync deps** — `uv sync --locked`. `--locked` fails if `uv.lock` is stale
   against `pyproject.toml`, matching existing CI behavior.
3. **Ruff lint** — `uv run ruff check .`
4. **Ruff format** — `uv run ruff format --check .`
5. **Unit tests** — `uv run pytest tests/ -m "not integration" --junitxml=unit.xml`
6. **Integration tests** — `uv run pytest tests/ -m integration --junitxml=integration.xml`

Steps 5 and 6 declare `spec.reports.type: JUnit` so failures render natively in
the Harness execution view. Neither Cloud Build nor the current Actions workflow
surfaces structured test results, so this is a genuine capability difference
worth recording in the evaluation.

### Caching

Cache Intelligence auto-detects Maven, Gradle, Bazel, Go, yarn, and .NET. It has
**no uv support**, so caching must be configured explicitly on `stage.spec`:

```yaml
caching:
  enabled: true
  key: uv-{{ checksum "uv.lock" }}
  paths:
    - "~/.cache/uv"
sharedPaths:
  - ~/.cache/uv
```

`UV_CACHE_DIR` is set as a stage variable pinned to the **same literal value** as
`caching.paths` and `sharedPaths`, since uv's default location differs across
platforms and a mismatch silently caches nothing. All three must agree.

Two open questions to resolve on first run, both cheap to test:

- **`~` vs absolute path.** The Harness python guide's example uses an absolute
  `/root/.cache`, not `~`. Whether Harness Cloud steps run as root, and whether
  `~` expands inside `caching.paths`, is unverified. Resolve by echoing
  `whoami` and `echo $HOME` in step 1 of the cold run, then pin all three
  settings to the resulting absolute path.
- **Cache key granularity.** `uv-{{ checksum "uv.lock" }}` invalidates on every
  dependency bump. Given renovate's volume that means frequent cold runs, which
  is correct behavior but worth noting when reading the warm/cold delta.

Cache retention is 15 days, resetting on each update.

This is the least certain part of the design and is expected to need a second
pass. Verifying it is one of the four go/no-go criteria precisely because it is
unproven.

## Go/no-go criteria

| Criterion | Target | Interpretation |
|---|---|---|
| Parity | ruff clean, 888 tests pass | Hard requirement. Nothing else counts if this fails. |
| Credits | measured <=4 credits/run | Validates the ~90-runs/month projection for any future full port. |
| Caching | warm-run `uv sync` faster than cold | Tests whether the custom uv paths above actually work. |
| Wall-clock | compared against 21s on Actions | **Harness is expected to lose this.** |

On wall-clock: the python job takes 21 seconds. VM provisioning alone will
plausibly be 30-60s, so Harness will likely be slower in absolute terms on a job
this short. That is a measurement, not a failure. The transferable number is
**post-provisioning step time**, which is what would matter if the frontend leg
ever moved. Record both, and do not treat the absolute comparison as
disqualifying.

## Measurement procedure

Run in this order, recording results in the eventual handover:

1. Execute manually, cold cache. Record per-step and total wall-clock, plus
   provisioning overhead as a separate line.
2. Execute again on the same commit. Record the warm-cache delta on the
   `uv sync` step specifically.
3. Read account credit consumption after both runs. Divide by 2 for per-run cost.
4. Compare post-provisioning step time against the Actions baseline of 21s
   (per-step timings captured in this spec's Credit Arithmetic section).

## Risks

- **uv is likely not preinstalled** on the Harness Cloud Linux image. Step 1
  exists to handle this; if the installer is blocked or slow, fall back to the
  `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` image, which reintroduces the
  registry connector.
- **Custom uv cache paths are unproven.** Cache Intelligence documents custom
  keys and paths but not uv specifically. Expect iteration.
- **888 tests on a clean runner** may surface fixture assumptions that a warm
  local environment hides. Note that `uv run pytest` is broken in the local dev
  environment (`rtk: Failed to spawn process`, per the 2026-07-26 handover), so
  the exact command cannot be pre-validated locally. Use
  `.venv/bin/python -m pytest tests/ -q` locally; the Harness runner is clean and
  should not reproduce the local failure.
- **Provisioning overhead dominates a 21s job**, which makes the wall-clock
  criterion structurally unflattering. Anticipated above; not a design flaw.

## Reversal

On a no-go verdict:

1. `harness delete project tcg_scout`
2. Delete the account-level `github_tcg_scout` connector and `github_pat` secret
3. `git rm .harness/python-ci.yaml`
4. Revoke the PAT at github.com/settings/tokens
5. Record the verdict and the credit arithmetic in a handover, so this is not
   re-litigated a third time

Nothing else in the repo is touched, so there is no other rollback surface.
