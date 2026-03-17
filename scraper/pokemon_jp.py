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

# JP card name -> EN card name translation map (built from TCGdex + manual)
# Energy names
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

# Division name mapping
DIVISION_MAP = {
    "ジュニア": "juniors",
    "シニア": "seniors",
    "マスター": "masters",
}


@dataclass
class JPPlacement:
    """A placement from the official JP site."""

    standing: int
    player_name: str
    region: str
    deck_url: str | None = None
    deck_code: str | None = None


@dataclass
class JPDeckCard:
    """A card in a JP decklist."""

    name_jp: str
    set_code: str = ""
    card_number: str = ""
    count: int = 1
    category: str = ""  # Pokemon, Trainer, Energy


@dataclass
class JPEventResult:
    """Results from a JP event."""

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

                # Extract event name and date
                event_name = title.split(" | ")[0].strip()
                date_text = await page.evaluate('''() => {
                    const text = document.body.innerText;
                    const match = text.match(/(\\d{4}\\/\\d{2}\\/\\d{2})/);
                    return match ? match[1] : '';
                }''')

                # Extract placements from all pages
                all_placements = []
                page_num = 1

                while True:
                    placements = await self._extract_placements(page)
                    all_placements.extend(placements)
                    logger.info(
                        "Event %d page %d: %d placements",
                        event_id, page_num, len(placements),
                    )

                    # Check for next page button
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
        """Extract placements from the current page."""
        data = await page.evaluate('''() => {
            const results = [];
            const rows = document.querySelectorAll('tr, [class*="result"] [class*="item"]');
            for (const row of rows) {
                const cells = row.querySelectorAll('td');
                if (cells.length < 3) continue;

                const standingText = cells[0]?.textContent?.trim() || '';
                const standingMatch = standingText.match(/(\\d+)/);
                if (!standingMatch) continue;

                const playerCell = cells[2] || cells[1];
                const playerName = playerCell?.textContent?.trim()?.split('\\n')[0]?.trim() || '';

                const regionCell = cells[3] || cells[2];
                const region = regionCell?.textContent?.trim() || '';

                // Find deck link
                const deckLink = row.querySelector('a[href*="deck/confirm"]');
                const deckUrl = deckLink?.href || '';
                const deckCodeMatch = deckUrl.match(/deckID\\/([\\w-]+)/);

                results.push({
                    standing: parseInt(standingMatch[1]),
                    playerName: playerName.replace(/プレイヤーID.*/, '').trim(),
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
        """Fetch a decklist from pokemon-card.com/deck/confirm.html."""
        kb = self._kernel.browsers.create()

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(kb.cdp_ws_url)
                context = browser.contexts[0]
                page = context.pages[0]

                await page.goto(deck_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(3)

                # Click "リスト表示" (List View) to get text card names
                list_btn = await page.query_selector('text=リスト表示')
                if list_btn:
                    await list_btn.click()
                    await asyncio.sleep(2)

                # Extract card data from list view
                cards = await page.evaluate('''() => {
                    const results = [];
                    const body = document.body.innerText;

                    // Parse the list view format:
                    // Category header (e.g., "ポケモン (23)")
                    // Card lines: "CardName\\nSETCODE\\nNUM/TOTAL\\tCount枚"
                    // or for trainers: "CardName\\tCount枚"
                    const lines = body.split('\\n').map(l => l.trim()).filter(l => l);

                    let currentCategory = '';
                    let i = 0;
                    while (i < lines.length) {
                        const line = lines[i];

                        // Category headers
                        if (line.match(/^ポケモン/)) { currentCategory = 'Pokemon'; i++; continue; }
                        if (line.match(/^グッズ/)) { currentCategory = 'Trainer'; i++; continue; }
                        if (line.match(/^ポケモンのどうぐ/)) { currentCategory = 'Trainer'; i++; continue; }
                        if (line.match(/^サポート/)) { currentCategory = 'Trainer'; i++; continue; }
                        if (line.match(/^スタジアム/)) { currentCategory = 'Trainer'; i++; continue; }
                        if (line.match(/^エネルギー/)) { currentCategory = 'Energy'; i++; continue; }

                        // Card line with count
                        const countMatch = line.match(/(\\d+)枚$/);
                        if (countMatch && currentCategory) {
                            const count = parseInt(countMatch[1]);
                            const cardName = line.replace(/\\t?\\d+枚$/, '').trim();

                            // Check if next lines have set code and number (Pokemon cards)
                            let setCode = '';
                            let cardNumber = '';
                            if (i + 2 < lines.length && lines[i+1].match(/^[A-Z0-9]{2,}$/) && lines[i+2].match(/^\\d+\\/\\d+$/)) {
                                // Actually the format is: "Name\\nSetCode\\nNum/Total\\tCount枚"
                                // But in innerText it may be on same or different lines
                            }

                            results.push({
                                name: cardName,
                                setCode,
                                cardNumber,
                                count,
                                category: currentCategory,
                            });
                        }
                        i++;
                    }
                    return results;
                }''')

                # Also extract from img alt attributes as backup (more reliable for names)
                img_cards = await page.evaluate('''() => {
                    const cards = [];
                    const imgs = document.querySelectorAll('.thumbsImageArea img, [class*="card"] img');
                    imgs.forEach(img => {
                        const alt = img.alt || '';
                        if (alt && !alt.includes('ポケモンカードゲーム') && !alt.includes('マイページ') && !alt.includes('ENJOY') && !alt.includes('CHALLENGE') && !alt.includes('チャンピオンシップ') && !alt.includes('プレイヤーズクラブ') && !alt.includes('LINEで送る')) {
                            // Extract set code from image URL
                            const src = img.src || '';
                            const setMatch = src.match(/card_images\\/large\\/([A-Za-z0-9]+)\\//);
                            cards.push({
                                name: alt,
                                setCode: setMatch ? setMatch[1] : '',
                                src: src,
                            });
                        }
                    });
                    return cards;
                }''')

                await browser.close()
        finally:
            self._kernel.browsers.delete_by_id(kb.session_id)

        # Merge data: use img_cards for JP names + set codes, text cards for counts
        result = []
        if cards:
            # Match img cards to text cards by position
            for i, card in enumerate(cards):
                jp_name = card["name"]
                set_code = ""
                card_number = ""

                if i < len(img_cards):
                    jp_name = img_cards[i]["name"] or jp_name
                    set_code = img_cards[i].get("setCode", "")

                result.append(JPDeckCard(
                    name_jp=jp_name,
                    set_code=set_code,
                    card_number=card_number,
                    count=card["count"],
                    category=card["category"],
                ))
        elif img_cards:
            # Fallback: only img data available
            for ic in img_cards:
                result.append(JPDeckCard(
                    name_jp=ic["name"],
                    set_code=ic.get("setCode", ""),
                    count=1,
                ))

        logger.info("Parsed %d cards from deck", len(result))
        return result


def build_jp_to_en_map(conn: sqlite3.Connection) -> dict[str, str]:
    """Build a JP card name to EN card name translation map from the cards table.

    Uses TCGdex set codes mapped from Limitless set codes to look up cards.
    This is a best-effort mapping — many JP-only cards won't have EN equivalents.
    """
    # For now, return the energy map as a baseline
    # The full translation will come from cross-referencing card images/IDs
    return dict(JP_ENERGY_MAP)
