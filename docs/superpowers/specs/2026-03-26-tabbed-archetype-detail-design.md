# Tabbed Archetype Detail Page

**Issue:** #116
**Date:** 2026-03-26

## Problem

The archetype detail page has 9 vertically stacked sections requiring heavy scrolling. Users must scroll past irrelevant sections to reach the ones they need.

## Solution

Replace the single vertical scroll with a tabbed layout. Header stays above tabs (always visible), content organized into 4 tabs.

## Tab Mapping

| Tab | Components | Default |
|-----|-----------|---------|
| Overview | PerformanceTrendline, VariantBreakdown, ArchetypeRadar, KeyMatchups | Yes |
| Decklist | DeckColumn x3, Top4CardStats | |
| Matchups | KeyMatchups (full view) | |
| Results | EvolutionTimeline, ResultsTable | |

## Architecture

### Server component (`page.tsx`)
- Fetches all data (archetype, matchups, reports, optimal60 index)
- Generates metadata
- Passes everything to `<ArchetypeDetailClient>`

### Client component (`archetype-detail-client.tsx`)
- Receives all data as props
- Manages tab state via `useSearchParams` (`?tab=overview|decklist|matchups|results`)
- Renders header (tier badge, sprites, name, stat cards, action links) above tabs
- Renders active tab content below tab bar
- Default tab: overview (omitted from URL)
- Invalid tab values fall back to overview

### Reusable tab bar (`components/tabs.tsx`)
- Matches existing buylist/champions pattern: `border-b-2 border-accent` active style
- Props: `tabs: {id, label}[]`, `activeTab: string`, `onTabChange: (id) => void`
- Mobile: `overflow-x-auto` horizontal scroll

## URL State

- `?tab=overview` -- default, omitted from URL
- `?tab=decklist`, `?tab=matchups`, `?tab=results`
- Tab changes use `router.replace` with shallow navigation
- Back/forward button navigates between tabs

## Files

| File | Action |
|------|--------|
| `web/app/[format]/archetypes/[slug]/page.tsx` | Refactor: data fetching only, render `<ArchetypeDetailClient>` |
| `web/app/[format]/archetypes/[slug]/archetype-detail-client.tsx` | New: client wrapper with tab state |
| `web/app/components/tabs.tsx` | New: reusable tab bar |
| Existing section components | No changes needed |

## Testing

- `tabs.test.tsx` -- renders tabs, highlights active, fires onChange
- `archetype-detail-client.test.tsx` -- renders correct tab content, URL param sync, default/invalid fallback
