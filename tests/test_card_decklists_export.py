"""Tests for per-card decklist export (export_card_decklists)."""

import json
import sqlite3

from db import init_db
from reports.json_export import export_card_decklists


def _seed(conn: sqlite3.Connection) -> None:
    """Seed DB with placements that have decklist_url and decklist cards."""
    conn.execute(
        "INSERT INTO tournaments (id, name, date, player_count) "
        "VALUES ('t1', 'Osaka CL', '2026-03-01', 64)"
    )
    conn.execute(
        "INSERT INTO tournaments (id, name, date, player_count) "
        "VALUES ('t2', 'Tokyo CL', '2026-03-08', 64)"
    )
    # Top-4 placements with decklist_url
    conn.executemany(
        "INSERT INTO placements (id, tournament_id, standing, player_name, archetype, decklist_url) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "t1", 1, "Alice", "Charizard Pidgeot", "https://limitlesstcg.com/decks/list/1"),
            (2, "t1", 2, "Bob", "Lugia Archeops", "https://limitlesstcg.com/decks/list/2"),
            (3, "t2", 3, "Charlie", "Charizard Pidgeot", None),  # No decklist URL
            (4, "t1", 8, "Diana", "Charizard Pidgeot", "https://limitlesstcg.com/decks/list/4"),
        ],
    )
    # Decklist cards
    conn.executemany(
        "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) VALUES (?, ?, ?, ?)",
        [
            (1, "boss-orders", "Boss's Orders", 2),
            (1, "nest-ball", "Nest Ball", 4),
            (2, "boss-orders", "Boss's Orders", 2),
            (2, "nest-ball", "Nest Ball", 4),
            (3, "boss-orders", "Boss's Orders", 2),
            (3, "nest-ball", "Nest Ball", 4),
            (4, "boss-orders", "Boss's Orders", 2),
        ],
    )
    conn.execute(
        "INSERT INTO meta_snapshots (id, generated_at, tournament_count, deck_count) "
        "VALUES (1, '2026-03-10', 2, 4)"
    )
    conn.executemany(
        "INSERT INTO archetype_stats (snapshot_id, archetype, deck_count, meta_share, tier) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (1, "Charizard Pidgeot", 3, 75.0, "S"),
            (1, "Lugia Archeops", 1, 25.0, "A"),
        ],
    )
    conn.commit()


def test_export_creates_per_card_json(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    _seed(conn)

    export_card_decklists(conn, tmp_path)

    # Should create card-decklists directory
    card_dir = tmp_path / "card-decklists"
    assert card_dir.exists()

    # Should create files for cards in top-4 placements
    boss_file = card_dir / "boss-s-orders.json"
    assert boss_file.exists()

    data = json.loads(boss_file.read_text())
    assert data["card_name"] == "Boss's Orders"
    assert len(data["top4_results"]) == 3  # pids 1, 2, 3 (standing <= 4)


def test_export_includes_decklist_url(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    _seed(conn)

    export_card_decklists(conn, tmp_path)

    data = json.loads((tmp_path / "card-decklists" / "boss-s-orders.json").read_text())
    urls = [r["decklist_url"] for r in data["top4_results"]]
    assert "https://limitlesstcg.com/decks/list/1" in urls
    assert None in urls  # pid 3 has no URL


def test_export_groups_by_archetype(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    _seed(conn)

    export_card_decklists(conn, tmp_path)

    data = json.loads((tmp_path / "card-decklists" / "boss-s-orders.json").read_text())
    archetypes = {r["archetype"] for r in data["top4_results"]}
    assert "Charizard Pidgeot" in archetypes
    assert "Lugia Archeops" in archetypes


def test_export_excludes_non_top4(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    _seed(conn)

    export_card_decklists(conn, tmp_path)

    data = json.loads((tmp_path / "card-decklists" / "boss-s-orders.json").read_text())
    standings = [r["standing"] for r in data["top4_results"]]
    assert all(s <= 4 for s in standings)


def test_export_result_fields(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    _seed(conn)

    export_card_decklists(conn, tmp_path)

    data = json.loads((tmp_path / "card-decklists" / "boss-s-orders.json").read_text())
    result = data["top4_results"][0]
    assert "archetype" in result
    assert "archetype_slug" in result
    assert "tournament_name" in result
    assert "date" in result
    assert "standing" in result
    assert "copies" in result
    assert "decklist_url" in result


def test_migration_adds_decklist_url():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    # Create schema without decklist_url (simulating old DB)
    old_schema = """
    CREATE TABLE IF NOT EXISTS tournaments (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, date TEXT NOT NULL,
        player_count INTEGER, country TEXT DEFAULT 'JP',
        division TEXT DEFAULT 'open', tournament_type TEXT DEFAULT 'city-league'
    );
    CREATE TABLE IF NOT EXISTS placements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id TEXT NOT NULL REFERENCES tournaments(id),
        standing INTEGER NOT NULL, player_name TEXT, archetype TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS decklist_cards (
        placement_id INTEGER NOT NULL REFERENCES placements(id),
        card_id TEXT NOT NULL, card_name TEXT, count INTEGER NOT NULL,
        PRIMARY KEY (placement_id, card_id)
    );
    CREATE TABLE IF NOT EXISTS meta_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        generated_at TEXT NOT NULL, tournament_count INTEGER, deck_count INTEGER
    );
    CREATE TABLE IF NOT EXISTS archetype_stats (
        snapshot_id INTEGER NOT NULL REFERENCES meta_snapshots(id),
        archetype TEXT NOT NULL, meta_share REAL NOT NULL,
        deck_count INTEGER NOT NULL, best_placement INTEGER,
        tier TEXT, PRIMARY KEY (snapshot_id, archetype)
    );
    """
    conn.executescript(old_schema)

    # Verify no decklist_url column
    cols = {row[1] for row in conn.execute("PRAGMA table_info(placements)")}
    assert "decklist_url" not in cols

    # Run migration
    init_db(conn)

    # Verify column added
    cols = {row[1] for row in conn.execute("PRAGMA table_info(placements)")}
    assert "decklist_url" in cols

    # Verify we can insert with the new column
    conn.execute("INSERT INTO tournaments (id, name, date) VALUES ('t1', 'Test', '2026-01-01')")
    conn.execute(
        "INSERT INTO placements (tournament_id, standing, player_name, archetype, decklist_url) "
        "VALUES ('t1', 1, 'Alice', 'Test Deck', 'https://example.com/deck/1')"
    )
    row = conn.execute("SELECT decklist_url FROM placements WHERE standing = 1").fetchone()
    assert row["decklist_url"] == "https://example.com/deck/1"
    conn.close()
