# Labs H2H Matchup Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up the full Labs H2H matchup pipeline -- from export to frontend -- so archetype detail pages show top 5 favorable/unfavorable matchups and a win-rate heat matrix.

**Architecture:** The backend infrastructure (scraper, database schema, matchup computation with Wilson CI) already exists in `labs_db.py`, `scraper/labs_limitless.py`, and `analysis/matchup.py`. This plan connects it to the JSON export and frontend. The export reads from `labs.db`, writes `matchup-h2h.json`, and per-archetype matchup data is embedded in each `archetypes/{slug}.json`. The frontend gets a new `ArchetypeMatchups` component on the detail page.

**Tech Stack:** Python 3.12+, SQLite, Next.js 16, TypeScript, Tailwind CSS, vitest, pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `analysis/matchup.py` | Modify | Add `extract_archetype_matchups()` helper |
| `reports/json_export.py` | Modify | Add `export_labs_matchup()`, enrich archetype exports |
| `web/app/lib/types.ts` | Modify | Add `LabsMatchupData`, `ArchetypeMatchup` types |
| `web/app/lib/data.ts` | Modify | Add `getLabsMatchup()` loader |
| `web/app/components/archetype-matchups.tsx` | Create | Top 5 favorable/unfavorable + mini heat row |
| `web/app/[format]/archetypes/[slug]/page.tsx` | Modify | Integrate matchup section |
| `tests/test_matchup.py` | Modify | Add tests for `extract_archetype_matchups()` |
| `tests/test_json_export.py` | Modify | Add test for `export_labs_matchup()` |
| `web/app/components/__tests__/archetype-matchups.test.tsx` | Create | Component tests |

---

### Task 1: Add `extract_archetype_matchups()` to analysis/matchup.py

**Files:**
- Modify: `analysis/matchup.py`
- Test: `tests/test_matchup.py`

This function takes a `MatchupMatrixResult` and an archetype name, returns the top N favorable and unfavorable matchups with win rates, sample sizes, and confidence intervals.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_matchup.py`:

```python
from analysis.matchup import extract_archetype_matchups


class TestExtractArchetypeMatchups:
    def test_returns_favorable_and_unfavorable(self, labs_db):
        from analysis.matchup import compute_labs_matchup_matrix

        matrix_result = compute_labs_matchup_matrix(labs_db, top_n=3, min_matches=1)
        result = extract_archetype_matchups(matrix_result, "Dragapult ex", top_n=5)

        assert "favorable" in result
        assert "unfavorable" in result
        assert isinstance(result["favorable"], list)
        assert isinstance(result["unfavorable"], list)

    def test_each_entry_has_required_fields(self, labs_db):
        from analysis.matchup import compute_labs_matchup_matrix

        matrix_result = compute_labs_matchup_matrix(labs_db, top_n=3, min_matches=1)
        result = extract_archetype_matchups(matrix_result, "Dragapult ex", top_n=5)

        for entry in result["favorable"] + result["unfavorable"]:
            assert "archetype" in entry
            assert "win_rate" in entry
            assert "sample_size" in entry
            assert "ci_lower" in entry
            assert "ci_upper" in entry

    def test_favorable_sorted_descending(self, labs_db):
        from analysis.matchup import compute_labs_matchup_matrix

        matrix_result = compute_labs_matchup_matrix(labs_db, top_n=3, min_matches=1)
        result = extract_archetype_matchups(matrix_result, "Dragapult ex", top_n=5)

        rates = [e["win_rate"] for e in result["favorable"]]
        assert rates == sorted(rates, reverse=True)

    def test_unfavorable_sorted_ascending(self, labs_db):
        from analysis.matchup import compute_labs_matchup_matrix

        matrix_result = compute_labs_matchup_matrix(labs_db, top_n=3, min_matches=1)
        result = extract_archetype_matchups(matrix_result, "Dragapult ex", top_n=5)

        rates = [e["win_rate"] for e in result["unfavorable"]]
        assert rates == sorted(rates)

    def test_unknown_archetype_returns_empty(self, labs_db):
        from analysis.matchup import compute_labs_matchup_matrix

        matrix_result = compute_labs_matchup_matrix(labs_db, top_n=3, min_matches=1)
        result = extract_archetype_matchups(matrix_result, "Nonexistent Deck", top_n=5)

        assert result["favorable"] == []
        assert result["unfavorable"] == []

    def test_empty_matrix_returns_empty(self):
        empty_result = {
            "archetypes": [],
            "matrix": [],
            "sample_sizes": [],
            "confidence": [],
            "source": "labs-h2h",
        }
        result = extract_archetype_matchups(empty_result, "Anything", top_n=5)
        assert result["favorable"] == []
        assert result["unfavorable"] == []

    def test_respects_top_n_limit(self, labs_db):
        from analysis.matchup import compute_labs_matchup_matrix

        matrix_result = compute_labs_matchup_matrix(labs_db, top_n=3, min_matches=1)
        result = extract_archetype_matchups(matrix_result, "Dragapult ex", top_n=1)

        assert len(result["favorable"]) <= 1
        assert len(result["unfavorable"]) <= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_matchup.py::TestExtractArchetypeMatchups -v`
Expected: FAIL with `ImportError: cannot import name 'extract_archetype_matchups'`

- [ ] **Step 3: Write the implementation**

Add to `analysis/matchup.py` after the existing `MatchupMatrixResult` TypedDict:

```python
class ArchetypeMatchupEntry(TypedDict):
    archetype: str
    win_rate: float
    sample_size: int
    ci_lower: float | None
    ci_upper: float | None


class ArchetypeMatchups(TypedDict):
    favorable: list[ArchetypeMatchupEntry]
    unfavorable: list[ArchetypeMatchupEntry]


def extract_archetype_matchups(
    matrix_result: MatchupMatrixResult,
    archetype: str,
    top_n: int = 5,
) -> ArchetypeMatchups:
    """Extract top favorable/unfavorable matchups for one archetype.

    Args:
        matrix_result: Output from compute_labs_matchup_matrix().
        archetype: The archetype name to extract matchups for.
        top_n: Number of matchups to return per category.

    Returns:
        {"favorable": [...], "unfavorable": [...]} sorted by win rate.
    """
    archetypes = matrix_result["archetypes"]
    if archetype not in archetypes:
        return {"favorable": [], "unfavorable": []}

    idx = archetypes.index(archetype)
    matrix = matrix_result["matrix"]
    samples = matrix_result["sample_sizes"]
    confidence = matrix_result["confidence"]

    entries: list[ArchetypeMatchupEntry] = []
    for j, opp in enumerate(archetypes):
        if j == idx:
            continue
        wr = matrix[idx][j]
        if wr is None:
            continue
        entries.append({
            "archetype": opp,
            "win_rate": round(wr, 4),
            "sample_size": samples[idx][j],
            "ci_lower": confidence[idx][j]["lower"],
            "ci_upper": confidence[idx][j]["upper"],
        })

    favorable = sorted(
        [e for e in entries if e["win_rate"] > 0.5],
        key=lambda e: e["win_rate"],
        reverse=True,
    )[:top_n]

    unfavorable = sorted(
        [e for e in entries if e["win_rate"] < 0.5],
        key=lambda e: e["win_rate"],
    )[:top_n]

    return {"favorable": favorable, "unfavorable": unfavorable}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_matchup.py::TestExtractArchetypeMatchups -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add analysis/matchup.py tests/test_matchup.py
git commit -m "feat: add extract_archetype_matchups() for per-archetype H2H data"
```

---

### Task 2: Add `export_labs_matchup()` to json_export.py

**Files:**
- Modify: `reports/json_export.py`
- Test: `tests/test_json_export.py`

Export Labs H2H matchup data as `matchup-h2h.json` and embed per-archetype matchups into archetype detail exports.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_json_export.py` (find the existing test pattern for export functions):

```python
class TestExportLabsMatchup:
    def test_exports_matchup_h2h_json(self, tmp_path, labs_db):
        from reports.json_export import export_labs_matchup

        export_labs_matchup(labs_db, tmp_path)
        output = tmp_path / "matchup-h2h.json"
        assert output.exists()

        import json
        data = json.loads(output.read_text())
        assert "archetypes" in data
        assert "matrix" in data
        assert "sample_sizes" in data
        assert "confidence" in data
        assert "source" in data

    def test_skips_on_empty_db(self, tmp_path, labs_db_empty):
        from reports.json_export import export_labs_matchup

        export_labs_matchup(labs_db_empty, tmp_path)
        output = tmp_path / "matchup-h2h.json"
        assert not output.exists()
```

Note: The `labs_db` and `labs_db_empty` fixtures are defined in `tests/test_labs.py`. Either move them to `tests/conftest.py` or import them. The simplest approach is to move just the `labs_db` fixture to `conftest.py`.

- [ ] **Step 2: Move Labs fixtures to conftest.py**

Add the `labs_db` and `labs_db_empty` fixtures from `tests/test_labs.py` to `tests/conftest.py`, then remove the duplicates from `test_labs.py` (keep the import). This lets all test files use them.

In `tests/conftest.py`, add after the existing fixtures:

```python
from labs_db import LABS_SCHEMA


@pytest.fixture()
def labs_db() -> sqlite3.Connection:
    """In-memory Labs database with seed data for matchup testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(LABS_SCHEMA)

    conn.executemany(
        "INSERT INTO tournaments (id, name, date, player_count, country, source) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("551", "Regional Houston, TX", "2026-03-21", 2635, "US", "limitless-labs"),
            ("552", "Regional Toronto", "2026-03-14", 1200, "CA", "limitless-labs"),
        ],
    )
    conn.executemany(
        "INSERT INTO players (id, name, country) VALUES (?, ?, ?)",
        [
            ("p1", "Alice", "US"),
            ("p2", "Bob", "US"),
            ("p3", "Charlie", "CA"),
            ("p4", "Diana", "JP"),
            ("p5", "Eve", "US"),
            ("p6", "Frank", "MX"),
        ],
    )
    conn.executemany(
        "INSERT INTO placements (id, tournament_id, player_id, standing, archetype, "
        "record_w, record_l, record_t) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "551", "p1", 1, "Dragapult ex", 14, 1, 1),
            (2, "551", "p2", 5, "Charizard ex", 11, 3, 2),
            (3, "551", "p3", 20, "Gardevoir ex", 9, 5, 2),
            (4, "551", "p4", 50, "Dragapult ex", 8, 6, 2),
            (5, "552", "p5", 1, "Charizard ex", 12, 1, 1),
            (6, "552", "p6", 3, "Dragapult ex", 10, 3, 1),
            (7, "552", "p3", 10, "Gardevoir ex", 8, 4, 2),
            (8, "552", "p1", 15, "Dragapult ex", 7, 5, 2),
        ],
    )
    conn.executemany(
        "INSERT INTO matches (id, tournament_id, round, player1_id, player2_id, "
        "winner_id, player1_archetype, player2_archetype) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("551:r1:p1:p3", "551", 1, "p1", "p3", "p1", "Dragapult ex", "Gardevoir ex"),
            ("551:r2:p2:p4", "551", 2, "p2", "p4", "p2", "Charizard ex", "Dragapult ex"),
            ("551:r3:p1:p2", "551", 3, "p1", "p2", "p1", "Dragapult ex", "Charizard ex"),
            ("552:r1:p5:p6", "552", 1, "p5", "p6", "p5", "Charizard ex", "Dragapult ex"),
        ],
    )
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture()
def labs_db_empty() -> sqlite3.Connection:
    """Empty Labs database with schema only."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(LABS_SCHEMA)
    conn.commit()
    yield conn
    conn.close()
```

In `tests/test_labs.py`, remove the `labs_db` and `labs_db_empty` fixture definitions (they'll be picked up from conftest.py automatically).

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_json_export.py::TestExportLabsMatchup -v`
Expected: FAIL with `ImportError: cannot import name 'export_labs_matchup'`

- [ ] **Step 4: Write the implementation**

Add to `reports/json_export.py`:

1. Add import at top: `from analysis.matchup import compute_labs_matchup_matrix`
2. Add new export function:

```python
def export_labs_matchup(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export Labs H2H matchup matrix with win rates and confidence intervals."""
    data = compute_labs_matchup_matrix(conn)
    if data["archetypes"]:
        _write_json(data, output_dir / "matchup-h2h.json")
        logger.info(
            "Exported Labs matchup matrix (%d archetypes, source=%s)",
            len(data["archetypes"]),
            data["source"],
        )
```

3. Wire into `export_all()` -- add after the existing `export_matchup_matrix` call in the optional exports list. This needs a Labs DB connection. Add a parameter to `export_all()`:

```python
def export_all(
    conn: sqlite3.Connection,
    output_dir: Path,
    *,
    format_slug: str = "",
    strict: bool = False,
    labs_conn: sqlite3.Connection | None = None,
) -> None:
```

Then after the existing matchup matrix export block (~line 3509), add:

```python
    if labs_conn is not None:
        try:
            export_labs_matchup(labs_conn, out)
        except (sqlite3.OperationalError, ValueError) as exc:
            if strict:
                raise
            logger.warning("Skipping Labs matchup export: %s", exc)
            skipped.append("labs matchup")
```

4. Update `cli.py` `export_web` command to pass `labs_conn` to `export_all()`:

```python
# In the export-web command, after getting the format connection:
labs_conn = None
try:
    from labs_db import get_labs_connection, init_labs_db
    labs_conn = get_labs_connection()
    init_labs_db(labs_conn)
except Exception:
    logger.info("No Labs database available, skipping Labs exports")

# Pass to export_all:
export_all(conn, out, format_slug=slug, strict=strict, labs_conn=labs_conn)

# Close labs_conn after export
if labs_conn:
    labs_conn.close()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_json_export.py::TestExportLabsMatchup -v`
Expected: All PASS

- [ ] **Step 6: Run full test suite to check for regressions**

Run: `python -m pytest tests/ -v`
Expected: All existing tests PASS

- [ ] **Step 7: Commit**

```bash
git add reports/json_export.py cli.py tests/conftest.py tests/test_labs.py tests/test_json_export.py
git commit -m "feat: add Labs H2H matchup export to JSON pipeline"
```

---

### Task 3: Add Labs matchup TypeScript types and data loader

**Files:**
- Modify: `web/app/lib/types.ts`
- Modify: `web/app/lib/data.ts`

- [ ] **Step 1: Add TypeScript types**

Add to `web/app/lib/types.ts` after the existing `MatchupMatrixData` interface:

```typescript
export interface ArchetypeMatchupEntry {
  archetype: string;
  win_rate: number;
  sample_size: number;
  ci_lower: number | null;
  ci_upper: number | null;
}

export interface ArchetypeMatchups {
  favorable: ArchetypeMatchupEntry[];
  unfavorable: ArchetypeMatchupEntry[];
}

export interface LabsMatchupData {
  archetypes: string[];
  matrix: (number | null)[][];
  sample_sizes: number[][];
  confidence: { lower: number | null; upper: number | null }[][];
  source: "labs-h2h" | "labs-records";
}
```

- [ ] **Step 2: Add data loader**

Add to `web/app/lib/data.ts` after the existing `getMatchupMatrix()`:

```typescript
export function getLabsMatchup(format: string): LabsMatchupData | null {
  try {
    return readJson(`${format}/matchup-h2h.json`);
  } catch (err) {
    if (isFileNotFound(err)) return null;
    console.error(`Failed to load Labs matchup for ${format}:`, err);
    return null;
  }
}

export function extractArchetypeMatchups(
  data: LabsMatchupData,
  archetype: string,
  topN: number = 5,
): ArchetypeMatchups {
  const idx = data.archetypes.indexOf(archetype);
  if (idx === -1) return { favorable: [], unfavorable: [] };

  const entries: ArchetypeMatchupEntry[] = [];
  for (let j = 0; j < data.archetypes.length; j++) {
    if (j === idx) continue;
    const wr = data.matrix[idx][j];
    if (wr === null) continue;
    entries.push({
      archetype: data.archetypes[j],
      win_rate: wr,
      sample_size: data.sample_sizes[idx][j],
      ci_lower: data.confidence[idx][j].lower,
      ci_upper: data.confidence[idx][j].upper,
    });
  }

  const favorable = entries
    .filter((e) => e.win_rate > 0.5)
    .sort((a, b) => b.win_rate - a.win_rate)
    .slice(0, topN);

  const unfavorable = entries
    .filter((e) => e.win_rate < 0.5)
    .sort((a, b) => a.win_rate - b.win_rate)
    .slice(0, topN);

  return { favorable, unfavorable };
}
```

Add the imports to the import block in `data.ts`:
```typescript
import type { LabsMatchupData, ArchetypeMatchups, ArchetypeMatchupEntry } from "./types";
```

- [ ] **Step 3: Commit**

```bash
git add web/app/lib/types.ts web/app/lib/data.ts
git commit -m "feat: add Labs H2H matchup types and data loader"
```

---

### Task 4: Create ArchetypeMatchups component

**Files:**
- Create: `web/app/components/archetype-matchups.tsx`
- Test: `web/app/components/__tests__/archetype-matchups.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `web/app/components/__tests__/archetype-matchups.test.tsx`:

```typescript
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ArchetypeMatchups } from "../archetype-matchups";
import type { ArchetypeMatchups as ArchetypeMatchupsType } from "@/app/lib/types";

const mockMatchups: ArchetypeMatchupsType = {
  favorable: [
    { archetype: "Gardevoir ex", win_rate: 0.65, sample_size: 42, ci_lower: 0.55, ci_upper: 0.75 },
    { archetype: "Lugia VSTAR", win_rate: 0.58, sample_size: 31, ci_lower: 0.48, ci_upper: 0.68 },
  ],
  unfavorable: [
    { archetype: "Charizard ex", win_rate: 0.38, sample_size: 55, ci_lower: 0.28, ci_upper: 0.48 },
    { archetype: "Raging Bolt ex", win_rate: 0.42, sample_size: 36, ci_lower: 0.32, ci_upper: 0.52 },
  ],
};

describe("ArchetypeMatchups", () => {
  it("renders favorable and unfavorable sections", () => {
    render(<ArchetypeMatchups matchups={mockMatchups} source="labs-h2h" format="ninja-spinner" />);
    expect(screen.getByText("Favorable")).toBeInTheDocument();
    expect(screen.getByText("Unfavorable")).toBeInTheDocument();
  });

  it("displays archetype names", () => {
    render(<ArchetypeMatchups matchups={mockMatchups} source="labs-h2h" format="ninja-spinner" />);
    expect(screen.getByText("Gardevoir ex")).toBeInTheDocument();
    expect(screen.getByText("Charizard ex")).toBeInTheDocument();
  });

  it("displays win rate percentages", () => {
    render(<ArchetypeMatchups matchups={mockMatchups} source="labs-h2h" format="ninja-spinner" />);
    expect(screen.getByText("65%")).toBeInTheDocument();
    expect(screen.getByText("38%")).toBeInTheDocument();
  });

  it("renders nothing when both lists are empty", () => {
    const { container } = render(
      <ArchetypeMatchups matchups={{ favorable: [], unfavorable: [] }} source="labs-h2h" format="ninja-spinner" />
    );
    expect(container.firstChild).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npx vitest run app/components/__tests__/archetype-matchups.test.tsx`
Expected: FAIL - module not found

- [ ] **Step 3: Write the component**

Create `web/app/components/archetype-matchups.tsx`:

```tsx
import Link from "next/link";
import { cn } from "@/app/lib/utils";
import type { ArchetypeMatchups as ArchetypeMatchupsType } from "@/app/lib/types";
import { Tooltip } from "@/app/components/tooltip";

function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function WinRateBar({
  winRate,
  favorable,
}: {
  winRate: number;
  favorable: boolean;
}) {
  // Scale: 50% = 0 width, 100%/0% = full width
  const deviation = Math.abs(winRate - 0.5);
  const widthPct = Math.min(deviation * 200, 100);

  return (
    <div className="w-16 h-1.5 rounded-full bg-surface-700 overflow-hidden">
      <div
        className={cn(
          "h-full rounded-full",
          favorable ? "bg-emerald-500" : "bg-red-500",
        )}
        style={{ width: `${widthPct}%` }}
      />
    </div>
  );
}

function MatchupRow({
  archetype,
  winRate,
  sampleSize,
  ciLower,
  ciUpper,
  favorable,
  format,
}: {
  archetype: string;
  winRate: number;
  sampleSize: number;
  ciLower: number | null;
  ciUpper: number | null;
  favorable: boolean;
  format: string;
}) {
  const pct = Math.round(winRate * 100);
  const ciText =
    ciLower != null && ciUpper != null
      ? `${Math.round(ciLower * 100)}-${Math.round(ciUpper * 100)}%`
      : null;

  return (
    <div className="flex items-center gap-3 py-1.5">
      <Link
        href={`/${format}/archetypes/${slugify(archetype)}`}
        className="text-sm text-surface-200 hover:text-terminal truncate min-w-0 flex-1"
      >
        {archetype}
      </Link>
      <WinRateBar winRate={winRate} favorable={favorable} />
      <Tooltip
        content={
          <>
            {pct}% win rate ({sampleSize} matches)
            {ciText && <>, 95% CI: {ciText}</>}
          </>
        }
      >
        <span
          className={cn(
            "text-sm font-mono tabular-nums w-10 text-right",
            favorable ? "text-emerald-400" : "text-red-400",
          )}
        >
          {pct}%
        </span>
      </Tooltip>
      <span className="text-xs text-surface-500 w-8 text-right">{sampleSize}</span>
    </div>
  );
}

export function ArchetypeMatchups({
  matchups,
  source,
  format,
}: {
  matchups: ArchetypeMatchupsType;
  source: string;
  format: string;
}) {
  if (matchups.favorable.length === 0 && matchups.unfavorable.length === 0) {
    return null;
  }

  const sourceLabel =
    source === "labs-h2h"
      ? "Based on head-to-head match results from international Regionals, Internationals, and Worlds."
      : "Based on win-rate performance comparison within shared tournaments.";

  return (
    <section>
      <h2 className="font-display text-lg font-semibold text-slate-100 mb-1">
        Matchups
      </h2>
      <p className="text-xs text-surface-400 mb-4">{sourceLabel}</p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {matchups.favorable.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-emerald-400 uppercase tracking-wide">
                Favorable
              </span>
              <span className="text-xs text-surface-500">Win %</span>
              <span className="text-xs text-surface-500 ml-auto">N</span>
            </div>
            {matchups.favorable.map((m) => (
              <MatchupRow
                key={m.archetype}
                archetype={m.archetype}
                winRate={m.win_rate}
                sampleSize={m.sample_size}
                ciLower={m.ci_lower}
                ciUpper={m.ci_upper}
                favorable
                format={format}
              />
            ))}
          </div>
        )}

        {matchups.unfavorable.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-red-400 uppercase tracking-wide">
                Unfavorable
              </span>
              <span className="text-xs text-surface-500">Win %</span>
              <span className="text-xs text-surface-500 ml-auto">N</span>
            </div>
            {matchups.unfavorable.map((m) => (
              <MatchupRow
                key={m.archetype}
                archetype={m.archetype}
                winRate={m.win_rate}
                sampleSize={m.sample_size}
                ciLower={m.ci_lower}
                ciUpper={m.ci_upper}
                favorable={false}
                format={format}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npx vitest run app/components/__tests__/archetype-matchups.test.tsx`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add web/app/components/archetype-matchups.tsx web/app/components/__tests__/archetype-matchups.test.tsx
git commit -m "feat: add ArchetypeMatchups component for detail pages"
```

---

### Task 5: Integrate matchup section into archetype detail page

**Files:**
- Modify: `web/app/[format]/archetypes/[slug]/page.tsx`

- [ ] **Step 1: Add matchup data loading and component**

In `web/app/[format]/archetypes/[slug]/page.tsx`:

1. Add imports at top:
```typescript
import { getLabsMatchup, extractArchetypeMatchups } from "@/app/lib/data";
import { ArchetypeMatchups } from "@/app/components/archetype-matchups";
```

2. In the `ArchetypeDetailPage` component, after loading `arch` (line 143), add:
```typescript
  const labsMatchup = getLabsMatchup(format);
  const matchups = labsMatchup
    ? extractArchetypeMatchups(labsMatchup, arch.archetype)
    : null;
```

3. Add the matchup section after the Radar section (after line 211) and before the Decklist section:
```tsx
      {/* Matchups */}
      {matchups && (matchups.favorable.length > 0 || matchups.unfavorable.length > 0) && (
        <ArchetypeMatchups
          matchups={matchups}
          source={labsMatchup!.source}
          format={format}
        />
      )}
```

- [ ] **Step 2: Verify build compiles**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npx next build 2>&1 | tail -20`
Expected: Build succeeds (matchup-h2h.json may not exist yet, but `getLabsMatchup` returns null gracefully)

- [ ] **Step 3: Run frontend tests**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npm test`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add web/app/[format]/archetypes/[slug]/page.tsx
git commit -m "feat: integrate matchup section into archetype detail page"
```

---

### Task 6: End-to-end verification

- [ ] **Step 1: Run full Python test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 2: Run full frontend test suite**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npm test`
Expected: All PASS

- [ ] **Step 3: Test export with Labs data**

If Labs data exists:
```bash
python cli.py --format ninja-spinner export-web
```

Check output includes `matchup-h2h.json`:
```bash
ls -la web/public/data/ninja-spinner/matchup-h2h.json
```

If no Labs data exists yet, verify the export completes without errors (it will skip the Labs export gracefully):
```bash
python cli.py --format ninja-spinner export-web 2>&1 | grep -i labs
```
Expected: "No Labs database available, skipping Labs exports" or similar info message.

- [ ] **Step 4: Scrape a test tournament (optional, requires live data)**

To test with real data, pick a recent international tournament from Limitless:
```bash
python cli.py scrape-labs <TOURNAMENT_ID> <LABS_ID> --max-placements 64
python cli.py labs-matchups --top 10
python cli.py --format ninja-spinner export-web
```

Then verify the archetype detail page renders matchup data by checking the JSON:
```bash
python -c "import json; d=json.load(open('web/public/data/ninja-spinner/matchup-h2h.json')); print(f'{len(d[\"archetypes\"])} archetypes, source={d[\"source\"]}')"
```

- [ ] **Step 5: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address issues found during e2e verification"
```
