# open_placements Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `open_placements` and the archetype export path fast enough that the scrape pipeline finishes well inside its timeout, unblocking Play LimitlessTCG ingestion.

**Architecture:** The root cause is not the view definition. **The database has no user-created indexes at all**, only SQLite autoindexes from PRIMARY KEY and UNIQUE constraints. The correlated `NOT EXISTS` in `open_placements` therefore drives a full `SCAN t2` for every one of 18,571 placement rows. Adding four indexes to `SCHEMA` in `db.py` and running `ANALYZE` converts those scans to index searches. No view rewrite and no materialization are required.

**Tech Stack:** Python 3.12, SQLite (WAL), pytest, uv, ruff.

## Global Constraints

- Run tests with `.venv/bin/python -m pytest tests/ -q`. **`uv run pytest` is broken in this environment** (`rtk: Failed to spawn process`).
- Lint and format with `uv run ruff check . && uv run ruff format .` before every commit.
- No em dashes anywhere: code, comments, docs, commit messages.
- `init_db` already runs `DROP VIEW IF EXISTS` then `executescript(SCHEMA)`, so `CREATE INDEX IF NOT EXISTS` statements placed in `SCHEMA` apply to both new and existing databases with no separate migration branch.
- Do not modify the `open_placements` or `open_tournaments` view definitions. Their dedup semantics are correct; only their access paths are slow. Changing them would alter row counts.

## Measured baseline

Taken on `data/ninja-spinner.db` (1,260 tournaments, 18,571 placements, 104,043 decklist_cards):

| Query | Before | After indexes |
|---|---|---|
| `SELECT COUNT(*) FROM open_placements` | 176.5 ms | 0.6 ms |
| `SELECT COUNT(*) FROM open_tournaments` | 10.9 ms | 0.3 ms |
| Per-archetype export query set | 75.4 ms | 5.8 ms |

Plan before: `SCAN p` then `CORRELATED SCALAR SUBQUERY` then `SCAN t2`.
Plan after: `SEARCH t2 USING INDEX idx_tournaments_date_div` and `SEARCH p USING COVERING INDEX idx_placements_tournament`.

Row counts are identical before and after (`open_placements` = 8,753; `open_tournaments` = 558). Task 1 locks that invariant into a test.

## File Structure

| File | Responsibility |
|---|---|
| `db.py` | Add four `CREATE INDEX IF NOT EXISTS` statements to `SCHEMA`; run `ANALYZE` at the end of `init_db`. |
| `tests/test_db_indexes.py` (new) | Assert the indexes exist after `init_db`, assert the query planner uses them, and assert view row counts are unchanged by indexing. |
| `scripts/bench_open_placements.py` (new) | Reproducible benchmark against any database file, used to verify against production data in Task 4. |

---

### Task 1: Lock the view row counts before touching anything

Indexes must not change results. This test is the safety net for Tasks 2 and 3, so it lands first and must pass against the current unindexed schema.

**Files:**
- Test: `tests/test_db_indexes.py` (create)

**Interfaces:**
- Consumes: the `db` fixture from `tests/conftest.py:18`, which yields an in-memory `sqlite3.Connection` with `init_db` already applied and seeded rows.
- Produces: nothing consumed by later tasks. This is a regression guard.

- [ ] **Step 1: Write the row-count invariant test**

Create `tests/test_db_indexes.py`:

```python
"""Index coverage for the dedup views.

The database shipped with no user-created indexes, so `open_placements` drove a
full scan of `tournaments` for every placement row. These tests assert the
indexes exist, that the planner uses them, and that adding them did not change
what the views return.
"""

import sqlite3

from db import SCHEMA, init_db

EXPECTED_INDEXES = {
    "idx_placements_tournament",
    "idx_tournaments_date_div",
    "idx_placements_dedup",
    "idx_decklist_cards_card",
}


def _index_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {r[0] for r in rows}


class TestViewResultsUnchangedByIndexes:
    """Indexes are an access-path change only. Row counts must be identical."""

    @staticmethod
    def _counts(conn: sqlite3.Connection) -> tuple[int, int]:
        placements = conn.execute("SELECT COUNT(*) FROM open_placements").fetchone()[0]
        tournaments = conn.execute("SELECT COUNT(*) FROM open_tournaments").fetchone()[0]
        return placements, tournaments

    def test_dropping_indexes_does_not_change_view_output(self, db):
        with_indexes = self._counts(db)
        for name in _index_names(db):
            db.execute(f"DROP INDEX {name}")
        without_indexes = self._counts(db)
        assert with_indexes == without_indexes
```

- [ ] **Step 2: Run it and confirm it passes on the current schema**

Run: `.venv/bin/python -m pytest tests/test_db_indexes.py -v`

Expected: PASS. There are currently no user indexes, so `_index_names` returns an empty set, the drop loop is a no-op, and both counts match trivially. It becomes a real assertion once Task 2 adds the indexes.

- [ ] **Step 3: Commit**

```bash
git add tests/test_db_indexes.py
git commit -m "test: lock open_placements view row counts before indexing"
```

---

### Task 2: Add the indexes to the schema

**Files:**
- Modify: `db.py` (append to the `SCHEMA` string, immediately before the closing `"""`)
- Test: `tests/test_db_indexes.py`

**Interfaces:**
- Consumes: `db.SCHEMA`, `db.init_db` from Task 1's imports.
- Produces: four named indexes that Task 3 asserts the planner uses, and that the Play ingestion plan relies on for its own volume.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_db_indexes.py`:

```python
class TestIndexesExist:
    def test_init_db_creates_expected_indexes(self, db):
        assert EXPECTED_INDEXES <= _index_names(db)

    def test_indexes_are_declared_in_schema_not_ad_hoc(self):
        """Indexes must live in SCHEMA so existing databases pick them up too."""
        for name in EXPECTED_INDEXES:
            assert f"CREATE INDEX IF NOT EXISTS {name}" in SCHEMA
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_db_indexes.py::TestIndexesExist -v`

Expected: FAIL. `test_init_db_creates_expected_indexes` fails because `_index_names(db)` is empty; `test_indexes_are_declared_in_schema_not_ad_hoc` fails because the strings are absent from `SCHEMA`.

- [ ] **Step 3: Add the indexes to SCHEMA**

In `db.py`, at the very end of the `SCHEMA` string (after the `placement_players` table definition, before the closing `"""`), add:

```sql

-- Indexes.
--
-- The dedup views (`open_placements`, `open_tournaments`) run a correlated
-- NOT EXISTS against `tournaments`. Without these, SQLite scans all of
-- `tournaments` once per placement row, which is what pushed the scrape
-- pipeline past its build timeout.
CREATE INDEX IF NOT EXISTS idx_placements_tournament
    ON placements(tournament_id);
CREATE INDEX IF NOT EXISTS idx_tournaments_date_div
    ON tournaments(date, division);
CREATE INDEX IF NOT EXISTS idx_placements_dedup
    ON placements(standing, archetype, player_name);
CREATE INDEX IF NOT EXISTS idx_decklist_cards_card
    ON decklist_cards(card_id);
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_db_indexes.py -v`

Expected: PASS, including `test_dropping_indexes_does_not_change_view_output` from Task 1, which is now doing real work because there are indexes to drop.

- [ ] **Step 5: Run the full suite to check nothing regressed**

Run: `.venv/bin/python -m pytest tests/ -q`

Expected: all tests pass (888 before this work started, plus the new ones).

- [ ] **Step 6: Lint, format, commit**

```bash
uv run ruff check . && uv run ruff format .
git add db.py tests/test_db_indexes.py
git commit -m "perf: index the columns the dedup views correlate on

The schema shipped with no user-created indexes, so open_placements drove a
full scan of tournaments for every one of 18,571 placement rows. Measured on
ninja-spinner.db: COUNT(*) over open_placements drops from 176.5ms to 0.6ms,
and the per-archetype export query set from 75.4ms to 5.8ms."
```

---

### Task 3: Run ANALYZE so the planner has statistics

Indexes alone let SQLite use them; `ANALYZE` populates `sqlite_stat1` so it chooses well between them. This is cheap and runs once per `init_db`.

**Files:**
- Modify: `db.py` (`init_db`, at the end, immediately before the existing `conn.commit()`)
- Test: `tests/test_db_indexes.py`

**Interfaces:**
- Consumes: the indexes created in Task 2.
- Produces: `sqlite_stat1` rows; no Python-level interface.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_db_indexes.py`:

```python
class TestPlannerUsesIndexes:
    def test_open_placements_searches_rather_than_scans_tournaments(self, db):
        plan = db.execute(
            "EXPLAIN QUERY PLAN SELECT COUNT(*) FROM open_placements"
        ).fetchall()
        detail = " | ".join(row[3] for row in plan)
        assert "SCAN t2" not in detail, f"planner still scans tournaments: {detail}"
        assert "idx_tournaments_date_div" in detail, detail

    def test_init_db_populates_planner_statistics(self, db):
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_stat1'"
        ).fetchall()
        assert tables, "ANALYZE was never run, so the planner has no statistics"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_db_indexes.py::TestPlannerUsesIndexes -v`

Expected: `test_init_db_populates_planner_statistics` FAILS because `sqlite_stat1` does not exist. `test_open_placements_searches_rather_than_scans_tournaments` may already pass after Task 2; that is fine, it guards against regression.

- [ ] **Step 3: Add ANALYZE to init_db**

In `db.py`, inside `init_db`, immediately before the existing `conn.commit()` at the end of the function:

```python
    # Populate sqlite_stat1 so the planner chooses between the dedup indexes
    # rather than guessing. Cheap at our row counts and re-run on every init.
    conn.execute("ANALYZE")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_db_indexes.py -v`

Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest tests/ -q`

Expected: all pass.

- [ ] **Step 6: Lint, format, commit**

```bash
uv run ruff check . && uv run ruff format .
git add db.py tests/test_db_indexes.py
git commit -m "perf: run ANALYZE in init_db so the planner has statistics"
```

---

### Task 4: Benchmark script and production verification

Local numbers understate the production gap. `data/ninja-spinner.db` has an unpopulated `cards` table (0 JP to EN mappings), so `compute_archetype_evolution` short-circuits locally and never runs the code path that dominated the Cloud Build log. This task produces a reusable measurement rather than a claim.

**Files:**
- Create: `scripts/bench_open_placements.py`
- Test: manual run, plus one unit test for the timing helper

**Interfaces:**
- Consumes: nothing from earlier tasks except the indexes being present.
- Produces: `bench(db_path: str) -> dict[str, float]` returning milliseconds keyed by query label. Not imported by application code.

- [ ] **Step 1: Write the benchmark script**

Create `scripts/bench_open_placements.py`:

```python
"""Benchmark the dedup views and the per-archetype export query set.

Usage:
    .venv/bin/python scripts/bench_open_placements.py data/ninja-spinner.db

Run against a production-sized database before and after an index change.
Local databases are not representative: `data/ninja-spinner.db` has an empty
`cards` table, so parts of the export short-circuit that do not short-circuit
in production.
"""

import sqlite3
import sys
import time

ARCHETYPE_QUERIES = (
    ("archetype_ids", "SELECT p.id FROM open_placements p WHERE p.archetype = ?"),
    (
        "archetype_cards",
        """
        SELECT dc.card_id, dc.card_name, COUNT(*) AS n, SUM(dc.count) AS total
        FROM decklist_cards dc
        WHERE dc.placement_id IN (
            SELECT p.id FROM open_placements p WHERE p.archetype = ?
        )
        GROUP BY dc.card_id, dc.card_name
        """,
    ),
    ("archetype_avg", "SELECT AVG(standing) FROM open_placements WHERE archetype = ?"),
)


def _time_ms(fn, repeats: int = 3) -> float:
    """Median-free mean of `repeats` runs, in milliseconds."""
    start = time.perf_counter()
    for _ in range(repeats):
        fn()
    return (time.perf_counter() - start) / repeats * 1000


def bench(db_path: str) -> dict[str, float]:
    conn = sqlite3.connect(db_path)
    results: dict[str, float] = {}

    results["open_placements_count"] = _time_ms(
        lambda: conn.execute("SELECT COUNT(*) FROM open_placements").fetchone()
    )
    results["open_tournaments_count"] = _time_ms(
        lambda: conn.execute("SELECT COUNT(*) FROM open_tournaments").fetchone()
    )

    row = conn.execute(
        "SELECT archetype FROM placements GROUP BY archetype ORDER BY COUNT(*) DESC LIMIT 1"
    ).fetchone()
    if row:
        archetype = row[0]
        for label, sql in ARCHETYPE_QUERIES:
            results[label] = _time_ms(lambda s=sql: conn.execute(s, (archetype,)).fetchall())

    conn.close()
    return results


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    print(f"Benchmarking {path}")
    for label, ms in bench(path).items():
        print(f"  {label:26s} {ms:9.2f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Write a test for the timing helper**

Create `tests/test_bench_open_placements.py`:

```python
"""The benchmark script is operational tooling, but its helpers still get tested."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from bench_open_placements import _time_ms, bench  # noqa: E402


def test_time_ms_returns_positive_milliseconds():
    calls = []
    assert _time_ms(lambda: calls.append(1), repeats=3) >= 0.0
    assert len(calls) == 3


def test_bench_reports_view_timings(tmp_path):
    import sqlite3

    from db import init_db

    db_path = tmp_path / "bench.db"
    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.execute(
        "INSERT INTO tournaments (id, name, date, player_count, division) "
        "VALUES ('play-1', 'Test Cup', '2026-07-01', 32, 'open')"
    )
    conn.execute(
        "INSERT INTO placements (tournament_id, standing, player_name, archetype) "
        "VALUES ('play-1', 1, 'tester', 'Wailord')"
    )
    conn.commit()
    conn.close()

    results = bench(str(db_path))
    assert "open_placements_count" in results
    assert "archetype_ids" in results
    assert all(value >= 0.0 for value in results.values())
```

- [ ] **Step 3: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_bench_open_placements.py -v`

Expected: PASS.

- [ ] **Step 4: Run the benchmark against the local database**

Run: `.venv/bin/python scripts/bench_open_placements.py data/ninja-spinner.db`

Expected: `open_placements_count` under 5 ms. If it is still in the 100 ms range, the indexes did not land; stop and re-check Task 2.

- [ ] **Step 5: Verify against production data**

Download the production database and benchmark it. This is the step that actually proves the timeout is fixed, because local data does not exercise every export path.

```bash
CLOUDSDK_CORE_ACCOUNT=daniel@appraisehq.ai gsutil cp \
  gs://tcg-scout-cache/scout-dbs/ninja-spinner.db /tmp/prod-ninja-spinner.db
.venv/bin/python scripts/bench_open_placements.py /tmp/prod-ninja-spinner.db
```

Note that the cached copy predates the indexes, so this measures the *before* state. Apply the fix and re-measure:

```bash
.venv/bin/python -c "
import sqlite3
from db import init_db
conn = sqlite3.connect('/tmp/prod-ninja-spinner.db')
init_db(conn)
conn.close()
"
.venv/bin/python scripts/bench_open_placements.py /tmp/prod-ninja-spinner.db
```

Record both numbers in the commit message. **If the production `open_placements_count` does not drop below roughly 5 ms, do not proceed to Play ingestion.** Investigate instead: the remaining cost is somewhere other than the view, and the ingestion plan's volume assumptions no longer hold.

- [ ] **Step 6: Lint, format, commit**

```bash
uv run ruff check . && uv run ruff format .
git add scripts/bench_open_placements.py tests/test_bench_open_placements.py
git commit -m "perf: add reproducible benchmark for the dedup views

Records production before/after numbers so the timeout fix is verified against
representative data rather than the local database, whose empty cards table
short-circuits part of the export path."
```

---

### Task 5: Restore the pipeline timeout and confirm a real build

The timeout was raised from 2700s to 7200s as headroom for one-time frozen-format seeding. Once seeding has happened and the indexes are in, the steady-state build should be far faster than either number.

**Files:**
- Modify: `cloudbuild-scrape.yaml:200` (the `timeout` key)

**Interfaces:**
- Consumes: nothing. This is a configuration change gated on observed build times.

- [ ] **Step 1: Push and let one full build run**

Do not change the timeout yet. Push the index work and let the scheduled `tcg-scout-scrape` trigger fire once with `timeout: 7200s` still in place, so a slow first run cannot fail.

```bash
git push origin main
```

- [ ] **Step 2: Read the actual step durations**

```bash
CLOUDSDK_CORE_ACCOUNT=daniel@appraisehq.ai gcloud builds list \
  --project=trainerlab-prod --region=us-central1 --limit=3 \
  --format='table(id,status,createTime,duration)'
```

Expected: `SUCCESS`, with total duration well under 2700s. Record the duration.

- [ ] **Step 3: Lower the timeout to a value with real headroom**

Only after a successful build. Set `timeout` in `cloudbuild-scrape.yaml` to roughly three times the observed steady-state duration, rounded up, and replace the stale comment above it:

```yaml
# Steady-state runs restore frozen snapshots and scrape only active formats.
# Sized at roughly 3x the observed steady-state duration.
timeout: 2700s
```

- [ ] **Step 4: Verify the substitution drift guard still passes**

Run: `.venv/bin/python -m pytest tests/test_jp_event_metadata.py -v`

Expected: PASS. `TestCloudBuildSubstitutionsMatchConfig` parses this file, so a malformed edit surfaces here.

- [ ] **Step 5: Commit**

```bash
git add cloudbuild-scrape.yaml
git commit -m "ci: restore scrape timeout now that the index fix landed"
```

---

## Self-Review

**Spec coverage.** The spec's Prerequisite section calls for materializing the view or indexing the correlated columns, reproduced against a production-sized database. Task 2 indexes, Task 3 adds statistics, Task 4 reproduces against production. Materialization is deliberately not implemented: the measured 201x from indexing alone makes it unnecessary complexity, and it would require invalidation logic on every ingest.

**Deliberate deviation from the spec.** The spec described the fix as "materialize the view or index the correlated columns" and framed the root cause as the `ff88fb4` view rewrite. Measurement shows the view rewrite was not the root cause. The schema never had any indexes; `ff88fb4` only made an already-unindexed correlated subquery more expensive. The fix is therefore narrower and safer than the spec anticipated, and the view definition is left untouched.

**Placeholder scan.** No TBDs. Task 5's timeout value is deliberately left to be derived from an observed build duration, with the derivation rule stated (3x observed, rounded up) rather than a guessed constant.

**Type consistency.** `bench(db_path: str) -> dict[str, float]` and `_time_ms(fn, repeats: int = 3) -> float` are used consistently in the script and its test. `EXPECTED_INDEXES` and `_index_names` are defined once in Task 1 and reused in Tasks 2 and 3 without renaming.
