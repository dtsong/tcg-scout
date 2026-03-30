"""Scraper for pokecazilla.com tournament results using kernel.sh cloud browsers.

Pokecazilla is a Japanese multi-TCG site that publishes tournament results
including Top 8 placements with deck codes and archetype names.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Deck code pattern: pokemon-card.com deck codes (e.g., kfF5VV-EpPYgW-fVkFkb)
DECK_CODE_RE = re.compile(r"[a-zA-Z0-9]{6}-[a-zA-Z0-9]{6}-[a-zA-Z0-9]{6}")

# Standing patterns for Top 8 placements
STANDING_PATTERNS = {
    "優勝": 1,
    "準優勝": 2,
    "1位": 1,
    "2位": 2,
    "3位": 3,
    "4位": 4,
    "5位": 5,
    "6位": 6,
    "7位": 7,
    "8位": 8,
}

# Patterns for Top 4 / Top 8 groupings
TOP4_PATTERNS = ["ベスト4", "TOP4", "Top4", "top4", "3位", "4位"]
TOP8_PATTERNS = ["ベスト8", "TOP8", "Top8", "top8", "5位", "6位", "7位", "8位"]


@dataclass
class PokecazillaPlacement:
    """A single placement from a Pokecazilla tournament article."""

    standing: int
    archetype_jp: str
    deck_code: str | None = None
    deck_url: str | None = None
    player_name: str | None = None


@dataclass
class PokecazillaArticle:
    """Parsed tournament results from a Pokecazilla article."""

    url: str
    title: str
    placements: list[PokecazillaPlacement] = field(default_factory=list)


@dataclass
class PokecazillaListEntry:
    """An article entry from the Pokecazilla article listing."""

    title: str
    url: str
    date: str | None = None


def parse_standing(text: str) -> int | None:
    """Extract a standing number from Japanese placement text.

    Handles patterns like 優勝 (1st), 準優勝 (2nd), ベスト4, ベスト8,
    and explicit numbered positions.
    """
    text = text.strip()

    # Check longer patterns first to avoid 優勝 matching before 準優勝
    # Sort by pattern length descending
    for pattern, standing in sorted(STANDING_PATTERNS.items(), key=lambda x: len(x[0]), reverse=True):
        if pattern in text:
            return standing

    # Top 4 group (assign 3 as standing, caller disambiguates)
    for pattern in TOP4_PATTERNS:
        if pattern in text:
            return 3

    # Top 8 group (assign 5 as standing, caller disambiguates)
    for pattern in TOP8_PATTERNS:
        if pattern in text:
            return 5

    # Numeric fallback: "第N位" or just "N位"
    m = re.search(r"(\d+)位", text)
    if m:
        return int(m.group(1))

    return None


def parse_placements_from_html(html: str) -> list[PokecazillaPlacement]:
    """Parse placement data from article HTML content.

    This is the pure-parsing function, separated from browser interaction
    for testability. Expects the inner HTML of the article content area.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    placements: list[PokecazillaPlacement] = []

    # Strategy 1: Look for heading + content blocks
    # Pokecazilla typically structures results as:
    #   <h2/h3> 優勝 デッキ名 </h2/h3>
    #   <p> deck code or link </p>
    headings = soup.find_all(["h2", "h3", "h4"])

    current_standing_counter = {"top4": 3, "top8": 5}

    for heading in headings:
        heading_text = heading.get_text(strip=True)
        standing = parse_standing(heading_text)
        if standing is None:
            continue

        # Disambiguate Top 4 / Top 8 entries
        if standing == 3 and any(p in heading_text for p in TOP4_PATTERNS):
            standing = current_standing_counter["top4"]
            current_standing_counter["top4"] += 1
        elif standing == 5 and any(p in heading_text for p in TOP8_PATTERNS):
            standing = current_standing_counter["top8"]
            current_standing_counter["top8"] += 1

        # Extract archetype name: remove standing text, keep the rest
        archetype = heading_text
        for pattern in list(STANDING_PATTERNS.keys()) + TOP4_PATTERNS + TOP8_PATTERNS:
            archetype = archetype.replace(pattern, "")
        # Also strip common decoration
        archetype = re.sub(r"[【】\[\]「」\s:：・/]+", " ", archetype).strip()
        # Remove "デッキ" (deck) suffix if present
        archetype = re.sub(r"\s*デッキ$", "", archetype).strip()

        if not archetype:
            archetype = heading_text

        # Look for deck code in siblings after this heading
        deck_code = None
        deck_url = None

        sibling = heading.find_next_sibling()
        siblings_checked = 0
        while sibling and siblings_checked < 5:
            sibling_text = sibling.get_text(strip=True)

            # Check for deck code in text
            code_match = DECK_CODE_RE.search(sibling_text)
            if code_match:
                deck_code = code_match.group(0)

            # Check for links to pokemon-card.com deck pages
            for link in sibling.find_all("a", href=True):
                href = link["href"]
                if "pokemon-card.com/deck" in href:
                    deck_url = href
                    # Extract deck code from URL
                    url_code = DECK_CODE_RE.search(href)
                    if url_code:
                        deck_code = url_code.group(0)

            # Also check sibling text for deck code
            if not deck_code:
                all_text = str(sibling)
                code_match = DECK_CODE_RE.search(all_text)
                if code_match:
                    deck_code = code_match.group(0)

            if deck_code:
                break

            # Stop if we hit another heading (next placement)
            if sibling.name in ("h2", "h3", "h4"):
                break

            sibling = sibling.find_next_sibling()
            siblings_checked += 1

        if deck_code and not deck_url:
            deck_url = f"https://www.pokemon-card.com/deck/confirm.html/deckID/{deck_code}"

        placements.append(
            PokecazillaPlacement(
                standing=standing,
                archetype_jp=archetype,
                deck_code=deck_code,
                deck_url=deck_url,
            )
        )

    # Strategy 2: If no headings found, try table-based extraction
    if not placements:
        placements = _parse_table_placements(soup)

    return placements


def _parse_table_placements(soup) -> list[PokecazillaPlacement]:
    """Fallback: parse placements from table rows."""
    placements: list[PokecazillaPlacement] = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            cell_texts = [c.get_text(strip=True) for c in cells]

            # Try to find a standing in the first cell
            standing = parse_standing(cell_texts[0])
            if standing is None:
                continue

            # Archetype from second cell
            archetype = cell_texts[1] if len(cell_texts) > 1 else ""

            # Look for deck code in any cell
            deck_code = None
            deck_url = None
            for cell in cells:
                full_text = str(cell)
                code_match = DECK_CODE_RE.search(full_text)
                if code_match:
                    deck_code = code_match.group(0)
                for link in cell.find_all("a", href=True):
                    href = link["href"]
                    if "pokemon-card.com/deck" in href:
                        deck_url = href
                        url_code = DECK_CODE_RE.search(href)
                        if url_code:
                            deck_code = url_code.group(0)

            if deck_code and not deck_url:
                deck_url = f"https://www.pokemon-card.com/deck/confirm.html/deckID/{deck_code}"

            placements.append(
                PokecazillaPlacement(
                    standing=standing,
                    archetype_jp=archetype,
                    deck_code=deck_code,
                    deck_url=deck_url,
                )
            )

    return placements


class PokecazillaClient:
    """Scraper for pokecazilla.com using kernel.sh cloud browsers.

    The site is WordPress-based and requires JS rendering for full content.
    """

    def __init__(self, api_key: str | None = None):
        from kernel import Kernel

        self._api_key = api_key or os.environ.get("KERNEL_API_KEY", "")
        if not self._api_key:
            raise ValueError("KERNEL_API_KEY not set")
        self._kernel = Kernel(api_key=self._api_key)

    async def fetch_article(self, url: str) -> PokecazillaArticle:
        """Fetch a tournament article and extract Top 8 placements.

        Args:
            url: Full URL to a Pokecazilla article (e.g.,
                 https://pokecazilla.com/column/cl2026osaka-decks/)

        Returns:
            PokecazillaArticle with parsed placements.
        """
        from playwright.async_api import async_playwright

        kb = self._kernel.browsers.create()

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(kb.cdp_ws_url)
                context = browser.contexts[0]
                page = context.pages[0]

                await page.goto(url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)

                title = await page.title()
                logger.info("Fetched article: %s", title)

                # Extract the main article content HTML
                content_html = await page.evaluate("""() => {
                    // WordPress article content selectors
                    const selectors = [
                        '.entry-content',
                        '.post-content',
                        'article .content',
                        'article',
                        '.main-content',
                        '#content',
                    ];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el) return el.innerHTML;
                    }
                    return document.body.innerHTML;
                }""")

                await browser.close()
        finally:
            self._kernel.browsers.delete_by_id(kb.session_id)

        placements = parse_placements_from_html(content_html)
        logger.info("Parsed %d placements from %s", len(placements), url)

        return PokecazillaArticle(
            url=url,
            title=title,
            placements=placements,
        )

    async def list_pokemon_articles(
        self, max_pages: int = 3
    ) -> list[PokecazillaListEntry]:
        """List recent Pokemon TCG articles from Pokecazilla.

        Browses the Pokemon TCG category/tag pages to find tournament result articles.

        Args:
            max_pages: Maximum number of listing pages to scan.

        Returns:
            List of article entries with title, URL, and date.
        """
        from playwright.async_api import async_playwright

        kb = self._kernel.browsers.create()
        articles: list[PokecazillaListEntry] = []

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(kb.cdp_ws_url)
                context = browser.contexts[0]
                page = context.pages[0]

                for page_num in range(1, max_pages + 1):
                    if page_num == 1:
                        url = "https://pokecazilla.com/category/pokemon/"
                    else:
                        url = f"https://pokecazilla.com/category/pokemon/page/{page_num}/"

                    logger.info("Listing articles page %d: %s", page_num, url)
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    await asyncio.sleep(2)

                    entries = await page.evaluate("""() => {
                        const results = [];
                        // Common WordPress listing selectors
                        const articleEls = document.querySelectorAll(
                            'article, .post, .entry, .archive-post'
                        );
                        for (const el of articleEls) {
                            const link = el.querySelector('a[href]');
                            const title = el.querySelector(
                                '.entry-title, .post-title, h2, h3'
                            );
                            const date = el.querySelector(
                                'time, .entry-date, .post-date, .date'
                            );
                            if (link) {
                                results.push({
                                    title: (title ? title.textContent : link.textContent).trim(),
                                    url: link.href,
                                    date: date ? (date.getAttribute('datetime') || date.textContent.trim()) : null,
                                });
                            }
                        }
                        return results;
                    }""")

                    if not entries:
                        logger.info("No more articles found on page %d", page_num)
                        break

                    for entry in entries:
                        articles.append(
                            PokecazillaListEntry(
                                title=entry["title"],
                                url=entry["url"],
                                date=entry.get("date"),
                            )
                        )

                await browser.close()
        finally:
            self._kernel.browsers.delete_by_id(kb.session_id)

        logger.info("Found %d Pokemon TCG articles", len(articles))
        return articles
