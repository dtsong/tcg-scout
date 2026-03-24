"""Labs Limitless scraper for international tournament data.

Scrapes tournament standings, player records, archetype classifications,
and decklists from Labs Limitless (labs.limitlesstcg.com) and the main
Limitless site (limitlesstcg.com).

Labs standings pages are server-rendered HTML — no browser rendering needed.
"""

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import Tag

from analysis.archetype import normalize_archetype
from config import (
    LABS_BASE_URL,
    LABS_MAX_RETRIES,
    LABS_REQUESTS_PER_MINUTE,
    LABS_TIMEOUT,
)
from scraper.http_client import RateLimitedHTTPClient

logger = logging.getLogger(__name__)

LABS_STANDINGS_URL = "https://labs.limitlesstcg.com"

_LABS_DECKLIST_LINE_RE = re.compile(
    r"^(\d+)\s+(.+?)\s+([A-Z0-9]{2,5}[A-Z]?|Energy)\s+(\d+|[A-Z]+\d*)$"
)

_MONTH_TO_NUM = {
    "Jan": "01",
    "Feb": "02",
    "Mar": "03",
    "Apr": "04",
    "May": "05",
    "Jun": "06",
    "Jul": "07",
    "Aug": "08",
    "Sep": "09",
    "Oct": "10",
    "Nov": "11",
    "Dec": "12",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class LabsPlayer:
    player_id: str
    name: str
    country: str = ""

    def __post_init__(self) -> None:
        if not self.player_id.strip():
            raise ValueError("player_id must be non-empty")


@dataclass
class LabsPlacement:
    standing: int
    player: LabsPlayer
    archetype: str
    record_w: int = 0
    record_l: int = 0
    record_t: int = 0
    decklist_url: str | None = None
    sprite_urls: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.standing < 1:
            raise ValueError(f"standing must be >= 1, got {self.standing}")
        if self.record_w < 0 or self.record_l < 0 or self.record_t < 0:
            raise ValueError("W/L/T records must be non-negative")


@dataclass
class LabsTournament:
    tournament_id: str
    name: str
    date: str
    player_count: int = 0
    country: str = ""
    region: str = ""
    format: str = ""
    placements: list[LabsPlacement] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.tournament_id.strip():
            raise ValueError("tournament_id must be non-empty")
        if not self.name.strip():
            raise ValueError("name must be non-empty")


@dataclass
class LabsDecklist:
    cards: list[dict[str, Any]]
    source_url: str | None = None


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class LabsLimitlessClient(RateLimitedHTTPClient):
    """Scraper for Labs Limitless international tournament data."""

    def __init__(self) -> None:
        super().__init__(
            base_url=LABS_BASE_URL,
            max_rpm=LABS_REQUESTS_PER_MINUTE,
            timeout=LABS_TIMEOUT,
            max_retries=LABS_MAX_RETRIES,
            user_agent="TrainerLab-Scout/1.0 (labs-analysis)",
        )
        self._labs_url = LABS_STANDINGS_URL

    # ------------------------------------------------------------------
    # Tournament metadata from main Limitless site
    # ------------------------------------------------------------------

    def fetch_tournament_metadata(self, tournament_id: str) -> LabsTournament:
        """Fetch tournament metadata from the main Limitless site.

        Args:
            tournament_id: Numeric tournament ID (e.g. "551").

        Returns:
            LabsTournament with metadata populated (no placements).
        """
        url = f"{self._base_url}/tournaments/{tournament_id}"
        soup = self._soup(url)

        name = ""
        date = ""
        player_count = 0
        country = ""

        # Tournament name from page title or header
        title_el = soup.find("h1") or soup.find("title")
        if title_el:
            name = title_el.get_text(strip=True)
            # Remove "| Pair" suffix or similar
            name = name.split("|")[0].strip()

        # Try to extract date and player count from info section
        for el in soup.find_all(["span", "div", "p"]):
            text = el.get_text(strip=True)
            # Look for date patterns like "21 Mar 26" or "March 21, 2026"
            date_match = re.search(
                r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{2,4})",
                text,
            )
            if date_match and not date:
                day, month, year = date_match.groups()
                if len(year) == 2:
                    year = f"20{year}"
                date = f"{year}-{_MONTH_TO_NUM[month]}-{int(day):02d}"

            # Look for player count
            players_match = re.search(r"(\d[\d,]+)\s*[Pp]layers?", text)
            if players_match and not player_count:
                player_count = int(players_match.group(1).replace(",", ""))

        # Extract country from flag image
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if "flags" in src or "flag" in src:
                alt = img.get("alt", "")
                if alt and len(alt) <= 3:
                    country = alt.upper()
                    break

        if not player_count:
            logger.warning("Could not parse player count from %s", url)
        if not name or not date:
            raise ValueError(
                f"Could not parse required metadata (name={name!r}, date={date!r}) from {url}"
            )

        return LabsTournament(
            tournament_id=tournament_id,
            name=name,
            date=date,
            player_count=player_count,
            country=country,
        )

    # ------------------------------------------------------------------
    # Standings from Labs Limitless
    # ------------------------------------------------------------------

    def fetch_standings(self, labs_tournament_id: str) -> list[LabsPlacement]:
        """Scrape standings from Labs Limitless.

        Labs standings pages are server-rendered HTML with player records,
        archetypes, and decklist links.

        Args:
            labs_tournament_id: Labs tournament ID (e.g. "0058").

        Returns:
            List of LabsPlacement objects.
        """
        url = f"{self._labs_url}/{labs_tournament_id}/standings"
        logger.info("Fetching Labs standings from %s", url)
        soup = self._soup(url)

        placements: list[LabsPlacement] = []

        # Find the standings table
        table = soup.find("table")
        if table is None:
            raise ValueError(
                f"No standings table found at {url}. "
                "The page structure may have changed or the tournament ID may be incorrect."
            )

        rows = table.find_all("tr")
        skipped_short = 0
        for row in rows[1:]:  # Skip header
            cells = row.find_all("td")
            if len(cells) < 5:
                skipped_short += 1
                logger.warning(
                    "Skipping standings row with %d cells (expected >=5) in tournament %s",
                    len(cells),
                    labs_tournament_id,
                )
                continue

            placement = self._parse_standings_row(cells)
            if placement:
                placements.append(placement)

        expected = len(rows) - 1 - skipped_short  # exclude header and short rows
        if placements and len(placements) < expected:
            logger.warning(
                "%d of %d standings rows failed to parse for tournament %s",
                expected - len(placements),
                expected,
                labs_tournament_id,
            )
        if placements:
            unknown_count = sum(1 for p in placements if p.archetype == "Unknown")
            if unknown_count > len(placements) * 0.5:
                logger.warning(
                    "%d of %d placements have Unknown archetype for tournament %s"
                    " -- sprite parsing may be broken",
                    unknown_count,
                    len(placements),
                    labs_tournament_id,
                )

        logger.info(
            "Parsed %d standings from Labs tournament %s", len(placements), labs_tournament_id
        )
        return placements

    def _parse_standings_row(self, cells: list[Tag]) -> LabsPlacement | None:
        """Parse a single standings table row."""
        # Parse rank from first cell
        try:
            rank_text = cells[0].get_text(strip=True)
            standing = int(rank_text.rstrip("."))
        except (ValueError, IndexError) as exc:
            logger.warning("Failed to parse rank from standings row: %s", exc)
            return None

        # Column 1: Player name (with link to player profile)
        player_link = cells[1].find("a")
        player_name = cells[1].get_text(strip=True)
        player_id = ""
        if player_link:
            href = player_link.get("href", "")
            player_name = player_link.get_text(strip=True)
            # Extract player ID from href like /players/1790
            id_match = re.search(r"/players?/(\d+)", href)
            if id_match:
                player_id = id_match.group(1)

        if not player_id:
            player_id = f"unknown-{player_name}"
            logger.warning(
                "No player ID found for %r (standing %d), using synthetic ID %r",
                player_name,
                standing,
                player_id,
            )

        # Column 2: Country flag
        country = ""
        flag_img = cells[2].find("img") if len(cells) > 2 else None
        if flag_img:
            country = flag_img.get("alt", "").upper()

        # Find record column (W-L-T format like "15 - 1 - 2")
        record_w, record_l, record_t = 0, 0, 0
        record_found = False
        for cell in cells:
            text = cell.get_text(strip=True)
            record_match = re.match(r"^(\d+)\s*-\s*(\d+)\s*-\s*(\d+)$", text)
            if record_match:
                record_w = int(record_match.group(1))
                record_l = int(record_match.group(2))
                record_t = int(record_match.group(3))
                record_found = True
                break
        if not record_found:
            logger.warning(
                "No W-L-T record parsed for player %s (standing %d)",
                player_name,
                standing,
            )

        # Find deck/archetype cell (contains sprite images)
        archetype = ""
        sprite_urls: list[str] = []
        decklist_url: str | None = None

        for cell in cells:
            imgs = cell.find_all("img")
            has_pokemon_sprites = any("pokemon" in (img.get("src", "") or "") for img in imgs)
            if has_pokemon_sprites:
                archetype, sprite_urls = self._extract_archetype(cell)
                # Check for decklist link
                link = cell.find("a")
                if link:
                    href = link.get("href", "")
                    if "/decks/" in href:
                        decklist_url = urljoin(self._base_url, href)
                break

        # Also check for separate decklist column
        if not decklist_url:
            for cell in cells:
                link = cell.find("a")
                if link:
                    href = link.get("href", "")
                    if "/decks/list/" in href:
                        decklist_url = urljoin(self._base_url, href)
                        break

        # Fallback archetype from text if no sprites found
        if not archetype:
            logger.debug(
                "No sprite-based archetype for player %s (standing %d), trying text fallback",
                player_name,
                standing,
            )
            for cell in cells:
                text = cell.get_text(strip=True)
                # Skip numeric cells, record cells (W-L-T pattern), country codes
                if text and not re.match(r"^[\d.\-%]+$", text):
                    if re.match(r"^\d+\s*-\s*\d+\s*-\s*\d+$", text):
                        continue
                    if len(text) > 3 and text != player_name:
                        archetype = text
                        break

        # Normalize archetype using sprite URLs (consistent with JP scraper)
        archetype = normalize_archetype(sprite_urls, html_archetype=archetype)

        player = LabsPlayer(
            player_id=player_id,
            name=player_name,
            country=country,
        )

        return LabsPlacement(
            standing=standing,
            player=player,
            archetype=archetype,
            record_w=record_w,
            record_l=record_l,
            record_t=record_t,
            decklist_url=decklist_url,
            sprite_urls=sprite_urls,
        )

    @staticmethod
    def _extract_archetype(cell: Tag) -> tuple[str, list[str]]:
        """Extract archetype name and sprite URLs from a cell."""
        sprite_urls: list[str] = []
        names: list[str] = []

        for img in cell.find_all("img"):
            src = img.get("src", "")
            alt = img.get("alt", "")
            if src and "pokemon" in src:
                sprite_urls.append(src)
            if alt and alt.strip():
                names.append(alt.strip())
            elif src:
                filename_match = re.search(r"/([a-zA-Z0-9_-]+)\.png", src)
                if filename_match:
                    raw = filename_match.group(1).replace("_", " ").replace("-", " ")
                    names.append(raw.title())

        # Also check link text
        link = cell.find("a")
        if link and not names:
            text = link.get_text(strip=True)
            if text:
                names.append(text)

        archetype = " ".join(names) if names else ""
        return archetype, sprite_urls

    # ------------------------------------------------------------------
    # Decklists (delegates to main Limitless site patterns)
    # ------------------------------------------------------------------

    def fetch_decklist(self, decklist_url: str) -> LabsDecklist | None:
        """Fetch and parse a decklist from the main Limitless site.

        Tries structured card-link elements (class="card-link") first.
        Falls back to text-line regex parsing if no card links are found.
        Does not handle bare basic energy lines (e.g., "2 Basic Fire Energy"
        without a set code).

        Args:
            decklist_url: Full URL to the decklist page.

        Returns:
            Parsed LabsDecklist, or None if parsing fails.
        """
        try:
            soup = self._soup(decklist_url)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in (401, 403):
                logger.error(
                    "HTTP %d fetching decklist %s — scraper may be blocked",
                    status,
                    decklist_url,
                )
            else:
                logger.warning("HTTP %d fetching decklist %s", status, decklist_url)
            return None
        except httpx.HTTPError as exc:
            logger.warning("Network error fetching decklist %s: %s", decklist_url, exc)
            return None

        cards: list[dict[str, Any]] = []

        # Strategy 1: Structured card-link elements
        card_links = soup.find_all("a", class_="card-link")
        if card_links:
            for link in card_links:
                href = link.get("href", "").split("?")[0].rstrip("/")
                parts = href.split("/")

                set_code = parts[2] if len(parts) > 2 else ""
                card_number = parts[3] if len(parts) > 3 else ""

                count_el = link.find("span", class_="card-count")
                name_el = link.find("span", class_="card-name")

                count = 1
                if count_el:
                    try:
                        count = int(count_el.get_text(strip=True))
                    except ValueError:
                        logger.warning(
                            "Could not parse card count %r in decklist %s, defaulting to 1",
                            count_el.get_text(strip=True),
                            decklist_url,
                        )

                name = name_el.get_text(strip=True) if name_el else link.get_text(strip=True)
                if not name:
                    continue

                cards.append(
                    {
                        "count": count,
                        "name": name,
                        "set_code": set_code,
                        "card_number": card_number,
                        "card_id": f"{set_code}-{card_number}"
                        if set_code and card_number
                        else name,
                    }
                )

        # Strategy 2: Text format fallback
        if not cards:
            logger.info(
                "No card-link elements found in %s, falling back to text parsing", decklist_url
            )
            decklist_re = _LABS_DECKLIST_LINE_RE
            text = soup.get_text("\n")
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                match = decklist_re.match(line)
                if match:
                    cards.append(
                        {
                            "count": int(match.group(1)),
                            "name": match.group(2).strip(),
                            "set_code": match.group(3),
                            "card_number": match.group(4),
                            "card_id": f"{match.group(3)}-{match.group(4)}",
                        }
                    )

        if not cards:
            logger.warning("No cards parsed from decklist: %s", decklist_url)
            return None

        return LabsDecklist(cards=cards, source_url=decklist_url)

    # ------------------------------------------------------------------
    # Ingestion — store scraped data into labs.db
    # ------------------------------------------------------------------

    def ingest_tournament(
        self,
        conn: sqlite3.Connection,
        tournament_id: str,
        labs_tournament_id: str,
        fetch_decklists: bool = True,
        max_placements: int | None = None,
    ) -> dict[str, int]:
        """Scrape and store a full tournament into labs.db.

        Args:
            conn: SQLite connection to labs.db.
            tournament_id: Main Limitless tournament ID (e.g. "551").
            labs_tournament_id: Labs tournament ID (e.g. "0058").
            fetch_decklists: Whether to fetch individual decklists.
            max_placements: Limit standings to top N (None = all).

        Returns:
            Dict with counts: players, placements, decklists, decklist_failures.
        """
        # Phase 1: Fetch all data over HTTP (no DB writes)
        tournament = self.fetch_tournament_metadata(tournament_id)

        standings = self.fetch_standings(labs_tournament_id)
        if not standings:
            raise ValueError(
                f"No standings found for Labs tournament {labs_tournament_id}. "
                "The page structure may have changed."
            )
        if max_placements:
            standings = standings[:max_placements]

        # Fetch decklists for all placements that have URLs
        fetched_decklists: dict[str, LabsDecklist] = {}
        decklist_failures = 0
        consecutive_fetch_failures = 0
        max_consecutive_fetch_failures = 3
        if fetch_decklists:
            placements_with_decklists = [p for p in standings if p.decklist_url]
            for placement in placements_with_decklists:
                decklist = self.fetch_decklist(placement.decklist_url)
                if decklist and decklist.cards:
                    fetched_decklists[placement.player.player_id] = decklist
                    consecutive_fetch_failures = 0
                else:
                    decklist_failures += 1
                    if decklist is None:
                        consecutive_fetch_failures += 1
                    if consecutive_fetch_failures >= max_consecutive_fetch_failures:
                        logger.error(
                            "Aborting decklist fetches after %d consecutive failures "
                            "for tournament %s — site may be down or scraper may be blocked",
                            consecutive_fetch_failures,
                            tournament_id,
                        )
                        break
            if placements_with_decklists and decklist_failures == len(placements_with_decklists):
                logger.error(
                    "ALL %d decklist fetches failed for tournament %s — site structure may have changed",
                    decklist_failures,
                    tournament_id,
                )
            elif decklist_failures > 0:
                logger.warning(
                    "Failed to fetch %d of %d decklists for tournament %s",
                    decklist_failures,
                    len(placements_with_decklists),
                    tournament_id,
                )

        # Phase 2: Write everything in a single fast transaction
        players_stored = 0
        placements_stored = 0
        decklists_stored = 0

        try:
            conn.execute(
                """INSERT INTO tournaments
                (id, name, date, player_count, country, region, format, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name, date=excluded.date,
                    player_count=excluded.player_count, country=excluded.country,
                    region=excluded.region, format=excluded.format""",
                (
                    tournament_id,
                    tournament.name,
                    tournament.date,
                    tournament.player_count,
                    tournament.country,
                    tournament.region,
                    tournament.format,
                    "limitless-labs",
                ),
            )

            for placement in standings:
                player = placement.player

                conn.execute(
                    """INSERT INTO players (id, name, country) VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name, country=excluded.country""",
                    (player.player_id, player.name, player.country),
                )
                players_stored += 1

                conn.execute(
                    """INSERT INTO placements
                    (tournament_id, player_id, standing, archetype, record_w, record_l, record_t)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(tournament_id, player_id) DO UPDATE SET
                        standing=excluded.standing, archetype=excluded.archetype,
                        record_w=excluded.record_w, record_l=excluded.record_l,
                        record_t=excluded.record_t""",
                    (
                        tournament_id,
                        player.player_id,
                        placement.standing,
                        placement.archetype,
                        placement.record_w,
                        placement.record_l,
                        placement.record_t,
                    ),
                )
                placements_stored += 1

                # Store decklist if fetched
                decklist = fetched_decklists.get(player.player_id)
                if decklist:
                    # Get the stable placement_id (preserved by upsert)
                    row = conn.execute(
                        "SELECT id FROM placements WHERE tournament_id=? AND player_id=?",
                        (tournament_id, player.player_id),
                    ).fetchone()
                    if row is None:
                        raise RuntimeError(
                            f"placement row missing after upsert for player {player.player_id!r} "
                            f"in tournament {tournament_id!r}"
                        )
                    placement_id = row[0]

                    conn.execute(
                        """INSERT INTO decklists
                        (placement_id, player_id, tournament_id) VALUES (?, ?, ?)
                        ON CONFLICT(tournament_id, player_id) DO UPDATE SET
                            placement_id=excluded.placement_id""",
                        (placement_id, player.player_id, tournament_id),
                    )
                    row = conn.execute(
                        "SELECT id FROM decklists WHERE tournament_id=? AND player_id=?",
                        (tournament_id, player.player_id),
                    ).fetchone()
                    if row is None:
                        raise RuntimeError(
                            f"decklist row missing after upsert for player {player.player_id!r} "
                            f"in tournament {tournament_id!r}"
                        )
                    decklist_id = row[0]

                    # Clear old cards and re-insert
                    conn.execute("DELETE FROM decklist_cards WHERE decklist_id=?", (decklist_id,))
                    for card in decklist.cards:
                        conn.execute(
                            """INSERT INTO decklist_cards
                            (decklist_id, card_name, card_id, count, category)
                            VALUES (?, ?, ?, ?, ?)""",
                            (
                                decklist_id,
                                card.get("name"),
                                card.get("card_id"),
                                card.get("count", 1),
                                None,
                            ),
                        )
                    decklists_stored += 1

            conn.commit()
        except Exception:
            logger.exception("Failed to ingest tournament %s, rolling back", tournament_id)
            conn.rollback()
            raise

        return {
            "players": players_stored,
            "placements": placements_stored,
            "decklists": decklists_stored,
            "decklist_failures": decklist_failures,
        }

    def __enter__(self) -> "LabsLimitlessClient":
        return self
