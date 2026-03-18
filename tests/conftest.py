"""Shared pytest fixtures — in-memory SQLite database with test data."""

import sqlite3

import pytest

# Import schema from the project
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import SCHEMA


@pytest.fixture()
def db() -> sqlite3.Connection:
    """Create an in-memory SQLite database with schema and seed data.

    Seed data layout:
    - 3 tournaments (2 early = before 2026-02-15, 1 late = on or after)
    - 6 placements across 3 archetypes:
        Charizard ex  — 3 placements (1st, 4th, 9th)
        Dragapult ex  — 2 placements (2nd, 8th)
        Raging Bolt ex — 1 placement (16th)
    - Decklist cards for every placement
    - 3 cards in the cards table (for JP→EN translation)
    - 1 CL event (masters) with 2 placements and JP card names
    - 1 meta snapshot + archetype stats (pre-computed)
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)

    # --- Tournaments ---
    conn.executemany(
        "INSERT INTO tournaments (id, name, date, player_count) VALUES (?, ?, ?, ?)",
        [
            ("t1", "Osaka CL Jan", "2026-01-25", 64),
            ("t2", "Tokyo CL Feb Early", "2026-02-10", 64),
            ("t3", "Nagoya CL Mar", "2026-03-01", 64),
        ],
    )

    # --- Placements ---
    conn.executemany(
        "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (1, "t1", 1, "Alice", "Charizard ex"),
            (2, "t1", 2, "Bob", "Dragapult ex"),
            (3, "t2", 4, "Charlie", "Charizard ex"),
            (4, "t2", 8, "Diana", "Dragapult ex"),
            (5, "t3", 9, "Eve", "Charizard ex"),
            (6, "t3", 16, "Frank", "Raging Bolt ex"),
        ],
    )

    # --- Decklist cards ---
    # Each placement gets a couple of cards so queries work.
    decklist_rows = []
    for pid in range(1, 7):
        decklist_rows.append((pid, "card-nest", "Nest Ball", 4))
        decklist_rows.append((pid, "card-ultra", "Ultra Ball", 4))
    # Give some placements unique cards for flex/trend tests
    decklist_rows.append((1, "card-boss", "Boss's Orders", 2))
    decklist_rows.append((2, "card-boss", "Boss's Orders", 2))
    decklist_rows.append((3, "card-boss", "Boss's Orders", 2))
    decklist_rows.append((4, "card-boss", "Boss's Orders", 2))
    decklist_rows.append((5, "card-boss", "Boss's Orders", 2))
    decklist_rows.append((6, "card-boss", "Boss's Orders", 2))
    # A card only in late tournament for trend testing
    decklist_rows.append((5, "card-iono", "Iono", 3))
    decklist_rows.append((6, "card-iono", "Iono", 3))

    conn.executemany(
        "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) "
        "VALUES (?, ?, ?, ?)",
        decklist_rows,
    )

    # --- Cards table (for JP→EN translation) ---
    conn.executemany(
        "INSERT INTO cards (id, name_en, name_jp, set_code) VALUES (?, ?, ?, ?)",
        [
            ("sv5-001", "Charizard ex", "リザードンex", "sv5"),
            ("sv5-002", "Dragapult ex", "ドラパルトex", "sv5"),
            ("sv5-003", "Rare Candy", "ふしぎなアメ", "sv5"),
        ],
    )

    # --- CL events ---
    conn.execute(
        "INSERT INTO cl_events (id, name, division, date, player_count) "
        "VALUES (?, ?, ?, ?, ?)",
        (900001, "Champions League Tokyo", "masters", "2026-02-20", 7000),
    )

    # CL placements
    conn.executemany(
        "INSERT INTO cl_placements (id, event_id, standing, player_name, region, deck_code) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (101, 900001, 1, "Taro", "Tokyo", "deck-abc"),
            (102, 900001, 2, "Hanako", "Osaka", "deck-xyz"),
        ],
    )

    # CL decklist cards (JP names — some translatable, some not)
    conn.executemany(
        "INSERT INTO cl_decklist_cards (placement_id, card_name_jp, card_name_en, count, category) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (101, "リザードンex", None, 2, "Pokemon"),
            (101, "ネストボール", None, 4, "Trainer"),
            (102, "ドラパルトex", None, 2, "Pokemon"),
            (102, "謎のカード", None, 1, "Trainer"),  # untranslatable
        ],
    )

    # --- Meta snapshot (pre-computed) ---
    conn.execute(
        "INSERT INTO meta_snapshots (id, generated_at, tournament_count, deck_count) "
        "VALUES (?, ?, ?, ?)",
        (1, "2026-03-10T00:00:00", 3, 6),
    )
    conn.executemany(
        "INSERT INTO archetype_stats (snapshot_id, archetype, meta_share, deck_count, best_placement, tier) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "Charizard ex", 50.0, 3, 1, "S"),
            (1, "Dragapult ex", 33.33, 2, 2, "S"),
            (1, "Raging Bolt ex", 16.67, 1, 16, "S"),
        ],
    )

    conn.commit()
    yield conn
    conn.close()
