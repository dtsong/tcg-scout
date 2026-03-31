"""Scraper for pokecabook.com using kernel.sh cloud browsers.

Fetches deck recipes, CL results, and average card counts from PokecaBook,
a Japanese Pokemon TCG analytics site. Requires JS rendering (WordPress/Cocoon theme).

PokecaBook articles do NOT contain card-level text data. Instead they embed:
  - Deck screenshot images (from pokemon-card.com)
  - Links to pokemon-card.com deck pages with deck IDs
  - Placement info in headings or figcaptions

The primary extracted data is PBDeckEntry: a deck ID, image URL, placement, and
event context. Card-level data must be fetched separately from pokemon-card.com.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)

# PokecaBook card category headers (JP)
# Ordered longest-first so "ポケモンのどうぐ" matches before "ポケモン"
_CATEGORY_HEADERS: list[tuple[str, str]] = [
    ("ポケモンのどうぐ", "Trainer"),
    ("ポケモン", "Pokemon"),
    ("グッズ", "Trainer"),
    ("サポート", "Trainer"),
    ("スタジアム", "Trainer"),
    ("エネルギー", "Energy"),
]

# Placement text to numeric rank mapping
_PLACEMENT_MAP: list[tuple[str, int]] = [
    ("優勝", 1),
    ("準優勝", 2),
    ("ベスト4", 4),
    ("TOP4", 4),
    ("3位", 3),
    ("4位", 4),
    ("ベスト8", 8),
    ("TOP8", 8),
    ("ベスト16", 16),
    ("TOP16", 16),
    ("ベスト32", 32),
    ("TOP32", 32),
]

# Regex to extract deck ID from pokemon-card.com URLs
_DECK_ID_RE = re.compile(r"pokemon-card\.com/deck/result\.html/deckID/([A-Za-z0-9-]+)")


@dataclass
class PBDeckEntry:
    """A deck entry from a PokecaBook article.

    PokecaBook embeds decks as screenshot images with links to pokemon-card.com.
    This captures the deck ID, image, placement, and context from the article.
    """

    deck_id: str  # pokemon-card.com deck ID (e.g., "kfF5VV-EpPYgW-fVkFkb")
    deck_url: str = ""  # full pokemon-card.com URL
    image_url: str = ""  # deck screenshot hosted on pokecabook.com
    placement: int | None = None  # 1=win, 2=runner-up, 4=top4, etc.
    placement_label: str = ""  # original JP text (e.g., "優勝", "TOP8")
    archetype_jp: str = ""  # archetype name if detectable
    event_label: str = ""  # event/date from figcaption (e.g., "3/27 ジムバトル優勝")


@dataclass
class PBCard:
    """A single card entry from a PokecaBook deck recipe."""

    name_jp: str
    count: int = 1
    category: str = ""  # Pokemon, Trainer, Energy


@dataclass
class PBAvgCard:
    """Average card count from PokecaBook archetype analysis.

    PokecaBook's unique data: average counts across multiple winning decklists.
    """

    name_jp: str
    avg_count: float = 0.0
    adoption_rate: float = 0.0  # percentage of decks running this card
    category: str = ""


@dataclass
class PBDeckRecipe:
    """A single deck recipe extracted from a PokecaBook article.

    For CL/tournament result articles, `cards` will be empty and `deck_entries`
    will contain the deck references. Card data lives on pokemon-card.com.
    """

    title: str
    cards: list[PBCard] = field(default_factory=list)
    deck_entries: list[PBDeckEntry] = field(default_factory=list)
    archetype_jp: str = ""
    event_name: str = ""
    placement: int | None = None
    player_name: str = ""


@dataclass
class PBArchetypeAnalysis:
    """Average card counts across winning decklists for an archetype.

    This is PokecaBook's unique analytical data -- not available elsewhere.
    """

    archetype_jp: str
    sample_size: int = 0  # number of decklists averaged
    avg_cards: list[PBAvgCard] = field(default_factory=list)
    source_url: str = ""


@dataclass
class PBArticle:
    """Metadata for a PokecaBook article."""

    url: str
    title: str
    date: str = ""
    category: str = ""  # CL, City League, archetype analysis, etc.
    excerpt: str = ""


def parse_deck_entries_from_html(html: str) -> list[PBDeckEntry]:
    """Parse deck entries from PokecaBook article HTML.

    PokecaBook articles embed decks as <figure> elements containing:
      - A deck screenshot <img> (hosted on pokecabook.com)
      - A <figcaption> with a link to pokemon-card.com/deck/result.html/deckID/...
      - Placement context from preceding <h4>/<h2> headings

    This is the primary extraction function for PokecaBook content.
    Returns a list of PBDeckEntry with deck IDs, image URLs, and placements.
    """
    soup = BeautifulSoup(html, "html.parser")
    entries: list[PBDeckEntry] = []

    # Track current placement from heading context
    current_placement: int | None = None
    current_placement_label = ""

    # Walk through all elements in document order to track heading context
    for element in soup.find_all(["h2", "h3", "h4", "figure"]):
        # Update placement context from headings
        if element.name in ("h2", "h3", "h4"):
            text = element.get_text(strip=True)
            placement, label = _parse_placement_text(text)
            if placement is not None:
                current_placement = placement
                current_placement_label = label
            continue

        # Process figure elements for deck data
        if element.name != "figure":
            continue

        # Extract deck URL from figcaption link
        deck_url = ""
        deck_id = ""
        event_label = ""
        figcaption = element.find("figcaption")
        if figcaption:
            link = figcaption.find("a", href=_DECK_ID_RE)
            if link:
                deck_url = link.get("href", "")
                id_match = _DECK_ID_RE.search(deck_url)
                if id_match:
                    deck_id = id_match.group(1)
            event_label = figcaption.get_text(strip=True)

        # Also check for deck URL in the figure's direct <a> href
        if not deck_id:
            for a_tag in element.find_all("a", href=True):
                id_match = _DECK_ID_RE.search(a_tag["href"])
                if id_match:
                    deck_id = id_match.group(1)
                    deck_url = a_tag["href"]
                    break

        if not deck_id:
            continue

        # Extract image URL
        image_url = ""
        img = element.find("img")
        if img:
            # Prefer data-src (lazy-loaded) over src (may be placeholder)
            image_url = img.get("data-src") or img.get("src", "")
            # Skip base64 placeholder images
            if image_url.startswith("data:"):
                image_url = img.get("data-src", "")

        # Check figcaption for placement override (e.g., "3/27 ジムバトル優勝")
        fig_placement = current_placement
        fig_label = current_placement_label
        if event_label:
            p, lbl = _parse_placement_text(event_label)
            if p is not None:
                fig_placement = p
                fig_label = lbl

        # Extract archetype from figure class (e.g., "o_001", "o_004")
        # Not directly useful but preserved as context
        archetype_jp = ""

        entries.append(
            PBDeckEntry(
                deck_id=deck_id,
                deck_url=deck_url,
                image_url=image_url,
                placement=fig_placement,
                placement_label=fig_label,
                archetype_jp=archetype_jp,
                event_label=event_label,
            )
        )

    return entries


def parse_deck_cards_from_html(html: str) -> list[PBCard]:
    """Parse deck recipe cards from article HTML content.

    PokecaBook formats decks as tables or structured lists with
    card names and quantities. This is the testable pure-parsing function.

    Note: Most PokecaBook articles do NOT contain card-level text. They embed
    deck screenshots with links to pokemon-card.com instead. Use
    parse_deck_entries_from_html() for those articles.
    """
    soup = BeautifulSoup(html, "html.parser")
    cards: list[PBCard] = []
    current_category = ""

    # Strategy 1: Look for table-based deck lists
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            # Check for category header row
            row_text = row.get_text(strip=True)
            for jp_cat, en_cat in _CATEGORY_HEADERS:
                if jp_cat in row_text and len(cells) <= 2:
                    current_category = en_cat
                    break

            # Look for card name + count patterns in cells
            if len(cells) >= 2:
                name_text = cells[0].get_text(strip=True)
                count_text = cells[-1].get_text(strip=True)

                # Count cell: plain number or "N枚"
                count_match = re.match(r"^(\d+)枚?$", count_text)
                if count_match and name_text and not _is_category_header(name_text):
                    cards.append(
                        PBCard(
                            name_jp=name_text,
                            count=int(count_match.group(1)),
                            category=current_category,
                        )
                    )

    if cards:
        return cards

    # Strategy 2: Look for list-based format (ul/li or plain text)
    current_category = ""
    for element in soup.find_all(["p", "li", "div", "h2", "h3", "h4"]):
        text = element.get_text(strip=True)
        if not text:
            continue

        # Check for category headers
        for jp_cat, en_cat in _CATEGORY_HEADERS:
            if text.startswith(jp_cat):
                current_category = en_cat
                break

        # Pattern: "カード名 N枚" or "カード名 x N" or "カード名　N"
        # Use \s+ before optional xX× to avoid matching 'x' in card names like "リザードンex"
        card_match = re.match(r"^(.+?)\s+[xX×]?\s*(\d+)枚?$", text)
        if card_match and current_category:
            name = card_match.group(1).strip()
            if not _is_category_header(name) and len(name) > 1:
                cards.append(
                    PBCard(
                        name_jp=name,
                        count=int(card_match.group(2)),
                        category=current_category,
                    )
                )

    return cards


def parse_avg_cards_from_html(html: str) -> list[PBAvgCard]:
    """Parse average card count tables from PokecaBook archetype analysis articles.

    These articles show average counts and adoption rates across multiple
    winning decklists -- PokecaBook's unique analytical data.
    """
    soup = BeautifulSoup(html, "html.parser")
    avg_cards: list[PBAvgCard] = []
    current_category = ""

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            row_text = row.get_text(strip=True)

            # Category headers
            for jp_cat, en_cat in _CATEGORY_HEADERS:
                if jp_cat in row_text and len(cells) <= 2:
                    current_category = en_cat
                    break

            if len(cells) < 2:
                continue

            name_text = cells[0].get_text(strip=True)
            if _is_category_header(name_text) or not name_text:
                continue

            # Look for average count (float) and optional adoption rate (percentage)
            avg_count = 0.0
            adoption_rate = 0.0

            for cell in cells[1:]:
                cell_text = cell.get_text(strip=True)

                # Adoption rate: "85%" or "85.5%"
                pct_match = re.match(r"^([\d.]+)%$", cell_text)
                if pct_match:
                    adoption_rate = float(pct_match.group(1))
                    continue

                # Average count: "3.5" or "2.8枚" or plain number
                avg_match = re.match(r"^([\d.]+)枚?$", cell_text)
                if avg_match and not pct_match:
                    val = float(avg_match.group(1))
                    # Distinguish: if > 100 it's probably not a card count
                    if val <= 60:
                        avg_count = val

            if avg_count > 0 or adoption_rate > 0:
                avg_cards.append(
                    PBAvgCard(
                        name_jp=name_text,
                        avg_count=avg_count,
                        adoption_rate=adoption_rate,
                        category=current_category,
                    )
                )

    return avg_cards


def _parse_placement_text(text: str) -> tuple[int | None, str]:
    """Extract placement rank from Japanese text.

    Returns (rank, label) where label is the matched JP text.
    Returns (None, '') if no placement found.

    Important: check "準優勝" before "優勝" since "優勝" is a substring.
    """
    # Check "準優勝" first to avoid false match on "優勝"
    if "準優勝" in text:
        return 2, "準優勝"
    for label, rank in _PLACEMENT_MAP:
        if label == "準優勝":
            continue  # already handled above
        if label in text:
            return rank, label
    return None, ""


def _is_category_header(text: str) -> bool:
    """Check if text is a deck category header rather than a card name."""
    for jp_cat, _ in _CATEGORY_HEADERS:
        if text.startswith(jp_cat):
            return True
    return False


class PokecaBookClient:
    """Scraper for pokecabook.com using kernel.sh cloud browsers.

    Usage:
        client = PokecaBookClient()
        recipe = await client.fetch_deck_recipe("https://pokecabook.com/archives/307010")
        articles = await client.list_articles()
    """

    BASE_URL = "https://pokecabook.com"

    def __init__(self, api_key: str | None = None):
        from kernel import Kernel

        self._api_key = api_key or os.environ.get("KERNEL_API_KEY", "")
        if not self._api_key:
            raise ValueError("KERNEL_API_KEY not set")
        self._kernel = Kernel(api_key=self._api_key)

    async def _run_in_browser(self, callback):
        """Execute a callback with a managed browser session.

        Handles browser creation, Playwright connection, and cleanup.
        The callback receives a Page instance.
        """
        from playwright.async_api import async_playwright

        kb = self._kernel.browsers.create()
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(kb.cdp_ws_url)
                page = browser.contexts[0].pages[0]
                result = await callback(page)
                await browser.close()
                return result
        finally:
            self._kernel.browsers.delete_by_id(kb.session_id)

    async def fetch_deck_recipe(self, url: str) -> PBDeckRecipe:
        """Fetch a deck recipe article and extract card data.

        Args:
            url: Full article URL (e.g., https://pokecabook.com/archives/307010)

        Returns:
            PBDeckRecipe with extracted cards, title, and metadata.
        """

        async def _scrape(page: Page) -> PBDeckRecipe:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            title = await page.title()
            title = title.split("|")[0].strip() if "|" in title else title

            # Extract article content HTML for parsing
            content_html = await page.evaluate("""() => {
                const article = document.querySelector('.entry-content')
                    || document.querySelector('article')
                    || document.querySelector('.post');
                return article ? article.innerHTML : document.body.innerHTML;
            }""")

            # Extract metadata from page
            meta = await page.evaluate("""() => {
                const result = {archetype: '', event: '', placement: 0, player: ''};

                // Title often contains archetype + event info
                const title = document.title || '';
                result.fullTitle = title;

                // Look for structured data in the article
                const content = document.querySelector('.entry-content')
                    || document.querySelector('article')
                    || document.body;
                const text = content ? content.innerText : '';

                // Try to find placement info (e.g., "優勝" = 1st, "準優勝" = 2nd)
                if (text.includes('優勝') && !text.includes('準優勝')) result.placement = 1;
                else if (text.includes('準優勝')) result.placement = 2;
                else if (text.includes('ベスト4') || text.includes('3位') || text.includes('4位')) result.placement = 4;
                else if (text.includes('ベスト8')) result.placement = 8;
                else if (text.includes('ベスト16')) result.placement = 16;

                return result;
            }""")

            # Primary: extract deck entries (images + deck IDs)
            deck_entries = parse_deck_entries_from_html(content_html)

            # Fallback: try card-level text extraction (rare on PokecaBook)
            cards = parse_deck_cards_from_html(content_html)
            if not cards:
                cards = await self._extract_cards_from_text(page)

            return PBDeckRecipe(
                title=title,
                cards=cards,
                deck_entries=deck_entries,
                archetype_jp=meta.get("archetype", ""),
                event_name=meta.get("event", ""),
                placement=meta.get("placement") or None,
                player_name=meta.get("player", ""),
            )

        return await self._run_in_browser(_scrape)

    async def fetch_archetype_analysis(self, url: str) -> PBArchetypeAnalysis:
        """Fetch an archetype analysis article with average card counts.

        PokecaBook publishes articles showing average card counts across
        multiple winning decklists for popular archetypes.

        Args:
            url: Full article URL.

        Returns:
            PBArchetypeAnalysis with average card data.
        """

        async def _scrape(page: Page) -> PBArchetypeAnalysis:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            title = await page.title()
            title = title.split("|")[0].strip() if "|" in title else title

            content_html = await page.evaluate("""() => {
                const article = document.querySelector('.entry-content')
                    || document.querySelector('article')
                    || document.querySelector('.post');
                return article ? article.innerHTML : document.body.innerHTML;
            }""")

            # Try to extract sample size from text like "N件のデッキ" or "N個のレシピ"
            sample_text = await page.evaluate("""() => {
                const text = document.body.innerText;
                const match = text.match(/(\\d+)\\s*[件個]の?(デッキ|レシピ)/);
                return match ? parseInt(match[1]) : 0;
            }""")

            avg_cards = parse_avg_cards_from_html(content_html)

            return PBArchetypeAnalysis(
                archetype_jp=title,
                sample_size=sample_text or 0,
                avg_cards=avg_cards,
                source_url=url,
            )

        return await self._run_in_browser(_scrape)

    async def list_articles(
        self,
        search_query: str | None = None,
        max_pages: int = 1,
    ) -> list[PBArticle]:
        """List recent articles, optionally filtered by search query.

        Args:
            search_query: Optional search term (e.g., "CL大阪", "シティリーグ")
            max_pages: Maximum number of listing pages to scrape.

        Returns:
            List of PBArticle metadata objects.
        """

        async def _scrape(page: Page) -> list[PBArticle]:
            articles: list[PBArticle] = []

            for page_num in range(1, max_pages + 1):
                if search_query:
                    url = f"{self.BASE_URL}/?s={search_query}&paged={page_num}"
                else:
                    url = f"{self.BASE_URL}/page/{page_num}" if page_num > 1 else self.BASE_URL

                await page.goto(url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)

                page_articles = await page.evaluate("""() => {
                    const results = [];
                    // Cocoon theme uses .entry-card-wrap or article elements
                    const entries = document.querySelectorAll(
                        '.entry-card-wrap, article.post, .post-list-item'
                    );

                    entries.forEach(entry => {
                        const link = entry.querySelector('a');
                        const titleEl = entry.querySelector(
                            '.entry-card-title, .post-title, h2, h3'
                        );
                        const dateEl = entry.querySelector(
                            '.entry-date, time, .post-date'
                        );
                        const excerptEl = entry.querySelector(
                            '.entry-card-snippet, .post-excerpt, .entry-summary'
                        );
                        const catEl = entry.querySelector(
                            '.cat-label, .category-label'
                        );

                        if (link && titleEl) {
                            results.push({
                                url: link.href || '',
                                title: titleEl.textContent.trim(),
                                date: dateEl ? dateEl.textContent.trim() : '',
                                category: catEl ? catEl.textContent.trim() : '',
                                excerpt: excerptEl ? excerptEl.textContent.trim() : '',
                            });
                        }
                    });
                    return results;
                }""")

                for a in page_articles:
                    articles.append(
                        PBArticle(
                            url=a["url"],
                            title=a["title"],
                            date=a.get("date", ""),
                            category=a.get("category", ""),
                            excerpt=a.get("excerpt", ""),
                        )
                    )

                if not page_articles:
                    break  # No more results

            return articles

        return await self._run_in_browser(_scrape)

    async def _extract_cards_from_text(self, page: Page) -> list[PBCard]:
        """Fallback: extract card data from page text when HTML parsing fails."""
        text_data = await page.evaluate("""() => {
            const body = document.body.innerText;
            const lines = body.split('\\n').map(l => l.trim()).filter(l => l);
            const cards = [];
            let category = '';

            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];

                // Category headers
                if (/^ポケモン/.test(line)) { category = 'Pokemon'; continue; }
                if (/^グッズ/.test(line)) { category = 'Trainer'; continue; }
                if (/^ポケモンのどうぐ/.test(line)) { category = 'Trainer'; continue; }
                if (/^サポート/.test(line)) { category = 'Trainer'; continue; }
                if (/^スタジアム/.test(line)) { category = 'Trainer'; continue; }
                if (/^エネルギー/.test(line)) { category = 'Energy'; continue; }

                // Card pattern: "name N枚" or "name\tN"
                const match = line.match(/^(.+?)\\s*[xX×]?\\s*(\\d+)枚?$/);
                if (match && category) {
                    const name = match[1].trim();
                    const count = parseInt(match[2]);
                    if (name.length > 1 && count > 0 && count <= 60) {
                        cards.push({name, count, category});
                    }
                }
            }
            return cards;
        }""")

        return [
            PBCard(
                name_jp=c["name"],
                count=c["count"],
                category=c.get("category", ""),
            )
            for c in text_data
        ]
