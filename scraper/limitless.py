"""Synchronous LimitlessTCG scraper adapted from the TrainerLab async version.

Scrapes Japanese City League tournament listings, placements, and decklists
from limitlesstcg.com using httpx sync client with rate limiting.
"""

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from analysis.archetype import normalize_archetype
from config import (
    LIMITLESS_BASE_URL,
    LIMITLESS_MAX_RETRIES,
    LIMITLESS_REQUESTS_PER_MINUTE,
    LIMITLESS_TIMEOUT,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LimitlessDecklist:
    cards: list[dict[str, Any]]  # Each dict has: count, name, set_code, card_number
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
# Decklist text-line regex
# ---------------------------------------------------------------------------

_DECKLIST_LINE_RE = re.compile(
    r"^(\d+)\s+(.+?)\s+([A-Z0-9]{2,5}[A-Z]?|Energy)\s+(\d+|[A-Z]+\d*)$"
)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class LimitlessClient:
    """Synchronous scraper for LimitlessTCG tournament data."""

    def __init__(self) -> None:
        self._base_url = LIMITLESS_BASE_URL
        self._max_rpm = LIMITLESS_REQUESTS_PER_MINUTE
        self._timeout = LIMITLESS_TIMEOUT
        self._max_retries = LIMITLESS_MAX_RETRIES
        self._request_timestamps: list[float] = []
        self._lock = threading.Lock()
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "TrainerLab-Scout/1.0 (rotation-analysis)",
            },
        )

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _rate_limit(self) -> None:
        """Block until a request slot is available (max N requests/minute)."""
        with self._lock:
            now = time.monotonic()
            # Remove timestamps older than 60 seconds
            self._request_timestamps = [
                ts for ts in self._request_timestamps if now - ts < 60.0
            ]
            if len(self._request_timestamps) >= self._max_rpm:
                oldest = self._request_timestamps[0]
                wait = 60.0 - (now - oldest) + 0.1
                if wait > 0:
                    logger.debug("Rate limit reached, sleeping %.1fs", wait)
                    time.sleep(wait)
                # Clean again after sleeping
                now = time.monotonic()
                self._request_timestamps = [
                    ts for ts in self._request_timestamps if now - ts < 60.0
                ]
            self._request_timestamps.append(time.monotonic())

    def _get(self, url: str) -> httpx.Response:
        """GET with rate limiting, retries, and exponential backoff."""
        base_delay = 1.0
        last_exc: Exception | None = None

        for attempt in range(self._max_retries):
            self._rate_limit()
            try:
                response = self._client.get(url)

                if response.status_code == 404:
                    raise httpx.HTTPStatusError(
                        "Not Found",
                        request=response.request,
                        response=response,
                    )

                if response.status_code == 429 or response.status_code >= 500:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        "Retryable status %d for %s, retrying in %.1fs (attempt %d/%d)",
                        response.status_code, url, delay, attempt + 1, self._max_retries,
                    )
                    time.sleep(delay)
                    continue

                response.raise_for_status()
                return response

            except httpx.HTTPStatusError:
                raise
            except httpx.HTTPError as exc:
                last_exc = exc
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "Request error for %s: %s, retrying in %.1fs (attempt %d/%d)",
                    url, exc, delay, attempt + 1, self._max_retries,
                )
                time.sleep(delay)

        raise httpx.ConnectError(
            f"Failed after {self._max_retries} retries: {last_exc}"
        )

    def _soup(self, url: str) -> BeautifulSoup:
        """Fetch a page and return parsed BeautifulSoup."""
        resp = self._get(url)
        return BeautifulSoup(resp.text, "html.parser")

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

            found_any = False
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

                found_any = True

                # Extract prefecture and link
                prefecture = cells[1].get_text(strip=True)
                link_tag = cells[1].find("a") or cells[0].find("a") or row.find("a")

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

        logger.info("Found %d tournaments in date range %s to %s", len(tournaments), start_date, end_date)
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
            url = url[len(self._base_url):]

        soup = self._soup(url)

        # Find standings table
        table = (
            soup.find("table", class_="striped")
            or soup.find("table", class_="standings")
        )

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
                continue

            # Column 0: rank
            rank_text = cells[0].get_text(strip=True)
            try:
                rank = int(rank_text.rstrip("."))
            except (ValueError, AttributeError):
                continue

            # Column 1: player name
            player_name = cells[1].get_text(strip=True) or None

            # Column 2: deck / archetype
            deck_cell = cells[2]
            deck_link = deck_cell.find("a")

            decklist_url: str | None = None
            archetype = ""
            sprite_urls: list[str] = []

            if deck_link:
                href = deck_link.get("href", "")
                if href:
                    decklist_url = urljoin(self._base_url, href)
                archetype, sprite_urls = self._extract_archetype_and_sprites(deck_link)
            else:
                archetype = deck_cell.get_text(strip=True)

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

        logger.info(
            "Parsed %d placements from %s", len(placements), tournament_url
        )
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
            url = url[len(self._base_url):]

        try:
            soup = self._soup(url)
        except httpx.HTTPStatusError:
            logger.warning("Failed to fetch decklist: %s", decklist_url)
            return None

        cards: list[dict[str, Any]] = []

        # Strategy 1: Structured card-link elements
        # Format: <a class="card-link" href="/cards/SET/NUM">
        #           <span class="card-count">4</span>
        #           <span class="card-name">Dragapult ex</span>
        #         </a>
        card_links = soup.find_all("a", class_="card-link")
        if card_links:
            for link in card_links:
                href = link.get("href", "")
                # Remove query params (e.g. ?translate=en)
                href_clean = href.split("?")[0].rstrip("/")
                parts = href_clean.split("/")

                set_code = parts[2] if len(parts) > 2 else ""
                card_number = parts[3] if len(parts) > 3 else ""

                # Extract count and name from spans
                count_el = link.find("span", class_="card-count")
                name_el = link.find("span", class_="card-name")

                count = 1
                if count_el:
                    try:
                        count = int(count_el.get_text(strip=True))
                    except ValueError:
                        pass

                name = name_el.get_text(strip=True) if name_el else link.get_text(strip=True)
                if not name:
                    continue

                cards.append({
                    "count": count,
                    "name": name,
                    "set_code": set_code,
                    "card_number": card_number,
                    "card_id": f"{set_code}-{card_number}" if set_code and card_number else name,
                })

        # Strategy 2: Text format fallback
        if not cards:
            text = soup.get_text("\n")
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue

                match = _DECKLIST_LINE_RE.match(line)
                if match:
                    count = int(match.group(1))
                    name = match.group(2).strip()
                    set_code = match.group(3)
                    card_number = match.group(4)
                    cards.append({
                        "count": count,
                        "name": name,
                        "set_code": set_code,
                        "card_number": card_number,
                        "card_id": f"{set_code}-{card_number}",
                    })
                    continue

                # Handle basic energy lines (no card number)
                energy_match = re.match(
                    r"^(\d+)\s+(Basic\s+\w+\s+Energy)\s*$", line, re.IGNORECASE
                )
                if energy_match:
                    name = energy_match.group(2).strip()
                    cards.append({
                        "count": int(energy_match.group(1)),
                        "name": name,
                        "set_code": "Energy",
                        "card_number": "",
                        "card_id": name,
                    })

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
        """Extract archetype name and sprite URLs from a deck link tag.

        Looks for <img> tags inside the link and extracts Pokemon names from
        the alt attribute or from the filename in the src attribute.

        Args:
            link_tag: A BeautifulSoup Tag (typically an <a> element).

        Returns:
            Tuple of (archetype_string, list_of_sprite_urls).
        """
        sprite_urls: list[str] = []
        names: list[str] = []

        imgs = link_tag.find_all("img") if link_tag else []
        for img in imgs:
            src = img.get("src", "")
            alt = img.get("alt", "")

            if src:
                sprite_urls.append(src)

            # Prefer alt text for the name
            if alt and alt.strip():
                names.append(alt.strip())
            elif src:
                # Extract name from filename
                filename_match = re.search(r"/([a-zA-Z0-9_-]+)\.png", src)
                if filename_match:
                    raw = filename_match.group(1).replace("_", " ").replace("-", " ")
                    names.append(raw.title())

        archetype = " / ".join(names) if names else ""
        return archetype, sprite_urls

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> "LimitlessClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
