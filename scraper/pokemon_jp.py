"""Scraper for players.pokemon-card.com using kernel.sh cloud browsers.

Fetches Champions League results and decklists from the official JP site,
which requires JavaScript rendering (Vue.js SPA).
"""

import asyncio
import logging
import os
import re
import sqlite3
from dataclasses import dataclass, field

from kernel import Kernel
from playwright.async_api import async_playwright, Page

logger = logging.getLogger(__name__)

# JP energy name -> EN energy name
JP_ENERGY_MAP = {
    "基本炎エネルギー": "Basic Fire Energy",
    "基本水エネルギー": "Basic Water Energy",
    "基本雷エネルギー": "Basic Lightning Energy",
    "基本超エネルギー": "Basic Psychic Energy",
    "基本草エネルギー": "Basic Grass Energy",
    "基本闘エネルギー": "Basic Fighting Energy",
    "基本悪エネルギー": "Basic Darkness Energy",
    "基本鋼エネルギー": "Basic Metal Energy",
    "基本フェアリーエネルギー": "Basic Fairy Energy",
    "基本無色エネルギー": "Basic Colorless Energy",
}

DIVISION_MAP = {
    "ジュニア": "juniors",
    "シニア": "seniors",
    "マスター": "masters",
}

# Fukuoka Champions League 2026 event IDs
FUKUOKA_CL_EVENTS = {
    903701: "seniors",
    903702: "juniors",
    903703: "masters",
}


@dataclass
class JPPlacement:
    standing: int
    player_name: str
    region: str
    deck_url: str | None = None
    deck_code: str | None = None


@dataclass
class JPDeckCard:
    name_jp: str
    set_code: str = ""
    card_number: str = ""
    count: int = 1
    category: str = ""  # Pokemon, Trainer, Energy


@dataclass
class JPEventResult:
    event_id: int
    event_name: str
    division: str  # juniors, seniors, masters
    date: str
    placements: list[JPPlacement] = field(default_factory=list)


class PokemonJPClient:
    """Scraper for players.pokemon-card.com using kernel.sh cloud browsers."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("KERNEL_API_KEY", "")
        if not self._api_key:
            raise ValueError("KERNEL_API_KEY not set")
        self._kernel = Kernel(api_key=self._api_key)

    async def fetch_event_results(self, event_id: int) -> JPEventResult:
        """Fetch placements and deck URLs from an event results page."""
        kb = self._kernel.browsers.create()

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(kb.cdp_ws_url)
                context = browser.contexts[0]
                page = context.pages[0]

                url = f"https://players.pokemon-card.com/event/detail/{event_id}/result"
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(3)

                title = await page.title()
                logger.info("Fetching event %d: %s", event_id, title)

                # Determine division from title
                division = "unknown"
                for jp_div, en_div in DIVISION_MAP.items():
                    if jp_div in title:
                        division = en_div
                        break

                event_name = title.split(" | ")[0].strip()
                date_text = await page.evaluate('''() => {
                    const text = document.body.innerText;
                    const match = text.match(/(\\d{4}\\/\\d{2}\\/\\d{2})/);
                    return match ? match[1] : '';
                }''')

                # Extract placements from all pages
                all_placements: list[JPPlacement] = []
                page_num = 1

                while True:
                    placements = await self._extract_placements(page)
                    all_placements.extend(placements)
                    logger.info(
                        "Event %d page %d: %d placements",
                        event_id, page_num, len(placements),
                    )

                    next_btn = await page.query_selector('text=次のページ')
                    if next_btn:
                        await next_btn.click()
                        await asyncio.sleep(2)
                        page_num += 1
                    else:
                        break

                await browser.close()
        finally:
            self._kernel.browsers.delete_by_id(kb.session_id)

        return JPEventResult(
            event_id=event_id,
            event_name=event_name,
            division=division,
            date=date_text.replace("/", "-") if date_text else "",
            placements=all_placements,
        )

    async def _extract_placements(self, page: Page) -> list[JPPlacement]:
        """Extract placements from the current results page."""
        data = await page.evaluate('''() => {
            const results = [];
            const rows = document.querySelectorAll('tr');
            for (const row of rows) {
                const cells = row.querySelectorAll('td');
                if (cells.length < 3) continue;

                const standingText = cells[0]?.textContent?.trim() || '';
                const standingMatch = standingText.match(/(\\d+)/);
                if (!standingMatch) continue;

                // Player name is in the cell that contains プレイヤーID
                let playerName = '';
                let region = '';
                for (const cell of cells) {
                    const text = cell.textContent || '';
                    if (text.includes('プレイヤーID')) {
                        playerName = text.split('\\n')[0].trim();
                        playerName = playerName.replace(/プレイヤーID.*/, '').trim();
                    }
                    // Region is typically a prefecture name (2-4 chars ending in 県/都/府/道)
                    const regionMatch = text.trim().match(/^(.{2,4}[県都府道])$/);
                    if (regionMatch) {
                        region = regionMatch[1];
                    }
                }

                const deckLink = row.querySelector('a[href*="deck/confirm"]');
                const deckUrl = deckLink?.href || '';
                const deckCodeMatch = deckUrl.match(/deckID\\/([\\w-]+)/);

                results.push({
                    standing: parseInt(standingMatch[1]),
                    playerName,
                    region,
                    deckUrl: deckUrl || null,
                    deckCode: deckCodeMatch ? deckCodeMatch[1] : null,
                });
            }
            return results;
        }''')

        return [
            JPPlacement(
                standing=d["standing"],
                player_name=d["playerName"],
                region=d["region"],
                deck_url=d["deckUrl"],
                deck_code=d["deckCode"],
            )
            for d in data
            if d["standing"] > 0
        ]

    async def fetch_decklist(self, deck_url: str) -> list[JPDeckCard]:
        """Fetch a decklist from pokemon-card.com/deck/confirm.html.

        Uses the list view which shows structured text with card names,
        set codes, card numbers, and counts. Also extracts JP set codes
        from card image URLs.
        """
        kb = self._kernel.browsers.create()

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(kb.cdp_ws_url)
                context = browser.contexts[0]
                page = context.pages[0]

                await page.goto(deck_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(3)

                # Click "リスト表示" (List View) for structured text
                list_btn = await page.query_selector('text=リスト表示')
                if list_btn:
                    await list_btn.click()
                    await asyncio.sleep(2)

                # Extract img alt (JP card names) + set codes from image URLs
                # This is the most reliable source of JP names
                img_cards = await page.evaluate('''() => {
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
                }''')

                # Extract structured text from list view for counts + categories
                text_data = await page.evaluate('''() => {
                    const body = document.body.innerText;
                    const lines = body.split('\\n').map(l => l.trim()).filter(l => l);
                    const cards = [];
                    let category = '';

                    for (let i = 0; i < lines.length; i++) {
                        const line = lines[i];

                        // Category headers
                        if (/^ポケモン\\s*\\(/.test(line)) { category = 'Pokemon'; continue; }
                        if (/^グッズ\\s*\\(/.test(line)) { category = 'Trainer'; continue; }
                        if (/^ポケモンのどうぐ\\s*\\(/.test(line)) { category = 'Trainer'; continue; }
                        if (/^サポート\\s*\\(/.test(line)) { category = 'Trainer'; continue; }
                        if (/^スタジアム\\s*\\(/.test(line)) { category = 'Trainer'; continue; }
                        if (/^エネルギー\\s*\\(/.test(line)) { category = 'Energy'; continue; }

                        // Count pattern: ends with N枚
                        const countMatch = line.match(/(\\d+)枚$/);
                        if (countMatch && category) {
                            const count = parseInt(countMatch[1]);
                            let cardName = line.replace(/\\t?\\d+枚$/, '').trim();

                            // Pokemon cards have set code + number on previous lines
                            // Format: CardName\\nSETCODE\\nNUM/TOTAL then count on this line
                            let setCode = '';
                            let cardNumber = '';

                            // Check if previous 2 lines are set code and card number
                            if (i >= 2) {
                                const maybeName = lines[i-2];
                                const maybeSet = lines[i-1];
                                const maybeNum = cardName;  // Current line might just be "NUM/TOTAL\\tN枚"

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
                }''')

                await browser.close()
        finally:
            self._kernel.browsers.delete_by_id(kb.session_id)

        # Merge: img_cards has reliable JP names + set codes, text_data has counts
        result: list[JPDeckCard] = []

        if text_data and img_cards and len(text_data) == len(img_cards):
            # Perfect alignment — merge both sources
            for i, td in enumerate(text_data):
                ic = img_cards[i]
                result.append(JPDeckCard(
                    name_jp=ic["name"],
                    set_code=ic.get("setCode", td.get("setCode", "")),
                    card_number=td.get("cardNumber", ""),
                    count=td["count"],
                    category=td["category"],
                ))
        elif text_data:
            # Use text data, supplement with img names where available
            for i, td in enumerate(text_data):
                name = td["name"]
                set_code = td.get("setCode", "")
                if i < len(img_cards):
                    name = img_cards[i]["name"] or name
                    set_code = img_cards[i].get("setCode", "") or set_code
                result.append(JPDeckCard(
                    name_jp=name,
                    set_code=set_code,
                    card_number=td.get("cardNumber", ""),
                    count=td["count"],
                    category=td["category"],
                ))
        elif img_cards:
            # Fallback: only img data, counts unknown (set to 1)
            for ic in img_cards:
                result.append(JPDeckCard(
                    name_jp=ic["name"],
                    set_code=ic.get("setCode", ""),
                    count=1,
                ))

        logger.info("Parsed %d cards from deck %s", len(result), deck_url)
        return result


def store_event_results(
    conn: sqlite3.Connection,
    event: JPEventResult,
    decklists: dict[str, list[JPDeckCard]],
) -> None:
    """Store Champions League event results and decklists in the database."""
    # Store event
    conn.execute(
        "INSERT OR REPLACE INTO cl_events (id, name, division, date) VALUES (?, ?, ?, ?)",
        (event.event_id, event.event_name, event.division, event.date),
    )

    for placement in event.placements:
        cursor = conn.execute(
            "INSERT INTO cl_placements (event_id, standing, player_name, region, deck_code, deck_url) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                event.event_id,
                placement.standing,
                placement.player_name,
                placement.region,
                placement.deck_code,
                placement.deck_url,
            ),
        )
        placement_id = cursor.lastrowid

        # Store decklist cards if we have them
        if placement.deck_code and placement.deck_code in decklists:
            for card in decklists[placement.deck_code]:
                en_name = JP_ENERGY_MAP.get(card.name_jp)
                conn.execute(
                    "INSERT OR REPLACE INTO cl_decklist_cards "
                    "(placement_id, card_name_jp, card_name_en, set_code, count, category) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        placement_id,
                        card.name_jp,
                        en_name,
                        card.set_code,
                        card.count,
                        card.category,
                    ),
                )

    conn.commit()
    logger.info(
        "Stored event %d (%s): %d placements, %d decklists",
        event.event_id,
        event.division,
        len(event.placements),
        len(decklists),
    )


def store_cl_city_league_results(
    conn: sqlite3.Connection,
    event: JPEventResult,
    decklists: dict[str, list[JPDeckCard]],
) -> None:
    """Store City League event results and decklists in the standard tournaments/placements tables."""
    tournament_id = f"jp-{event.event_id}"

    # Store tournament
    conn.execute(
        "INSERT OR REPLACE INTO tournaments (id, name, date, country) VALUES (?, ?, ?, ?)",
        (tournament_id, event.event_name, event.date, "JP"),
    )

    for placement in event.placements:
        cursor = conn.execute(
            "INSERT INTO placements (tournament_id, standing, player_name, archetype) "
            "VALUES (?, ?, ?, ?)",
            (
                tournament_id,
                placement.standing,
                placement.player_name,
                "Unknown",
            ),
        )
        placement_id = cursor.lastrowid

        # Store decklist cards if available
        if placement.deck_code and placement.deck_code in decklists:
            for card in decklists[placement.deck_code]:
                if card.set_code and card.card_number:
                    card_id = f"{card.set_code}-{card.card_number}"
                else:
                    card_id = card.name_jp
                conn.execute(
                    "INSERT OR REPLACE INTO decklist_cards "
                    "(placement_id, card_id, card_name, count) "
                    "VALUES (?, ?, ?, ?)",
                    (placement_id, card_id, card.name_jp, card.count),
                )

    conn.commit()
    logger.info(
        "Stored City League event %d (%s): %d placements, %d decklists",
        event.event_id,
        event.division,
        len(event.placements),
        len(decklists),
    )


def translate_cl_decklists(conn: sqlite3.Connection) -> int:
    """Translate JP card names in cl_decklist_cards using card_mappings table.

    Returns count of cards translated.
    """
    # Build JP name -> EN name lookup from card_mappings
    rows = conn.execute(
        "SELECT card_name_jp, card_name_en FROM card_mappings WHERE card_name_en IS NOT NULL"
    ).fetchall()
    jp_to_en: dict[str, str] = {r["card_name_jp"]: r["card_name_en"] for r in rows if r["card_name_jp"]}

    # Add energy translations
    jp_to_en.update(JP_ENERGY_MAP)

    # Update cl_decklist_cards where card_name_en is NULL
    untranslated = conn.execute(
        "SELECT rowid, card_name_jp FROM cl_decklist_cards WHERE card_name_en IS NULL"
    ).fetchall()

    translated = 0
    for row in untranslated:
        en_name = jp_to_en.get(row["card_name_jp"])
        if en_name:
            conn.execute(
                "UPDATE cl_decklist_cards SET card_name_en = ? WHERE rowid = ?",
                (en_name, row["rowid"]),
            )
            translated += 1

    conn.commit()
    logger.info("Translated %d/%d CL decklist cards", translated, len(untranslated))
    return translated
