"""SQLite database schema and connection helpers for Labs Limitless data.

Separate database (data/labs.db) for international tournament H2H match data.
Schema follows existing naming conventions for future unification with JP data.
"""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
LABS_DB_PATH = DATA_DIR / "labs.db"

LABS_SCHEMA = """
CREATE TABLE IF NOT EXISTS tournaments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    player_count INTEGER,
    country TEXT,
    region TEXT,
    format TEXT,
    source TEXT DEFAULT 'limitless-labs'
);

CREATE TABLE IF NOT EXISTS players (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT
);

CREATE TABLE IF NOT EXISTS matches (
    id TEXT PRIMARY KEY,
    tournament_id TEXT NOT NULL REFERENCES tournaments(id),
    round INTEGER NOT NULL,
    player1_id TEXT NOT NULL REFERENCES players(id),
    player2_id TEXT NOT NULL REFERENCES players(id),
    winner_id TEXT,
    player1_archetype TEXT,
    player2_archetype TEXT
);

CREATE TABLE IF NOT EXISTS placements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id TEXT NOT NULL REFERENCES tournaments(id),
    player_id TEXT NOT NULL REFERENCES players(id),
    standing INTEGER NOT NULL,
    archetype TEXT,
    record_w INTEGER DEFAULT 0,
    record_l INTEGER DEFAULT 0,
    record_t INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS decklists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    placement_id INTEGER REFERENCES placements(id),
    player_id TEXT NOT NULL REFERENCES players(id),
    tournament_id TEXT NOT NULL REFERENCES tournaments(id)
);

CREATE TABLE IF NOT EXISTS decklist_cards (
    decklist_id INTEGER NOT NULL REFERENCES decklists(id),
    card_name TEXT NOT NULL,
    card_id TEXT,
    count INTEGER NOT NULL,
    category TEXT,
    PRIMARY KEY (decklist_id, card_name)
);

CREATE TABLE IF NOT EXISTS archetype_mapping (
    labs_label TEXT PRIMARY KEY,
    scout_slug TEXT NOT NULL,
    scout_name TEXT NOT NULL
);
"""


def get_labs_connection() -> sqlite3.Connection:
    """Get a SQLite connection for the Labs database."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(LABS_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_labs_db(conn: sqlite3.Connection | None = None) -> None:
    """Create all Labs tables if they don't exist."""
    close = False
    if conn is None:
        conn = get_labs_connection()
        close = True
    conn.executescript(LABS_SCHEMA)
    conn.commit()
    if close:
        conn.close()


def reset_labs_db() -> None:
    """Drop and recreate the Labs database."""
    if LABS_DB_PATH.exists():
        LABS_DB_PATH.unlink()
    conn = get_labs_connection()
    init_labs_db(conn)
    conn.close()


def make_match_id(tournament_id: str, round_num: int, p1_id: str, p2_id: str) -> str:
    """Generate a deterministic match ID for idempotent ingestion."""
    # Sort player IDs so the same match always gets the same ID
    players = sorted([p1_id, p2_id])
    return f"{tournament_id}:r{round_num}:{players[0]}:{players[1]}"
