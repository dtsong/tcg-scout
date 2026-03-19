"""Tests for scripts/populate_supertypes.py."""

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.populate_supertypes import fetch_card_category, populate_supertypes


@pytest.fixture()
def cards_db():
    """In-memory DB with a minimal cards table."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE cards (id TEXT PRIMARY KEY, name_en TEXT, supertype TEXT)")
    conn.executemany(
        "INSERT INTO cards (id, name_en, supertype) VALUES (?, ?, ?)",
        [
            ("card-001", "Charizard ex", None),
            ("card-002", "Nest Ball", None),
            ("card-003", "Basic Fire Energy", None),
            ("card-004", "Pidgeot ex", "Pokemon"),  # already has supertype
        ],
    )
    conn.commit()
    return conn


class TestPopulateSupertypes:
    def test_updates_cards_with_valid_categories(self, cards_db):
        categories = {
            "card-001": "Pokemon",
            "card-002": "Trainer",
            "card-003": "Energy",
        }
        with patch(
            "scripts.populate_supertypes.fetch_card_category",
            side_effect=lambda cid: categories.get(cid),
        ):
            summary = populate_supertypes(cards_db, rate_limit=0)

        assert summary["updated"] == 3
        assert summary["not_found"] == 0
        assert summary["errors"] == 0

        rows = {
            r["id"]: r["supertype"]
            for r in cards_db.execute("SELECT id, supertype FROM cards").fetchall()
        }
        assert rows["card-001"] == "Pokemon"
        assert rows["card-002"] == "Trainer"
        assert rows["card-003"] == "Energy"
        assert rows["card-004"] == "Pokemon"  # unchanged

    def test_handles_not_found(self, cards_db):
        with patch(
            "scripts.populate_supertypes.fetch_card_category",
            return_value=None,
        ):
            summary = populate_supertypes(cards_db, rate_limit=0)

        assert summary["updated"] == 0
        assert summary["not_found"] == 3  # 3 cards with NULL supertype

    def test_handles_unexpected_category(self, cards_db):
        with patch(
            "scripts.populate_supertypes.fetch_card_category",
            return_value="SpecialType",
        ):
            summary = populate_supertypes(cards_db, rate_limit=0)

        assert summary["errors"] == 3
        assert summary["updated"] == 0

    def test_aborts_after_consecutive_failures(self, cards_db):
        # Add enough cards to trigger the 10-consecutive-failure abort
        for i in range(15):
            cards_db.execute(
                "INSERT INTO cards (id, name_en, supertype) VALUES (?, ?, NULL)",
                (f"fail-{i:03d}", f"Card {i}"),
            )
        cards_db.commit()

        with patch(
            "scripts.populate_supertypes.fetch_card_category",
            return_value=None,
        ):
            summary = populate_supertypes(cards_db, rate_limit=0)

        # Should abort after 10 consecutive failures, not process all 18
        assert summary["not_found"] == 10


class TestFetchCardCategory:
    def test_returns_none_on_404(self):
        import urllib.error

        with patch(
            "scripts.populate_supertypes.urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                url="", code=404, msg="Not Found", hdrs=None, fp=None
            ),
        ):
            result = fetch_card_category("nonexistent-card")
        assert result is None

    def test_returns_none_on_network_error(self):
        import urllib.error

        with patch(
            "scripts.populate_supertypes.urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            result = fetch_card_category("card-001")
        assert result is None
