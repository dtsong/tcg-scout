"""Populate cards.supertype from the tcgdex API.

Fetches the card category (Pokemon, Trainer, Energy) for each card
that has a NULL or empty supertype in the cards table.

Usage:
    python scripts/populate_supertypes.py --format nihil-zero
"""

import argparse
import json
import logging
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import FORMATS, TCGDEX_API_URL
from db import get_format_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


def fetch_card_category(card_id: str) -> str | None:
    """Fetch a card's category from tcgdex API.

    Returns 'Pokemon', 'Trainer', or 'Energy', or None on failure.
    """
    url = f"{TCGDEX_API_URL}/cards/{card_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "tcg-scout/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("category")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log.warning("Card not found on tcgdex: %s", card_id)
        else:
            log.warning("HTTP %d fetching card %s: %s", e.code, card_id, e.reason)
        return None
    except Exception as e:
        log.warning("Error fetching card %s: %s", card_id, e)
        return None


def populate_supertypes(conn: sqlite3.Connection, rate_limit: float = 1.0) -> dict:
    """Populate supertype for all cards missing it.

    Returns a summary dict with counts.
    """
    rows = conn.execute(
        "SELECT id, name_en FROM cards WHERE supertype IS NULL OR supertype = ''"
    ).fetchall()

    total = len(rows)
    log.info("Found %d cards with missing supertype", total)

    updated = 0
    not_found = 0
    errors = 0

    for i, row in enumerate(rows, 1):
        card_id = row["id"]
        name = row["name_en"]

        category = fetch_card_category(card_id)

        if category in ("Pokemon", "Trainer", "Energy"):
            conn.execute(
                "UPDATE cards SET supertype = ? WHERE id = ?",
                (category, card_id),
            )
            updated += 1
            log.info("[%d/%d] %s (%s) -> %s", i, total, name, card_id, category)
        elif category is not None:
            # Unexpected category value
            log.warning(
                "[%d/%d] %s (%s) unexpected category: %s", i, total, name, card_id, category
            )
            errors += 1
        else:
            not_found += 1
            log.warning("[%d/%d] %s (%s) not found", i, total, name, card_id)

        # Commit periodically
        if updated % 50 == 0 and updated > 0:
            conn.commit()

        # Rate limit (skip on last item)
        if i < total:
            time.sleep(rate_limit)

    conn.commit()

    summary = {
        "total": total,
        "updated": updated,
        "not_found": not_found,
        "errors": errors,
    }
    log.info("Done: %s", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Populate card supertypes from tcgdex API")
    parser.add_argument(
        "--format",
        required=True,
        choices=list(FORMATS.keys()),
        help="Format slug (e.g., nihil-zero)",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=1.0,
        help="Seconds between API requests (default: 1.0)",
    )
    args = parser.parse_args()

    conn = get_format_connection(args.format)
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        populate_supertypes(conn, rate_limit=args.rate_limit)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
