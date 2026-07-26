# Play LimitlessTCG Ingestion Design

Date: 2026-07-26
Status: Approved, pending implementation plan

## Motivation

`abyss-eye` is the World Championships format. Physical events are in offseason
between NAIC and Worlds, and the JP City League feed is on summer break, so both
of Scout's existing sources are dry past roughly 2026-06-10. Testing has moved
online.

Scout previously excluded `play.limitlesstcg.com` because grassroots events were
out of scope. That decision is reversed: grassroots events now count.

Caveat that shapes the product, not the pipeline: players sandbag real tech until
Worlds. Online results are a leading indicator of what is being *explored*, which
is not the same as what will be *played*. The design must keep that distinction
legible rather than averaging it away.

## Source

Base URL `https://play.limitlesstcg.com/api`, documented at
`https://docs.limitlesstcg.com/developer/tournaments.html`.

**No API key is required** for the endpoints we need. Only `/games/{game}/decks`
is gated. Rate limits are advertised via response headers.

| Endpoint | Fields we consume |
|---|---|
| `GET /tournaments?game=PTCG&limit=&page=` | `id`, `name`, `date`, `format`, `players`, `organizerId` |
| `GET /tournaments/{id}/details` | `decklists` (bool), `isOnline` (bool), `organizer` |
| `GET /tournaments/{id}/standings` | `placing`, `name`, `player`, `country`, `record{wins,losses,ties}`, `deck{id,name,icons}`, `decklist` |

The decisive property, verified live: **standings return the full decklist
inline**, already partitioned into `pokemon` / `trainer` / `energy` with `count`,
`set`, `number`, and `name`. There is no second decklist fetch and no Playwright
dependency. This is a structurally cleaner source than anything Scout currently
scrapes.

Verified sample (tournament `69725552b1294bfab720364d`, placing 1):

```json
{
  "name": "Historicdork224",
  "country": "US",
  "placing": 1,
  "player": "historicdork224",
  "record": {"wins": 3, "losses": 1, "ties": 0},
  "deck": {"id": "wailord-ex", "name": "Wailord", "icons": ["wailord"]},
  "decklist": {
    "pokemon": [{"count": 3, "set": "CRI", "number": "8", "name": "Vulpix"}, "..."],
    "trainer": [{"count": 3, "set": "MEG", "number": "114", "name": "Boss's Orders"}, "..."],
    "energy":  [{"count": 8, "set": "MEE", "number": "3", "name": "Water Energy"}, "..."]
  }
}
```

### Volume

A single 500-entry listing page covered only 2026-07-12 to 2026-07-26, roughly
36 events per day. Of those 500, 450 were `STANDARD`; player counts ran min 4,
median 26, max 504, with 201 events at 32+ players.

Extrapolated across the abyss-eye window (2026-06-05 onward), that is on the
order of **1,500 to 1,800 candidate events**. The share publishing decklists is
not yet measured and must be surveyed during implementation, but even at 50% this
implies **15,000 to 30,000 new placements**, comparable to or larger than the
entire existing `ninja-spinner` dataset (18,571 placements).

This volume is the single most important constraint on the design. It drives the
incremental-scrape requirement and makes the `open_placements` performance work a
hard prerequisite rather than optional cleanup.

## Decisions

| Decision | Choice |
|---|---|
| Scoring model | Caliber weight scaled by field size, applied as a multiplier |
| Caliber scope | **All sources**, not Play-only |
| Surfacing | Merged into the existing meta, with a visible source label everywhere |
| Event scope | `format == STANDARD`, within the active format's date window, `details.decklists == true`, `players >= 8` |
| Online vs in-person | Both ingested; `is_online` recorded as a column so it stays sliceable |

Rejected alternatives and why:

- **Player-count floor only.** Preserves existing scoring but discards the long
  tail and creates a hard cliff at the threshold boundary.
- **Flat weighting.** A 4-player weekly's 1st place would carry the same 3.0x as
  winning NAIC.
- **Separate unmerged online meta.** Safest, but directly contradicts the
  decision to count grassroots events.
- **Silent merge.** Cheapest to build, but destroys the ability to tell whether
  a spike is a real trend or an online experiment. Given sandbagging, that
  attribution is the primary product value.
- **Ingesting events without decklists.** Those return an empty `deck` object,
  so they yield no archetype at all. They would add unscoreable rows.

## Architecture

### New module: `scraper/play_limitless.py`

Pure JSON. No BeautifulSoup, no Playwright. Reuses `RateLimitedHTTPClient` from
`scraper/http_client.py` for rate limiting and retries.

```
list      GET /tournaments?game=PTCG&limit=&page=N
          paginate until date < dataset_start
filter    format == "STANDARD"
          dataset_start <= date <= dataset_end
          players >= MIN_TOURNAMENT_PLAYERS (8)
skip      id already present in tournaments (incremental)
details   GET /tournaments/{id}/details -> require decklists == true
          capture isOnline
standings GET /tournaments/{id}/standings -> placements + decklists in one call
```

Dataclasses mirroring the existing scrapers' shape: `PlayTournament`,
`PlayPlacement`, `PlayDecklist`.

Persistence lives in the module as `store_play_results(conn, tournament,
placements)`, following the `scraper/pokemon_jp.py::store_cl_city_league_results`
precedent. It does **not** add a fourth inline `INSERT INTO tournaments` to
`cli.py`, which already has three (lines 229, 1736, 2427). Consolidating those
three is out of scope for this work.

CLI surface: `scout --format <slug> scrape-play [--since DATE] [--limit N]
[--dry-run]`.

### Incrementality

Steady-state runs fetch only listing pages until they hit an already-known id,
then stop. The initial backfill across the full abyss-eye window is a one-time
operation run out of band by the operator, not inside the 3h Cloud Build
pipeline.

### Archetype derivation

`deck.icons` returns bare stems (`["wailord"]`), but `analysis/archetype.py`'s
`_FILENAME_RE` requires a `/name.png` shape. The scraper synthesizes CDN URLs:

```python
sprite_urls = [f"{LIMITLESS_SPRITE_CDN}/{icon}.png" for icon in deck.get("icons", [])]
```

`LIMITLESS_SPRITE_CDN` already exists in `analysis/archetype.py`. Verified:
`["charizard", "pidgeot"]` yields archetype `"Charizard / Pidgeot"` and sprite
key `"charizard-pidgeot"`, matching the existing convention exactly. No new
archetype logic and no lookup table are needed.

Where `icons` is empty but `deck.name` is present, `deck.name` is passed as the
`html_archetype` fallback argument.

### Decklist mapping

Play's `set` + `number` map directly onto Scout's existing `card_id` convention
(`f"{set_code}-{card_number}"`, per `scraper/http_client.py::parse_card_links`).
No translation layer is required. Cards are flattened from the three category
lists into `decklist_cards` rows preserving `card_name` and `count`.

## Schema changes

Two columns added to `tournaments` via the established `ALTER TABLE` migration
pattern in `db.py` (mirroring how `tournament_type` was added):

```sql
source   TEXT    DEFAULT 'limitless'   -- 'play' for this source
is_online INTEGER DEFAULT 0
```

`player_count` already exists and receives the API's `players` value.

Tournament ids are prefixed `play-<id>`. This matters for the `open_placements`
and `open_tournaments` dedup views, whose `NOT EXISTS` clauses only suppress a
non-`jp-%` event when it matches a `jp-%` event on the same date and division by
store name, prefecture plus capacity, or exact standing plus player name plus
archetype. Play events carry NULL `store_name` and `prefecture`, and Play player
names are usernames (`historicdork224`), so false-positive suppression against JP
events is not a practical risk. This should nonetheless be asserted in tests.

## Caliber weighting

`analysis/shared.py::placement_weight(standing, boost=1.0)` already accepts a
multiplier, so caliber requires no new plumbing:

```python
CALIBER_REFERENCE_PLAYERS = 64
CALIBER_MIN = 0.25
CALIBER_MAX = 2.0
MIN_TOURNAMENT_PLAYERS = 8

def caliber_weight(player_count: int | None) -> float:
    """Scale a placement by field size. 1.0 at the 64-player reference."""
    if not player_count:
        return 1.0          # unknown field size stays neutral
    return min(CALIBER_MAX, max(CALIBER_MIN, sqrt(player_count / CALIBER_REFERENCE_PLAYERS)))
```

64 is the anchor because `config.PLACEMENT_WEIGHTS` is explicitly documented as
calibrated to a 64-player City League, so a 64-player event's scoring is
unchanged by definition.

| Players | Caliber |
|---|---|
| 8 | 0.35 |
| 16 | 0.50 |
| 32 | 0.71 |
| 64 | 1.00 |
| 128 | 1.41 |
| 256+ | 2.00 (clamped) |

Events under `MIN_TOURNAMENT_PLAYERS` (8, fewer than 3 Swiss rounds) are not
ingested. That is a pod, not a tournament.

### Scope: all sources

Caliber applies to every placement, not only Play placements. Applying it
Play-only would score a 30-player JP local at 1.0 while scoring a 30-player
online event at 0.71, baking in a source bias that would need permanent
explanation.

The consequence is accepted and explicit: **this retroactively shifts weighted
shares and therefore tier assignments across existing formats.** Championship
events (NAIC and similar, 1000+ players) rise to the 2.0 clamp, which is the
correct relative outcome. A null or zero `player_count` yields 1.0, so any
historical row lacking a field size is unaffected.

### Consumers to correct

`reports/json_export.py:302` and `reports/json_export.py:480` read
`PLACEMENT_WEIGHTS` directly instead of calling `placement_weight`, so caliber
would silently bypass them. Both are routed through the helper as part of this
work. `analysis/meta.py::compute_meta_snapshot` already calls `placement_weight`
and needs its query extended to select `t.player_count`.

## Exports and frontend

New optional fields, per the project's backward-compatibility convention:

- Tournament-shaped export objects gain `source` and `is_online`.
- Archetype exports gain an online/physical placement split so a share movement
  is attributable to a source.
- `web/app/lib/types.ts` gains the matching optional fields.

Archetype detail pages surface the split. This is the deliverable that makes
sandbagging legible rather than hidden: a spike visible only in online data is
labeled as a testing signal, not presented as the meta.

## Prerequisite: `open_placements` performance

`open_placements` uses a correlated `NOT EXISTS` containing a `LEFT JOIN`,
introduced in `ff88fb4`. Its plan is `SCAN p` plus a correlated scalar subquery,
which is quadratic in placements times tournaments. It is the confirmed location
of the Cloud Build timeouts.

Adding 15,000 to 30,000 placements makes this materially worse.

**The view must be fixed before Play ingestion lands.** Either materialize it or
index the correlated columns, reproduced against a production-sized database
rather than the local copy, which is not representative. Landing ingestion first
reintroduces the multi-hour build.

This fix is a separate work item with its own plan. It is a sequencing
dependency of this spec, not a component of it, and nothing in this document
should be implemented before it ships.

## Testing

Recorded API fixtures rather than live calls:

1. A tournament with decklists (archetype, decklist, record all populated).
2. A tournament with `decklists: false` (empty `deck`, null `decklist`).
3. A `CUSTOM` format tournament.
4. A tournament below the 8-player floor.

Assertions:

- Filter correctness: `CUSTOM`, no-decklist, out-of-window, and sub-floor events
  are all excluded.
- `deck.icons` to archetype via synthesized CDN URLs, including the multi-icon
  alphabetical join and the empty-icons fallback to `deck.name`.
- Decklist card ids resolve to `SET-number` and cover all three categories.
- `caliber_weight` endpoints, clamps, and the `None`/0 neutral case.
- Incremental skip: a second run over the same fixture adds no rows.
- Dedup safety: a Play event on the same date as a JP event is not suppressed by
  `open_placements`.
- Round-trip: `PLACEMENT_WEIGHTS` times caliber flows into `weighted_share` in
  `archetype_stats` and out to exported JSON, extending the existing
  `tests/test_integration.py:326` pattern.

## Out of scope

- Consolidating the three inline `INSERT INTO tournaments` sites in `cli.py`.
- The `/pairings` endpoint. Head-to-head matchup data is a plausible follow-up
  but is not required for meta signal.
- Non-PTCG games, and non-Standard formats including `CUSTOM`.
- Card pricing and the card relationship graph, tracked separately.

## Risks

- **Decklist publication rate is unmeasured.** If materially below 50%, event
  coverage drops. Survey during implementation before committing to backfill
  scope.
- **Tier churn from caliber weighting.** Accepted and documented above, but it
  will visibly change historical pages on first deploy.
- **Organizer quality varies.** `organizerId` is captured but unused for now;
  it is the natural hook if specific organizers later prove to be noise.
- **Rate limits are undocumented in specifics.** The client must honor rate limit
  response headers and back off rather than assuming a fixed budget.
