# How Scout Works Guide

**Date:** 2026-03-20
**Status:** Draft

## Problem

Scout's educational content is fragmented across a dismissible welcome modal, scattered tooltips, a blog post, and brief page headers. No single place explains how the analytics tools connect or how to interpret key metrics like winning edge, trend delta, or weighted share. New visitors don't know where to start, and returning users miss value because they don't understand what the numbers mean.

## Solution

A dedicated `/guide` page that explains Scout through player goals, plus contextual one-liner subtitles on each existing page that link into the guide.

## Guide Page Structure

Route: `/guide` (top-level, not format-scoped)

### Section 1: "What are you trying to do?"

4-5 scenario cards at the top, each 2-3 sentences directing users to the right tools:

| Scenario | Tools | Description |
|----------|-------|-------------|
| Pick a deck for this weekend | Dashboard + Buy List | Check the tier list for what's performing, then use the buy list to see what cards you need |
| Find cards that actually win | Format Edge | See which cards are overrepresented in 1st-place decks compared to the overall field |
| Track what's changing in the meta | Trends + Dashboard | Identify surging and declining cards, spot format shifts early |
| Scout a matchup | Archetypes + Matchup Matrix | Check head-to-head performance and card overlap between two decks |
| Study winning decklists | Champions League | Browse full translated decklists from Japan's premier events |

Each scenario card links to the relevant tool section(s) below via anchor.

### Section 2: "Your tools"

One collapsible section per Scout page. First section (Dashboard) open by default, rest collapsed. Each section covers:
- What the page shows
- How to read the key metrics (with concrete examples)
- When to use it

**Dashboard (#dashboard)**
- Tier list: S (15%+), A (8%+), B (3%+), C (1%+), Rogue (<1%) by meta share
- Weighted share: placements weighted by finish position (1st = 3x, 2nd = 2.5x, etc.) so winning decks rank higher
- Surging/Declining cards: change in usage between first and second half of the time window
- Winning Edge cards: difference between a card's inclusion rate in 1st-place decks vs. all S/A/B-tier decks
- ACE SPEC distribution: percentage of all decks running each ACE SPEC

**Archetypes (#archetypes)**
- Browse all detected archetypes with meta share and trend
- Performance Advantage Matrix: average standing difference when two archetypes appear in the same tournament. +2.0 means the row archetype finishes 2 places better on average. Minimum 10 shared tournaments.
- Card Overlap Matrix: Jaccard similarity of core card pools (cards in 30%+ of decks). Higher = more shared staples.
- Archetype detail pages: core cards, inclusion rates, tournament results

**Format Edge (#format-edge)**
- Ranks cards by how much more often they appear in 1st-place decks than the overall field
- Example: if a card is in 52% of 1st-place decks but 29% of all decks, that's a +23 point edge
- Avg Edge: average across all archetypes the card appears in. Best Edge: highest single-archetype edge.
- A high edge means the card is contributing to wins beyond what its play rate predicts

**Buy List (#buy-list)**
- Priority-scored card list across S/A/B tier archetypes
- Staples tab: cards that appear across many top decks
- Flex tab: cards specific to certain archetypes but high-impact

**Trends (#trends)**
- Surging cards: biggest usage increases between early and late halves of the time window
- Declining cards: biggest usage decreases
- Trend delta: the percentage point change (e.g., +23% means 23 points more decks are playing this card recently)
- Time window filters: 7-day, 30-day, or full format

**Champions League (#champions-league)**
- Full decklists from Japan's largest events
- Division tabs: Juniors, Seniors, Masters
- Translated card names

### Section 3: Metric Glossary (#glossary)

Compact reference table at the bottom with anchor IDs for deep-linking.

| Metric | Definition | Found on |
|--------|-----------|----------|
| Meta share | Percentage of total decks playing this archetype | Dashboard, Archetypes |
| Weighted share | Meta share with placements weighted by finish (1st=3x, 2nd=2.5x, 3rd-4th=2x, 5th-8th=1.5x, 9th-16th=1.2x, 17th+=1x) | Dashboard, Archetype detail |
| Winning edge | Difference between a card's inclusion rate in 1st-place decks vs. all S/A/B decks. +11 means 11 percentage points more common in winners. | Dashboard, Trends, Format Edge |
| Trend delta | Change in archetype meta share between early and late halves of the time window | Dashboard, Archetypes |
| Surging/Declining | Change in card usage between early and late halves of the time window | Dashboard, Trends |
| Performance advantage | Average standing difference when two archetypes meet in the same tournament | Archetypes (matrix) |
| Card overlap | Jaccard similarity of core card pools (cards in 30%+ of decks) | Archetypes (matrix) |
| Avg/Best edge | Average and maximum winning edge across all archetypes a card appears in | Format Edge |

## Contextual Subtitles

Each existing page gets a one-line description under its `<h1>` with a link to the guide:

| Page | Subtitle | Link |
|------|----------|------|
| Dashboard | Your meta overview: tier list, key signals, and weekly movement. | /guide#dashboard |
| Archetypes | Every deck in the format with matchups, cards, and results. | /guide#archetypes |
| Format Edge | Cards that win more than they're played. | /guide#format-edge |
| Buy List | Priority-ranked cards across top-tier decks. | /guide#buy-list |
| Trends | What's rising and falling in card usage. | /guide#trends |
| Champions League | Full decklists from Japan's premier events. | /guide#champions-league |

Format: `<p>Subtitle text. <Link href="/guide#section">How this works →</Link></p>`

## Nav Update

Add "Guide" link to the nav component. Since it is not format-scoped, it sits alongside the blog link as a top-level route, not inside the format nav items.

## Welcome Guide Update

Add a final line to the existing dismissible welcome modal: "For a full walkthrough, see the Guide." with a link to `/guide`. No other changes to the modal.

## Implementation Details

### Files to create
- `web/app/guide/page.tsx` -- Guide page with static metadata and content
- `web/app/guide/layout.tsx` -- Layout with nav (same pattern as blog/layout.tsx)
- `web/app/guide/guide-client.tsx` -- Client component for collapsible accordion sections
- `web/app/guide/__tests__/guide-client.test.tsx` -- Tests for guide page

### Files to modify
- `web/app/components/nav.tsx` -- Add "Guide" link
- `web/app/components/welcome-guide.tsx` -- Add guide link at the bottom
- `web/app/[format]/dashboard-client.tsx` -- Add contextual subtitle
- `web/app/[format]/archetypes/archetypes-client.tsx` -- Add contextual subtitle
- `web/app/[format]/card-analysis/card-analysis-client.tsx` -- Add contextual subtitle
- `web/app/[format]/buylist/buylist-client.tsx` -- Add contextual subtitle
- `web/app/[format]/trends/trends-client.tsx` -- Add contextual subtitle
- `web/app/[format]/champions/champions-client.tsx` -- Add contextual subtitle

### Styling
- Same conventions as blog page: `font-display` headings, `font-body` content, `text-surface-300/400` body
- Scenario cards: `bg-surface-800 border border-surface-600 rounded-lg p-4`
- Accordion headers: `text-amber-400` with chevron indicator
- Glossary table: same table styling as trends/archetypes tables
- Contextual subtitles: `text-sm text-surface-400` with `text-accent` link

### Testing
- Guide page: renders heading, scenario cards, all tool sections, glossary table
- Accordion: expands/collapses on click, first section open by default
- Contextual subtitles: correct `href` anchors on each modified page
- Existing tests must continue passing

## Scope Boundaries

**In scope:**
- `/guide` page with three content sections
- Contextual subtitles on 6 existing pages
- Nav link to guide
- Welcome guide update with guide link
- Tests for new and modified components

**Out of scope:**
- Replacing existing tooltips (they stay as complementary to the guide)
- Format-specific guide content (guide is format-agnostic)
- Interactive tutorials or onboarding flows
- Changes to the blog page
