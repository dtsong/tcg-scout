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

5 scenario cards at the top, each 2-3 sentences directing users to the right tools:

| Scenario | Tools | Description |
|----------|-------|-------------|
| Pick a deck for this weekend | Dashboard + Buy List | Check the tier list for what's performing, then use the buy list to see what cards you need |
| Find cards that actually win | Format Edge | See which cards are overrepresented in top-4 finishes compared to the overall field, broken down by archetype |
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
- Surging/Declining cards: change in card usage between first and second half of the time window (e.g., +23% means 23 percentage points more decks include this card in the recent half)
- Winning Edge cards: difference between a card's inclusion rate in 1st-place decks vs. all S/A/B-tier decks. Uses only tournament winners, not top-4.
- ACE SPEC distribution: percentage of all decks running each ACE SPEC

**Archetypes (#archetypes)**
- Browse all detected archetypes with meta share and archetype trend delta (change in archetype meta share between early and late halves of the time window)
- Performance Advantage Matrix: average standing difference when two archetypes appear in the same tournament. +2.0 means the row archetype finishes 2 places better on average. Minimum 10 tournament co-occurrences required; cells below threshold show as blank.
- Card Overlap Matrix: Jaccard similarity of core card pools (cards in 30%+ of decks). Higher = more shared staples.
- Archetype detail pages: core cards, inclusion rates, tournament results

**Format Edge (#format-edge)**
- Ranks cards by how much more often they appear in top-4 finishing decks than the overall field, computed per archetype. This is distinct from the Dashboard's Winning Edge, which uses only 1st-place.
- Example: if a card is in 80% of an archetype's top-4 decks but only 55% of all that archetype's decks, that's a +25 point edge for that archetype.
- Avg Edge: average delta across all archetypes the card appears in. Best Edge: highest single-archetype delta.
- A high edge means the card is contributing to top finishes beyond what its play rate predicts

**Cards (#cards)**
- Browse all cards in the format with usage statistics
- Card detail pages show inclusion rate, average copies, and which archetypes run the card

**Buy List (#buy-list)**
- Priority-scored card list across S/A/B tier archetypes
- Staples tab: cards that appear across many top decks
- Flex tab: cards specific to certain archetypes but high-impact

**Trends (#trends)**
- Surging cards: biggest card usage increases between early and late halves of the time window
- Declining cards: biggest card usage decreases
- Winning Edge table: same 1st-place overrepresentation metric as the Dashboard, shown in full table form
- Time window filters: 7-day, 30-day, or full format

**Champions League (#champions-league)**
- Full decklists from Japan's largest events
- Division tabs: Juniors, Seniors, Masters
- Translated card names

**Report (#report)**
- Auto-generated weekly meta summary (when available)
- Structured sections covering tier movements, cards to watch, matchup spotlights

### Section 3: Metric Glossary (#glossary)

Compact reference table at the bottom with anchor IDs for deep-linking.

| Metric | Definition | Found on |
|--------|-----------|----------|
| Meta share | Percentage of total decks playing this archetype | Dashboard, Archetypes |
| Weighted share | Meta share with placements weighted by finish (1st=3x, 2nd=2.5x, 3rd-4th=2x, 5th-8th=1.5x, 9th-16th=1.2x, 17th+=1x) | Dashboard, Archetype detail |
| Winning edge | Difference between a card's inclusion rate in 1st-place decks vs. all S/A/B decks. +11 means 11 percentage points more common in tournament winners. Uses only 1st-place finishes. | Dashboard, Trends |
| Top-4 edge (Avg/Best) | Difference between a card's inclusion rate in top-4 decks vs. all decks within each archetype. Avg Edge averages across archetypes; Best Edge is the highest single-archetype delta. | Format Edge |
| Archetype trend delta | Change in an archetype's meta share between early and late halves of the time window | Archetypes |
| Card trend (Surging/Declining) | Change in a card's usage rate between early and late halves of the time window. +23% means 23 percentage points more decks include this card recently. | Dashboard, Trends |
| Performance advantage | Average standing difference when two archetypes meet in the same tournament. Minimum 10 co-occurrences. | Archetypes (matrix) |
| Card overlap | Jaccard similarity of core card pools (cards in 30%+ of decks) | Archetypes (matrix) |

## Contextual Subtitles

Each existing page gets a one-line description under its `<h1>` with a link to the guide:

| Page | Subtitle | Link |
|------|----------|------|
| Dashboard | Your meta overview: tier list, key signals, and weekly movement. | /guide#dashboard |
| Archetypes | Every deck in the format with matchups, cards, and results. | /guide#archetypes |
| Format Edge | Cards that win more than they're played. | /guide#format-edge |
| Cards | Browse every card in the format with usage stats. | /guide#cards |
| Buy List | Priority-ranked cards across top-tier decks. | /guide#buy-list |
| Trends | What's rising and falling in card usage. | /guide#trends |
| Champions League | Full decklists from Japan's premier events. | /guide#champions-league |
| Report | Auto-generated weekly meta summary. | /guide#report |

Format: `<p>Subtitle text. <Link href="/guide#section">How this works &rarr;</Link></p>`

## Nav Update

Add a "Guide" link to `web/app/components/nav.tsx`. The link is not format-scoped, so it should be rendered separately from the `links` array (which contains format-relative paths). Add it after the format-scoped links as a standalone `<Link href="/guide">Guide</Link>` element, styled the same as adjacent nav items. Handle active state by checking `pathname === "/guide"`.

## Welcome Guide Update

Add a final line to the existing dismissible welcome modal: "For a full walkthrough, see the Guide." with a `<Link href="/guide">` styled as `text-accent text-sm`. No other changes to the modal.

## Implementation Details

### Files to create
- `web/app/guide/page.tsx` -- Guide page with static metadata and content
- `web/app/guide/layout.tsx` -- Layout matching blog pattern but using `max-w-5xl` (wider than blog's `max-w-3xl` to accommodate glossary table)
- `web/app/guide/guide-client.tsx` -- Client component for collapsible accordion sections
- `web/app/guide/__tests__/guide-client.test.tsx` -- Tests for guide page

### Files to modify
- `web/app/components/nav.tsx` -- Add "Guide" link after format-scoped links
- `web/app/components/welcome-guide.tsx` -- Add guide link at the bottom
- `web/app/[format]/dashboard-client.tsx` -- Add contextual subtitle
- `web/app/[format]/archetypes/archetypes-client.tsx` -- Add contextual subtitle
- `web/app/[format]/card-analysis/card-analysis-client.tsx` -- Add contextual subtitle
- `web/app/[format]/cards/cards-client.tsx` -- Add contextual subtitle
- `web/app/[format]/buylist/buylist-client.tsx` -- Add contextual subtitle
- `web/app/[format]/trends/trends-client.tsx` -- Add contextual subtitle
- `web/app/[format]/champions/champions-client.tsx` -- Add contextual subtitle
- `web/app/[format]/report/report-client.tsx` -- Add contextual subtitle

### Styling
- Same conventions as blog page: `font-display` headings, `font-body` content, `text-surface-300/400` body
- Guide layout uses `max-w-5xl` for glossary table readability
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
- Contextual subtitles on 8 existing pages
- Nav link to guide
- Welcome guide update with guide link
- Tests for new and modified components

**Out of scope:**
- Replacing existing tooltips (they stay as complementary to the guide)
- Format-specific guide content (guide is format-agnostic)
- Interactive tutorials or onboarding flows
- Changes to the blog page
