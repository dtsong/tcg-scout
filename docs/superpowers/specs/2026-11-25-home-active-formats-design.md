# Home page: active formats first, archive section (design)

Status: approved by the owner on 2026-11-25. Size: small change.

## Intent

The home page lists all 8 formats in `config.FORMATS` order, so the two oldest JP formats come first and the live format is 4th.
The owner wants the page to focus on the active formats and to show archived formats in a separate section.

## Goals

- Active formats appear first, as full cards with the strong accent.
- Upcoming formats appear in the active section as dimmed cards that are not links.
- Archived (frozen) formats appear in their own section as compact rows, newest `dataset_end` first.
- `getFormats()` returns formats in this order: active, upcoming, frozen (frozen by `dataset_end` desc). The nav dropdowns use the same order.

## Non-goals

- The card-analysis "why" work. It needs export changes and gets its own session.
- A JP vs TPCi filter.

## Anti-goals

- The archive must stay visible without a click (no tabs, no collapsed panel).

## Approaches

| Approach | Trade-off | Decision |
|---|---|---|
| Two sections: active cards, archive rows | Clear focus, archive still one scroll away | Picked |
| Tabs (Active / Archive) | Hides the archive behind a click | Rejected |
| One large hero card for the active format | With 2 active formats, the second one looks hidden | Rejected |

## Design

- `web/app/lib/data.ts`: `getFormats()` sorts with a pure, exported `sortFormats()`. Status rank: active 0, upcoming 1, frozen 2. Within frozen, `dataset_end` desc. Within active and upcoming, keep the file order (stable sort).
- `web/app/page.tsx`:
  - "Active formats" section: cards for status `active` and `upcoming`.
  - "Archived formats" section: one compact row per frozen format with name, `name_en`, date range, tournament and deck counts, and a link.
  - Card style comes from status, not from a hard-coded slug map.
  - Upcoming cards render as a `div`, not a `Link` to `#`.
  - Oak copy mentions TPCi as well as Japan's City League.
- Tests: vitest for `sortFormats()`, and a render test for the two sections.

## Left to the builder

- Exact Tailwind classes, following the existing surface/accent tokens.
- The date format in archive rows.
