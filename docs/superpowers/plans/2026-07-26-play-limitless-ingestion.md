# Play LimitlessTCG Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest online and grassroots tournament results from the Play LimitlessTCG JSON API into Scout, weighted by field size, with the data source visible everywhere it appears.

**Architecture:** A new `scraper/play_limitless.py` calls three public JSON endpoints, needing no API key and no browser. Standings responses carry full decklists inline, so there is no second fetch. Archetypes come from `deck.icons` through the existing sprite-filename derivation. Field size enters scoring through the `boost` parameter that `placement_weight` already accepts, so no new scoring plumbing is required.

**Tech Stack:** Python 3.12, httpx, SQLite, Click, pytest, ruff; TypeScript and Next.js 16 for the frontend types.

## Global Constraints

- **This plan is blocked.** `docs/superpowers/plans/2026-07-26-open-placements-performance.md` must ship first, and its Task 4 production verification must show `open_placements_count` below roughly 5 ms. This plan adds 15,000 to 30,000 placements; starting before the index fix reintroduces the build timeout.
- Run tests with `.venv/bin/python -m pytest tests/ -q`. **`uv run pytest` is broken in this environment.**
- Lint and format with `uv run ruff check . && uv run ruff format .` before every commit.
- No em dashes anywhere: code, comments, UI copy, docs, commit messages.
- Keep Python exports and `web/app/lib/types.ts` in sync. New TypeScript fields are **optional**, for backward compatibility with already-published JSON.
- API base URL: `https://play.limitlesstcg.com/api`. No API key. Honor rate limit response headers.
- Archetype slugs are lowercase with `[^a-z0-9]+` replaced by hyphens, via `analysis.shared.slugify`.

## Verified API facts

These were confirmed against the live API on 2026-07-26. Do not re-derive them.

| Endpoint | Notes |
|---|---|
| `GET /tournaments?game=PTCG&limit=&page=` | Returns `id`, `name`, `date` (ISO 8601 with `Z`), `format`, `players`, `organizerId`. Newest first. |
| `GET /tournaments/{id}/details` | Returns `decklists` (bool), `isOnline` (bool), `organizer`, `phases`. |
| `GET /tournaments/{id}/standings` | Returns `placing`, `name`, `player`, `country`, `record{wins,losses,ties}`, `deck{id,name,icons}`, `decklist{pokemon,trainer,energy}`. |

- `format` is only `STANDARD` or `CUSTOM`. It is **not** a rotation slug, so format assignment comes from the date window.
- When a tournament has `decklists: false`, every standing has `decklist: null` **and** `deck: {}`. Such events yield no archetype and are excluded.
- `deck.icons` holds bare stems such as `["wailord"]`. `analysis.archetype._FILENAME_RE` requires a `/name.png` shape, so URLs must be synthesized against `LIMITLESS_SPRITE_CDN`. Verified: `["charizard", "pidgeot"]` yields `"Charizard / Pidgeot"` and sprite key `"charizard-pidgeot"`.
- Decklist entries carry `set` and `number`, which compose into Scout's existing `card_id` convention `f"{set_code}-{card_number}"`.

## File Structure

| File | Responsibility |
|---|---|
| `config.py` | Caliber constants, Play API constants. |
| `analysis/shared.py` | `caliber_weight()`, pure function beside `placement_weight()`. |
| `analysis/meta.py` | Pass field size into `placement_weight` when computing weighted shares. |
| `reports/json_export.py` | Route the two direct `PLACEMENT_WEIGHTS` reads through `placement_weight`; emit `source` and `is_online`. |
| `db.py` | `source` and `is_online` columns plus migrations. |
| `scraper/play_limitless.py` (new) | API client, dataclasses, filtering, parsing, and `store_play_results`. |
| `cli.py` | `scrape-play` command. |
| `web/app/lib/types.ts` | Optional `source` and `isOnline` fields. |
| `tests/fixtures/play/*.json` (new) | Recorded API responses. |
| `tests/test_caliber_weight.py` (new) | Caliber curve, clamps, neutral cases. |
| `tests/test_play_limitless.py` (new) | Filtering, parsing, archetype, persistence, incrementality, dedup safety. |

**Sequencing note.** Caliber weighting (Tasks 1 to 3) lands *before* ingestion (Tasks 4 onward), even though ingestion is the motivating feature. Caliber changes historical tier assignments; shipping it alone makes that change attributable to one deploy. Shipping both together would make an unexpected tier shift ambiguous between the new scoring and the new data.

---

### Task 1: `caliber_weight` as a pure function

**Files:**
- Modify: `config.py` (after `PLACEMENT_WEIGHT_DEFAULT`, around line 168)
- Modify: `analysis/shared.py`
- Test: `tests/test_caliber_weight.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `analysis.shared.caliber_weight(player_count: int | None) -> float`, and the constants `config.CALIBER_REFERENCE_PLAYERS`, `config.CALIBER_MIN`, `config.CALIBER_MAX`, `config.MIN_TOURNAMENT_PLAYERS`. Tasks 2, 3, 4 and 5 all use these exact names.

- [ ] **Step 1: Write the failing test**

Create `tests/test_caliber_weight.py`:

```python
"""Field-size weighting.

PLACEMENT_WEIGHTS is calibrated to a 64-player City League, so a 64-player
event must score exactly as it did before caliber weighting existed.
"""

import pytest

from analysis.shared import caliber_weight, placement_weight
from config import CALIBER_MAX, CALIBER_MIN, CALIBER_REFERENCE_PLAYERS


class TestCaliberCurve:
    @pytest.mark.parametrize(
        ("players", "expected"),
        [
            (8, 0.35),
            (16, 0.50),
            (32, 0.71),
            (64, 1.00),
            (128, 1.41),
        ],
    )
    def test_curve_matches_the_published_table(self, players, expected):
        assert caliber_weight(players) == pytest.approx(expected, abs=0.01)

    def test_reference_field_is_exactly_neutral(self):
        assert caliber_weight(CALIBER_REFERENCE_PLAYERS) == 1.0

    def test_curve_is_monotonic(self):
        sizes = [8, 16, 32, 64, 128, 256, 512]
        weights = [caliber_weight(n) for n in sizes]
        assert weights == sorted(weights)


class TestCaliberClamps:
    def test_very_large_fields_clamp_to_max(self):
        assert caliber_weight(256) == CALIBER_MAX
        assert caliber_weight(5000) == CALIBER_MAX

    def test_tiny_fields_clamp_to_min(self):
        assert caliber_weight(1) == CALIBER_MIN


class TestCaliberNeutralCases:
    """Historical rows have no player_count. They must be left alone."""

    @pytest.mark.parametrize("value", [None, 0])
    def test_unknown_field_size_is_neutral(self, value):
        assert caliber_weight(value) == 1.0


class TestCaliberComposesWithPlacementWeight:
    def test_boost_parameter_carries_caliber(self):
        # 1st place is 3.0x; a 16-player field halves it.
        assert placement_weight(1, boost=caliber_weight(16)) == pytest.approx(1.5)

    def test_reference_field_leaves_placement_weight_untouched(self):
        assert placement_weight(1, boost=caliber_weight(64)) == placement_weight(1)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_caliber_weight.py -v`

Expected: FAIL with `ImportError: cannot import name 'caliber_weight' from 'analysis.shared'`.

- [ ] **Step 3: Add the constants to config.py**

In `config.py`, immediately after `PLACEMENT_WEIGHT_DEFAULT = 1.0`:

```python
# Field-size (caliber) weighting.
#
# PLACEMENT_WEIGHTS above is calibrated to a 64-player City League, so 64 is the
# neutral reference: an event that size scores exactly as it did before caliber
# weighting existed. Smaller fields are discounted, larger ones amplified, on a
# square-root curve so the effect is smooth rather than a cliff.
CALIBER_REFERENCE_PLAYERS = 64
CALIBER_MIN = 0.25
CALIBER_MAX = 2.0

# Below three Swiss rounds it is a pod, not a tournament. Not ingested at all.
MIN_TOURNAMENT_PLAYERS = 8
```

- [ ] **Step 4: Implement `caliber_weight`**

In `analysis/shared.py`, change the import line and add the function after `placement_weight`:

```python
from math import sqrt

from config import (
    CALIBER_MAX,
    CALIBER_MIN,
    CALIBER_REFERENCE_PLAYERS,
    PLACEMENT_WEIGHT_DEFAULT,
    PLACEMENT_WEIGHTS,
)
```

```python
def caliber_weight(player_count: int | None) -> float:
    """Scale a placement by the size of the field it was earned in.

    Returns 1.0 at CALIBER_REFERENCE_PLAYERS, and 1.0 for an unknown field size
    so historical rows without a player_count are unaffected.
    """
    if not player_count:
        return 1.0
    raw = sqrt(player_count / CALIBER_REFERENCE_PLAYERS)
    return min(CALIBER_MAX, max(CALIBER_MIN, raw))
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_caliber_weight.py -v`

Expected: PASS, 11 tests.

- [ ] **Step 6: Lint, format, commit**

```bash
uv run ruff check . && uv run ruff format .
git add config.py analysis/shared.py tests/test_caliber_weight.py
git commit -m "feat: add field-size caliber weighting

Anchored at 64 players because PLACEMENT_WEIGHTS is calibrated to a 64-player
City League, so events that size score identically to before. Unknown field
sizes return 1.0 so historical rows are unaffected."
```

---

### Task 2: Route every weight consumer through `placement_weight`

`reports/json_export.py` reads `PLACEMENT_WEIGHTS` directly in two places, so caliber would silently bypass them. Fix that before wiring caliber in, or the bug ships invisibly.

**Files:**
- Modify: `reports/json_export.py:302`, `reports/json_export.py:480`, and the import block at `reports/json_export.py:48-49`
- Test: `tests/test_weight_consumers.py` (create)

**Interfaces:**
- Consumes: `analysis.shared.placement_weight` from Task 1.
- Produces: no new symbols. Removes `PLACEMENT_WEIGHTS` and `PLACEMENT_WEIGHT_DEFAULT` from `json_export`'s imports.

- [ ] **Step 1: Write the failing test**

Create `tests/test_weight_consumers.py`:

```python
"""Every weighted-scoring path must go through placement_weight().

Reading PLACEMENT_WEIGHTS directly bypasses the caliber boost, which is the
kind of bug that produces plausible-looking but wrong numbers.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARDED_MODULES = ["reports/json_export.py", "analysis/meta.py"]


def _names_used(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}


class TestNoDirectWeightTableAccess:
    def test_modules_do_not_read_the_weight_table_directly(self):
        offenders = []
        for rel in GUARDED_MODULES:
            used = _names_used(REPO_ROOT / rel)
            if "PLACEMENT_WEIGHTS" in used or "PLACEMENT_WEIGHT_DEFAULT" in used:
                offenders.append(rel)
        assert not offenders, (
            f"{offenders} read PLACEMENT_WEIGHTS directly; call placement_weight() "
            "so the caliber boost is applied"
        )
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_weight_consumers.py -v`

Expected: FAIL, listing `reports/json_export.py`.

- [ ] **Step 3: Replace the direct reads**

In `reports/json_export.py`, remove `PLACEMENT_WEIGHT_DEFAULT` and `PLACEMENT_WEIGHTS` from the `config` import block at lines 48 and 49, and ensure `placement_weight` is imported from `analysis.shared`.

At line 302, replace:

```python
        weight = PLACEMENT_WEIGHTS.get(standing, PLACEMENT_WEIGHT_DEFAULT)
```

with:

```python
        weight = placement_weight(standing)
```

At line 480, replace:

```python
        weight = PLACEMENT_WEIGHTS.get(row["standing"], PLACEMENT_WEIGHT_DEFAULT)
```

with:

```python
        weight = placement_weight(row["standing"])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_weight_consumers.py tests/test_integration.py -v`

Expected: PASS. `tests/test_integration.py` covers the weight round-trip into exported JSON and must not regress; the substitution is behaviour-preserving because `placement_weight` with a default boost of 1.0 is exactly the old expression.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest tests/ -q`

Expected: all pass.

- [ ] **Step 6: Lint, format, commit**

```bash
uv run ruff check . && uv run ruff format .
git add reports/json_export.py tests/test_weight_consumers.py
git commit -m "refactor: route json_export weighting through placement_weight

Two call sites read PLACEMENT_WEIGHTS directly, which would silently bypass the
caliber boost. Adds an AST guard so new direct reads fail the suite."
```

---

### Task 3: Apply caliber in the meta snapshot

**Files:**
- Modify: `analysis/meta.py:71-77` (the weighted-share loop)
- Test: `tests/test_caliber_snapshot.py` (create)

**Interfaces:**
- Consumes: `caliber_weight` from Task 1, `placement_weight` from `analysis.shared`.
- Produces: `weighted_share` values in `archetype_stats` that reflect field size. No signature changes.

- [ ] **Step 1: Write the failing test**

Create `tests/test_caliber_snapshot.py`:

```python
"""Field size must reach weighted_share, not just exist as a helper."""

import sqlite3

from analysis.meta import compute_meta_snapshot
from db import init_db


def _seed(conn: sqlite3.Connection, tid: str, players: int, archetype: str) -> None:
    conn.execute(
        "INSERT INTO tournaments (id, name, date, player_count, division) VALUES (?, ?, ?, ?, 'open')",
        (tid, f"Event {tid}", "2026-07-01", players),
    )
    conn.execute(
        "INSERT INTO placements (tournament_id, standing, player_name, archetype) VALUES (?, 1, ?, ?)",
        (tid, f"player-{tid}", archetype),
    )


class TestCaliberReachesWeightedShare:
    def test_larger_field_earns_a_larger_weighted_share(self, tmp_path):
        conn = sqlite3.connect(tmp_path / "caliber.db")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        _seed(conn, "play-big", 256, "Bigfield")
        _seed(conn, "play-small", 8, "Smallfield")
        conn.commit()

        snapshot_id = compute_meta_snapshot(conn)
        rows = {
            r["archetype"]: r["weighted_share"]
            for r in conn.execute(
                "SELECT archetype, weighted_share FROM archetype_stats WHERE snapshot_id = ?",
                (snapshot_id,),
            )
        }
        # Both are a single 1st place. Only field size separates them.
        assert rows["Bigfield"] > rows["Smallfield"]
        conn.close()

    def test_missing_player_count_stays_neutral(self, tmp_path):
        conn = sqlite3.connect(tmp_path / "neutral.db")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        conn.execute(
            "INSERT INTO tournaments (id, name, date, division) VALUES ('t-1', 'No Count', '2026-07-01', 'open')"
        )
        conn.execute(
            "INSERT INTO placements (tournament_id, standing, player_name, archetype) "
            "VALUES ('t-1', 1, 'a', 'Solo')"
        )
        conn.commit()

        snapshot_id = compute_meta_snapshot(conn)
        share = conn.execute(
            "SELECT weighted_share FROM archetype_stats WHERE snapshot_id = ?", (snapshot_id,)
        ).fetchone()["weighted_share"]
        assert share == 100.0
        conn.close()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_caliber_snapshot.py -v`

Expected: `test_larger_field_earns_a_larger_weighted_share` FAILS, because both archetypes currently get an identical 50.0 share.

- [ ] **Step 3: Apply caliber in the weighted-share loop**

In `analysis/meta.py`, change the import to include `caliber_weight`, then replace the query and loop at lines 71 to 77:

```python
    # Compute performance-weighted shares, scaled by the size of the field each
    # placement was earned in. A null player_count yields a neutral 1.0 boost.
    weight_rows = conn.execute(
        """
        SELECT p.archetype, p.standing, t.player_count
        FROM open_placements p
        JOIN tournaments t ON t.id = p.tournament_id
        """
    ).fetchall()
    weighted_sums: dict[str, float] = {}
    total_weight = 0.0
    for wr in weight_rows:
        w = placement_weight(wr["standing"], boost=caliber_weight(wr["player_count"]))
        weighted_sums[wr["archetype"]] = weighted_sums.get(wr["archetype"], 0.0) + w
        total_weight += w
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_caliber_snapshot.py -v`

Expected: PASS.

- [ ] **Step 5: Run the full suite and inspect the tier delta**

Run: `.venv/bin/python -m pytest tests/ -q`

Expected: all pass. Some meta fixtures may encode pre-caliber weighted shares; if a test fails on an exact share value, update the expected number and note in the commit that it is an intentional scoring change, not a regression.

Then measure the real-world impact before committing:

```bash
uv run scout --format ninja-spinner meta
uv run scout --format ninja-spinner export-web
git diff --stat web/public/data/ninja-spinner/meta.json
```

Expected: tier assignments move. That is the documented, accepted consequence. Record which archetypes changed tier in the commit message.

- [ ] **Step 6: Lint, format, commit**

```bash
uv run ruff check . && uv run ruff format .
git add analysis/meta.py tests/test_caliber_snapshot.py
git commit -m "feat: weight meta shares by tournament field size

Applies caliber_weight to every placement, not only online ones, so a 30-player
event scores the same regardless of source. Retroactively shifts tier
assignments; that is intended and documented in the spec."
```

---

### Task 4: Schema columns for source provenance

**Files:**
- Modify: `db.py` (`tournaments` table in `SCHEMA` around line 29, and the migration block in `init_db` around line 277)
- Test: `tests/test_play_limitless.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `tournaments.source TEXT DEFAULT 'limitless'` and `tournaments.is_online INTEGER DEFAULT 0`. Task 5 writes them, Task 7 exports them.

- [ ] **Step 1: Write the failing test**

Create `tests/test_play_limitless.py`:

```python
"""Play LimitlessTCG ingestion.

Covers the API filter rules, archetype derivation from bare icon stems,
decklist mapping, persistence, incrementality, and dedup safety against the
JP-preferring open_placements view.
"""

import sqlite3

from db import init_db


class TestSourceProvenanceColumns:
    def test_tournaments_carries_source_and_is_online(self, tmp_path):
        conn = sqlite3.connect(tmp_path / "schema.db")
        init_db(conn)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(tournaments)")}
        assert "source" in cols
        assert "is_online" in cols
        conn.close()

    def test_existing_rows_default_to_the_legacy_source(self, tmp_path):
        conn = sqlite3.connect(tmp_path / "defaults.db")
        init_db(conn)
        conn.execute(
            "INSERT INTO tournaments (id, name, date, division) "
            "VALUES ('jp-1', 'City League Osaka', '2026-07-01', 'open')"
        )
        row = conn.execute("SELECT source, is_online FROM tournaments WHERE id = 'jp-1'").fetchone()
        assert row == ("limitless", 0)
        conn.close()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_play_limitless.py -v`

Expected: FAIL, `assert 'source' in cols`.

- [ ] **Step 3: Add the columns to SCHEMA**

In `db.py`, in the `tournaments` table definition, after the `capacity INTEGER` line:

```sql
    source TEXT DEFAULT 'limitless',
    is_online INTEGER DEFAULT 0
```

- [ ] **Step 4: Add migrations for existing databases**

In `db.py`, inside `init_db`, alongside the other `tournaments` column migrations (after the `capacity` block around line 289):

```python
    if "source" not in cols:
        conn.execute("ALTER TABLE tournaments ADD COLUMN source TEXT DEFAULT 'limitless'")
        logger.info("Migration: added source column to tournaments")
    if "is_online" not in cols:
        conn.execute("ALTER TABLE tournaments ADD COLUMN is_online INTEGER DEFAULT 0")
        logger.info("Migration: added is_online column to tournaments")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_play_limitless.py -v`

Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest tests/ -q`

Expected: all pass.

- [ ] **Step 7: Lint, format, commit**

```bash
uv run ruff check . && uv run ruff format .
git add db.py tests/test_play_limitless.py
git commit -m "feat: record tournament source and online flag"
```

---

### Task 5: API client, filtering, and parsing

**Files:**
- Modify: `config.py` (Play API constants, near the other `LIMITLESS_*` constants)
- Create: `scraper/play_limitless.py`
- Create: `tests/fixtures/play/tournaments.json`, `tests/fixtures/play/details_with_decklists.json`, `tests/fixtures/play/details_no_decklists.json`, `tests/fixtures/play/standings_with_decklists.json`
- Test: `tests/test_play_limitless.py`

**Interfaces:**
- Consumes: `RateLimitedHTTPClient` from `scraper/http_client.py:119`, `normalize_archetype` and `LIMITLESS_SPRITE_CDN` from `analysis/archetype.py`, `MIN_TOURNAMENT_PLAYERS` from Task 1.
- Produces:
  - `PlayTournament(id: str, name: str, date: str, players: int, format: str, organizer_id: int | None, is_online: bool)`
  - `PlayPlacement(standing: int, player_name: str, player_id: str, country: str, archetype: str, wins: int, losses: int, ties: int, cards: list[CardEntry])`
  - `PlayLimitlessClient.fetch_tournaments(start: str, end: str) -> list[PlayTournament]`
  - `PlayLimitlessClient.fetch_standings(tournament_id: str) -> list[PlayPlacement]`
  - `is_ingestable(raw: dict, start: str, end: str) -> bool`
  - `parse_standing(raw: dict) -> PlayPlacement`

- [ ] **Step 1: Record the fixtures**

Create `tests/fixtures/play/tournaments.json`:

```json
[
  {"game": "PTCG", "name": "Turtwig Den Revival Series Challenge 41", "date": "2026-07-20T18:00:00.000Z", "format": "STANDARD", "id": "with-lists", "players": 64, "organizerId": 1611},
  {"game": "PTCG", "name": "Card Party 4 - FL Sunday", "date": "2026-07-26T15:00:00.000Z", "format": "STANDARD", "id": "no-lists", "players": 59, "organizerId": 2431},
  {"game": "PTCG", "name": "Moscow Off-Season Series #3", "date": "2026-07-26T10:00:00.000Z", "format": "CUSTOM", "id": "custom-format", "players": 11, "organizerId": 362},
  {"game": "PTCG", "name": "ITA Weekly #2", "date": "2026-07-26T08:30:00.000Z", "format": "STANDARD", "id": "too-small", "players": 4, "organizerId": 2622},
  {"game": "PTCG", "name": "Old Format Cup", "date": "2026-05-01T08:00:00.000Z", "format": "STANDARD", "id": "out-of-window", "players": 80, "organizerId": 99}
]
```

Create `tests/fixtures/play/details_with_decklists.json`:

```json
{"id": "with-lists", "decklists": true, "isOnline": true, "platform": "PTCGL", "organizer": {"id": 1611, "name": "Turtwig Den"}}
```

Create `tests/fixtures/play/details_no_decklists.json`:

```json
{"id": "no-lists", "decklists": false, "isOnline": false, "platform": "IRL", "organizer": {"id": 2431, "name": "Card Party"}}
```

Create `tests/fixtures/play/standings_with_decklists.json`:

```json
[
  {
    "name": "Historicdork224",
    "country": "US",
    "placing": 1,
    "player": "historicdork224",
    "record": {"wins": 3, "losses": 1, "ties": 0},
    "deck": {"id": "wailord-ex", "name": "Wailord", "icons": ["wailord"]},
    "decklist": {
      "pokemon": [
        {"count": 3, "set": "CRI", "number": "8", "name": "Vulpix"},
        {"count": 3, "set": "PBL", "number": "16", "name": "Wailord ex"}
      ],
      "trainer": [{"count": 3, "set": "MEG", "number": "114", "name": "Boss's Orders"}],
      "energy": [{"count": 8, "set": "MEE", "number": "3", "name": "Water Energy"}]
    },
    "drop": null
  },
  {
    "name": "Second Place",
    "country": "GB",
    "placing": 2,
    "player": "secondplace",
    "record": {"wins": 3, "losses": 1, "ties": 0},
    "deck": {"id": "charizard-pidgeot", "name": "Charizard", "icons": ["charizard", "pidgeot"]},
    "decklist": {
      "pokemon": [{"count": 2, "set": "OBF", "number": "125", "name": "Charizard ex"}],
      "trainer": [],
      "energy": []
    },
    "drop": null
  },
  {
    "name": "No Deck Assigned",
    "country": "JP",
    "placing": 3,
    "player": "nodeck",
    "record": {"wins": 2, "losses": 2, "ties": 0},
    "deck": {"id": "unknown", "name": "Other", "icons": []},
    "decklist": {"pokemon": [], "trainer": [], "energy": []},
    "drop": null
  }
]
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_play_limitless.py`:

```python
import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "play"
WINDOW_START = "2026-06-05"
WINDOW_END = "2026-09-04"


def _fixture(name: str):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class TestIngestFilter:
    def test_accepts_a_standard_event_inside_the_window(self):
        from scraper.play_limitless import is_ingestable

        raw = next(t for t in _fixture("tournaments") if t["id"] == "with-lists")
        assert is_ingestable(raw, WINDOW_START, WINDOW_END)

    def test_rejects_custom_format(self):
        from scraper.play_limitless import is_ingestable

        raw = next(t for t in _fixture("tournaments") if t["id"] == "custom-format")
        assert not is_ingestable(raw, WINDOW_START, WINDOW_END)

    def test_rejects_a_field_below_the_floor(self):
        from scraper.play_limitless import is_ingestable

        raw = next(t for t in _fixture("tournaments") if t["id"] == "too-small")
        assert not is_ingestable(raw, WINDOW_START, WINDOW_END)

    def test_rejects_events_outside_the_format_window(self):
        from scraper.play_limitless import is_ingestable

        raw = next(t for t in _fixture("tournaments") if t["id"] == "out-of-window")
        assert not is_ingestable(raw, WINDOW_START, WINDOW_END)


class TestStandingParsing:
    def test_single_icon_becomes_a_titled_archetype(self):
        from scraper.play_limitless import parse_standing

        placement = parse_standing(_fixture("standings_with_decklists")[0])
        assert placement.archetype == "Wailord"
        assert placement.standing == 1
        assert placement.player_name == "Historicdork224"
        assert (placement.wins, placement.losses, placement.ties) == (3, 1, 0)

    def test_multiple_icons_join_alphabetically(self):
        from scraper.play_limitless import parse_standing

        placement = parse_standing(_fixture("standings_with_decklists")[1])
        assert placement.archetype == "Charizard / Pidgeot"

    def test_empty_icons_fall_back_to_the_deck_name(self):
        from scraper.play_limitless import parse_standing

        placement = parse_standing(_fixture("standings_with_decklists")[2])
        assert placement.archetype == "Other"

    def test_decklist_cards_use_the_set_number_card_id_convention(self):
        from scraper.play_limitless import parse_standing

        placement = parse_standing(_fixture("standings_with_decklists")[0])
        by_id = {c["card_id"]: c for c in placement.cards}
        assert by_id["CRI-8"]["name"] == "Vulpix"
        assert by_id["CRI-8"]["count"] == 3
        # All three categories are flattened into one list.
        assert "MEG-114" in by_id
        assert "MEE-3" in by_id
        assert len(placement.cards) == 4
```

- [ ] **Step 3: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_play_limitless.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'scraper.play_limitless'`.

- [ ] **Step 4: Add the Play API constants to config.py**

In `config.py`, beside the other `LIMITLESS_*` constants:

```python
# Play LimitlessTCG API. Public, no key required for tournaments/standings.
PLAY_API_BASE_URL = "https://play.limitlesstcg.com/api"
PLAY_REQUESTS_PER_MINUTE = 30
PLAY_TIMEOUT = 30.0
PLAY_MAX_RETRIES = 3
PLAY_PAGE_SIZE = 100
PLAY_GAME = "PTCG"
PLAY_STANDARD_FORMAT = "STANDARD"
```

- [ ] **Step 5: Write the module**

Create `scraper/play_limitless.py`:

```python
"""Play LimitlessTCG scraper.

Reads the public JSON API at play.limitlesstcg.com/api. No API key is required
for the endpoints used here, and standings responses carry full decklists
inline, so unlike the other scrapers there is no second decklist fetch and no
browser rendering.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from analysis.archetype import LIMITLESS_SPRITE_CDN, normalize_archetype
from config import (
    MIN_TOURNAMENT_PLAYERS,
    PLAY_API_BASE_URL,
    PLAY_GAME,
    PLAY_MAX_RETRIES,
    PLAY_PAGE_SIZE,
    PLAY_REQUESTS_PER_MINUTE,
    PLAY_STANDARD_FORMAT,
    PLAY_TIMEOUT,
)
from scraper.http_client import CardEntry, RateLimitedHTTPClient

logger = logging.getLogger(__name__)

DECK_CATEGORIES = ("pokemon", "trainer", "energy")


@dataclass
class PlayTournament:
    id: str
    name: str
    date: str  # YYYY-MM-DD
    players: int
    format: str
    organizer_id: int | None = None
    is_online: bool = False


@dataclass
class PlayPlacement:
    standing: int
    player_name: str
    player_id: str
    country: str
    archetype: str
    wins: int = 0
    losses: int = 0
    ties: int = 0
    cards: list[CardEntry] = field(default_factory=list)


def _event_date(raw: dict[str, Any]) -> str:
    """ISO 8601 timestamp to YYYY-MM-DD. The API always sends a Z-suffixed UTC time."""
    return str(raw.get("date", ""))[:10]


def is_ingestable(raw: dict[str, Any], start: str, end: str) -> bool:
    """Listing-level filter, applied before spending a details request.

    Rejects non-Standard formats, events outside the format's dataset window,
    and fields too small to be a tournament.
    """
    if raw.get("format") != PLAY_STANDARD_FORMAT:
        return False
    date = _event_date(raw)
    if not date or date < start or date > end:
        return False
    return (raw.get("players") or 0) >= MIN_TOURNAMENT_PLAYERS


def _sprite_urls(deck: dict[str, Any]) -> list[str]:
    """The API sends bare icon stems; the archetype regex needs a /name.png shape."""
    return [f"{LIMITLESS_SPRITE_CDN}/{icon}.png" for icon in deck.get("icons") or []]


def _decklist_cards(decklist: dict[str, Any] | None) -> list[CardEntry]:
    """Flatten the three category lists, keeping Scout's SET-number card id."""
    cards: list[CardEntry] = []
    if not decklist:
        return cards
    for category in DECK_CATEGORIES:
        for entry in decklist.get(category) or []:
            set_code = str(entry.get("set", ""))
            number = str(entry.get("number", ""))
            name = str(entry.get("name", ""))
            if not name:
                continue
            cards.append(
                {
                    "count": int(entry.get("count", 1)),
                    "name": name,
                    "set_code": set_code,
                    "card_number": number,
                    "card_id": f"{set_code}-{number}" if set_code and number else name,
                }
            )
    return cards


def parse_standing(raw: dict[str, Any]) -> PlayPlacement:
    """Build a placement from one standings entry."""
    deck = raw.get("deck") or {}
    record = raw.get("record") or {}
    return PlayPlacement(
        standing=int(raw.get("placing", 0)),
        player_name=str(raw.get("name", "")),
        player_id=str(raw.get("player", "")),
        country=str(raw.get("country", "")),
        archetype=normalize_archetype(_sprite_urls(deck), str(deck.get("name", ""))),
        wins=int(record.get("wins", 0)),
        losses=int(record.get("losses", 0)),
        ties=int(record.get("ties", 0)),
        cards=_decklist_cards(raw.get("decklist")),
    )


class PlayLimitlessClient(RateLimitedHTTPClient):
    """Client for the public Play LimitlessTCG JSON API."""

    def __init__(self) -> None:
        super().__init__(
            base_url=PLAY_API_BASE_URL,
            max_rpm=PLAY_REQUESTS_PER_MINUTE,
            timeout=PLAY_TIMEOUT,
            max_retries=PLAY_MAX_RETRIES,
            user_agent="TrainerLab-Scout/1.0",
        )

    def _json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{PLAY_API_BASE_URL}{path}"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"
        return self._get(url).json()

    def fetch_tournament_details(self, tournament_id: str) -> dict[str, Any]:
        return self._json(f"/tournaments/{tournament_id}/details") or {}

    def fetch_tournaments(self, start: str, end: str) -> list[PlayTournament]:
        """List ingestable tournaments in a date window, newest first.

        Paginates until a page yields nothing or every event on it predates the
        window. Each surviving candidate costs one extra details request, used
        to confirm decklists were published.
        """
        found: list[PlayTournament] = []
        page = 1
        while True:
            raw_page = self._json(
                "/tournaments",
                {"game": PLAY_GAME, "limit": PLAY_PAGE_SIZE, "page": page},
            )
            if not raw_page:
                break

            for raw in raw_page:
                if not is_ingestable(raw, start, end):
                    continue
                details = self.fetch_tournament_details(str(raw["id"]))
                if not details.get("decklists"):
                    logger.debug("Skipping %s: no decklists published", raw["id"])
                    continue
                found.append(
                    PlayTournament(
                        id=str(raw["id"]),
                        name=str(raw.get("name", "")),
                        date=_event_date(raw),
                        players=int(raw.get("players") or 0),
                        format=str(raw.get("format", "")),
                        organizer_id=raw.get("organizerId"),
                        is_online=bool(details.get("isOnline")),
                    )
                )

            # Listings are newest-first, so once a whole page predates the
            # window there is nothing older worth fetching.
            if all(_event_date(raw) < start for raw in raw_page):
                break
            page += 1

        logger.info("Found %d ingestable Play tournaments", len(found))
        return found

    def fetch_standings(self, tournament_id: str) -> list[PlayPlacement]:
        raw = self._json(f"/tournaments/{tournament_id}/standings") or []
        placements = [parse_standing(entry) for entry in raw]
        placements.sort(key=lambda p: p.standing)
        return placements
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_play_limitless.py -v`

Expected: PASS.

- [ ] **Step 7: Lint, format, commit**

```bash
uv run ruff check . && uv run ruff format .
git add config.py scraper/play_limitless.py tests/fixtures/play tests/test_play_limitless.py
git commit -m "feat: add Play LimitlessTCG API client

Public JSON API, no key required. Standings carry decklists inline, so there is
no second fetch. Icon stems are expanded to CDN URLs so the existing
sprite-filename archetype derivation applies unchanged."
```

---

### Task 6: Persistence

**Files:**
- Modify: `scraper/play_limitless.py` (append `store_play_results`)
- Test: `tests/test_play_limitless.py`

**Interfaces:**
- Consumes: `PlayTournament` and `PlayPlacement` from Task 5; the `source` and `is_online` columns from Task 4.
- Produces: `store_play_results(conn: sqlite3.Connection, tournament: PlayTournament, placements: list[PlayPlacement]) -> int`, returning the number of placements written. Task 7 calls it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_play_limitless.py`:

```python
class TestPersistence:
    @staticmethod
    def _conn(tmp_path, name):
        conn = sqlite3.connect(tmp_path / name)
        conn.row_factory = sqlite3.Row
        init_db(conn)
        return conn

    @staticmethod
    def _sample():
        from scraper.play_limitless import PlayTournament, parse_standing

        tournament = PlayTournament(
            id="with-lists",
            name="Turtwig Den Revival Series Challenge 41",
            date="2026-07-20",
            players=64,
            format="STANDARD",
            organizer_id=1611,
            is_online=True,
        )
        placements = [parse_standing(r) for r in _fixture("standings_with_decklists")]
        return tournament, placements

    def test_writes_tournament_with_play_prefix_and_provenance(self, tmp_path):
        from scraper.play_limitless import store_play_results

        conn = self._conn(tmp_path, "store.db")
        tournament, placements = self._sample()
        store_play_results(conn, tournament, placements)

        row = conn.execute(
            "SELECT id, player_count, source, is_online, division FROM tournaments"
        ).fetchone()
        assert row["id"] == "play-with-lists"
        assert row["player_count"] == 64
        assert row["source"] == "play"
        assert row["is_online"] == 1
        assert row["division"] == "open"
        conn.close()

    def test_writes_placements_and_decklist_cards(self, tmp_path):
        from scraper.play_limitless import store_play_results

        conn = self._conn(tmp_path, "cards.db")
        tournament, placements = self._sample()
        written = store_play_results(conn, tournament, placements)

        assert written == 3
        archetypes = [
            r["archetype"]
            for r in conn.execute("SELECT archetype FROM placements ORDER BY standing")
        ]
        assert archetypes == ["Wailord", "Charizard / Pidgeot", "Other"]

        count = conn.execute(
            "SELECT SUM(count) AS n FROM decklist_cards WHERE card_id = 'CRI-8'"
        ).fetchone()["n"]
        assert count == 3
        conn.close()

    def test_reingesting_the_same_event_does_not_duplicate_placements(self, tmp_path):
        """Steady-state runs re-see recent events; they must be idempotent."""
        from scraper.play_limitless import store_play_results

        conn = self._conn(tmp_path, "idempotent.db")
        tournament, placements = self._sample()
        store_play_results(conn, tournament, placements)
        store_play_results(conn, tournament, placements)

        total = conn.execute("SELECT COUNT(*) AS n FROM placements").fetchone()["n"]
        assert total == 3
        conn.close()


class TestDedupSafety:
    """open_placements suppresses non-jp events that look like a jp event.

    Play events carry no prefecture or store name and use usernames, so they
    must survive that filter even on a date a JP event also ran.
    """

    def test_play_event_survives_alongside_a_same_day_jp_event(self, tmp_path):
        from scraper.play_limitless import store_play_results

        conn = sqlite3.connect(tmp_path / "dedup.db")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        conn.execute(
            "INSERT INTO tournaments (id, name, date, division, prefecture, store_name) "
            "VALUES ('jp-1', 'Osaka Shop', '2026-07-20', 'open', 'Osaka', 'Card Shop')"
        )
        conn.execute(
            "INSERT INTO placements (tournament_id, standing, player_name, archetype) "
            "VALUES ('jp-1', 1, 'JP Player', 'Dragapult')"
        )
        conn.commit()

        tournament, placements = TestPersistence._sample()
        store_play_results(conn, tournament, placements)

        ids = {r["id"] for r in conn.execute("SELECT id FROM open_tournaments")}
        assert "play-with-lists" in ids
        assert "jp-1" in ids
        conn.close()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_play_limitless.py::TestPersistence -v`

Expected: FAIL with `ImportError: cannot import name 'store_play_results'`.

- [ ] **Step 3: Implement `store_play_results`**

Append to `scraper/play_limitless.py`:

```python
def store_play_results(
    conn: "sqlite3.Connection",
    tournament: PlayTournament,
    placements: list[PlayPlacement],
) -> int:
    """Persist one Play tournament and its placements. Returns rows written.

    Idempotent: re-ingesting an event replaces the tournament row and rebuilds
    its placements, so steady-state runs that re-see a recent event do not
    duplicate it.
    """
    tournament_id = f"play-{tournament.id}"

    conn.execute(
        "INSERT OR REPLACE INTO tournaments "
        "(id, name, date, player_count, country, division, tournament_type, source, is_online) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            tournament_id,
            tournament.name,
            tournament.date,
            tournament.players,
            "",  # Play is international; country belongs to the player, not the event
            "open",
            "online",
            "play",
            1 if tournament.is_online else 0,
        ),
    )

    # Rebuild rather than append, so a re-ingest is idempotent.
    old_ids = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM placements WHERE tournament_id = ?", (tournament_id,)
        )
    ]
    if old_ids:
        marks = ",".join("?" * len(old_ids))
        conn.execute(f"DELETE FROM decklist_cards WHERE placement_id IN ({marks})", old_ids)
        conn.execute("DELETE FROM placements WHERE tournament_id = ?", (tournament_id,))

    written = 0
    for placement in placements:
        cursor = conn.execute(
            "INSERT INTO placements (tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?)",
            (tournament_id, placement.standing, placement.player_name, placement.archetype),
        )
        placement_id = cursor.lastrowid
        for card in placement.cards:
            conn.execute(
                "INSERT OR REPLACE INTO decklist_cards (placement_id, card_id, card_name, count) "
                "VALUES (?, ?, ?, ?)",
                (placement_id, card["card_id"], card["name"], card["count"]),
            )
        written += 1

    conn.commit()
    return written
```

Add `import sqlite3` to the module's imports.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_play_limitless.py -v`

Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest tests/ -q`

Expected: all pass.

- [ ] **Step 6: Lint, format, commit**

```bash
uv run ruff check . && uv run ruff format .
git add scraper/play_limitless.py tests/test_play_limitless.py
git commit -m "feat: persist Play tournament results idempotently"
```

---

### Task 7: `scrape-play` CLI command

**Files:**
- Modify: `cli.py` (add a command following the `scrape_jp` pattern)
- Test: `tests/test_play_limitless.py`

**Interfaces:**
- Consumes: `PlayLimitlessClient`, `store_play_results` from Tasks 5 and 6; `get_format_config` from `config.py`.
- Produces: the `scout --format <slug> scrape-play` command. Task 8 calls it from the pipeline.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_play_limitless.py`:

```python
class TestCliCommand:
    def test_scrape_play_is_registered(self):
        from cli import cli

        assert "scrape-play" in cli.commands

    def test_scrape_play_exposes_the_documented_options(self):
        from cli import cli

        options = {
            opt
            for param in cli.commands["scrape-play"].params
            for opt in getattr(param, "opts", [])
        }
        assert {"--since", "--limit", "--dry-run"} <= options
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_play_limitless.py::TestCliCommand -v`

Expected: FAIL, `assert 'scrape-play' in cli.commands`.

- [ ] **Step 3: Add the command**

In `cli.py`, after the existing `scrape_jp` command:

```python
@cli.command("scrape-play")
@click.option("--since", default=None, help="Start date (YYYY-MM-DD), defaults to dataset_start")
@click.option("--limit", default=None, type=int, help="Stop after N new tournaments")
@click.option("--dry-run", is_flag=True, help="List what would be ingested without writing")
@click.pass_context
def scrape_play(ctx, since, limit, dry_run):
    """Scrape online and grassroots results from play.limitlesstcg.com."""
    from scraper.play_limitless import PlayLimitlessClient, store_play_results

    format_slug = ctx.obj["format"]
    fmt = get_format_config(format_slug)
    start = since or fmt["dataset_start"]
    end = fmt["dataset_end"]

    conn = get_format_connection(format_slug)
    known = {row[0] for row in conn.execute("SELECT id FROM tournaments WHERE id LIKE 'play-%'")}

    console.print(f"Scraping Play tournaments ({start} to {end}), {len(known)} already ingested")

    ingested = 0
    placements_written = 0
    with PlayLimitlessClient() as client:
        for tournament in client.fetch_tournaments(start, end):
            if f"play-{tournament.id}" in known:
                continue
            if limit is not None and ingested >= limit:
                console.print(f"Reached --limit of {limit}, stopping")
                break

            if dry_run:
                console.print(
                    f"  would ingest {tournament.date} {tournament.name} "
                    f"({tournament.players} players)",
                    highlight=False,
                )
                ingested += 1
                continue

            placements = client.fetch_standings(tournament.id)
            if not placements:
                continue
            placements_written += store_play_results(conn, tournament, placements)
            ingested += 1

    verb = "Would ingest" if dry_run else "Ingested"
    console.print(f"{verb} {ingested} tournaments, {placements_written} placements")
    conn.close()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_play_limitless.py -v`

Expected: PASS.

- [ ] **Step 5: Survey the decklist publication rate**

This is the unmeasured number the spec flagged as a risk. Measure it before committing to a full backfill.

```bash
uv run scout --format abyss-eye scrape-play --dry-run --limit 50
```

Expected: a list of candidate events. Compare the count against the number of Standard in-window events the listing returned. **If the publication rate is materially below 50%, stop and report it** before running the full backfill, because the volume assumptions in the spec no longer hold.

- [ ] **Step 6: Lint, format, commit**

```bash
uv run ruff check . && uv run ruff format .
git add cli.py tests/test_play_limitless.py
git commit -m "feat: add scrape-play CLI command

Incremental by default: already-ingested play- ids are skipped, so steady-state
runs only fetch recent events."
```

---

### Task 8: Export provenance and frontend types

**Files:**
- Modify: `reports/json_export.py` (the tournament-shaped export queries)
- Modify: `web/app/lib/types.ts`
- Test: `tests/test_play_limitless.py`, `web/app/lib/__tests__/` (follow the existing vitest layout)

**Interfaces:**
- Consumes: the `source` and `is_online` columns from Task 4.
- Produces: `source?: string` and `isOnline?: boolean` on the tournament-shaped TypeScript interfaces.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_play_limitless.py`:

```python
class TestExportProvenance:
    def test_exported_tournaments_carry_source_and_online_flag(self, tmp_path):
        from scraper.play_limitless import store_play_results

        conn = sqlite3.connect(tmp_path / "export.db")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        tournament, placements = TestPersistence._sample()
        store_play_results(conn, tournament, placements)

        row = conn.execute(
            "SELECT source, is_online FROM open_tournaments WHERE id = 'play-with-lists'"
        ).fetchone()
        assert row["source"] == "play"
        assert row["is_online"] == 1
        conn.close()
```

- [ ] **Step 2: Run it to verify it passes or fails**

Run: `.venv/bin/python -m pytest tests/test_play_limitless.py::TestExportProvenance -v`

Expected: PASS. `open_tournaments` is `SELECT t.*`, so the new columns flow through automatically. This test exists to catch a future view rewrite that projects an explicit column list and silently drops them.

- [ ] **Step 3: Emit the fields in the JSON export**

In `reports/json_export.py`, find the query that builds tournament-shaped export objects and add `t.source` and `t.is_online` to its `SELECT`, then include them in the emitted dict:

```python
            "source": row["source"],
            "isOnline": bool(row["is_online"]),
```

Use `--strict` export to catch a missing column immediately:

```bash
uv run scout --format abyss-eye export-web --strict
```

- [ ] **Step 4: Add the optional TypeScript fields**

In `web/app/lib/types.ts`, on the tournament-shaped interface, add:

```typescript
  /** Data source: "limitless" for scraped physical events, "play" for Play LimitlessTCG. */
  source?: string;
  /** True when the event was played online rather than in person. */
  isOnline?: boolean;
```

They are optional so already-published JSON without them still type-checks.

- [ ] **Step 5: Type-check and test the frontend**

```bash
source ~/.nvm/nvm.sh && nvm use default --silent && cd web && npx tsc --noEmit && npm test
```

Expected: no type errors, tests pass.

- [ ] **Step 6: Run the full Python suite**

Run: `.venv/bin/python -m pytest tests/ -q`

Expected: all pass.

- [ ] **Step 7: Lint, format, commit**

```bash
uv run ruff check . && uv run ruff format .
git add reports/json_export.py web/app/lib/types.ts tests/test_play_limitless.py
git commit -m "feat: expose tournament source and online flag in exports

Optional TypeScript fields so previously published JSON still type-checks."
```

---

### Task 9: Pipeline wiring and backfill

**Files:**
- Modify: `cloudbuild-scrape.yaml` (the `scrape` step's per-format loop, around line 52)

**Interfaces:**
- Consumes: the `scrape-play` command from Task 7.
- Produces: nothing consumed elsewhere.

- [ ] **Step 1: Run the one-time backfill locally**

The full window is thousands of API calls and must not run inside a build. Run it once, out of band, and upload the resulting database.

```bash
uv run scout --format abyss-eye scrape-play
uv run scout --format abyss-eye backfill-archetypes
uv run scout --format abyss-eye meta
uv run scout --format abyss-eye export-web --strict
```

Record the tournament and placement counts. Then confirm the perf work still holds at the new volume:

```bash
.venv/bin/python scripts/bench_open_placements.py data/abyss-eye.db
```

Expected: `open_placements_count` under roughly 5 ms. **If it is not, stop.** The index fix did not survive the volume increase and the pipeline will time out again.

- [ ] **Step 2: Upload the backfilled database**

```bash
CLOUDSDK_CORE_ACCOUNT=daniel@appraisehq.ai gsutil cp \
  data/abyss-eye.db gs://tcg-scout-cache/scout-dbs/abyss-eye.db
```

- [ ] **Step 3: Add the incremental scrape to the pipeline**

In `cloudbuild-scrape.yaml`, inside the `for slug in ${_SCRAPE_FORMATS}` loop, between the `scrape-jp` and `backfill-archetypes` lines:

```bash
          uv run python cli.py --format "$slug" scrape-play
```

- [ ] **Step 4: Verify the substitution drift guard still passes**

Run: `.venv/bin/python -m pytest tests/test_jp_event_metadata.py -v`

Expected: PASS. `TestCloudBuildSubstitutionsMatchConfig` parses this file.

- [ ] **Step 5: Commit and watch one build**

```bash
git add cloudbuild-scrape.yaml
git commit -m "ci: scrape Play tournaments for active formats"
git push origin main
```

Then confirm the build succeeded and note its duration:

```bash
CLOUDSDK_CORE_ACCOUNT=daniel@appraisehq.ai gcloud builds list \
  --project=trainerlab-prod --region=us-central1 --limit=3 \
  --format='table(id,status,createTime,duration)'
```

Expected: `SUCCESS`, comfortably inside the timeout.

---

## Self-Review

**Spec coverage.**

| Spec section | Task |
|---|---|
| Source, three endpoints, no key | 5 |
| Incremental scraping | 7 (`known` id set), 9 (pipeline) |
| Archetype from `deck.icons` via synthesized CDN URLs | 5 |
| Decklist mapping to `SET-number` | 5 |
| `source` and `is_online` columns, `play-` id prefix | 4, 6 |
| Caliber weighting formula, clamps, floor | 1 |
| Caliber applied to all sources | 3 |
| `json_export` direct-read consumers corrected | 2 |
| Exports and optional TypeScript fields | 8 |
| `open_placements` prerequisite | Global Constraints; separate plan |
| Testing: fixtures, filters, dedup safety, round-trip | 4, 5, 6, 8 |
| Risk: unmeasured decklist publication rate | 7 Step 5 |

**Gap found and closed.** The spec calls for archetype detail pages to show an online versus physical split. Tasks 1 to 9 carry `source` and `is_online` all the way into the exported JSON and the TypeScript types, but do not build the UI. That is deliberate: it is frontend work, and this project's session guidelines require Python pipeline work and Next.js work to be split across separate sessions. The split view is a follow-up plan, and the data it needs is fully in place after Task 8.

**Placeholder scan.** No TBDs. Task 8 Step 3 names a query by role rather than line number because the exact tournament-export query must be located in the file; the fields to add and the emission shape are both given verbatim.

**Type consistency.** `PlayTournament` and `PlayPlacement` field names are identical across Tasks 5, 6, 7 and 8. `store_play_results(conn, tournament, placements) -> int` has one signature everywhere. `caliber_weight(player_count)` is used with that parameter name in Tasks 1 and 3. `CardEntry` is the existing TypedDict from `scraper/http_client.py`, and `_decklist_cards` populates all five of its keys.

**Known deviation from the spec.** The spec's Architecture section proposed a `PlayDecklist` dataclass. It is not implemented: decklist entries flatten directly into the existing `CardEntry` TypedDict that both other scrapers already produce, so a third representation would add a conversion step and no clarity.
