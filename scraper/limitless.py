"""Synchronous LimitlessTCG scraper adapted from the TrainerLab async version.

Scrapes Japanese City League tournament listings, placements, and decklists
from limitlesstcg.com using httpx sync client with rate limiting.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from urllib.parse import urljoin

import httpx
from bs4 import Tag

from analysis.archetype import normalize_archetype
from config import (
    LIMITLESS_BASE_URL,
    LIMITLESS_MAX_RETRIES,
    LIMITLESS_REQUESTS_PER_MINUTE,
    LIMITLESS_TIMEOUT,
)
from scraper.http_client import (
    DECKLIST_LINE_RE,
    CardEntry,
    RateLimitedHTTPClient,
    extract_sprites,
    parse_card_links,
)

# Backward-compatible alias — tests/test_limitless_transforms.py imports this name
_DECKLIST_LINE_RE = DECKLIST_LINE_RE

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class LimitlessDecklist:
    cards: list[CardEntry]
    source_url: str | None = None


@dataclass
class LimitlessPlacement:
    placement: int
    player_name: str | None
    archetype: str
    decklist: LimitlessDecklist | None = None
    decklist_url: str | None = None
    sprite_urls: list[str] = field(default_factory=list)


@dataclass
class LimitlessTournament:
    name: str
    tournament_date: date
    source_url: str
    player_count: int = 0
    placements: list[LimitlessPlacement] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class LimitlessClient(RateLimitedHTTPClient):
    """Synchronous scraper for LimitlessTCG tournament data."""

    def __init__(self) -> None:
        super().__init__(
            base_url=LIMITLESS_BASE_URL,
            max_rpm=LIMITLESS_REQUESTS_PER_MINUTE,
            timeout=LIMITLESS_TIMEOUT,
            max_retries=LIMITLESS_MAX_RETRIES,
            user_agent="TrainerLab-Scout/1.0 (rotation-analysis)",
            use_base_url=True,
        )

    # ------------------------------------------------------------------
    # Tournament listings
    # ------------------------------------------------------------------

    def fetch_jp_city_league_listings(
        self, start_date: str, end_date: str
    ) -> list[LimitlessTournament]:
        """Scrape JP City League tournament listings within a date range.

        Args:
            start_date: Inclusive start date in ISO format (YYYY-MM-DD).
            end_date: Inclusive end date in ISO format (YYYY-MM-DD).

        Returns:
            List of LimitlessTournament objects (without placements populated).
        """
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        tournaments: list[LimitlessTournament] = []
        page = 1

        while True:
            url = f"/tournaments/jp?show=100&page={page}"
            logger.info("Fetching tournament listings page %d", page)
            soup = self._soup(url)

            table = soup.find("table")
            if table is None:
                logger.warning("No table found on page %d, stopping pagination", page)
                break

            rows = table.find_all("tr")  # type: ignore[union-attr]
            if len(rows) <= 1:
                # Only header row or empty
                break

            stop_early = False

            for row in rows[1:]:  # Skip header
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue

                # Parse date from first cell: "01 Feb 26"
                date_text = cells[0].get_text(strip=True)
                try:
                    tournament_date = datetime.strptime(date_text, "%d %b %y").date()
                except ValueError:
                    logger.debug("Could not parse date: %r", date_text)
                    continue

                # If tournament is before our window, we've gone past it
                if tournament_date < start:
                    stop_early = True
                    break

                # Skip if after end date
                if tournament_date > end:
                    continue

                # Extract prefecture and link
                prefecture = cells[1].get_text(strip=True)

                # Find tournament link (pattern: /tournaments/jp/[ID])
                tournament_href = None
                for a_tag in row.find_all("a"):
                    href = a_tag.get("href", "")
                    if "/tournaments/jp/" in href:
                        tournament_href = href
                        if not prefecture:
                            prefecture = a_tag.get_text(strip=True)
                        break

                if not tournament_href:
                    logger.debug("No tournament link found in row, skipping")
                    continue

                source_url = urljoin(self._base_url, tournament_href)
                name = f"City League {prefecture}"

                tournaments.append(
                    LimitlessTournament(
                        name=name,
                        tournament_date=tournament_date,
                        source_url=source_url,
                    )
                )

            if stop_early:
                break

            # Always paginate if the page had rows (reverse chronological order
            # means we may need to go past pages with dates > end to reach
            # dates within the window)
            page += 1
            if page > 20:  # Safety limit
                break

        logger.info(
            "Found %d tournaments in date range %s to %s", len(tournaments), start_date, end_date
        )
        return tournaments

    # ------------------------------------------------------------------
    # Placements
    # ------------------------------------------------------------------

    def fetch_jp_city_league_placements(
        self, tournament_url: str, max_placements: int = 32
    ) -> list[LimitlessPlacement]:
        """Scrape standings from a tournament page.

        Args:
            tournament_url: Full URL to the tournament page.
            max_placements: Maximum number of placements to return.

        Returns:
            List of LimitlessPlacement objects.
        """
        # Use relative URL if it starts with base
        url = tournament_url
        if url.startswith(self._base_url):
            url = url[len(self._base_url) :]

        soup = self._soup(url)

        # Find standings table
        table = soup.find("table", class_="striped") or soup.find("table", class_="standings")

        if table is None:
            # Fallback: find any table with 3+ data rows
            for candidate in soup.find_all("table"):
                data_rows = candidate.find_all("tr")
                if len(data_rows) >= 4:  # header + 3 data rows
                    table = candidate
                    break

        if table is None:
            logger.warning("No standings table found at %s", tournament_url)
            return []

        placements: list[LimitlessPlacement] = []
        rows = table.find_all("tr")  # type: ignore[union-attr]

        for row in rows[1:]:  # Skip header
            if len(placements) >= max_placements:
                break

            cells = row.find_all("td")
            if len(cells) < 3:
                logger.warning(
                    "Skipping standings row with %d cells (expected >=3) at %s",
                    len(cells),
                    tournament_url,
                )
                continue

            # Column 0: rank
            rank_text = cells[0].get_text(strip=True)
            try:
                rank = int(rank_text.rstrip("."))
            except (ValueError, AttributeError):
                logger.warning(
                    "Failed to parse rank %r at %s, skipping row",
                    rank_text,
                    tournament_url,
                )
                continue

            # Column 1: player name
            player_name = cells[1].get_text(strip=True) or None

            # Find deck/archetype cell and decklist URL
            # Column layout varies: JP City Leagues have deck in col 2,
            # international tournaments may have Country in col 2, Deck in col 3, List in col 4
            decklist_url: str | None = None
            archetype = ""
            sprite_urls: list[str] = []

            for cell in cells[2:]:
                imgs = cell.find_all("img")
                has_sprites = any("pokemon" in (img.get("src", "") or "") for img in imgs)
                cell_link = cell.find("a")

                if has_sprites and cell_link and not sprite_urls:
                    # This is the archetype/deck cell — extract sprites
                    archetype, sprite_urls = self._extract_archetype_and_sprites(cell_link)
                    # Only use this href as decklist if it looks like a list URL
                    href = cell_link.get("href", "")
                    if href and "/decks/list/" in href:
                        decklist_url = urljoin(self._base_url, href)
                elif cell_link:
                    href = cell_link.get("href", "")
                    # Separate decklist column (e.g. /decks/list/24428)
                    if "/decks/list/" in href:
                        decklist_url = urljoin(self._base_url, href)

            if not archetype and not sprite_urls:
                # Fallback: try cells[2] as plain text archetype
                archetype = cells[2].get_text(strip=True)

            # Normalize archetype using sprite URLs
            archetype = normalize_archetype(sprite_urls, html_archetype=archetype)

            placements.append(
                LimitlessPlacement(
                    placement=rank,
                    player_name=player_name,
                    archetype=archetype,
                    decklist_url=decklist_url,
                    sprite_urls=sprite_urls,
                )
            )

        logger.info("Parsed %d placements from %s", len(placements), tournament_url)
        return placements

    # ------------------------------------------------------------------
    # Decklist parsing
    # ------------------------------------------------------------------

    def fetch_decklist(self, decklist_url: str) -> LimitlessDecklist | None:
        """Fetch and parse a decklist page.

        Tries the official card-link format first, then falls back to text
        format parsing.

        Args:
            decklist_url: Full URL to the decklist page.

        Returns:
            Parsed LimitlessDecklist, or None if parsing fails.
        """
        url = decklist_url
        if url.startswith(self._base_url):
            url = url[len(self._base_url) :]

        try:
            soup = self._soup(url)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in (401, 403):
                logger.error(
                    "HTTP %d fetching decklist %s — scraper may be blocked",
                    status,
                    decklist_url,
                )
                raise  # Let caller trip circuit breaker
            logger.warning("HTTP %d fetching decklist %s", status, decklist_url)
            return None
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
            logger.warning("Network error fetching decklist %s: %s", decklist_url, exc)
            return None

        # Strategy 1: Structured card-link elements
        cards = parse_card_links(soup, decklist_url)

        # Strategy 2: Text format fallback
        if not cards:
            logger.info(
                "No card-link elements found in %s, falling back to text parsing", decklist_url
            )
            text = soup.get_text("\n")
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue

                match = DECKLIST_LINE_RE.match(line)
                if match:
                    count = int(match.group(1))
                    name = match.group(2).strip()
                    set_code = match.group(3)
                    card_number = match.group(4)
                    cards.append(
                        {
                            "count": count,
                            "name": name,
                            "set_code": set_code,
                            "card_number": card_number,
                            "card_id": f"{set_code}-{card_number}",
                        }
                    )
                    continue

                # Handle basic energy lines (no card number)
                energy_match = re.match(r"^(\d+)\s+(Basic\s+\w+\s+Energy)\s*$", line, re.IGNORECASE)
                if energy_match:
                    name = energy_match.group(2).strip()
                    cards.append(
                        {
                            "count": int(energy_match.group(1)),
                            "name": name,
                            "set_code": "Energy",
                            "card_number": "",
                            "card_id": name,
                        }
                    )

        if not cards:
            logger.warning("No cards parsed from decklist: %s", decklist_url)
            return None

        return LimitlessDecklist(cards=cards, source_url=decklist_url)

    # ------------------------------------------------------------------
    # Sprite / archetype extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_archetype_and_sprites(
        link_tag: Tag,
    ) -> tuple[str, list[str]]:
        """Extract archetype name and sprite URLs from a deck link tag."""
        return extract_sprites(link_tag, join_sep=" / ")

    def __enter__(self) -> "LimitlessClient":
        return self


def match_archetype_labels(
    jp_placements: list[dict],
    limitless_data: list[dict],
) -> list[dict]:
    """Match Limitless archetype labels to JP placements by date + standing.

    Args:
        jp_placements: Dicts with 'date', 'standing', 'player_name' keys.
        limitless_data: Dicts with 'date', 'standing', 'archetype' keys.

    Returns:
        Copy of jp_placements with 'archetype' field populated where matched.
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
