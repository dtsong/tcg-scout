"""Shared pytest fixtures — in-memory SQLite database with test data."""

import sqlite3

# Import schema from the project
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import SCHEMA


@pytest.fixture()
def db() -> sqlite3.Connection:
    """Create an in-memory SQLite database with schema and seed data.

    Seed data layout:
    - 4 tournaments (2 early = before 2026-02-15, 1 late = on or after, 1 senior division)
    - 7 placements across 3 archetypes:
        Charizard ex  — 3 open + 1 senior placements (1st, 4th, 9th, 1st-senior)
        Dragapult ex  — 2 placements (2nd, 8th)
        Raging Bolt ex — 1 placement (16th)
    - Decklist cards for every placement
    - 3 cards in the cards table (for JP→EN translation)
    - 1 CL event (masters) with 2 placements and JP card names
    - 1 meta snapshot + archetype stats (pre-computed, open division only)
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)

    # --- Tournaments ---
    conn.executemany(
        "INSERT INTO tournaments (id, name, date, player_count, division) VALUES (?, ?, ?, ?, ?)",
        [
            ("t1", "Osaka CL Jan", "2026-01-25", 64, "open"),
            ("t2", "Tokyo CL Feb Early", "2026-02-10", 64, "open"),
            ("t3", "Nagoya CL Mar", "2026-03-01", 64, "open"),
            ("t4", "Osaka Junior Cup", "2026-02-20", 32, "senior"),
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
            (7, "t4", 1, "Greta", "Charizard ex"),
        ],
    )

    # --- Decklist cards ---
    # Each placement gets a couple of cards so queries work.
    decklist_rows = []
    for pid in range(1, 8):
        decklist_rows.append((pid, "card-nest", "Nest Ball", 4))
        decklist_rows.append((pid, "card-ultra", "Ultra Ball", 4))
    # Give some placements unique cards for flex/trend tests
    decklist_rows.append((1, "card-boss", "Boss's Orders", 2))
    decklist_rows.append((2, "card-boss", "Boss's Orders", 2))
    decklist_rows.append((3, "card-boss", "Boss's Orders", 2))
    decklist_rows.append((4, "card-boss", "Boss's Orders", 2))
    decklist_rows.append((5, "card-boss", "Boss's Orders", 2))
    decklist_rows.append((6, "card-boss", "Boss's Orders", 2))
    decklist_rows.append((7, "card-boss", "Boss's Orders", 2))
    # A card only in late tournament for trend testing
    decklist_rows.append((5, "card-iono", "Iono", 3))
    decklist_rows.append((6, "card-iono", "Iono", 3))
    # A card only in top-4 Charizard placements (1st, 4th) but not 9th
    decklist_rows.append((1, "card-arven", "Arven", 2))
    decklist_rows.append((3, "card-arven", "Arven", 2))

    conn.executemany(
        "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
        decklist_rows,
    )

    # --- Cards table (for JP→EN translation + image URLs) ---
    conn.executemany(
        "INSERT INTO cards (id, name_en, name_jp, set_code, image_url, supertype, rotation_legal) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "sv5-001",
                "Charizard ex",
                "リザードンex",
                "sv5",
                "https://images.pokemontcg.io/sv5/001.png",
                "Pokemon",
                1,
            ),
            (
                "sv5-002",
                "Dragapult ex",
                "ドラパルトex",
                "sv5",
                "https://images.pokemontcg.io/sv5/002.png",
                "Pokemon",
                1,
            ),
            (
                "sv5-003",
                "Rare Candy",
                "ふしぎなアメ",
                "sv5",
                "https://images.pokemontcg.io/sv5/003.png",
                "Trainer",
                1,
            ),
            (
                "sv5-rotated",
                "Rotated Card",
                "ローテカード",
                "sv1",
                "https://images.pokemontcg.io/sv1/001.png",
                "Trainer",
                0,
            ),
        ],
    )

    # --- CL events ---
    conn.execute(
        "INSERT INTO cl_events (id, name, division, date, player_count) VALUES (?, ?, ?, ?, ?)",
        (900001, "Champions League Tokyo", "masters", "2026-02-20", 7000),
    )

    # CL placements
    conn.executemany(
        "INSERT INTO cl_placements (id, event_id, standing, player_name, region, deck_code) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (101, 900001, 1, "Taro", "Tokyo", "deck-abc"),
            (102, 900001, 2, "Hanako", "Osaka", "deck-xyz"),
            (103, 900001, 3, "Jiro", "Nagoya", "deck-unk"),
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
            (103, "謎のカードA", None, 2, "Trainer"),  # unclassifiable placement
            (103, "謎のカードB", None, 1, "Trainer"),
        ],
    )

    # --- Meta snapshot (pre-computed) ---
    conn.execute(
        "INSERT INTO meta_snapshots (id, generated_at, tournament_count, deck_count) "
        "VALUES (?, ?, ?, ?)",
        (1, "2026-03-10T00:00:00", 3, 6),
    )
    conn.executemany(
        "INSERT INTO archetype_stats (snapshot_id, archetype, meta_share, deck_count, best_placement, tier, weighted_share) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "Charizard ex", 50.0, 3, 1, "S", 54.39),
            (1, "Dragapult ex", 33.33, 2, 2, "S", 35.09),
            (1, "Raging Bolt ex", 16.67, 1, 16, "S", 10.53),
        ],
    )

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture()
def db_integration() -> sqlite3.Connection:
    """Richer in-memory SQLite database for integration tests.

    Extends the unit fixture with more data to exercise edge cases:
    - 6 tournaments (4 open spanning 4 weeks, 1 senior, 1 junior)
    - 12 placements across 5 archetypes with varied standings (1st-32nd)
    - Tier distribution: S (Charizard ex), A (Dragapult ex), B (Raging Bolt ex),
      Rogue (Gardevoir ex, Gholdengo ex)
    - card_mappings rows for JP→EN translation path
    - Enough weekly spread for trend/evolution analysis
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)

    # --- Tournaments (4 open across 4 weeks, 1 senior, 1 junior) ---
    conn.executemany(
        "INSERT INTO tournaments (id, name, date, player_count, division) VALUES (?, ?, ?, ?, ?)",
        [
            ("t1", "Osaka CL Week1", "2026-01-25", 64, "open"),
            ("t2", "Tokyo CL Week2", "2026-02-01", 64, "open"),
            ("t3", "Nagoya CL Week3", "2026-02-15", 64, "open"),
            ("t4", "Fukuoka CL Week4", "2026-02-22", 64, "open"),
            ("t5", "Osaka Senior Cup", "2026-02-10", 32, "senior"),
            ("t6", "Osaka Junior Cup", "2026-02-10", 16, "junior"),
        ],
    )

    # --- Placements (12 open + 2 non-open = 14 total) ---
    # Designed so meta shares yield: Charizard ~33% (S), Dragapult ~25% (A),
    # Raging Bolt ~17% (B), Gardevoir ~8%, Gholdengo ~8% (Rogue)
    conn.executemany(
        "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            # Week 1 — t1
            (1, "t1", 1, "Alice", "Charizard ex"),
            (2, "t1", 2, "Bob", "Dragapult ex"),
            (3, "t1", 8, "Charlie", "Raging Bolt ex"),
            # Week 2 — t2
            (4, "t2", 1, "Diana", "Charizard ex"),
            (5, "t2", 4, "Eve", "Dragapult ex"),
            (6, "t2", 16, "Frank", "Gardevoir ex"),
            # Week 3 — t3
            (7, "t3", 2, "Grace", "Charizard ex"),
            (8, "t3", 9, "Hiro", "Dragapult ex"),
            (9, "t3", 32, "Ivy", "Gholdengo ex"),  # standing > 16
            # Week 4 — t4
            (10, "t4", 1, "Jack", "Charizard ex"),
            (11, "t4", 4, "Kate", "Raging Bolt ex"),
            (12, "t4", 8, "Leo", "Gholdengo ex"),
            # Senior/Junior — should be excluded from open_placements
            (13, "t5", 1, "Senior1", "Charizard ex"),
            (14, "t6", 1, "Junior1", "Dragapult ex"),
        ],
    )

    # --- Decklist cards ---
    decklist_rows = []
    # Universal staples in all 12 open placements
    for pid in range(1, 13):
        decklist_rows.append((pid, "card-nest", "Nest Ball", 4))
        decklist_rows.append((pid, "card-ultra", "Ultra Ball", 4))
        decklist_rows.append((pid, "card-boss", "Boss's Orders", 2))

    # Archetype-specific cards
    charizard_pids = [1, 4, 7, 10]
    for pid in charizard_pids:
        decklist_rows.append((pid, "card-charizard", "Charizard ex", 2))
        decklist_rows.append((pid, "card-arven", "Arven", 2))
        decklist_rows.append((pid, "card-rare-candy", "Rare Candy", 4))

    dragapult_pids = [2, 5, 8]
    for pid in dragapult_pids:
        decklist_rows.append((pid, "card-dragapult", "Dragapult ex", 3))
        decklist_rows.append((pid, "card-iono", "Iono", 3))

    bolt_pids = [3, 11]
    for pid in bolt_pids:
        decklist_rows.append((pid, "card-bolt", "Raging Bolt ex", 3))

    gardevoir_pids = [6]
    for pid in gardevoir_pids:
        decklist_rows.append((pid, "card-garde", "Gardevoir ex", 3))

    gholdengo_pids = [9, 12]
    for pid in gholdengo_pids:
        decklist_rows.append((pid, "card-gholdengo", "Gholdengo ex", 2))

    # Rotated card (rotation_legal=0) in all open placements — buylist should exclude
    for pid in range(1, 13):
        decklist_rows.append((pid, "sv1-rotated", "Rotated Card", 1))

    # Late-week-only card for trend testing (weeks 3-4 only)
    for pid in [7, 8, 9, 10, 11, 12]:
        decklist_rows.append((pid, "card-judge", "Judge", 2))

    # Senior/junior decklist (should not appear in open exports)
    decklist_rows.append((13, "card-nest", "Nest Ball", 4))
    decklist_rows.append((13, "card-charizard", "Charizard ex", 2))
    decklist_rows.append((14, "card-nest", "Nest Ball", 4))
    decklist_rows.append((14, "card-dragapult", "Dragapult ex", 3))

    conn.executemany(
        "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
        decklist_rows,
    )

    # --- Cards table ---
    conn.executemany(
        "INSERT INTO cards (id, name_en, name_jp, set_code, image_url, supertype, rotation_legal) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "sv5-001",
                "Charizard ex",
                "リザードンex",
                "sv5",
                "https://img/sv5-001.png",
                "Pokemon",
                1,
            ),
            (
                "sv5-002",
                "Dragapult ex",
                "ドラパルトex",
                "sv5",
                "https://img/sv5-002.png",
                "Pokemon",
                1,
            ),
            (
                "sv5-003",
                "Rare Candy",
                "ふしぎなアメ",
                "sv5",
                "https://img/sv5-003.png",
                "Trainer",
                1,
            ),
            (
                "sv5-004",
                "Raging Bolt ex",
                "タケルライコex",
                "sv5",
                "https://img/sv5-004.png",
                "Pokemon",
                1,
            ),
            (
                "sv5-005",
                "Gardevoir ex",
                "サーナイトex",
                "sv5",
                "https://img/sv5-005.png",
                "Pokemon",
                1,
            ),
            (
                "sv5-006",
                "Gholdengo ex",
                "サーフゴーex",
                "sv5",
                "https://img/sv5-006.png",
                "Pokemon",
                1,
            ),
            (
                "sv1-rotated",
                "Rotated Card",
                "ローテカード",
                "sv1",
                "https://img/sv1-001.png",
                "Trainer",
                0,
            ),
        ],
    )

    # --- Card mappings (JP→EN translation path) ---
    conn.executemany(
        "INSERT INTO card_mappings (jp_card_id, en_card_id, card_name_jp, card_name_en) "
        "VALUES (?, ?, ?, ?)",
        [
            ("SV5-001", "sv5-001", "リザードンex", "Charizard ex"),
            ("SV5-002", "sv5-002", "ドラパルトex", "Dragapult ex"),
        ],
    )

    # --- CL events ---
    conn.execute(
        "INSERT INTO cl_events (id, name, division, date, player_count) VALUES (?, ?, ?, ?, ?)",
        (900001, "Champions League Tokyo", "masters", "2026-02-20", 7000),
    )
    conn.executemany(
        "INSERT INTO cl_placements (id, event_id, standing, player_name, region, deck_code) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (101, 900001, 1, "Taro", "Tokyo", "deck-abc"),
            (102, 900001, 2, "Hanako", "Osaka", "deck-xyz"),
        ],
    )
    conn.executemany(
        "INSERT INTO cl_decklist_cards (placement_id, card_name_jp, card_name_en, count, category) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (101, "リザードンex", None, 2, "Pokemon"),
            (101, "ネストボール", None, 4, "Trainer"),
            (102, "ドラパルトex", None, 2, "Pokemon"),
        ],
    )

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture()
def db_empty() -> sqlite3.Connection:
    """Empty in-memory SQLite database with schema only. No seed data."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture()
def db_single_tournament() -> sqlite3.Connection:
    """Single tournament with 2 placements -- minimum viable export data."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)

    conn.execute(
        "INSERT INTO tournaments (id, name, date, player_count, division) VALUES (?, ?, ?, ?, ?)",
        ("t1", "Solo Tournament", "2026-03-01", 32, "open"),
    )
    conn.executemany(
        "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (1, "t1", 1, "Alice", "Charizard ex"),
            (2, "t1", 2, "Bob", "Dragapult ex"),
        ],
    )
    conn.executemany(
        "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
        [
            (1, "card-nest", "Nest Ball", 4),
            (1, "card-ultra", "Ultra Ball", 4),
            (2, "card-nest", "Nest Ball", 4),
            (2, "card-ultra", "Ultra Ball", 4),
        ],
    )

    conn.commit()
    yield conn
    conn.close()
