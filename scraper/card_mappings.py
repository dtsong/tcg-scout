"""Fetch JP-to-EN card ID mappings from Limitless TCG and store in SQLite.

Scrapes limitlesstcg.com/cards/jp to build a mapping table from Japanese card
IDs to their English equivalents, using the same sync httpx pattern as
limitless.py.
"""

import logging
import re
import sqlite3
import threading
import time
from typing import Any

import httpx
from bs4 import BeautifulSoup
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn

from config import (
    LIMITLESS_BASE_URL,
    LIMITLESS_MAX_RETRIES,
    LIMITLESS_REQUESTS_PER_MINUTE,
    LIMITLESS_TIMEOUT,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Limitless set code -> TCGdex set ID mapping
# ---------------------------------------------------------------------------

LIMITLESS_TO_TCGDEX = {
    "BLK": "sv10.5b",
    "WHT": "sv10.5w",
    "DRI": "sv10",
    "JTG": "sv09",
    "PRE": "sv08.5",
    "SSP": "sv08",
    "SCR": "sv07",
    "SFA": "sv06.5",
    "TWM": "sv06",
    "TEF": "sv05",
    "PAF": "sv04.5",
    "PAR": "sv04",
    "MEW": "sv03.5",
    "OBF": "sv03",
    "PAL": "sv02",
    "SVI": "sv01",
    "SVE": "sve",
    "SVP": "svp",
    # Mega Evolution
    "ASC": "me02.5",
    "PFL": "me02",
    "MEG": "me01",
    "MEE": "mee",
    "MEP": "mep",
}


def map_set_code(limitless_code: str) -> str:
    """Convert a Limitless EN set code to a TCGdex set ID."""
    return LIMITLESS_TO_TCGDEX.get(limitless_code, limitless_code.lower())


# Reverse mapping: TCGdex set ID -> Limitless EN set code
TCGDEX_TO_LIMITLESS = {v: k for k, v in LIMITLESS_TO_TCGDEX.items()}


def tcgdex_to_limitless(tcgdex_set: str) -> str:
    """Convert a TCGdex set ID to a Limitless EN set code."""
    return TCGDEX_TO_LIMITLESS.get(tcgdex_set, tcgdex_set.upper())


# ---------------------------------------------------------------------------
# HTTP client (mirrors LimitlessClient pattern from limitless.py)
# ---------------------------------------------------------------------------


class _CardMappingClient:
    """Synchronous scraper for Limitless card pages."""

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
                "User-Agent": "TrainerLab-Scout/1.0 (card-mappings)",
            },
        )

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _rate_limit(self) -> None:
        """Block until a request slot is available (max N requests/minute)."""
        with self._lock:
            now = time.monotonic()
            self._request_timestamps = [ts for ts in self._request_timestamps if now - ts < 60.0]
            if len(self._request_timestamps) >= self._max_rpm:
                oldest = self._request_timestamps[0]
                wait = 60.0 - (now - oldest) + 0.1
                if wait > 0:
                    logger.debug("Rate limit reached, sleeping %.1fs", wait)
                    time.sleep(wait)
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
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        "Retryable status %d for %s, retrying in %.1fs (attempt %d/%d)",
                        response.status_code,
                        url,
                        delay,
                        attempt + 1,
                        self._max_retries,
                    )
                    time.sleep(delay)
                    continue

                response.raise_for_status()
                return response

            except httpx.HTTPStatusError:
                raise
            except httpx.HTTPError as exc:
                last_exc = exc
                delay = base_delay * (2**attempt)
                logger.warning(
                    "Request error for %s: %s, retrying in %.1fs (attempt %d/%d)",
                    url,
                    exc,
                    delay,
                    attempt + 1,
                    self._max_retries,
                )
                time.sleep(delay)

        raise httpx.ConnectError(f"Failed after {self._max_retries} retries: {last_exc}")

    def _soup(self, url: str) -> BeautifulSoup:
        """Fetch a page and return parsed BeautifulSoup."""
        resp = self._get(url)
        return BeautifulSoup(resp.text, "html.parser")

    # ------------------------------------------------------------------
    # Scraping methods
    # ------------------------------------------------------------------

    def fetch_jp_sets(self) -> list[str]:
        """Fetch all JP set codes from the Limitless cards/jp index page.

        Returns:
            List of JP set codes (e.g. ["SV7", "SV8a", "M2a"]).
        """
        soup = self._soup("/cards/jp")
        set_codes: list[str] = []

        for link in soup.find_all("a", href=True):
            href = link["href"]
            match = re.match(r"^/cards/jp/([A-Za-z0-9]+)$", href)
            if match:
                code = match.group(1)
                if code not in set_codes:
                    set_codes.append(code)

        logger.info("Found %d JP sets on Limitless", len(set_codes))
        return set_codes

    def fetch_set_cards(self, set_code: str) -> list[str]:
        """Fetch all card IDs for a JP set (translated to EN names).

        Args:
            set_code: JP set code (e.g. "SV7").

        Returns:
            List of JP card IDs (e.g. ["SV7-1", "SV7-2", ...]).
        """
        soup = self._soup(f"/cards/jp/{set_code}?translate=en")
        card_ids: list[str] = []

        pattern = re.compile(rf"^/cards/jp/{re.escape(set_code)}/(\d+)$")

        for link in soup.find_all("a", href=True):
            href = link["href"].split("?")[0]
            match = pattern.match(href)
            if match:
                number = match.group(1)
                card_id = f"{set_code}-{number}"
                if card_id not in card_ids:
                    card_ids.append(card_id)

        logger.info("Found %d cards in JP set %s", len(card_ids), set_code)
        return card_ids

    def fetch_card_equivalent(self, jp_card_id: str, jp_set_id: str) -> dict[str, str | None]:
        """Fetch the EN equivalent for a JP card.

        Args:
            jp_card_id: JP card ID (e.g. "SV7-18").
            jp_set_id: JP set code (e.g. "SV7").

        Returns:
            Dict with keys: en_card_id, card_name_jp, card_name_en, en_set_id.
            Values may be None if not found.
        """
        number = jp_card_id.split("-", 1)[1] if "-" in jp_card_id else jp_card_id

        result: dict[str, str | None] = {
            "en_card_id": None,
            "card_name_jp": None,
            "card_name_en": None,
            "en_set_id": None,
        }

        # Fetch EN-translated page to get the English name
        try:
            soup_en = self._soup(f"/cards/jp/{jp_set_id}/{number}?translate=en")
            result["card_name_en"] = self._extract_card_name(soup_en)
        except httpx.HTTPStatusError:
            logger.debug("Could not fetch EN-translated page for %s", jp_card_id)
            soup_en = None

        # Fetch JP page to get the Japanese name and the Int. Prints table
        try:
            soup_jp = self._soup(f"/cards/jp/{jp_set_id}/{number}")
            result["card_name_jp"] = self._extract_card_name(soup_jp)

            # Parse the "Int. Prints" section
            en_card_id, en_set_id = self._parse_int_prints(soup_jp)
            if en_card_id:
                result["en_card_id"] = en_card_id
                result["en_set_id"] = en_set_id
        except httpx.HTTPStatusError:
            logger.debug("Could not fetch JP page for %s", jp_card_id)

        return result

    @staticmethod
    def _extract_card_name(soup: BeautifulSoup) -> str | None:
        """Extract card name from a Limitless card page.

        Tries multiple strategies: .card-name element, h1 heading, img alt text.
        """
        # Strategy 1: .card-name class
        name_el = soup.find(class_="card-name")
        if name_el:
            text = name_el.get_text(strip=True)
            if text:
                return text

        # Strategy 2: h1 heading
        h1 = soup.find("h1")
        if h1:
            text = h1.get_text(strip=True)
            if text:
                return text

        # Strategy 3: first img alt text that looks like a card name
        for img in soup.find_all("img", alt=True):
            alt = img["alt"].strip()
            # Skip generic images (logos, icons, etc.)
            if alt and len(alt) > 2 and not alt.lower().startswith(("logo", "icon")):
                return alt

        return None

    @staticmethod
    def _parse_int_prints(soup: BeautifulSoup) -> tuple[str | None, str | None]:
        """Parse the 'Int. Prints' table to find EN card ID and set.

        Returns:
            Tuple of (en_card_id, en_set_id) or (None, None).
        """
        # Look for the card-prints-versions table
        table = soup.find("table", class_="card-prints-versions")
        if not table:
            # Fallback: look for any table containing "Int. Prints"
            for t in soup.find_all("table"):
                th = t.find("th", string=re.compile(r"Int\.\s*Prints", re.IGNORECASE))
                if th:
                    table = t
                    break

        if not table:
            return None, None

        # Find the row with the EN card link
        for row in table.find_all("tr"):  # type: ignore[union-attr]
            # Skip header rows
            th = row.find("th")
            if th and "Int" in th.get_text():
                continue

            link = row.find("a", href=True)
            if not link:
                continue

            href = link["href"]
            # Pattern: /cards/en/{SET}/{NUMBER}
            match = re.match(r"^/cards/en/([A-Za-z0-9]+)/(\d+)$", href)
            if match:
                limitless_set = match.group(1)
                en_number = match.group(2)
                tcgdex_set = map_set_code(limitless_set)
                en_card_id = f"{tcgdex_set}-{en_number}"
                return en_card_id, tcgdex_set

        return None, None

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> "_CardMappingClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Database sync
# ---------------------------------------------------------------------------


def sync_card_mappings(
    conn: sqlite3.Connection,
    set_codes: list[str] | None = None,
    force: bool = False,
) -> int:
    """Sync JP-to-EN card mappings from Limitless into the card_mappings table.

    Args:
        conn: SQLite connection (card_mappings table must exist).
        set_codes: Optional list of JP set codes to sync. If None, syncs all.
        force: If True, re-fetch cards that already have a mapping.

    Returns:
        Number of new/updated mappings stored.
    """
    stored = 0

    with _CardMappingClient() as client:
        if set_codes is None:
            set_codes = client.fetch_jp_sets()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
        ) as progress:
            sets_task = progress.add_task("JP sets", total=len(set_codes))

            for set_code in set_codes:
                progress.update(sets_task, description=f"Set {set_code}")

                try:
                    card_ids = client.fetch_set_cards(set_code)
                except httpx.HTTPStatusError as exc:
                    logger.warning("Skipping set %s: %s", set_code, exc)
                    progress.advance(sets_task)
                    continue

                cards_task = progress.add_task(f"  {set_code} cards", total=len(card_ids))

                for jp_card_id in card_ids:
                    # Check if already mapped
                    if not force:
                        row = conn.execute(
                            "SELECT 1 FROM card_mappings WHERE jp_card_id = ?",
                            (jp_card_id,),
                        ).fetchone()
                        if row:
                            progress.advance(cards_task)
                            continue

                    try:
                        info = client.fetch_card_equivalent(jp_card_id, set_code)
                    except httpx.HTTPStatusError as exc:
                        logger.warning("Failed to fetch equivalent for %s: %s", jp_card_id, exc)
                        progress.advance(cards_task)
                        continue

                    if not info["en_card_id"]:
                        logger.debug("No EN equivalent for %s, skipping", jp_card_id)
                        progress.advance(cards_task)
                        continue

                    conn.execute(
                        """INSERT OR REPLACE INTO card_mappings
                           (jp_card_id, en_card_id, card_name_jp, card_name_en,
                            jp_set_id, en_set_id)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            jp_card_id,
                            info["en_card_id"],
                            info["card_name_jp"],
                            info["card_name_en"],
                            set_code,
                            info["en_set_id"],
                        ),
                    )
                    stored += 1
                    progress.advance(cards_task)

                conn.commit()
                progress.remove_task(cards_task)
                progress.advance(sets_task)

    logger.info("Stored %d card mappings", stored)
    return stored


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def get_en_name(
    conn: sqlite3.Connection,
    jp_card_name: str,
    jp_set_code: str,
) -> str | None:
    """Look up an English card name from a JP card name and set code.

    Args:
        conn: SQLite connection.
        jp_card_name: Japanese card name (or partial match).
        jp_set_code: JP set code (e.g. "SV7").

    Returns:
        English card name, or None if not found.
    """
    row = conn.execute(
        """SELECT card_name_en FROM card_mappings
           WHERE jp_set_id = ? AND card_name_jp LIKE ?
           LIMIT 1""",
        (jp_set_code, f"%{jp_card_name}%"),
    ).fetchone()

    if row:
        return row[0] if isinstance(row, tuple) else row["card_name_en"]
    return None


def translate_decklist(
    conn: sqlite3.Connection,
    jp_cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Translate a JP decklist to EN using the card_mappings table.

    Each dict in jp_cards should have keys: name_jp, set_code, count.
    Returns the same list with card_name_en and card_id fields populated.

    Args:
        conn: SQLite connection.
        jp_cards: List of card dicts with name_jp, set_code, count.

    Returns:
        List of card dicts with card_name_en and card_id added.
    """
    result: list[dict[str, Any]] = []

    for card in jp_cards:
        name_jp = card.get("name_jp", "")
        set_code = card.get("set_code", "")

        translated = dict(card)

        # Try exact match on JP card name within the set
        row = conn.execute(
            """SELECT card_name_en, en_card_id FROM card_mappings
               WHERE jp_set_id = ? AND card_name_jp LIKE ?
               LIMIT 1""",
            (set_code, f"%{name_jp}%"),
        ).fetchone()

        if not row:
            # Fallback: search across all sets
            row = conn.execute(
                """SELECT card_name_en, en_card_id FROM card_mappings
                   WHERE card_name_jp LIKE ?
                   LIMIT 1""",
                (f"%{name_jp}%",),
            ).fetchone()

        if row:
            if isinstance(row, tuple):
                translated["card_name_en"] = row[0]
                translated["card_id"] = row[1]
            else:
                translated["card_name_en"] = row["card_name_en"]
                translated["card_id"] = row["en_card_id"]
        else:
            translated["card_name_en"] = None
            translated["card_id"] = None
            logger.debug("No EN mapping found for %s (set %s)", name_jp, set_code)

        result.append(translated)

    return result
