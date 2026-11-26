# Home Page Active Formats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The home page shows active and upcoming formats first, and frozen formats in a separate "Archived formats" section.

**Architecture:** A pure `sortFormats()` in `data.ts` sets one order for every `getFormats()` consumer. The home page renders through a new presentational component, so the two sections can be unit-tested without the fs mock.

**Tech Stack:** Next.js 16 (static export), Tailwind CSS, vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-11-25-home-active-formats-design.md`

## Global Constraints

- No em dashes in UI text, comments, or commit messages.
- Status rank: active 0, upcoming 1, frozen 2. Frozen sorts by `dataset_end` desc. Active and upcoming keep file order.
- Use the existing surface/accent Tailwind tokens. No new colors.
- Upcoming formats are not links.
- Node commands: `source ~/.nvm/nvm.sh && nvm use default --silent && <cmd>`, run from `web/`.

## Review Focus

- No active formats (between seasons): the active section shows only upcoming cards, or a one-line empty state if there are none. Test in Task 2.
- No frozen formats: the "Archived formats" heading does not render. Test in Task 2.
- A frozen format with `tournament_count` 0 or missing: the row still renders and shows "0 tournaments", not "undefined". Test in Task 2.
- `getFormats()` must not mutate the parsed array in place across calls: `sortFormats` returns a new array. Test in Task 1.
- `getDefaultFormat()` keeps its current results after the sort. The existing `getDefaultFormat` tests must still pass in Task 1.

---

### Task 1: Sort formats in `getFormats()`

**Files:**
- Modify: `web/app/lib/data.ts:90-92`
- Test: `web/app/lib/__tests__/data.test.ts` (extend `describe("getFormats")`)

**Interfaces:**
- Produces: `export function sortFormats(formats: FormatInfo[]): FormatInfo[]` in `web/app/lib/data.ts`. `getFormats()` returns `sortFormats(readRootJson("formats.json"))`.

- [ ] **Step 1: Write the failing tests** in `data.test.ts`:
  - `it("orders active, then upcoming, then frozen by dataset_end desc")`: input slugs in this order with these statuses and ends: `old` frozen 2026-03-13, `up` upcoming 2027-09-03, `live` active 2026-12-10, `mid` frozen 2026-08-13, `older` frozen 2025-09-11. Assert `getFormats().map(f => f.slug)` equals `["live", "up", "mid", "old", "older"]`.
  - `it("keeps file order within active formats")`: two active formats `b` then `a`. Assert order `["b", "a"]`.
  - `it("sortFormats returns a new array")`: `const input = [...]; const out = sortFormats(input); expect(out).not.toBe(input); expect(input.map(f => f.slug)).toEqual(<original order>)`.
- [ ] **Step 2: Run and confirm failure.** `npx vitest run app/lib/__tests__/data.test.ts`. Expected: FAIL, `sortFormats` is not exported and the order test fails.
- [ ] **Step 3: Implement `sortFormats`** with `[...formats].sort(...)` (stable in V8). Compare status rank first. For two frozen formats, compare `b.dataset_end.localeCompare(a.dataset_end)`. Otherwise return 0. Simplify `getDefaultFormat()` only if it stays correct; its existing tests are the guard.
- [ ] **Step 4: Run and confirm pass.** Same command. Expected: all `getFormats` and `getDefaultFormat` tests PASS.
- [ ] **Step 5: Commit.** `git add web/app/lib/data.ts web/app/lib/__tests__/data.test.ts docs/superpowers/specs/2026-11-25-home-active-formats-design.md docs/superpowers/plans/2026-11-25-home-active-formats.md && git commit -m "feat(web): order formats active, upcoming, then archived"`

### Task 2: Home page sections

**Files:**
- Create: `web/app/components/home-format-sections.tsx`
- Modify: `web/app/page.tsx` (replace the format grid at lines 89-185, remove `FORMAT_STYLES` and `DEFAULT_STYLE`, update the Oak copy)
- Test: `web/app/components/__tests__/home-format-sections.test.tsx`

**Interfaces:**
- Consumes: `getFormats()` from Task 1 (already sorted).
- Produces: `export function HomeFormatSections({ formats }: { formats: FormatInfo[] })`. It renders two `<section>` elements:
  - `aria-labelledby="active-formats-heading"`, heading text "Active formats": a card grid for status `active` and `upcoming`.
  - `aria-labelledby="archived-formats-heading"`, heading text "Archived formats": one compact row per `frozen` format.
- Move `formatFreshness` from `page.tsx` into this file.

- [ ] **Step 1: Write the failing tests.** Mock `next/link` as in `app/[format]/__tests__/dashboard-client.test.tsx`. Cases:
  - `it("puts active and upcoming formats in the active section")`: formats `live` active, `up` upcoming, `old` frozen. `within(getByRole("region", { name: "Active formats" }))` contains "Live" and "Up" names, not "Old".
  - `it("lists frozen formats as links in the archive section")`: the archive region contains a link with `href="/old"` and the text `430 tournaments`.
  - `it("does not link upcoming formats")`: `queryByRole("link", { name: /Up/ })` is null.
  - `it("hides the archive section when no format is frozen")`: `queryByRole("region", { name: "Archived formats" })` is null.
  - `it("shows an empty state when no format is active or upcoming")`: the active region contains the text "No active formats right now".
  - `it("shows 0 tournaments when the count is missing")`: frozen format without `tournament_count` renders `0 tournaments`.
- [ ] **Step 2: Run and confirm failure.** `npx vitest run app/components/__tests__/home-format-sections.test.tsx`. Expected: FAIL, module not found.
- [ ] **Step 3: Implement `HomeFormatSections`.**
  - Active cards: keep the current card layout (status badge, `name`, `name_en`, `description`, stats, freshness). Active cards use the `text-accent` heading and the accent badge. Upcoming cards render as a `div` with `opacity-60`, a "Coming Soon" badge, and "First results expected after {dataset_start}".
  - Archive rows: one `Link` per row in a single bordered `bg-surface-800` list. Show `name`, `name_en`, the date range, `{n} tournaments`, `{n} decks`, and a `ChevronRight`. Format dates with `toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" })`.
- [ ] **Step 4: Wire it into `page.tsx`.** Replace the grid with `<HomeFormatSections formats={formats} />`. Change the second Oak line to: "I'm here to help you explore the Japanese City League and TPCi metas."
- [ ] **Step 5: Run and confirm pass.** Same vitest command. Expected: 6 PASS.
- [ ] **Step 6: Full verification.** From `web/`: `npx tsc --noEmit && npx eslint . --quiet && npm test`. Expected: no errors, all tests pass.
- [ ] **Step 7: Visual check.** Run `npm run dev` and load `/` at 375 px and 1280 px wide. Confirm Storm Emeralda is first and the archive is a compact list. Local `public/data` is stale (Storm Emeralda shows "upcoming"), so refresh it first with `uv run scout --format storm-emeralda export-web` from the repo root, or note the stale status.
- [ ] **Step 8: Commit.** `git add web/app/components/home-format-sections.tsx web/app/components/__tests__/home-format-sections.test.tsx web/app/page.tsx && git commit -m "feat(web): focus the home page on active formats"`
