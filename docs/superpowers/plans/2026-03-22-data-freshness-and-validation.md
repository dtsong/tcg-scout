# Data Freshness, Validation & Format Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CI export validation that prevents regressions, surface data freshness timestamps to users, and communicate Nihil Zero's completed format status clearly.

**Architecture:** Three independent changes: (1) enhance `validation.py` and `prebuild.mjs` to catch missing/stale data before deploy, (2) add `generated_at` to `FormatInfo` and display relative timestamps on format cards, (3) replace "Frozen" badge with "Complete" messaging and a contextual description.

**Tech Stack:** Python (validation.py), Node.js (prebuild.mjs), Next.js/React (page.tsx, nav.tsx), vitest, pytest

---

### Task 1: Add `generated_at` to formats.json export

The Python export writes `formats.json` but doesn't include per-format `generated_at`. We need it so the frontend can show freshness.

**Files:**
- Modify: `reports/json_export.py:3240-3300` (the `export_formats` function)
- Modify: `web/app/lib/types.ts:5-15` (`FormatInfo` interface)
- Test: `tests/test_data_contracts.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_data_contracts.py`, add a test that verifies `formats.json` entries include `generated_at`:

```python
def test_formats_json_includes_generated_at(self, export_dir):
    """formats.json entries should include generated_at from meta.json."""
    formats_path = export_dir / "formats.json"
    assert formats_path.exists()
    formats = json.loads(formats_path.read_text())
    for fmt in formats:
        if fmt["status"] in ("active", "frozen"):
            assert "generated_at" in fmt, f"{fmt['slug']} missing generated_at"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_data_contracts.py::TestDataContracts::test_formats_json_includes_generated_at -v`
Expected: FAIL - `generated_at` not in format entry

- [ ] **Step 3: Add `generated_at` to `export_formats`**

In `reports/json_export.py`, find the `export_formats` function. It builds a list of format entries. After setting `tournament_count` and `deck_count` from `meta.json`, also read `generated_at`:

```python
# After reading meta.json stats, add:
entry["generated_at"] = meta_data.get("generated_at", "")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_data_contracts.py::TestDataContracts::test_formats_json_includes_generated_at -v`
Expected: PASS

- [ ] **Step 5: Update TypeScript `FormatInfo` type**

In `web/app/lib/types.ts`, add to `FormatInfo`:

```typescript
export interface FormatInfo {
  slug: string;
  name: string;
  name_en: string;
  description: string;
  dataset_start: string;
  dataset_end: string;
  status: "active" | "frozen" | "upcoming";
  tournament_count?: number;
  deck_count?: number;
  generated_at?: string;  // ISO timestamp from last export
}
```

- [ ] **Step 6: Commit**

```bash
git add reports/json_export.py web/app/lib/types.ts tests/test_data_contracts.py
git commit -m "feat: include generated_at in formats.json for freshness display"
```

---

### Task 2: Display data freshness on format selector page

Show "Updated X hours ago" on active format cards and "Final dataset" on frozen formats.

**Files:**
- Modify: `web/app/page.tsx:78-155` (format card rendering)
- Test: `web/app/__tests__/page.test.tsx` (create if needed, or add to existing)

- [ ] **Step 1: Write the failing test**

Create or update a vitest test that checks the format selector renders freshness text:

```typescript
// In web/app/__tests__/format-selector.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock data module
vi.mock("@/app/lib/data", () => ({
  getFormats: () => [
    {
      slug: "ninja-spinner",
      name: "Ninja Spinner",
      name_en: "Chaos Rising",
      description: "Test format",
      dataset_start: "2026-03-14",
      dataset_end: "2026-05-22",
      status: "active" as const,
      tournament_count: 168,
      deck_count: 2432,
      generated_at: new Date(Date.now() - 3 * 3600_000).toISOString(),
    },
    {
      slug: "nihil-zero",
      name: "Nihil Zero",
      name_en: "Perfect Order",
      description: "Test frozen",
      dataset_start: "2026-01-23",
      dataset_end: "2026-03-13",
      status: "frozen" as const,
      tournament_count: 430,
      deck_count: 6756,
      generated_at: "2026-03-13T09:00:00Z",
    },
  ],
}));

describe("FormatSelectorPage", () => {
  it("shows relative freshness for active formats", async () => {
    const Page = (await import("@/app/page")).default;
    render(<Page />);
    expect(screen.getByText(/Updated \d+h ago/)).toBeTruthy();
  });

  it("shows 'Complete' instead of 'Frozen' for frozen formats", async () => {
    const Page = (await import("@/app/page")).default;
    render(<Page />);
    expect(screen.getByText("Complete")).toBeTruthy();
    expect(screen.queryByText("Frozen")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npx vitest run app/__tests__/format-selector.test.tsx`
Expected: FAIL - "Frozen" is rendered, no freshness text

- [ ] **Step 3: Add freshness helper and update format cards**

In `web/app/page.tsx`, add a helper function and update the card rendering:

```typescript
function formatFreshness(generatedAt?: string, status?: string): string | null {
  if (!generatedAt) return null;
  if (status === "frozen") return null; // Frozen formats use "Complete" badge instead
  const ms = Date.now() - new Date(generatedAt).getTime();
  const hours = Math.floor(ms / 3_600_000);
  if (hours < 1) return "Updated just now";
  if (hours < 24) return `Updated ${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `Updated ${days}d ago`;
}
```

In the format card JSX, replace the status badge text:
- Change `{isFrozen ? "Frozen" : fmt.status === "active" ? "Active" : "Coming Soon"}` to `{isFrozen ? "Complete" : fmt.status === "active" ? "Active" : "Coming Soon"}`

Add freshness indicator below the stats section for active formats:
```tsx
{fmt.status === "active" && fmt.generated_at && (
  <p className="text-[10px] text-surface-400 mt-2">
    {formatFreshness(fmt.generated_at, fmt.status)}
  </p>
)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npx vitest run app/__tests__/format-selector.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/app/page.tsx web/app/__tests__/format-selector.test.tsx
git commit -m "feat: show data freshness on format cards and Complete badge for frozen formats"
```

---

### Task 3: Nihil Zero "Complete Record" messaging

Add a contextual description for frozen formats explaining they are complete historical records.

**Files:**
- Modify: `web/app/page.tsx:78-155` (format card, add description line for frozen)
- Modify: `web/app/[format]/dashboard-client.tsx:95-115` (hero section, frozen-aware copy)
- Test: update `web/app/__tests__/format-selector.test.tsx`

- [ ] **Step 1: Write the failing test**

Add to the format-selector test:

```typescript
it("shows completed format context for frozen formats", async () => {
  const Page = (await import("@/app/page")).default;
  render(<Page />);
  expect(screen.getByText(/complete competitive record/i)).toBeTruthy();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npx vitest run app/__tests__/format-selector.test.tsx`
Expected: FAIL

- [ ] **Step 3: Add frozen format context to format cards**

In `web/app/page.tsx`, in the stats section of frozen format cards, add a contextual line after the tournament/deck counts:

```tsx
{isFrozen && (
  <p className="text-[10px] text-surface-400 mt-2">
    Complete competitive record -- format has concluded
  </p>
)}
```

- [ ] **Step 4: Update dashboard hero for frozen formats**

In `web/app/[format]/dashboard-client.tsx`, update the hero description (around line 100-103) to be format-status-aware. The `DashboardClient` component doesn't currently know if the format is frozen. Pass format status info through:

In `web/app/[format]/page.tsx`, pass the format list to DashboardClient so it can determine frozen status. Or simpler: check if `meta.date_range.end < today` to determine frozen status, since the dashboard already has meta.

Update the hero text around line 100-103:
```tsx
const isFrozen = new Date(meta.date_range.end) < new Date();
// ...
<p className="text-sm text-surface-300 max-w-xl">
  <span className="text-slate-200 font-medium">{formatName}</span>{" "}
  {isFrozen
    ? "is a completed format. This is the final competitive record from Japan's City Leagues."
    : <>is Japan&apos;s post-rotation format. {rotationDays > 0
        ? `These results preview the Standard meta. Set legal internationally on ${meta.rotation_date}.`
        : "This set is now legal internationally."}</>
  }
</p>
```

- [ ] **Step 5: Run tests**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npx vitest run`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add web/app/page.tsx web/app/[format]/dashboard-client.tsx web/app/__tests__/format-selector.test.tsx
git commit -m "feat: add completed format messaging for Nihil Zero"
```

---

### Task 4: Enhance prebuild validation

Make `prebuild.mjs` validate that each format with data has its core files. This catches the exact bug class that broke optimal-60.

**Files:**
- Modify: `web/scripts/prebuild.mjs`
- Test: manual verification via `node web/scripts/prebuild.mjs`

- [ ] **Step 1: Enhance prebuild.mjs**

Replace the current prebuild script with one that validates each format's required files:

```javascript
#!/usr/bin/env node
/**
 * Prebuild step: verify JSON data exists and is complete for all formats.
 * Catches missing files before they become broken pages in production.
 */
import fs from "fs";
import path from "path";

const DATA_DIR = path.resolve(import.meta.dirname, "..", "public", "data");
const formatsPath = path.join(DATA_DIR, "formats.json");

if (!fs.existsSync(formatsPath)) {
  console.error(
    "prebuild: FATAL - No data found at public/data/formats.json.\n" +
      "  Data should be committed to git by Cloud Build.\n" +
      "  For local development, run: python cli.py --format <format> export-web",
  );
  process.exit(1);
}

const formats = JSON.parse(fs.readFileSync(formatsPath, "utf-8"));
const REQUIRED_FILES = [
  "meta.json",
  "buylist.json",
  "staples.json",
  "flex.json",
  "trends.json",
  "winning-edge.json",
];

let errors = 0;

for (const fmt of formats) {
  if (fmt.status === "upcoming") continue;

  const fmtDir = path.join(DATA_DIR, fmt.slug);
  for (const file of REQUIRED_FILES) {
    const filePath = path.join(fmtDir, file);
    if (!fs.existsSync(filePath)) {
      console.error(`prebuild: MISSING ${fmt.slug}/${file}`);
      errors++;
    }
  }

  // Check archetypes directory is non-empty
  const archDir = path.join(fmtDir, "archetypes");
  if (!fs.existsSync(archDir) || fs.readdirSync(archDir).length === 0) {
    console.error(`prebuild: MISSING ${fmt.slug}/archetypes/ (empty or absent)`);
    errors++;
  }
}

if (errors > 0) {
  console.error(`\nprebuild: FATAL - ${errors} missing file(s) detected. Aborting build.`);
  process.exit(1);
}

console.log(`prebuild: All ${formats.filter((f) => f.status !== "upcoming").length} format(s) validated`);
```

- [ ] **Step 2: Test locally**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && node scripts/prebuild.mjs`
Expected: "prebuild: All 2 format(s) validated"

- [ ] **Step 3: Commit**

```bash
git add web/scripts/prebuild.mjs
git commit -m "feat: prebuild validates all format data files exist before build"
```

---

### Task 5: Add `optimal-60` and `card-decklists` to export validation

The validation.py `REQUIRED_FILES` list doesn't include optional-but-expected directories. Add them as warnings so the pipeline surfaces missing data.

**Files:**
- Modify: `validation.py:16-27` (add optional directory checks)
- Test: `tests/test_validation.py`

- [ ] **Step 1: Write the failing test**

```python
def test_validate_warns_on_missing_optional_dirs(tmp_path):
    """validate_export should warn when expected optional dirs are missing."""
    from validation import validate_export
    # Create minimal valid export
    export_dir = tmp_path / "test-format"
    export_dir.mkdir()
    (export_dir / "meta.json").write_text('{"archetypes": [{"archetype": "Test", "slug": "test", "tier": "S", "meta_share": 20}]}')
    for f in ["buylist.json", "staples.json", "flex.json", "trends.json", "winning-edge.json"]:
        (export_dir / f).write_text("[]")
    (export_dir / "archetypes").mkdir()
    (export_dir / "archetypes" / "test.json").write_text("{}")

    result = validate_export(export_dir)
    # Should warn about missing optional dirs
    optional_warnings = [w for w in result.warnings if "optimal-60" in w or "card-decklists" in w]
    assert len(optional_warnings) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_validation.py::test_validate_warns_on_missing_optional_dirs -v`
Expected: FAIL

- [ ] **Step 3: Add optional directory warnings to validation.py**

In `validation.py`, after the required directory checks, add:

```python
# Optional directories -- warn if missing (catch accidental deletions)
OPTIONAL_DIRS = ["optimal-60", "card-decklists"]

# Inside validate_export, after required dir checks:
for dirname in OPTIONAL_DIRS:
    dirpath = export_dir / dirname
    if not dirpath.is_dir():
        result.warnings.append(f"Optional directory missing: {dirname}")
    elif not any(dirpath.iterdir()):
        result.warnings.append(f"Optional directory is empty: {dirname}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_validation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add validation.py tests/test_validation.py
git commit -m "feat: validation warns on missing optional data directories"
```

---

### Task 6: Update nav format switcher for frozen status

The nav dropdown doesn't show format status (except "Soon" for upcoming). Add a subtle "Complete" indicator.

**Files:**
- Modify: `web/app/components/nav.tsx:183-213` (format dropdown)

- [ ] **Step 1: Update nav format dropdown**

In `web/app/components/nav.tsx`, in the format dropdown (around line 199-203), add a "Complete" badge for frozen formats alongside the existing "Soon" badge:

```tsx
{f.status === "upcoming" && (
  <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-600 text-surface-400">
    Soon
  </span>
)}
{f.status === "frozen" && (
  <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-600 text-surface-400">
    Complete
  </span>
)}
```

- [ ] **Step 2: Run all frontend tests**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npm test`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add web/app/components/nav.tsx
git commit -m "feat: show Complete badge in nav format switcher for frozen formats"
```

---

### Task 7: Regenerate formats.json and verify end-to-end

Re-export formats.json so it includes the new `generated_at` field, then run the full build.

**Files:**
- Modify: `web/public/data/formats.json` (via re-export)

- [ ] **Step 1: Re-export formats.json**

Run: `python -c "from reports.json_export import export_formats; export_formats()"`

- [ ] **Step 2: Verify formats.json has generated_at**

Run: `cat web/public/data/formats.json | python -m json.tool`
Expected: Each format entry with status != "upcoming" has a `generated_at` field

- [ ] **Step 3: Run prebuild validation**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && node scripts/prebuild.mjs`
Expected: "prebuild: All 2 format(s) validated"

- [ ] **Step 4: Run full test suites**

Run: `python -m pytest tests/ -v && cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npm test`
Expected: All tests pass

- [ ] **Step 5: Build the site**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 6: Commit data and final changes**

```bash
git add web/public/data/formats.json
git commit -m "data: regenerate formats.json with generated_at timestamps"
```

---

## Verification

After all tasks are complete:

1. **Python tests**: `python -m pytest tests/ -v` -- all pass
2. **Frontend tests**: `cd web && npm test` -- all pass
3. **Prebuild check**: `node web/scripts/prebuild.mjs` -- validates all formats
4. **Build**: `cd web && npm run build` -- succeeds
5. **Visual check**: Verify format cards show "Complete" badge (not "Frozen"), freshness text on active format, and contextual description on frozen format
