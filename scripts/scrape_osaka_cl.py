#!/usr/bin/env python3
"""Scrape Osaka CL 2026 results from pokekameshi.com using Kernel.sh cloud browsers.

Phase 1: Scrape standings + deck codes from pokekameshi
Phase 2: Fetch decklists from pokemon-card.com using deck codes
Output: CSV files compatible with `scout import-cl --dir data/osaka-cl`

Usage:
  python scripts/scrape_osaka_cl.py [divisions...] [--no-decklists] [--decklists-only] [--debug]

  --decklists-only  Skip Phase 1 (pokekameshi), read existing placement CSVs,
                    and only fetch decklists for entries with deck codes.
  --no-decklists    Skip Phase 2 (decklist fetching).
  --debug           Dump page structure during Phase 1.
"""

import asyncio
import csv
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/osaka-cl")

# pokekameshi URLs for CL2026 Osaka
PAGES = {
    "masters": "https://pokekameshi.com/cl2026osaka/",
    "seniors": "https://pokekameshi.com/cl2026osaka-senior/",
    "juniors": "https://pokekameshi.com/cl2026osaka-junior/",
}

# Temporary event IDs (will be replaced when official IDs are published)
TEMP_EVENT_IDS = {
    "masters": 999903,
    "seniors": 999901,
    "juniors": 999902,
}

JP_ENERGY_MAP = {
    "基本草エネルギー": ("Grass Energy", "Energy"),
    "基本炎エネルギー": ("Fire Energy", "Energy"),
    "基本水エネルギー": ("Water Energy", "Energy"),
    "基本雷エネルギー": ("Lightning Energy", "Energy"),
    "基本超エネルギー": ("Psychic Energy", "Energy"),
    "基本闘エネルギー": ("Fighting Energy", "Energy"),
    "基本悪エネルギー": ("Darkness Energy", "Energy"),
    "基本鋼エネルギー": ("Metal Energy", "Energy"),
}

BROWSER_POOL_SIZE = 4


@dataclass
class Placement:
    standing: int
    player_name: str
    region: str
    deck_code: str
    deck_url: str


@dataclass
class DeckCard:
    card_name_jp: str
    set_code: str
    card_number: str
    count: int
    category: str


def _create_kernel():
    """Create a Kernel client, raising if no API key is set."""
    from kernel import Kernel

    api_key = os.environ.get("KERNEL_API_KEY", "")
    if not api_key:
        raise ValueError("KERNEL_API_KEY environment variable is required")
    return Kernel(api_key=api_key)


async def _create_browser(pw, kernel):
    """Create a Kernel.sh cloud browser and return (session_id, browser, page)."""
    kb = kernel.browsers.create()
    browser = await pw.chromium.connect_over_cdp(kb.cdp_ws_url)
    page = browser.contexts[0].pages[0]
    return kb.session_id, browser, page


async def _destroy_browser(kernel, session_id, browser):
    """Close a browser and delete its Kernel session."""
    try:
        await browser.close()
    except Exception:
        pass
    try:
        kernel.browsers.delete_by_id(session_id)
    except Exception:
        pass


async def scrape_pokekameshi(page, url: str) -> list[Placement]:
    """Scrape standings and deck codes from a pokekameshi CL results page."""
    logger.info("Scraping %s", url)
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(5)  # Let JS render content

    # Scroll down to load lazy content
    for _ in range(10):
        await page.evaluate("window.scrollBy(0, 1000)")
        await asyncio.sleep(0.5)
    # Scroll back to top
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(1)

    # Extract placement data by finding deck links and their preceding H3 headings
    # pokekameshi format: H3 = 【{standing}位】{archetype_name}, followed by deck code link
    placements = await page.evaluate("""() => {
        const results = [];
        const deckLinks = document.querySelectorAll('a[href*="pokemon-card.com/deck/confirm"]');

        for (const link of deckLinks) {
            const href = link.href;
            const deckCodeMatch = href.match(/deckID\\/([\\w-]+)/);
            if (!deckCodeMatch) continue;

            const deckCode = deckCodeMatch[1];

            // Find the preceding H3 heading by walking up the DOM
            let heading = '';
            let el = link;
            while (el) {
                // Check previous siblings at each level
                let sib = el.previousElementSibling;
                while (sib) {
                    if (['H3', 'H4', 'H2'].includes(sib.tagName)) {
                        heading = sib.innerText.trim();
                        break;
                    }
                    sib = sib.previousElementSibling;
                }
                if (heading) break;
                el = el.parentElement;
            }

            results.push({
                deck_code: deckCode,
                deck_url: href,
                heading: heading,
            });
        }

        return results;
    }""")

    logger.info("Found %d deck entries on %s", len(placements), url)

    # Parse placement info from headings
    # Format: 【{standing}位】{archetype} or 【{record}】{archetype}
    parsed = []
    seen_codes = set()
    for entry in placements:
        code = entry["deck_code"]
        if code in seen_codes:
            continue
        seen_codes.add(code)

        heading = entry.get("heading", "")
        standing = _parse_standing(heading)
        # pokekameshi doesn't have player names - use archetype as identifier
        archetype = _parse_archetype_from_heading(heading)
        player_name = ""  # Not available from pokekameshi

        parsed.append(
            Placement(
                standing=standing,
                player_name=player_name,
                region="",
                deck_code=code,
                deck_url=entry["deck_url"],
            )
        )
        logger.info("  Parsed: #%d %s - %s", standing, archetype, code)

    # Sort by standing
    parsed.sort(key=lambda p: (p.standing, p.player_name))
    return parsed


def _parse_standing(heading: str) -> int:
    """Parse standing from heading text like 【62位】おまつりおんど or 【優勝】."""
    import re

    # Check for specific placement terms
    if "優勝" in heading and "準優勝" not in heading:
        return 1
    if "準優勝" in heading:
        return 2
    if "ベスト4" in heading or "ベスト４" in heading:
        return 3
    if "ベスト8" in heading or "ベスト８" in heading:
        return 5
    if "ベスト16" in heading or "ベスト１６" in heading:
        return 9
    if "ベスト32" in heading or "ベスト３２" in heading:
        return 17
    if "ベスト64" in heading or "ベスト６４" in heading:
        return 33

    # Numeric standing: 【62位】
    m = re.search(r"【(\d+)位】", heading)
    if m:
        return int(m.group(1))

    # Win-loss record: 【7−4】 or 【7-4】
    m = re.search(r"【(\d+)[−\-](\d+)】", heading)
    if m:
        # No clear standing, use a high number but mark with wins
        return 900 + int(m.group(2))  # Sort by losses ascending

    return 999


def _parse_archetype_from_heading(heading: str) -> str:
    """Extract archetype name from heading like 【62位】おまつりおんど."""
    import re

    m = re.search(r"】(.+)$", heading)
    return m.group(1).strip() if m else heading.strip()


async def fetch_decklist(page, deck_url: str) -> list[DeckCard]:
    """Fetch a decklist from pokemon-card.com deck confirm page.

    Uses the same extraction logic as PokemonJPClient._extract_decklist_from_page.
    """
    logger.info("Fetching decklist: %s", deck_url)
    try:
        await page.goto(deck_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)

        # Click list view button
        list_btn = await page.query_selector("text=リスト表示")
        if list_btn:
            await list_btn.click()
            await asyncio.sleep(1.5)

        # Get card names from image alt text
        img_cards = await page.evaluate("""() => {
            const cards = [];
            const imgs = document.querySelectorAll('.thumbsImageArea img');
            imgs.forEach(img => {
                const alt = img.alt || '';
                if (!alt) return;
                const src = img.src || '';
                const setMatch = src.match(/card_images\\/large\\/([A-Za-z0-9]+)\\//);
                cards.push({
                    name: alt,
                    setCode: setMatch ? setMatch[1] : '',
                });
            });
            return cards;
        }""")

        # Get card counts/categories from structured text
        text_data = await page.evaluate("""() => {
            const body = document.body.innerText;
            const lines = body.split('\\n').map(l => l.trim()).filter(l => l);
            const cards = [];
            let category = '';

            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];

                if (/^ポケモン\\s*\\(/.test(line)) { category = 'Pokemon'; continue; }
                if (/^グッズ\\s*\\(/.test(line)) { category = 'Trainer'; continue; }
                if (/^ポケモンのどうぐ\\s*\\(/.test(line)) { category = 'Trainer'; continue; }
                if (/^サポート\\s*\\(/.test(line)) { category = 'Trainer'; continue; }
                if (/^スタジアム\\s*\\(/.test(line)) { category = 'Trainer'; continue; }
                if (/^エネルギー\\s*\\(/.test(line)) { category = 'Energy'; continue; }

                const countMatch = line.match(/(\\d+)枚$/);
                if (countMatch && category) {
                    const count = parseInt(countMatch[1]);
                    let cardName = line.replace(/\\t?\\d+枚$/, '').trim();

                    let setCode = '';
                    let cardNumber = '';

                    if (i >= 2) {
                        const maybeName = lines[i-2];
                        const maybeSet = lines[i-1];
                        const maybeNum = cardName;

                        if (/^[A-Za-z0-9]{2,}$/.test(maybeSet)) {
                            setCode = maybeSet;
                            const numMatch = maybeNum.match(/^(\\d+)\\/\\d+/);
                            if (numMatch) {
                                cardNumber = numMatch[1];
                                cardName = maybeName;
                            }
                        }
                    }

                    cards.push({ name: cardName, setCode, cardNumber, count, category });
                }
            }
            return cards;
        }""")

        # Merge: prefer img alt for names (more reliable), text for counts/categories
        return _merge_card_data(img_cards, text_data, deck_url)
    except Exception as e:
        logger.warning("Failed to fetch decklist %s: %s", deck_url, e)
        return []


def _merge_card_data(img_cards: list[dict], text_data: list[dict], deck_url: str) -> list[DeckCard]:
    """Merge card data from img alt text and structured text."""
    result: list[DeckCard] = []

    if text_data and img_cards and len(text_data) == len(img_cards):
        for i, td in enumerate(text_data):
            ic = img_cards[i]
            result.append(
                DeckCard(
                    card_name_jp=ic["name"],
                    set_code=ic.get("setCode", td.get("setCode", "")),
                    card_number=td.get("cardNumber", ""),
                    count=td["count"],
                    category=td["category"],
                )
            )
    elif text_data:
        for i, td in enumerate(text_data):
            name = td["name"]
            set_code = td.get("setCode", "")
            if i < len(img_cards):
                name = img_cards[i]["name"] or name
                set_code = img_cards[i].get("setCode", "") or set_code
            result.append(
                DeckCard(
                    card_name_jp=name,
                    set_code=set_code,
                    card_number=td.get("cardNumber", ""),
                    count=td["count"],
                    category=td["category"],
                )
            )
    elif img_cards:
        for ic in img_cards:
            result.append(
                DeckCard(
                    card_name_jp=ic["name"],
                    set_code=ic.get("setCode", ""),
                    card_number="",
                    count=1,
                    category="",
                )
            )

    logger.info("Parsed %d cards from deck %s", len(result), deck_url)
    return result


def read_placements_csv(division: str) -> list[Placement]:
    """Read existing placement CSV and return Placement objects."""
    csv_path = OUTPUT_DIR / f"{division}-placements.csv"
    if not csv_path.exists():
        logger.warning("No placement CSV found: %s", csv_path)
        return []

    placements = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            placements.append(
                Placement(
                    standing=int(row["standing"]),
                    player_name=row.get("player_name", ""),
                    region=row.get("region", ""),
                    deck_code=row.get("deck_code", ""),
                    deck_url=row.get("deck_url", ""),
                )
            )
    logger.info("Read %d placements from %s", len(placements), csv_path)
    return placements


def write_csvs(division: str, placements: list[Placement], decklists: dict[str, list[DeckCard]]):
    """Write the CSV and meta files for a division."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    event_id = TEMP_EVENT_IDS[division]

    # Meta JSON
    meta = {
        "event_id": event_id,
        "event_name": f"チャンピオンズリーグ2026 大阪 {division.title()}",
        "division": division,
        "date": "2026-03-29",
    }
    with open(OUTPUT_DIR / f"{division}-meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # Placements CSV
    with open(OUTPUT_DIR / f"{division}-placements.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["standing", "player_name", "region", "deck_code", "deck_url"])
        for p in placements:
            writer.writerow([p.standing, p.player_name, p.region, p.deck_code, p.deck_url])

    # Decklists CSV
    with open(OUTPUT_DIR / f"{division}-decklists.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "standing",
                "player_name",
                "deck_code",
                "card_name_jp",
                "set_code",
                "card_number",
                "count",
                "category",
            ]
        )
        for p in placements:
            cards = decklists.get(p.deck_code, [])
            for card in cards:
                writer.writerow(
                    [
                        p.standing,
                        p.player_name,
                        p.deck_code,
                        card.card_name_jp,
                        card.set_code,
                        card.card_number,
                        card.count,
                        card.category,
                    ]
                )

    logger.info(
        "Wrote %s: %d placements, %d with decklists",
        division,
        len(placements),
        sum(1 for p in placements if p.deck_code in decklists and decklists[p.deck_code]),
    )


async def fetch_decklists_pooled(
    pw, kernel, placements: list[Placement]
) -> dict[str, list[DeckCard]]:
    """Fetch decklists concurrently using a pool of Kernel.sh cloud browsers."""
    # Filter to placements that have deck codes
    targets = [p for p in placements if p.deck_code and p.deck_url]
    if not targets:
        return {}

    pool_size = min(BROWSER_POOL_SIZE, len(targets))
    logger.info(
        "Fetching %d decklists with %d browser pool", len(targets), pool_size
    )

    # Create browser pool
    pool_queue: asyncio.Queue = asyncio.Queue()
    pool_entries: list[tuple[str, object, object]] = []
    for _ in range(pool_size):
        session_id, browser, page = await _create_browser(pw, kernel)
        entry = (session_id, browser, page)
        pool_entries.append(entry)
        await pool_queue.put(entry)

    decklists: dict[str, list[DeckCard]] = {}
    sem = asyncio.Semaphore(pool_size)

    async def _fetch_one(placement: Placement):
        async with sem:
            session_id, browser, page = await pool_queue.get()
            try:
                cards = await fetch_decklist(page, placement.deck_url)
                if cards:
                    decklists[placement.deck_code] = cards
                    logger.info("  %s: %d cards", placement.deck_code, len(cards))
                else:
                    logger.warning("  %s: no cards extracted", placement.deck_code)
                await asyncio.sleep(1)  # Be respectful
            finally:
                await pool_queue.put((session_id, browser, page))

    # Run all fetches concurrently (bounded by pool size via semaphore)
    await asyncio.gather(*[_fetch_one(p) for p in targets])

    # Tear down pool
    for session_id, browser, _ in pool_entries:
        await _destroy_browser(kernel, session_id, browser)
    logger.info("Browser pool stopped")

    return decklists


async def main():
    from playwright.async_api import async_playwright

    flags = {a for a in sys.argv[1:] if a.startswith("-")}
    fetch_decklists = "--no-decklists" not in flags
    decklists_only = "--decklists-only" in flags
    debug = "--debug" in flags

    divisions = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not divisions:
        divisions = list(PAGES.keys())

    kernel = _create_kernel()

    async with async_playwright() as pw:
        for division in divisions:
            logger.info("=== Processing %s ===", division)

            if decklists_only:
                # Phase 1 skipped: read existing placements from CSV
                placements = read_placements_csv(division)
                if not placements:
                    logger.warning("No placements for %s, skipping", division)
                    continue
            else:
                # Phase 1: Scrape standings from pokekameshi using a single browser
                url = PAGES.get(division)
                if not url:
                    logger.warning("Unknown division: %s", division)
                    continue

                session_id, browser, page = await _create_browser(pw, kernel)
                try:
                    placements = await scrape_pokekameshi(page, url)
                    logger.info("Found %d placements for %s", len(placements), division)

                    for p in placements[:5]:
                        logger.info(
                            "  #%d %s - %s",
                            p.standing,
                            p.player_name or "(unknown)",
                            p.deck_code,
                        )

                    if debug:
                        debug_html = await page.evaluate("""() => {
                            const headings = document.querySelectorAll('.entry-content h2, .entry-content h3, .entry-content h4');
                            const results = [];
                            for (const h of headings) {
                                results.push({
                                    tag: h.tagName,
                                    text: h.innerText.substring(0, 200),
                                    id: h.id || '',
                                });
                            }

                            const links = document.querySelectorAll('a[href*="pokemon-card.com/deck/confirm"]');
                            const linkContexts = [];
                            for (let i = 0; i < Math.min(links.length, 5); i++) {
                                const link = links[i];
                                let el = link;
                                for (let j = 0; j < 15; j++) {
                                    if (el.parentElement) el = el.parentElement;
                                    if (el.tagName === 'ARTICLE' || el.classList.contains('entry-content')) break;
                                }
                                let prev = link;
                                let heading = '';
                                while (prev) {
                                    prev = prev.previousElementSibling || (prev.parentElement ? prev.parentElement.previousElementSibling : null);
                                    if (prev && ['H2','H3','H4'].includes(prev.tagName)) {
                                        heading = prev.innerText;
                                        break;
                                    }
                                    if (!prev && link.parentElement) {
                                        let parent = link.parentElement;
                                        for (let k = 0; k < 10; k++) {
                                            if (!parent) break;
                                            let sib = parent.previousElementSibling;
                                            while (sib) {
                                                if (['H2','H3','H4'].includes(sib.tagName)) {
                                                    heading = sib.innerText;
                                                    break;
                                                }
                                                sib = sib.previousElementSibling;
                                            }
                                            if (heading) break;
                                            parent = parent.parentElement;
                                        }
                                        break;
                                    }
                                }
                                linkContexts.push({
                                    index: i,
                                    href: link.href,
                                    heading: heading.substring(0, 200),
                                });
                            }
                            return { headings: results, link_contexts: linkContexts };
                        }""")
                        logger.info("=== PAGE HEADINGS ===")
                        for h in debug_html.get("headings", []):
                            logger.info("  %s: %s", h["tag"], h["text"])
                        logger.info("=== DECK LINK CONTEXTS ===")
                        for lc in debug_html.get("link_contexts", []):
                            logger.info(
                                "  Entry %d: heading='%s' href=%s",
                                lc["index"],
                                lc["heading"],
                                lc["href"][-30:],
                            )
                finally:
                    await _destroy_browser(kernel, session_id, browser)

            # Phase 2: Fetch decklists (optional)
            decklists: dict[str, list[DeckCard]] = {}
            if fetch_decklists and placements:
                decklists = await fetch_decklists_pooled(pw, kernel, placements)

            # Write output
            write_csvs(division, placements, decklists)

    logger.info("\n=== Done! Files written to %s ===", OUTPUT_DIR)
    logger.info("Next: scout --format ninja-spinner import-cl --dir %s", OUTPUT_DIR)


if __name__ == "__main__":
    asyncio.run(main())
