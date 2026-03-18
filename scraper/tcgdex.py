"""TCGdex REST API client for fetching Pokemon TCG card data."""

import logging
import sqlite3

import httpx
from rich.progress import Progress

from config import ROTATION_LEGAL_REGULATION_MARKS, ROTATION_LEGAL_SETS, TCGDEX_API_URL

logger = logging.getLogger(__name__)


class TCGdexClient:
    """Client for the TCGdex REST API."""

    def __init__(self) -> None:
        self.client = httpx.Client(base_url=TCGDEX_API_URL, timeout=30.0)

    def fetch_sets(self) -> list[dict]:
        """GET /sets — fetch all available set summaries."""
        response = self.client.get("/sets")
        response.raise_for_status()
        return response.json()

    def fetch_set_cards(self, set_id: str) -> list[dict]:
        """GET /sets/{set_id} — fetch full set info including cards array."""
        response = self.client.get(f"/sets/{set_id}")
        response.raise_for_status()
        data = response.json()
        return data.get("cards", [])

    def fetch_rotation_legal_cards(self) -> list[dict]:
        """Fetch all sets and return only rotation-legal cards with normalized fields."""
        sets = self.fetch_sets()
        legal_cards: list[dict] = []

        with Progress() as progress:
            task = progress.add_task("Fetching sets...", total=len(sets))

            for set_info in sets:
                set_id = set_info.get("id", "")
                set_name = set_info.get("name", "")

                try:
                    cards = self.fetch_set_cards(set_id)
                except Exception:
                    logger.warning("Failed to fetch set '%s' (%s), skipping.", set_id, set_name)
                    progress.advance(task)
                    continue

                for card in cards:
                    regulation_mark = card.get("regulationMark", "")
                    is_legal = (
                        regulation_mark in ROTATION_LEGAL_REGULATION_MARKS
                        or set_id in ROTATION_LEGAL_SETS
                    )

                    if not is_legal:
                        progress.advance(task, 0)
                        continue

                    image = card.get("image", "")
                    image_url = f"{image}/high.png" if image else ""

                    legal_cards.append(
                        {
                            "id": card.get("id", ""),
                            "name_en": card.get("name", ""),
                            "set_code": set_id,
                            "set_name": set_name,
                            "set_number": card.get("localId", ""),
                            "regulation_mark": regulation_mark,
                            "supertype": card.get("category", ""),
                            "rarity": card.get("rarity", ""),
                            "image_url": image_url,
                            "rotation_legal": True,
                        }
                    )

                progress.advance(task)

        logger.info("Found %d rotation-legal cards across %d sets.", len(legal_cards), len(sets))
        return legal_cards

    def populate_cards_table(self, conn: sqlite3.Connection) -> int:
        """Fetch rotation-legal cards and INSERT OR REPLACE into the cards table.

        Returns the count of cards inserted.
        """
        cards = self.fetch_rotation_legal_cards()

        cursor = conn.cursor()
        for card in cards:
            cursor.execute(
                """
                INSERT OR REPLACE INTO cards
                    (id, name_en, name_jp, set_code, set_name, set_number,
                     regulation_mark, supertype, rarity, image_url, rotation_legal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    card["id"],
                    card["name_en"],
                    None,  # name_jp — not available from TCGdex EN endpoint
                    card["set_code"],
                    card["set_name"],
                    card["set_number"],
                    card["regulation_mark"],
                    card["supertype"],
                    card["rarity"],
                    card["image_url"],
                    card["rotation_legal"],
                ),
            )
        conn.commit()

        logger.info("Inserted %d cards into the cards table.", len(cards))
        return len(cards)
