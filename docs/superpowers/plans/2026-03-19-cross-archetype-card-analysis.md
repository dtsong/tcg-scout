# Cross-Archetype Card Analysis Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a top-level "Card Analysis" page that aggregates top-4 card performance data across all archetypes in a format, letting users compare which cards overperform in top-4 finishers across different decks.

**Architecture:** A new Python export (`card-analysis.json`) aggregates top4_card_stats from all archetypes into a single file keyed by card name with per-archetype deltas. A Next.js server page loads this JSON at build time and passes it to a client component with archetype filtering, card category filtering, and sort controls. This avoids loading 269 individual archetype JSON files on the client.

**Tech Stack:** Python 3.12+ (export), Next.js 16 / TypeScript (page), Tailwind CSS (styling), vitest + @testing-library/react (tests), pytest (Python tests)

---

## File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `reports/json_export.py` (modify ~line 1500) | New `export_card_analysis()` function |
| Create | `web/public/data/{format}/card-analysis.json` | Pre-aggregated cross-archetype card data |
| Modify | `web/app/lib/types.ts` | New `CardAnalysisEntry` and `CardAnalysisData` types |
| Modify | `web/app/lib/data.ts` | New `getCardAnalysis(format)` loader |
| Create | `web/app/[format]/card-analysis/page.tsx` | Server page (data loading + guard) |
| Create | `web/app/[format]/card-analysis/card-analysis-client.tsx` | Client component (filtering, sorting, rendering) |
| Modify | `web/app/components/nav.tsx:37-44` | Add "Card Analysis" nav link |
| Create | `tests/test_card_analysis_export.py` | Python tests for new export |
| Create | `web/app/[format]/card-analysis/__tests__/card-analysis-client.test.tsx` | Frontend component tests |
| Modify | `web/app/lib/__tests__/data.test.ts` | Test for new data loader |

---

### Task 1: Python Export — `export_card_analysis()`

**Files:**
- Modify: `reports/json_export.py` (add new function after `export_archetypes`)
- Create: `tests/test_card_analysis_export.py`

The export aggregates top4_card_stats across all archetypes into a flat structure:

```json
{
  "cards": [
    {
      "card_name": "Boss's Orders",
      "category": "Trainer",
      "archetypes": [
        {
          "archetype": "Charizard Pidgeot",
          "slug": "charizard-pidgeot",
          "tier": "S",
          "delta_vs_field": 12.5,
          "top4_inclusion_pct": 95.0,
          "field_inclusion_pct": 82.5,
          "avg_copies": 2.8,
          "top4_sample_size": 12
        }
      ],
      "avg_delta": 5.2,
      "archetype_count": 8,
      "max_delta": 12.5,
      "best_archetype": "Charizard Pidgeot"
    }
  ],
  "generated_at": "2026-03-19T..."
}
```

- [ ] **Step 1: Write the failing test**

Create `tests/test_card_analysis_export.py`:

```python
"""Tests for cross-archetype card analysis export."""
import sqlite3
from reports.json_export import export_card_analysis
from db import init_db


def _seed(conn: sqlite3.Connection) -> None:
    """Seed DB with two archetypes, each having top-4 and non-top-4 placements."""
    conn.execute(
        "INSERT INTO tournaments (id, name, date, url) VALUES (1, 'T1', '2026-03-01', 'http://t1')"
    )
    # Archetype A: 4 placements, 2 in top-4
    for i, standing in enumerate([1, 3, 9, 12], start=1):
        conn.execute(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, 1, ?, ?, 'Charizard Pidgeot')",
            (i, standing, f"Player{i}"),
        )
    # Archetype B: 4 placements, 2 in top-4
    for i, standing in enumerate([2, 4, 10, 15], start=5):
        conn.execute(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, 1, ?, ?, 'Lugia Archeops')",
            (i, standing, f"Player{i}"),
        )
    # Boss's Orders in all 8 decks
    for pid in range(1, 9):
        conn.execute(
            "INSERT INTO decklist_cards (placement_id, card_name, count) VALUES (?, 'Boss''s Orders', 2)",
            (pid,),
        )
    # Rare Candy only in top-4 of archetype A
    for pid in [1, 2]:
        conn.execute(
            "INSERT INTO decklist_cards (placement_id, card_name, count) VALUES (?, 'Rare Candy', 3)",
            (pid,),
        )
    # Snapshot + archetype_stats
    conn.execute(
        "INSERT INTO meta_snapshots (id, generated_at, tournament_count, deck_count) "
        "VALUES (1, '2026-03-01', 1, 8)"
    )
    conn.execute(
        "INSERT INTO archetype_stats (snapshot_id, archetype, deck_count, meta_share, tier) "
        "VALUES (1, 'Charizard Pidgeot', 4, 50.0, 'S')"
    )
    conn.execute(
        "INSERT INTO archetype_stats (snapshot_id, archetype, deck_count, meta_share, tier) "
        "VALUES (1, 'Lugia Archeops', 4, 50.0, 'A')"
    )
    conn.commit()


def test_export_card_analysis_returns_cards(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    _seed(conn)

    export_card_analysis(conn, tmp_path)

    import json
    data = json.loads((tmp_path / "card-analysis.json").read_text())
    assert "cards" in data
    assert len(data["cards"]) > 0

    # Boss's Orders should appear with 2 archetypes
    boss = next(c for c in data["cards"] if c["card_name"] == "Boss's Orders")
    assert len(boss["archetypes"]) == 2
    assert boss["archetype_count"] == 2

    # Rare Candy only in Charizard Pidgeot
    candy = next(c for c in data["cards"] if c["card_name"] == "Rare Candy")
    assert len(candy["archetypes"]) == 1
    assert candy["archetypes"][0]["archetype"] == "Charizard Pidgeot"


def test_export_card_analysis_computes_delta(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    _seed(conn)

    export_card_analysis(conn, tmp_path)

    import json
    data = json.loads((tmp_path / "card-analysis.json").read_text())

    # Rare Candy: top4=100% (2/2 top-4 decks), field=50% (2/4 total decks) -> delta = 50
    candy = next(c for c in data["cards"] if c["card_name"] == "Rare Candy")
    arch = candy["archetypes"][0]
    assert arch["delta_vs_field"] == 50.0


def test_export_card_analysis_sorts_by_avg_delta(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    _seed(conn)

    export_card_analysis(conn, tmp_path)

    import json
    data = json.loads((tmp_path / "card-analysis.json").read_text())
    deltas = [c["avg_delta"] for c in data["cards"]]
    assert deltas == sorted(deltas, reverse=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_card_analysis_export.py -v`
Expected: ImportError — `export_card_analysis` does not exist yet.

- [ ] **Step 3: Implement `export_card_analysis` in `reports/json_export.py`**

Add after the `export_archetypes` function (around line 1700). The function:
1. Gets the latest snapshot and archetype tiers
2. Iterates each archetype's placements
3. Computes per-card field inclusion and top-4 inclusion using `_compute_card_stats_for_ids`
4. Aggregates cards across archetypes into a dict keyed by card_name
5. Computes avg_delta, max_delta, best_archetype per card
6. Sorts by avg_delta descending
7. Writes `card-analysis.json`

Also add the call in `export_all()` at the bottom alongside other exports.

```python
def export_card_analysis(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export cross-archetype card analysis aggregating top-4 deltas."""
    snapshot = get_latest_snapshot(conn)
    if not snapshot:
        return

    category_lookup = build_category_lookup(conn)

    # Build archetype tiers from snapshot
    archetype_tiers = {}
    for arch in snapshot["archetypes"]:
        archetype_tiers[arch["archetype"]] = arch["tier"]

    # card_name -> list of per-archetype entries
    card_archetypes: dict[str, list[dict]] = defaultdict(list)

    for arch in snapshot["archetypes"]:
        archetype_name = arch["archetype"]
        placements = conn.execute(
            "SELECT id, standing FROM placements WHERE archetype = ?",
            (archetype_name,),
        ).fetchall()

        placement_ids = [p["id"] for p in placements]
        top4_ids = [p["id"] for p in placements if p["standing"] <= 4]

        if len(placement_ids) < 4 or len(top4_ids) < 2:
            continue

        all_cards = _compute_card_stats_for_ids(conn, placement_ids, category_lookup)
        field_inclusion = {c["card_name"]: c["inclusion_pct"] for c in all_cards}

        top4_cards = _compute_card_stats_for_ids(conn, top4_ids, category_lookup)

        for card in top4_cards:
            field_pct = field_inclusion.get(card["card_name"], 0)
            delta = round(card["inclusion_pct"] - field_pct, 1)
            if delta == 0:
                continue
            card_archetypes[card["card_name"]].append({
                "archetype": archetype_name,
                "slug": _slugify(archetype_name),
                "tier": archetype_tiers.get(archetype_name, "Rogue"),
                "delta_vs_field": delta,
                "top4_inclusion_pct": card["inclusion_pct"],
                "field_inclusion_pct": field_pct,
                "avg_copies": card["avg_copies"],
                "top4_sample_size": len(top4_ids),
            })

        # Field-only cards (negative deltas)
        top4_names = {c["card_name"] for c in top4_cards}
        for card in all_cards:
            if card["card_name"] not in top4_names and card["inclusion_pct"] > 0:
                delta = round(-card["inclusion_pct"], 1)
                card_archetypes[card["card_name"]].append({
                    "archetype": archetype_name,
                    "slug": _slugify(archetype_name),
                    "tier": archetype_tiers.get(archetype_name, "Rogue"),
                    "delta_vs_field": delta,
                    "top4_inclusion_pct": 0,
                    "field_inclusion_pct": card["inclusion_pct"],
                    "avg_copies": 0,
                    "top4_sample_size": len(top4_ids),
                })

    # Aggregate per card
    cards = []
    for card_name, archetypes in card_archetypes.items():
        deltas = [a["delta_vs_field"] for a in archetypes]
        avg_delta = round(sum(deltas) / len(deltas), 1)
        max_entry = max(archetypes, key=lambda a: a["delta_vs_field"])
        cards.append({
            "card_name": card_name,
            "category": classify_card(card_name, category_lookup),
            "archetypes": sorted(archetypes, key=lambda a: a["delta_vs_field"], reverse=True),
            "avg_delta": avg_delta,
            "archetype_count": len(archetypes),
            "max_delta": max_entry["delta_vs_field"],
            "best_archetype": max_entry["archetype"],
        })

    cards.sort(key=lambda c: c["avg_delta"], reverse=True)

    _write_json({"cards": cards, "generated_at": snapshot["generated_at"]}, output_dir / "card-analysis.json")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_card_analysis_export.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Run full Python test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass (no regressions).

- [ ] **Step 6: Commit**

```bash
git add reports/json_export.py tests/test_card_analysis_export.py
git commit -m "feat: add cross-archetype card analysis export"
```

---

### Task 2: TypeScript Types and Data Loader

**Files:**
- Modify: `web/app/lib/types.ts`
- Modify: `web/app/lib/data.ts`
- Modify: `web/app/lib/__tests__/data.test.ts`

- [ ] **Step 1: Add TypeScript types**

In `web/app/lib/types.ts`, add after the `TopPerformerCard` interface:

```typescript
export interface CardAnalysisArchetype {
  archetype: string;
  slug: string;
  tier: Tier;
  delta_vs_field: number;
  top4_inclusion_pct: number;
  field_inclusion_pct: number;
  avg_copies: number;
  top4_sample_size: number;
}

export interface CardAnalysisEntry {
  card_name: string;
  category: "Pokemon" | "Trainer" | "Energy";
  archetypes: CardAnalysisArchetype[];
  avg_delta: number;
  archetype_count: number;
  max_delta: number;
  best_archetype: string;
}

export interface CardAnalysisData {
  cards: CardAnalysisEntry[];
  generated_at: string;
}
```

- [ ] **Step 2: Add data loader**

In `web/app/lib/data.ts`, add the import for the new type and a loader function:

```typescript
// Add to imports at top:
import type { CardAnalysisData } from "./types";

// Add function:
export function getCardAnalysis(format: string): CardAnalysisData | null {
  try {
    return readJson(`${format}/card-analysis.json`);
  } catch (err) {
    if (isFileNotFound(err)) return null;
    console.error(`Failed to load card analysis for ${format}:`, err);
    return null;
  }
}
```

- [ ] **Step 3: Add test for the loader**

In `web/app/lib/__tests__/data.test.ts`, add a test following existing patterns (mocked fs):

```typescript
describe("getCardAnalysis", () => {
  it("returns null when file does not exist", () => {
    vi.mocked(fs.readFileSync).mockImplementation(() => {
      throw Object.assign(new Error("ENOENT"), { code: "ENOENT" });
    });
    expect(getCardAnalysis("test-format")).toBeNull();
  });
});
```

- [ ] **Step 4: Run frontend tests**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npx vitest run`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/app/lib/types.ts web/app/lib/data.ts web/app/lib/__tests__/data.test.ts
git commit -m "feat: add card analysis types and data loader"
```

---

### Task 3: Navigation Tab

**Files:**
- Modify: `web/app/components/nav.tsx:37-44`

- [ ] **Step 1: Add Card Analysis link to nav**

In `web/app/components/nav.tsx`, insert a new link in the `links` array between "Cards" and "Buy List":

```typescript
const links = [
  { href: `/${format}`, label: "Dashboard" },
  { href: `/${format}/archetypes`, label: "Archetypes" },
  { href: `/${format}/cards`, label: "Cards" },
  { href: `/${format}/card-analysis`, label: "Card Analysis" },
  { href: `/${format}/buylist`, label: "Buy List" },
  { href: `/${format}/trends`, label: "Trends" },
  { href: `/${format}/champions`, label: "Champions League" },
];
```

- [ ] **Step 2: Commit**

```bash
git add web/app/components/nav.tsx
git commit -m "feat: add Card Analysis tab to navigation"
```

---

### Task 4: Server Page

**Files:**
- Create: `web/app/[format]/card-analysis/page.tsx`

Follow the pattern from `web/app/[format]/cards/page.tsx`: server component that loads data and delegates to a client component.

- [ ] **Step 1: Create the server page**

```typescript
import { getCardAnalysis, formatHasData } from "@/app/lib/data";
import { CardAnalysisClient } from "./card-analysis-client";
import Link from "next/link";

export default async function CardAnalysisPage({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;

  if (!formatHasData(format)) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">No data available yet for this format.</p>
        <Link href="/" className="mt-4 inline-block text-sm text-accent">Back to formats</Link>
      </div>
    );
  }

  const data = getCardAnalysis(format);

  if (!data || data.cards.length === 0) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">No card analysis data available yet.</p>
        <Link href={`/${format}`} className="mt-4 inline-block text-sm text-accent">Back to dashboard</Link>
      </div>
    );
  }

  return <CardAnalysisClient data={data} format={format} />;
}
```

- [ ] **Step 2: Create a placeholder client component** (so the page compiles)

Create `web/app/[format]/card-analysis/card-analysis-client.tsx`:

```typescript
"use client";

import type { CardAnalysisData } from "@/app/lib/types";

export function CardAnalysisClient({
  data,
  format,
}: {
  data: CardAnalysisData;
  format: string;
}) {
  return (
    <div className="space-y-6">
      <h1 className="font-display text-2xl font-bold text-slate-100">
        Card Analysis
      </h1>
      <p className="text-sm text-surface-400">
        {data.cards.length} cards with top-4 performance data across archetypes.
      </p>
    </div>
  );
}
```

- [ ] **Step 3: Verify build compiles**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npx next build 2>&1 | tail -20`
Expected: Build succeeds (page may 404 without data, but should compile).

- [ ] **Step 4: Commit**

```bash
git add web/app/\[format\]/card-analysis/
git commit -m "feat: add card analysis page skeleton"
```

---

### Task 5: Client Component — Full Implementation

**Files:**
- Modify: `web/app/[format]/card-analysis/card-analysis-client.tsx`
- Create: `web/app/[format]/card-analysis/__tests__/card-analysis-client.test.tsx`

The client component should provide:
- **Category filter buttons** (All / Pokemon / Trainer / Energy) — reuse pattern from `Top4CardStats`
- **Archetype filter** — searchable text input to filter cards by archetype name
- **Sort control** — toggle between "Avg Delta" and "Max Delta"
- **Card table** — each row shows card name, category, avg delta, max delta, best archetype, archetype count
- **Expandable rows** — click a card to see per-archetype breakdown with delta bars

- [ ] **Step 1: Write tests for the client component**

Create `web/app/[format]/card-analysis/__tests__/card-analysis-client.test.tsx`:

```typescript
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CardAnalysisClient } from "../card-analysis-client";
import type { CardAnalysisData } from "@/app/lib/types";

const mockData: CardAnalysisData = {
  cards: [
    {
      card_name: "Boss's Orders",
      category: "Trainer",
      archetypes: [
        { archetype: "Charizard Pidgeot", slug: "charizard-pidgeot", tier: "S", delta_vs_field: 15.0, top4_inclusion_pct: 100, field_inclusion_pct: 85, avg_copies: 2.8, top4_sample_size: 10 },
        { archetype: "Lugia Archeops", slug: "lugia-archeops", tier: "A", delta_vs_field: 8.0, top4_inclusion_pct: 90, field_inclusion_pct: 82, avg_copies: 2.5, top4_sample_size: 6 },
      ],
      avg_delta: 11.5,
      archetype_count: 2,
      max_delta: 15.0,
      best_archetype: "Charizard Pidgeot",
    },
    {
      card_name: "Charizard ex",
      category: "Pokemon",
      archetypes: [
        { archetype: "Charizard Pidgeot", slug: "charizard-pidgeot", tier: "S", delta_vs_field: 20.0, top4_inclusion_pct: 100, field_inclusion_pct: 80, avg_copies: 3, top4_sample_size: 10 },
      ],
      avg_delta: 20.0,
      archetype_count: 1,
      max_delta: 20.0,
      best_archetype: "Charizard Pidgeot",
    },
    {
      card_name: "Basic Fire Energy",
      category: "Energy",
      archetypes: [
        { archetype: "Charizard Pidgeot", slug: "charizard-pidgeot", tier: "S", delta_vs_field: 5.0, top4_inclusion_pct: 100, field_inclusion_pct: 95, avg_copies: 8, top4_sample_size: 10 },
      ],
      avg_delta: 5.0,
      archetype_count: 1,
      max_delta: 5.0,
      best_archetype: "Charizard Pidgeot",
    },
  ],
  generated_at: "2026-03-19T12:00:00",
};

describe("CardAnalysisClient", () => {
  afterEach(cleanup);

  it("renders all cards", () => {
    render(<CardAnalysisClient data={mockData} format="nihil-zero" />);
    expect(screen.getByText("Boss's Orders")).toBeInTheDocument();
    expect(screen.getByText("Charizard ex")).toBeInTheDocument();
    expect(screen.getByText("Basic Fire Energy")).toBeInTheDocument();
  });

  it("filters by category", async () => {
    const user = userEvent.setup();
    render(<CardAnalysisClient data={mockData} format="nihil-zero" />);

    await user.click(screen.getByRole("button", { name: "Pokemon" }));

    expect(screen.getByText("Charizard ex")).toBeInTheDocument();
    expect(screen.queryByText("Boss's Orders")).not.toBeInTheDocument();
    expect(screen.queryByText("Basic Fire Energy")).not.toBeInTheDocument();
  });

  it("shows card count", () => {
    render(<CardAnalysisClient data={mockData} format="nihil-zero" />);
    expect(screen.getByText(/3 cards/)).toBeInTheDocument();
  });

  it("renders empty state gracefully", () => {
    const empty: CardAnalysisData = { cards: [], generated_at: "" };
    render(<CardAnalysisClient data={empty} format="nihil-zero" />);
    expect(screen.getByText("Card Analysis")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npx vitest run app/\[format\]/card-analysis/__tests__/`
Expected: FAIL — placeholder component does not render card names.

- [ ] **Step 3: Implement the full client component**

Replace `card-analysis-client.tsx` with the full implementation. Key design:

- Module-scope `categories` array (same pattern as `top4-card-stats.tsx`)
- `useState` for category filter and search text
- Table with columns: Card Name, Category, Avg Delta, Max Delta, Best Archetype, # Archetypes
- Delta values color-coded (green positive, red negative)
- Clickable rows expand to show per-archetype breakdown with delta bars
- Reuse `DeltaBadge`-style formatting
- Archetype names link to `/{format}/archetypes/{slug}`

```typescript
"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import type { CardAnalysisData, CardAnalysisEntry } from "@/app/lib/types";

type CategoryFilter = "all" | "Pokemon" | "Trainer" | "Energy";
type SortField = "avg_delta" | "max_delta" | "archetype_count";

const categories: { label: string; value: CategoryFilter }[] = [
  { label: "All", value: "all" },
  { label: "Pokemon", value: "Pokemon" },
  { label: "Trainer", value: "Trainer" },
  { label: "Energy", value: "Energy" },
];

function DeltaValue({ delta }: { delta: number }) {
  if (delta === 0) return <span className="text-xs font-mono text-surface-400">0.0</span>;
  const positive = delta > 0;
  return (
    <span className={`text-xs font-mono tabular-nums ${positive ? "text-emerald-400" : "text-red-400"}`}>
      {positive ? "+" : ""}{delta.toFixed(1)}
    </span>
  );
}

function CardRow({
  card,
  format,
  expanded,
  onToggle,
}: {
  card: CardAnalysisEntry;
  format: string;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="border-b border-surface-700 last:border-0">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between gap-4 hover:bg-surface-700/40 transition-colors text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-sm text-slate-300 truncate">{card.card_name}</span>
          <span className="text-[10px] text-surface-500 uppercase">{card.category}</span>
        </div>
        <div className="flex items-center gap-6 shrink-0">
          <div className="text-right w-16">
            <DeltaValue delta={card.avg_delta} />
          </div>
          <div className="text-right w-16">
            <DeltaValue delta={card.max_delta} />
          </div>
          <span className="text-xs text-surface-400 font-mono w-8 text-right">
            {card.archetype_count}
          </span>
        </div>
      </button>
      {expanded && (
        <div className="px-4 pb-3 space-y-1">
          {card.archetypes.map((a) => (
            <div key={a.slug} className="flex items-center justify-between gap-2 py-1.5 px-3 rounded bg-surface-800">
              <Link
                href={`/${format}/archetypes/${a.slug}`}
                className="text-xs text-slate-400 hover:text-accent truncate"
              >
                {a.archetype}
              </Link>
              <div className="flex items-center gap-4 shrink-0">
                <span className="text-[10px] text-surface-500">{a.top4_inclusion_pct.toFixed(0)}% top4</span>
                <span className="text-[10px] text-surface-500">{a.field_inclusion_pct.toFixed(0)}% field</span>
                <span className="w-14 text-right"><DeltaValue delta={a.delta_vs_field} /></span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function CardAnalysisClient({
  data,
  format,
}: {
  data: CardAnalysisData;
  format: string;
}) {
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>("all");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<SortField>("avg_delta");
  const [expandedCard, setExpandedCard] = useState<string | null>(null);

  const filtered = useMemo(() => {
    let cards = data.cards;
    if (categoryFilter !== "all") {
      cards = cards.filter((c) => c.category === categoryFilter);
    }
    if (search) {
      const q = search.toLowerCase();
      cards = cards.filter(
        (c) =>
          c.card_name.toLowerCase().includes(q) ||
          c.best_archetype.toLowerCase().includes(q) ||
          c.archetypes.some((a) => a.archetype.toLowerCase().includes(q)),
      );
    }
    return [...cards].sort((a, b) => {
      if (sortBy === "archetype_count") return b.archetype_count - a.archetype_count;
      return b[sortBy] - a[sortBy];
    });
  }, [data.cards, categoryFilter, search, sortBy]);

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-100">Card Analysis</h1>
          <p className="text-sm text-surface-400 mt-1">
            Top-4 inclusion deltas across archetypes. {filtered.length} cards shown.
          </p>
        </div>
        <div className="flex gap-1 shrink-0">
          {categories.map((cat) => (
            <button
              key={cat.value}
              onClick={() => setCategoryFilter(cat.value)}
              className={`px-2 py-0.5 rounded text-xs transition-colors ${
                categoryFilter === cat.value
                  ? "bg-surface-600 text-slate-200"
                  : "text-surface-400 hover:text-slate-300"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <input
          type="text"
          placeholder="Search cards or archetypes..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="bg-surface-700 border border-surface-600 rounded-md px-3 py-1.5 text-sm text-slate-300 placeholder:text-surface-500 focus:outline-none focus:border-surface-400 w-64"
        />
        <div className="flex gap-1 text-[10px]">
          {(["avg_delta", "max_delta", "archetype_count"] as SortField[]).map((field) => (
            <button
              key={field}
              onClick={() => setSortBy(field)}
              className={`px-2 py-1 rounded transition-colors ${
                sortBy === field ? "bg-surface-600 text-slate-200" : "text-surface-400 hover:text-slate-300"
              }`}
            >
              {field === "avg_delta" ? "Avg Delta" : field === "max_delta" ? "Max Delta" : "# Archetypes"}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
        {/* Header */}
        <div className="px-4 py-2 border-b border-surface-600 flex items-center justify-between">
          <span className="text-[10px] text-surface-500 uppercase tracking-wider">Card</span>
          <div className="flex items-center gap-6">
            <span className="text-[10px] text-surface-500 uppercase tracking-wider w-16 text-right">Avg Delta</span>
            <span className="text-[10px] text-surface-500 uppercase tracking-wider w-16 text-right">Max Delta</span>
            <span className="text-[10px] text-surface-500 uppercase tracking-wider w-8 text-right">Archs</span>
          </div>
        </div>
        {filtered.length === 0 ? (
          <div className="px-4 py-8 text-center text-surface-400 text-sm">No matching cards.</div>
        ) : (
          filtered.map((card) => (
            <CardRow
              key={card.card_name}
              card={card}
              format={format}
              expanded={expandedCard === card.card_name}
              onToggle={() => setExpandedCard(expandedCard === card.card_name ? null : card.card_name)}
            />
          ))
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npx vitest run`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/app/\[format\]/card-analysis/
git commit -m "feat: implement card analysis client with filtering and expandable rows"
```

---

### Task 6: Generate Data and Verify End-to-End

**Files:** None new — this task runs the pipeline and verifies output.

- [ ] **Step 1: Run the export to generate `card-analysis.json`**

Run: `python -c "from db import get_connection; from reports.json_export import export_card_analysis; conn = get_connection(); export_card_analysis(conn, __import__('pathlib').Path('web/public/data/nihil-zero'))"`

Verify: `ls -la web/public/data/nihil-zero/card-analysis.json`
Expected: File exists, non-empty.

- [ ] **Step 2: Inspect the output**

Run: `python -c "import json; d = json.load(open('web/public/data/nihil-zero/card-analysis.json')); print(f'{len(d[\"cards\"])} cards'); print(json.dumps(d['cards'][:2], indent=2))"`
Expected: Shows cards with archetypes, avg_delta, etc.

- [ ] **Step 3: Build and verify**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npx next build 2>&1 | tail -20`
Expected: Build succeeds, `/nihil-zero/card-analysis` page is generated.

- [ ] **Step 4: Commit data**

```bash
git add web/public/data/*/card-analysis.json
git commit -m "data: generate card-analysis.json for all formats"
```

---

### Task 7: Run Full Test Suites

- [ ] **Step 1: Python tests**

Run: `python -m pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 2: Frontend tests**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npx vitest run`
Expected: All tests pass.

- [ ] **Step 3: TypeScript type check**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npx tsc --noEmit`
Expected: No errors.
