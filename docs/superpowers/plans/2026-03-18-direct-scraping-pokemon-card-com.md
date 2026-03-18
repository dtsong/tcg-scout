# Direct Scraping from pokemon-card.com Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Limitless as the data source for City League results by scraping directly from players.pokemon-card.com, eliminating 1-3 day data lag and gaining full independence.

**Architecture:** Two-phase approach. Phase 1 (Hybrid) scrapes City League event listings and decklists from pokemon-card.com for freshness, but cross-references Limitless for archetype labels by matching on tournament date + finish position. Phase 2 (Full Independence) builds a content-based archetype classifier that assigns archetype names from decklist card contents, removing the Limitless dependency entirely. Both phases use the existing `PokemonJPClient` (kernel.sh cloud browser) pattern and `card_mappings` JP-to-EN translation pipeline.

**Tech Stack:** Python 3.12+, Playwright (via kernel.sh cloud browsers), SQLite, existing card_mappings translation pipeline

---

## File Structure

### Phase 1: Hybrid Scraper

| File | Action | Responsibility |
|------|--------|----------------|
| `scraper/pokemon_jp.py` | Modify | Add `fetch_cl_event_list()` and `fetch_cl_event_results()` for City League scraping |
| `scraper/pokemon_jp_api.py` | Create | HTTP API client for pokemon-card.com's internal Vue.js API endpoints (no browser needed) |
| `scraper/limitless.py` | Modify | Extract `fetch_archetype_labels()` method for cross-referencing |
| `db.py` | No change | Dedup uses `jp-{event_id}` ID prefix in `tournaments.id` -- no schema change needed |
| `cli.py` | Modify | Add `scrape-jp` command using the new direct scraper |
| `tests/test_pokemon_jp_api.py` | Create | Tests for the API client |
| `tests/test_archetype_classifier.py` | Create (Phase 2) | Tests for content-based classifier |

### Phase 2: Content-Based Archetype Classifier

| File | Action | Responsibility |
|------|--------|----------------|
| `analysis/archetype_classifier.py` | Create | Content-based archetype classification from decklist cards |
| `analysis/archetype.py` | Modify | Add `classify_from_decklist()` entry point that delegates to classifier |
| `config.py` | Modify | Add `ARCHETYPE_ANCHOR_CARDS` config structure |
| `tests/test_archetype_classifier.py` | Create | Tests for the classifier |

---

## Phase 1: Hybrid Scraper (Direct Scraping + Limitless Archetype Labels)

### Preamble: Understanding pokemon-card.com's Architecture

The official site (`players.pokemon-card.com`) is a Vue.js SPA. However, it fetches data from an internal JSON API. The key insight: we may be able to hit the API directly with httpx (no browser needed for event listings), falling back to Playwright only for decklists that require JS rendering.

Key URLs:
- Event list: `https://players.pokemon-card.com/event/result/list` (SPA -- need to discover API)
- Event detail: `https://players.pokemon-card.com/event/detail/{event_id}/result`
- Deck confirm: `https://players.pokemon-card.com/deck/confirm.html/deckID/{deck_code}`

The existing `PokemonJPClient` already handles the detail + deck pages via Playwright. We need to add the event list discovery.

---

### Task 1: Discover pokemon-card.com API Endpoints

**Files:**
- Create: `scraper/pokemon_jp_api.py`
- Test: `tests/test_pokemon_jp_api.py`

This task investigates the API the Vue.js SPA calls. Use browser devtools or the existing Playwright infra to intercept network requests.

- [ ] **Step 1: Write a spike script to intercept API calls**

Add a method to `PokemonJPClient` that navigates to the event list page and logs all XHR/fetch requests to discover the API endpoint pattern.

```python
# Temporary spike in scraper/pokemon_jp_api.py
async def discover_api_endpoints(self):
    """Navigate to event list page and capture API calls."""
    kb = self._kernel.browsers.create()
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(kb.cdp_ws_url)
            context = browser.contexts[0]
            page = context.pages[0]

            api_calls = []
            page.on("request", lambda req: api_calls.append(req.url)
                     if "api" in req.url or "event" in req.url else None)

            await page.goto(
                "https://players.pokemon-card.com/event/result/list",
                wait_until="networkidle", timeout=30000,
            )
            await asyncio.sleep(5)

            await browser.close()
    finally:
        self._kernel.browsers.delete_by_id(kb.session_id)
    return api_calls
```

- [ ] **Step 2: Run the spike and document the API structure**

```bash
python -c "
import asyncio
from dotenv import load_dotenv
load_dotenv()
from scraper.pokemon_jp import PokemonJPClient
client = PokemonJPClient()
urls = asyncio.run(client.discover_api_endpoints())
for u in urls:
    print(u)
"
```

Document the discovered endpoints in a comment at the top of `pokemon_jp_api.py`. Expected: a JSON endpoint returning event listings with event IDs, dates, and venue info.

- [ ] **Step 3: Commit spike results**

```bash
git add scraper/pokemon_jp_api.py
git commit -m "spike: discover pokemon-card.com API endpoints for CL listings"
```

---

### Task 2: Build Direct Event Listing Client

**Files:**
- Create: `scraper/pokemon_jp_api.py`
- Test: `tests/test_pokemon_jp_api.py`

Based on Task 1's findings, build a client that fetches City League event listings. If the API is accessible via plain HTTP (likely), this avoids Playwright entirely for listings.

- [ ] **Step 1: Write failing test for event listing fetch**

```python
# tests/test_pokemon_jp_api.py
import pytest
from scraper.pokemon_jp_api import PokemonJPAPIClient, JPCityLeagueEvent

class TestParseCLEventList:
    def test_parses_event_from_api_response(self):
        """Test parsing a single event from API JSON response."""
        sample_response = {
            "event_id": 952866,
            "event_name": "シティリーグ シーズン5",
            "store_name": "CARDBOX 青馬堂矢向店",
            "prefecture": "神奈川県",
            "date": "2026/03/17",
            "capacity": 64,
        }
        event = JPCityLeagueEvent.from_api(sample_response)
        assert event.event_id == 952866
        assert event.date == "2026-03-17"
        assert event.prefecture == "神奈川県"

    def test_filters_by_date_range(self):
        """Test filtering events by start/end date."""
        events = [
            JPCityLeagueEvent(event_id=1, date="2026-03-10", prefecture="", store_name="", capacity=0),
            JPCityLeagueEvent(event_id=2, date="2026-03-15", prefecture="", store_name="", capacity=0),
            JPCityLeagueEvent(event_id=3, date="2026-03-20", prefecture="", store_name="", capacity=0),
        ]
        filtered = [e for e in events if "2026-03-14" <= e.date <= "2026-03-17"]
        assert len(filtered) == 1
        assert filtered[0].event_id == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_pokemon_jp_api.py -v
```

Expected: ImportError (module doesn't exist yet)

- [ ] **Step 3: Implement the API client**

```python
# scraper/pokemon_jp_api.py
"""HTTP client for players.pokemon-card.com internal API.

Fetches City League event listings without requiring browser rendering.
"""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://players.pokemon-card.com"


@dataclass
class JPCityLeagueEvent:
    event_id: int
    date: str           # YYYY-MM-DD
    prefecture: str
    store_name: str
    capacity: int

    @classmethod
    def from_api(cls, data: dict) -> "JPCityLeagueEvent":
        date_raw = data.get("date", "")
        date_iso = date_raw.replace("/", "-") if "/" in date_raw else date_raw
        return cls(
            event_id=data["event_id"],
            date=date_iso,
            prefecture=data.get("prefecture", ""),
            store_name=data.get("store_name", ""),
            capacity=data.get("capacity", 0),
        )


class PokemonJPAPIClient:
    """Fetch City League event listings from pokemon-card.com API."""

    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=BASE_URL,
            timeout=30.0,
            headers={"User-Agent": "Scout/1.0"},
        )

    def fetch_cl_events(self, start: str, end: str) -> list[JPCityLeagueEvent]:
        """Fetch City League events in a date range.

        Args:
            start: Start date YYYY-MM-DD (inclusive)
            end: End date YYYY-MM-DD (inclusive)

        Returns:
            List of events within the date range.
        """
        # Implementation depends on Task 1 API discovery.
        # Replace this stub with the actual API call once the endpoint is known.
        # If the API is not directly accessible, fall back to Playwright-based
        # extraction (extend PokemonJPClient.fetch_event_results with a listing page).
        raise NotImplementedError("API endpoint TBD from Task 1 spike")

    # --- IMPORTANT: Task 1's spike will determine the actual implementation. ---
    # After running the spike, replace the stub above with real code. Example patterns:
    #
    # Pattern A (JSON API found):
    #   resp = self._client.get("/api/event/search", params={"type": "city_league", ...})
    #   return [JPCityLeagueEvent.from_api(e) for e in resp.json()["events"]]
    #
    # Pattern B (No API, use Playwright):
    #   Use PokemonJPClient to navigate to the event list SPA and extract event IDs
    #   from the rendered DOM, similar to _extract_placements().
    #
    # Pattern C (Hybrid -- use Limitless for event IDs, pokemon-card.com for decklists):
    #   Use LimitlessClient.fetch_jp_city_league_listings() for event discovery,
    #   then map Limitless tournament URLs to pokemon-card.com event IDs.

    def close(self) -> None:
        self._client.close()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_pokemon_jp_api.py::TestParseCLEventList -v
```

- [ ] **Step 5: Commit**

```bash
git add scraper/pokemon_jp_api.py tests/test_pokemon_jp_api.py
git commit -m "feat: add pokemon-card.com API client skeleton with event parsing"
```

---

### Task 3: Extend PokemonJPClient for City League Results

**Files:**
- Modify: `scraper/pokemon_jp.py`
- Test: `tests/test_pokemon_jp_api.py`

The existing `PokemonJPClient.fetch_event_results()` already scrapes placements from individual event pages. It works for both Champions League and City League -- the page structure is the same. We need to:
1. Add a `fetch_cl_results()` method that combines event listing + per-event scraping
2. Store results using the existing `placements` table (not `cl_placements`)

- [ ] **Step 1: Write failing test for CL result storage**

```python
# tests/test_pokemon_jp_api.py
class TestStoreCLResults:
    def test_stores_placement_with_jp_event_id(self, db):
        """CL placements from pokemon-card.com get stored with jp_event_id."""
        from scraper.pokemon_jp import JPPlacement, JPEventResult

        event = JPEventResult(
            event_id=952866,
            event_name="City League Kanagawa",
            division="masters",
            date="2026-03-17",
            placements=[
                JPPlacement(standing=1, player_name="Taro", region="神奈川県"),
                JPPlacement(standing=2, player_name="Hanako", region="東京都"),
            ],
        )
        # Test that we can store and retrieve
        from scraper.pokemon_jp import store_cl_city_league_results
        store_cl_city_league_results(db, event, decklists={})

        rows = db.execute("SELECT * FROM tournaments WHERE id = ?", ("jp-952866",)).fetchall()
        assert len(rows) == 1
        assert rows[0]["name"] == "City League Kanagawa"

        placements = db.execute(
            "SELECT * FROM placements WHERE tournament_id = ?", ("jp-952866",)
        ).fetchall()
        assert len(placements) == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_pokemon_jp_api.py::TestStoreCLResults -v
```

- [ ] **Step 3: Implement store function**

Add to `scraper/pokemon_jp.py`:

```python
def store_cl_city_league_results(
    conn: sqlite3.Connection,
    event: JPEventResult,
    decklists: dict[str, list[JPDeckCard]],
) -> None:
    """Store City League results from pokemon-card.com into the standard tables.

    Uses 'jp-{event_id}' as tournament ID to avoid collision with Limitless URLs.
    """
    tournament_id = f"jp-{event.event_id}"

    conn.execute(
        "INSERT OR REPLACE INTO tournaments (id, name, date, player_count, country) "
        "VALUES (?, ?, ?, ?, ?)",
        (tournament_id, event.event_name, event.date, len(event.placements), "JP"),
    )

    for placement in event.placements:
        cursor = conn.execute(
            "INSERT INTO placements (tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?)",
            (tournament_id, placement.standing, placement.player_name, "Unknown"),
        )
        placement_id = cursor.lastrowid

        if placement.deck_code and placement.deck_code in decklists:
            for card in decklists[placement.deck_code]:
                conn.execute(
                    "INSERT OR REPLACE INTO decklist_cards "
                    "(placement_id, card_id, card_name, count) "
                    "VALUES (?, ?, ?, ?)",
                    (placement_id, card.set_code or card.name_jp, card.name_jp, card.count),
                )

    conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_pokemon_jp_api.py::TestStoreCLResults -v
```

- [ ] **Step 5: Commit**

```bash
git add scraper/pokemon_jp.py tests/test_pokemon_jp_api.py
git commit -m "feat: store City League results from pokemon-card.com in standard tables"
```

---

### Task 4: Limitless Archetype Cross-Reference

**Files:**
- Modify: `scraper/limitless.py`
- Test: `tests/test_pokemon_jp_api.py`

For Phase 1, we need to fetch archetype labels from Limitless by matching on date + standing, then backfill the `archetype` column in our `placements` table.

- [ ] **Step 1: Write failing test for archetype cross-reference**

```python
# tests/test_pokemon_jp_api.py
class TestArchetypeCrossRef:
    def test_matches_by_date_and_standing(self):
        """Cross-reference matches Limitless archetypes to JP placements by date+standing."""
        from scraper.limitless import match_archetype_labels

        limitless_data = [
            {"date": "2026-03-17", "standing": 1, "archetype": "Dragapult ex"},
            {"date": "2026-03-17", "standing": 2, "archetype": "Charizard ex"},
        ]
        jp_placements = [
            {"date": "2026-03-17", "standing": 1, "player_name": "Taro"},
            {"date": "2026-03-17", "standing": 2, "player_name": "Hanako"},
        ]
        matched = match_archetype_labels(jp_placements, limitless_data)
        assert matched[0]["archetype"] == "Dragapult ex"
        assert matched[1]["archetype"] == "Charizard ex"

    def test_unmatched_stays_unknown(self):
        """Placements without a Limitless match keep 'Unknown' archetype."""
        from scraper.limitless import match_archetype_labels

        limitless_data = [
            {"date": "2026-03-17", "standing": 1, "archetype": "Dragapult ex"},
        ]
        jp_placements = [
            {"date": "2026-03-17", "standing": 1, "player_name": "Taro"},
            {"date": "2026-03-17", "standing": 3, "player_name": "Eve"},
        ]
        matched = match_archetype_labels(jp_placements, limitless_data)
        assert matched[0]["archetype"] == "Dragapult ex"
        assert matched[1]["archetype"] == "Unknown"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_pokemon_jp_api.py::TestArchetypeCrossRef -v
```

- [ ] **Step 3: Implement cross-reference function**

Add to `scraper/limitless.py`:

```python
def match_archetype_labels(
    jp_placements: list[dict],
    limitless_data: list[dict],
) -> list[dict]:
    """Match Limitless archetype labels to JP placements by date + standing.

    Args:
        jp_placements: Dicts with 'date', 'standing', 'player_name' keys.
        limitless_data: Dicts with 'date', 'standing', 'archetype' keys.

    Returns:
        jp_placements with 'archetype' field populated where matched.
    """
    lookup = {}
    for ld in limitless_data:
        key = (ld["date"], ld["standing"])
        lookup[key] = ld["archetype"]

    result = []
    for jp in jp_placements:
        entry = dict(jp)
        key = (jp["date"], jp["standing"])
        entry["archetype"] = lookup.get(key, jp.get("archetype", "Unknown"))
        result.append(entry)

    return result
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_pokemon_jp_api.py::TestArchetypeCrossRef -v
```

- [ ] **Step 5: Commit**

```bash
git add scraper/limitless.py tests/test_pokemon_jp_api.py
git commit -m "feat: cross-reference Limitless archetype labels by date+standing"
```

---

### Task 5: JP-to-EN Decklist Translation Pipeline

**Files:**
- Modify: `scraper/card_mappings.py`
- Modify: `reports/json_export.py`

The existing `translate_decklist()` in `card_mappings.py` and `JP_CARD_NAMES` dict in `json_export.py` handle JP-to-EN. For direct scraping, we need to run this translation on City League decklists (currently only used for CL decklists).

- [ ] **Step 1: Write failing test for CL decklist translation**

```python
# tests/test_pokemon_jp_api.py
class TestTranslateCLDecklist:
    def test_translates_known_cards(self, db):
        """JP card names are translated to EN using card_mappings table."""
        from scraper.card_mappings import translate_decklist

        # Seed card_mappings table (conftest only seeds `cards`, not `card_mappings`)
        db.executemany(
            "INSERT INTO card_mappings (jp_card_id, en_card_id, card_name_jp, card_name_en, jp_set_id, en_set_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("SV5-001", "sv5-001", "リザードンex", "Charizard ex", "SV5", "sv5"),
                ("SV5-100", "sv5-100", "ネストボール", "Nest Ball", "SV5", "sv5"),
            ],
        )
        db.commit()

        jp_cards = [
            {"name_jp": "リザードンex", "set_code": "SV5", "count": 2},
            {"name_jp": "ネストボール", "set_code": "SV5", "count": 4},
        ]
        result = translate_decklist(db, jp_cards)
        assert result[0]["card_name_en"] == "Charizard ex"
        assert result[1]["card_name_en"] == "Nest Ball"
```

- [ ] **Step 2: Run test to verify it fails or passes**

```bash
python -m pytest tests/test_pokemon_jp_api.py::TestTranslateCLDecklist -v
```

The existing `translate_decklist` may already handle this. If so, mark as passing and move on.

- [ ] **Step 3: Commit if any changes**

```bash
git add scraper/card_mappings.py tests/test_pokemon_jp_api.py
git commit -m "test: verify CL decklist translation works for direct scraper"
```

---

### Task 6: CLI `scrape-jp` Command

**Files:**
- Modify: `cli.py`

Wire everything together with a new CLI command that:
1. Fetches CL event listings from pokemon-card.com
2. Scrapes placements + decklists for each event
3. Cross-references Limitless for archetype labels
4. Translates JP card names to EN
5. Stores everything in the format's SQLite DB

- [ ] **Step 1: Add `scrape-jp` command skeleton**

```python
# cli.py
@cli.command("scrape-jp")
@click.option("--start", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--end", default=None, help="End date (YYYY-MM-DD)")
@click.option("--fetch-decklists/--no-decklists", default=True)
@click.option("--top", default=16, help="Max placements to fetch decklists for")
@click.pass_context
def scrape_jp(ctx: click.Context, start: str | None, end: str | None,
              fetch_decklists: bool, top: int) -> None:
    """Scrape City League results directly from pokemon-card.com."""
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()

    from scraper.pokemon_jp import PokemonJPClient, store_cl_city_league_results
    from scraper.pokemon_jp_api import PokemonJPAPIClient

    fmt_slug = ctx.obj["format"]
    fmt = get_format_config(fmt_slug)
    start = start or fmt["dataset_start"]
    end = end or fmt["dataset_end"]

    conn = get_format_connection(fmt_slug)
    init_db(conn)

    try:
        # Step 1: Get event listings
        api_client = PokemonJPAPIClient()
        events = api_client.fetch_cl_events(start, end)
        console.print(f"Found [bold]{len(events)}[/bold] City League events")

        # Step 2: Filter out already-scraped events
        existing = set()
        for row in conn.execute("SELECT id FROM tournaments"):
            existing.add(row["id"])
        new_events = [e for e in events if f"jp-{e.event_id}" not in existing]
        console.print(f"[cyan]{len(new_events)} new events to process[/cyan]")

        # Step 3: Scrape each event
        client = PokemonJPClient()
        for i, event_info in enumerate(new_events, 1):
            console.print(f"  [{i}/{len(new_events)}] {event_info.store_name} ({event_info.date})")
            event = asyncio.run(client.fetch_event_results(event_info.event_id))

            decklists = {}
            if fetch_decklists:
                for p in event.placements:
                    if p.deck_url and p.standing <= top:
                        try:
                            cards = asyncio.run(client.fetch_decklist(p.deck_url))
                            if cards and p.deck_code:
                                decklists[p.deck_code] = cards
                        except Exception as e:
                            console.print(f"    [red]Deck error: {e}[/red]")

            store_cl_city_league_results(conn, event, decklists)

        console.print(f"[green]Done! Processed {len(new_events)} events.[/green]")
    finally:
        conn.close()
```

- [ ] **Step 2: Test the command manually**

```bash
python cli.py --format ninja-spinner scrape-jp --start 2026-03-14 --end 2026-03-18
```

- [ ] **Step 3: Commit**

```bash
git add cli.py
git commit -m "feat: add scrape-jp command for direct pokemon-card.com scraping"
```

---

### Task 7: Archetype Backfill from Limitless

**Files:**
- Modify: `cli.py`

Add a `backfill-archetypes` command that reads placements with `archetype = 'Unknown'` and attempts to match them against Limitless data.

- [ ] **Step 1: Add backfill command**

```python
@cli.command("backfill-archetypes")
@click.pass_context
def backfill_archetypes(ctx: click.Context) -> None:
    """Backfill archetype labels from Limitless for Unknown placements."""
    from scraper.limitless import LimitlessClient, match_archetype_labels

    fmt_slug = ctx.obj["format"]
    fmt = get_format_config(fmt_slug)
    conn = get_format_connection(fmt_slug)

    try:
        # Get Unknown placements grouped by tournament date
        unknowns = conn.execute(
            """SELECT p.id, p.standing, t.date
               FROM placements p
               JOIN tournaments t ON t.id = p.tournament_id
               WHERE p.archetype = 'Unknown'
               ORDER BY t.date, p.standing"""
        ).fetchall()

        if not unknowns:
            console.print("[green]No Unknown archetypes to backfill.[/green]")
            return

        console.print(f"[cyan]{len(unknowns)} placements need archetype labels[/cyan]")

        # Fetch Limitless data for matching dates
        dates = sorted(set(row["date"] for row in unknowns))
        client = LimitlessClient()
        try:
            tournaments = client.fetch_jp_city_league_listings(dates[0], dates[-1])
            # Fetch placements from each Limitless tournament
            limitless_data = []
            for t in tournaments:
                placements = client.fetch_jp_city_league_placements(t.source_url, 32)
                for p in placements:
                    limitless_data.append({
                        "date": t.tournament_date.isoformat(),
                        "standing": p.placement,
                        "archetype": p.archetype,
                    })
        finally:
            client.close()

        # Match and update
        lookup = {(d["date"], d["standing"]): d["archetype"] for d in limitless_data}
        updated = 0
        for row in unknowns:
            key = (row["date"], row["standing"])
            archetype = lookup.get(key)
            if archetype and archetype != "Unknown":
                conn.execute(
                    "UPDATE placements SET archetype = ? WHERE id = ?",
                    (archetype, row["id"]),
                )
                updated += 1

        conn.commit()
        console.print(f"[green]Updated {updated}/{len(unknowns)} placements[/green]")
    finally:
        conn.close()
```

- [ ] **Step 2: Test manually**

```bash
python cli.py --format ninja-spinner backfill-archetypes
```

- [ ] **Step 3: Commit**

```bash
git add cli.py
git commit -m "feat: add backfill-archetypes command for Limitless cross-reference"
```

---

## Phase 2: Content-Based Archetype Classifier

### Task 8: Design Anchor Card Config

**Files:**
- Modify: `config.py`
- Test: `tests/test_archetype_classifier.py`

The classifier identifies archetypes by looking for "anchor" Pokemon in a decklist -- the signature Pokemon that define a deck's identity. E.g., if a deck has Charizard ex + Pidgeot ex, it's "Charizard ex". If it has Dragapult ex + Dusknoir, it's "Dragapult Dusknoir".

- [ ] **Step 1: Write failing test for anchor card matching**

```python
# tests/test_archetype_classifier.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.archetype_classifier import classify_decklist


class TestClassifyDecklist:
    def test_charizard_pidgeot(self):
        cards = [
            {"card_name": "Charizard ex", "count": 2, "category": "Pokemon"},
            {"card_name": "Pidgeot ex", "count": 2, "category": "Pokemon"},
            {"card_name": "Charmander", "count": 3, "category": "Pokemon"},
            {"card_name": "Rare Candy", "count": 4, "category": "Trainer"},
        ]
        assert classify_decklist(cards) == "Charizard ex"

    def test_dragapult_dusknoir(self):
        cards = [
            {"card_name": "Dragapult ex", "count": 3, "category": "Pokemon"},
            {"card_name": "Dusknoir", "count": 2, "category": "Pokemon"},
            {"card_name": "Dreepy", "count": 4, "category": "Pokemon"},
        ]
        assert classify_decklist(cards) == "Dragapult Dusknoir"

    def test_single_anchor(self):
        cards = [
            {"card_name": "Gardevoir ex", "count": 3, "category": "Pokemon"},
            {"card_name": "Ralts", "count": 4, "category": "Pokemon"},
            {"card_name": "Kirlia", "count": 3, "category": "Pokemon"},
        ]
        assert classify_decklist(cards) == "Gardevoir ex"

    def test_unknown_deck(self):
        cards = [
            {"card_name": "Bidoof", "count": 4, "category": "Pokemon"},
            {"card_name": "Nest Ball", "count": 4, "category": "Trainer"},
        ]
        assert classify_decklist(cards) == "Unknown"

    def test_mega_archetype(self):
        # NOTE: Card names must match actual EN names from Limitless/card_mappings
        cards = [
            {"card_name": "Lucario ex", "count": 3, "category": "Pokemon"},
            {"card_name": "Solrock", "count": 2, "category": "Pokemon"},
        ]
        assert classify_decklist(cards) == "Mega Lucario Solrock"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_archetype_classifier.py -v
```

- [ ] **Step 3: Add anchor card config to `config.py`**

```python
# config.py -- add after FORMATS

# Anchor cards for content-based archetype classification.
# Each entry: primary anchor -> {secondary anchor -> archetype name}
# If no secondary matches, uses the primary's default name.
ARCHETYPE_ANCHOR_CARDS: dict[str, dict[str, str] | str] = {
    "Charizard ex": {
        "_default": "Charizard ex",
        "Dusknoir": "Charizard Dusknoir",
    },
    "Dragapult ex": {
        "_default": "Dragapult ex",
        "Pidgeot ex": "Dragapult ex",
        "Dusknoir": "Dragapult Dusknoir",
        "Noctowl": "Dragapult Noctowl",
    },
    "Gardevoir ex": "Gardevoir ex",
    "Raging Bolt ex": "Raging Bolt ex",
    "Gholdengo ex": "Gholdengo ex",
    "Terapagos ex": "Terapagos ex",
    "Archaludon ex": "Archaludon ex",
    "Miraidon ex": "Miraidon ex",
    "Grimmsnarl ex": {
        "_default": "Grimmsnarl ex",
        "Munkidori": "Grimmsnarl Munkidori",
    },
    "Froslass ex": {
        "_default": "Froslass ex",
        "Munkidori": "Froslass Munkidori",
        "Grimmsnarl": "Froslass Grimmsnarl",
    },
    "Alakazam ex": {
        "_default": "Alakazam ex",
        "Dudunsparce": "Alakazam Dudunsparce",
    },
    # Mega archetypes
    # NOTE: These key names MUST match the exact EN card names as stored in
    # the `decklist_cards.card_name` column (from Limitless) or translated via
    # `card_mappings`. Verify against actual DB data before finalizing.
    # Run: SELECT DISTINCT card_name FROM decklist_cards WHERE card_name LIKE '%Mega%' OR card_name LIKE '%Lucario%'
    "Lucario ex": {
        "_default": "Mega Lucario ex",
        "Solrock": "Mega Lucario Solrock",
    },
    "Starmie ex": {
        "_default": "Mega Starmie ex",
        "Greninja ex": "Mega Starmie Greninja",
        "Dusknoir": "Mega Starmie Dusknoir",
    },
    "Venusaur ex": {
        "_default": "Mega Venusaur ex",
        "Ogerpon ex": "Mega Venusaur",
    },
    # Add more as the meta evolves. Verify card names against actual DB data.
}
```

- [ ] **Step 4: Implement classifier**

```python
# analysis/archetype_classifier.py
"""Content-based archetype classification from decklist cards.

Identifies archetypes by detecting anchor Pokemon in a decklist.
"""

from config import ARCHETYPE_ANCHOR_CARDS


def classify_decklist(cards: list[dict]) -> str:
    """Classify a decklist into an archetype based on card contents.

    Args:
        cards: List of dicts with 'card_name', 'count', 'category' keys.

    Returns:
        Archetype name string, or "Unknown" if no match.
    """
    pokemon_names = {
        c["card_name"] for c in cards
        if c.get("category") == "Pokemon"
    }

    # Try each anchor card in priority order
    for anchor, mapping in ARCHETYPE_ANCHOR_CARDS.items():
        if anchor not in pokemon_names:
            continue

        if isinstance(mapping, str):
            return mapping

        # Check secondary anchors
        for secondary, archetype_name in mapping.items():
            if secondary == "_default":
                continue
            if secondary in pokemon_names:
                return archetype_name

        # No secondary match -- use default
        return mapping.get("_default", anchor)

    return "Unknown"
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_archetype_classifier.py -v
```

- [ ] **Step 6: Commit**

```bash
git add config.py analysis/archetype_classifier.py tests/test_archetype_classifier.py
git commit -m "feat: content-based archetype classifier with anchor card config"
```

---

### Task 9: Integrate Classifier into Pipeline

**Files:**
- Modify: `scraper/pokemon_jp.py`
- Modify: `analysis/archetype.py`

Replace `archetype = "Unknown"` in `store_cl_city_league_results()` with a call to the classifier. Also add a `classify_from_decklist()` entry point in `archetype.py` that tries content-based first, falls back to sprite-based.

- [ ] **Step 1: Write failing test**

```python
# tests/test_archetype_classifier.py
class TestClassifyFromDecklist:
    def test_content_based_takes_priority(self):
        from analysis.archetype import classify_from_decklist

        cards = [
            {"card_name": "Charizard ex", "count": 2, "category": "Pokemon"},
            {"card_name": "Pidgeot ex", "count": 2, "category": "Pokemon"},
        ]
        assert classify_from_decklist(cards) == "Charizard ex"

    def test_falls_back_to_unknown(self):
        from analysis.archetype import classify_from_decklist

        cards = [
            {"card_name": "Bidoof", "count": 4, "category": "Pokemon"},
        ]
        assert classify_from_decklist(cards) == "Unknown"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_archetype_classifier.py::TestClassifyFromDecklist -v
```

- [ ] **Step 3: Add entry point to `analysis/archetype.py`**

```python
# Add to analysis/archetype.py

def classify_from_decklist(cards: list[dict]) -> str:
    """Classify archetype from decklist card contents.

    Uses content-based anchor card detection.
    Falls back to "Unknown" if no anchor cards match.
    """
    from analysis.archetype_classifier import classify_decklist
    return classify_decklist(cards)
```

- [ ] **Step 4: Update `store_cl_city_league_results` to use classifier**

In `scraper/pokemon_jp.py`, update the archetype assignment:

```python
# In store_cl_city_league_results(), replace archetype="Unknown" with:
from analysis.archetype import classify_from_decklist

# After building the decklist for a placement:
if placement.deck_code and placement.deck_code in decklists:
    deck_cards = [
        {"card_name": c.name_jp, "count": c.count, "category": c.category}
        for c in decklists[placement.deck_code]
    ]
    archetype = classify_from_decklist(deck_cards)
else:
    archetype = "Unknown"
```

**Important:** The classifier uses EN card names in `ARCHETYPE_ANCHOR_CARDS`. JP decklists must be translated BEFORE classification. The full pipeline is:

```python
# Translate JP card names to EN first
from scraper.card_mappings import translate_decklist
translated = translate_decklist(conn, [
    {"name_jp": c.name_jp, "set_code": c.set_code, "count": c.count}
    for c in decklists[placement.deck_code]
])
# Then classify using EN names
deck_cards = [
    {"card_name": c.get("card_name_en") or c["name_jp"], "count": c["count"], "category": c.get("category", "Pokemon")}
    for c in translated
]
archetype = classify_from_decklist(deck_cards)
```

- [ ] **Step 5: Run all tests**

```bash
python -m pytest tests/ -v
```

- [ ] **Step 6: Commit**

```bash
git add analysis/archetype.py scraper/pokemon_jp.py tests/test_archetype_classifier.py
git commit -m "feat: integrate content-based classifier into pokemon-card.com pipeline"
```

---

### Task 10: Classifier Validation Against Limitless Labels

**Files:**
- Create: `scripts/validate_classifier.py`

Build a validation script that compares the classifier's output against Limitless archetype labels on existing data. This tells us accuracy before we go fully independent.

- [ ] **Step 1: Write validation script**

```python
# scripts/validate_classifier.py
"""Validate the content-based classifier against Limitless labels.

Runs the classifier on every decklist in the DB and compares
against the Limitless-assigned archetype. Outputs accuracy stats.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.archetype import classify_from_decklist
from db import get_format_connection


def validate(format_slug: str = "nihil-zero") -> None:
    conn = get_format_connection(format_slug)

    placements = conn.execute(
        "SELECT id, archetype FROM placements WHERE archetype != 'Unknown'"
    ).fetchall()

    correct = 0
    wrong = 0
    no_decklist = 0

    for p in placements:
        cards = conn.execute(
            "SELECT card_name, count FROM decklist_cards WHERE placement_id = ?",
            (p["id"],),
        ).fetchall()

        if not cards:
            no_decklist += 1
            continue

        card_dicts = [
            {"card_name": c["card_name"], "count": c["count"], "category": "Pokemon"}
            for c in cards
        ]
        predicted = classify_from_decklist(card_dicts)
        actual = p["archetype"]

        if predicted == actual:
            correct += 1
        else:
            wrong += 1
            if wrong <= 20:
                print(f"  WRONG: predicted={predicted}, actual={actual}")

    total = correct + wrong
    accuracy = correct / total * 100 if total > 0 else 0
    print(f"\nResults: {correct}/{total} correct ({accuracy:.1f}%)")
    print(f"  No decklist: {no_decklist}")

    conn.close()


if __name__ == "__main__":
    validate(sys.argv[1] if len(sys.argv) > 1 else "nihil-zero")
```

- [ ] **Step 2: Run validation**

```bash
python scripts/validate_classifier.py nihil-zero
```

Target: >80% accuracy before Phase 2 is considered complete. Iterate on `ARCHETYPE_ANCHOR_CARDS` to cover misses.

- [ ] **Step 3: Commit**

```bash
git add scripts/validate_classifier.py
git commit -m "feat: add classifier validation script against Limitless labels"
```

---

## Phase Transition Criteria

**Phase 1 is complete when:**
- `scrape-jp` successfully fetches City League data from pokemon-card.com
- `backfill-archetypes` successfully labels placements from Limitless
- JP-to-EN translation covers >95% of cards in decklists
- Data appears correctly in the frontend

**Phase 2 is complete when:**
- Content-based classifier achieves >85% accuracy vs. Limitless labels on nihil-zero data
- `ARCHETYPE_ANCHOR_CARDS` covers all S/A/B tier archetypes
- `scrape-jp` can operate fully without `backfill-archetypes`
- Limitless scraping can be disabled without data quality regression

**Phase 2 deferred items (future work):**
- Automatic anchor card discovery from decklist clustering
- "Freshness" badges in the UI showing when data was last updated
- Automated scheduled scraping (cron/GitHub Actions)
