# Scout 2026-27: Analytics and SEO Roadmap

Date: 2026-09-13. Status: proposal for discussion, nothing here is implemented.

## TL;DR

1. **Data first.** The 2026-27 season has no published results yet (JP City League S1 starts mid-September, TPCi Regionals in October). Until then the site is a Worlds 2026 archive plus frozen JP formats. The single highest-value data move is ingesting play.limitlesstcg.com online events, which publish daily and cover the gap between offline seasons.
2. **Analytics: three features, in this order.** (a) Online meta view from play.limitlesstcg.com, (b) event-caliber weighting so a Regional Day 2 list outweighs a 32-player League Cup, (c) card co-occurrence graph on top of `analysis/synergy.py`, surfaced as "runs with" on card pages.
3. **SEO: ship the boring foundation this month.** There is no `sitemap.ts`, no `robots.ts`, no canonical URLs, and no structured data. The site has roughly 300 archetype pages per format and the same order of card pages that Google cannot discover except via internal links. That is a one-day fix with the largest expected traffic gain.
4. **Content compounding.** Programmatic pages (archetype, card, player, tournament) already exist. Add one durable landing page per format and per marquee event (Worlds 2026, CL Yokohama 2027), which are the queries people actually type.

## Where the platform stands (2026-09-13)

| Area | State |
| --- | --- |
| Formats | `storm-emeralda` and `tpci-standard-2027` registered, empty, shown as "Coming Soon". Six frozen formats with data. |
| Pipeline | Cloud Build every 3h. JP API unblocked (curl_cffi). Empty formats no longer fail the build. |
| JP sources | Official API (event_search, event_result_detail_search): results end 2026-06-07, S1 2027 events publish from ~2026-09-20. Limitless JP feed: dead since 2026-05-06, do not rebuild on it. pokecabook/pokecazilla: need KERNEL_API_KEY, not in Cloud Build secrets. |
| TPCi sources | Limitless main site + labs.limitlesstcg.com. Worlds 2026 (797 players) ingested into `tpci-standard`. |
| Untapped | play.limitlesstcg.com (online events, daily). |
| Frontend | 20 routes per format. Vercel Analytics installed. Root `metadata` has OG and Twitter cards. Archetype and card pages have `generateMetadata`. No sitemap, robots, canonical, or JSON-LD. |

## Analytics roadmap

### Tier 1: do before the season's first Regional (October 2026)

**A1. Online meta from play.limitlesstcg.com.**
Why: the only daily-updating signal. It answers "what is people testing right now" two to four weeks before offline results confirm it, which is the question every competitive player asks after a set release. Online lists also carry full decklists and W/L records, which offline JP results do not.
How: new scraper module mirroring `scraper/limitless_tpci.py` (tournament list, standings, decklist pages). Store with `source = "limitless-online"` and a `caliber` value (see A2). Keep online out of the headline meta share by default; expose it as a separate "Online" toggle on `/[format]` and `/[format]/trends` so the offline numbers stay comparable across seasons.
Cost: 2-3 days pipeline, 1 day frontend.

**A2. Event-caliber weighting.**
Why: `PLACEMENT_WEIGHTS` already weights by finish, but a 1st at a 16-player League Challenge scores the same as 1st at a 1,500-player Regional. That distorts tier lists early in a season when only small events have reported.
How: add a `caliber` column on tournaments (worlds, ic, regional, cl, city-league, league-cup, online-major, online-weekly) derived from name and player count at ingest. Multiply placement weight by a caliber factor in `analysis/shared.placement_weight`. Export both raw and weighted shares so the UI can show the delta ("+1.4 pts from majors").
Cost: 1 day, mostly tests.

**A3. Card co-occurrence graph, surfaced as "runs with" and "tech alternatives".**
Why: `analysis/synergy.py` already computes pair lift. Nothing renders it. Players choosing the last 4 slots of a list want "decks that run Card X also run Y at Z%". This is also the most linkable content for SEO (see S4).
How: export top 10 co-occurring cards per card per archetype into `cards/<slug>.json`; render as a chip list with lift and count. Later: an interactive graph for the archetype report page.
Cost: 1 day pipeline, 1 day frontend.

### Tier 2: mid-season (November 2026 to January 2027)

**A4. Matchup confidence intervals.** `analysis/matchup.py` reports point estimates. Add Wilson intervals and grey out cells under 20 games. Cheap, and it stops the site from confidently reporting 70/30 on 7 games.

**A5. Card price overlay.** The handover already lists this idea. Cheapest path is TCGplayer market price via the pokemontcg.io API for TPCi and cardrush or Yuyu-tei scrape for JP. Turns `buylist` from "what to buy" into "what to buy and what it costs", and "budget version of Archetype X" pages are strong search queries.

**A6. Player Elo and consistency.** `analysis/players.py` has profiles. Add a per-format rating from placements and a "consistency" score (share of events in Top 32). Powers a leaderboard page and "who to watch at Regional X" content.

**A7. Deck evolution diff view.** `analysis/evolution.py` computes card-count movements. Render a two-column diff between the archetype's list from event N and event N+1, including the "why" hints from co-occurrence (A3).

### Tier 3: platform

**A8. open_placements performance.** Still unresolved from July. Materialise `open_placements` as a table refreshed at the end of each scrape instead of a view. Blocks nothing today but export time grows linearly with tournaments.

**A9. Snapshot history.** Keep every `meta_snapshots` row and export a time series, not only the latest. Enables "meta share over the season" on trends without recomputing from placements.

**A10. Notifications.** A Slack or email digest when a new major's results land (event name, top 8 archetypes, biggest movers). Uses existing export data. Low effort, high retention.

## SEO roadmap

### S1. Crawlability foundation (one day, do first)

- `web/app/sitemap.ts`: enumerate every route in `find web/app -name page.tsx` for every format in `formats.json`, plus archetype, card, and player slugs from the exported JSON. Static export supports `sitemap.ts` with `generateSitemaps` or a single file. Expect ~3,000 URLs.
- `web/app/robots.ts`: allow all, point at the sitemap, disallow `/data/`.
- Canonical URLs via `alternates.canonical` in every `generateMetadata`. Format-scoped pages must not be seen as duplicates across formats.
- Submit the sitemap in Google Search Console and Bing Webmaster Tools. If no Search Console property exists, create one for scout.trainerlab.io; it is the only way to see what queries already land.

### S2. Titles and descriptions that match queries

Current root title is "Scout | JP Meta Explorer". Query intent is "[archetype] deck list", "[card] pokemon tcg", "[event] results", "pokemon tcg meta [month year]".

| Page | Proposed title pattern |
| --- | --- |
| `/[format]` | "Pokemon TCG Meta Tier List, {Month Year} ({Format name}) \| Scout" |
| `/[format]/archetypes/[slug]` | "{Archetype} Deck List and Meta Share, {Format name} \| Scout" |
| `/[format]/cards/[slug]` | "{Card} Usage Rates and Decks ({Format name}) \| Scout" |
| `/[format]/tournaments` | "{Event} Results and Top Decks \| Scout" once per-event pages exist |

Add `generateMetadata` to the pages that still lack it (buylist, matchups, trends, players index, tournaments). Include `generated_at` in descriptions ("updated 13 Sep 2026") since freshness is a ranking signal for this vertical.

### S3. Structured data

- `Dataset` JSON-LD on `/[format]` (name, temporalCoverage from dataset_start/end, distribution pointing at the JSON export).
- `ItemList` on archetype index and card index.
- `Event` on per-tournament pages (S5) with location, date, attendee count.
- `BreadcrumbList` everywhere under `/[format]`.
Implementation: a small `JsonLd` component rendering `<script type="application/ld+json">`.

### S4. Internal linking

Programmatic pages rank only when linked. Add:
- On archetype pages: links to each card page in the list, and "similar archetypes" (share the same sprite key prefix or top 10 cards).
- On card pages: "runs with" chips (A3) linking to other card pages, and "appears in" archetype links.
- On the landing page: link to every format, not only the default.
- A footer with the top 10 archetypes per active format.

### S5. Content that earns links

- **Per-tournament pages** (`/[format]/tournaments/[slug]`): "Worlds 2026 results", "Regional Charlotte 2026 top 8" are the highest-volume queries in this space and the site already has the data. Currently only an index exists.
- **Format landing pages that persist**: `/formats/storm-emeralda` with a plain-language explainer (what rotated, legal sets, key dates). Rotation queries spike every three months in JP and every September for TPCi.
- **Monthly "state of the meta" post** under `/blog`, generated from exports plus a short human edit. Recurring, dateable, shareable.
- **Deck guides**: the `/[format]/archetypes/[slug]/report` page already reads like one. Give it a stable title ("{Archetype} Deck Guide") and an author byline.

### S6. Technical

- Static export is already ideal for crawl budget. Check Core Web Vitals in Search Console after S1; Recharts pages may need lazy loading.
- `og-default.png` is the only OG image. Generate per-archetype OG images at build time (Next `ImageResponse` works in static export via `opengraph-image.tsx`) so shares on X and Discord carry the sprite and tier.
- Add `hreflang` only if a Japanese UI is planned; otherwise skip.

### S7. Measurement

Vercel Analytics gives pageviews. Add Search Console (queries, impressions, position) and define the goal: organic sessions per week, tracked monthly. Baseline this before S1 ships so the effect is attributable.

## Suggested sequencing

| Week of | Ship |
| --- | --- |
| 2026-09-14 | S1 sitemap, robots, canonical. Search Console property. Baseline. |
| 2026-09-21 | A1 play.limitlesstcg.com scraper (behind a toggle). CL Yokohama event IDs into `POKEMON_JP_CL_EVENTS` after Sept 22. |
| 2026-09-28 | S2 titles and descriptions, S3 JSON-LD, S5 per-tournament pages. |
| 2026-10-05 | A2 caliber weighting before the first Regional's results. A3 co-occurrence chips (S4 internal links ride on it). |
| 2026-10-19 | A4 matchup intervals, S6 OG images. |
| November | A5 prices, A6 player ratings, S5 monthly meta post. |

## Open decisions for the owner

1. Is the online meta (A1) shown blended with offline or as a separate view? Recommendation: separate toggle, default off, until we have a season of evidence on how well it predicts offline results.
2. Do we want `tpci-standard-2027` to include grassroots majors from Limitless (League Cups, 100+ players) or only Regionals and up? Caliber weighting (A2) makes "include everything" safe.
3. Should pokecabook/pokecazilla be revived? It requires adding KERNEL_API_KEY to Cloud Build secrets and costs cloud-browser minutes per run. Only worth it if the official JP API stops publishing decklists for City League this season; check after the first S1 events.
