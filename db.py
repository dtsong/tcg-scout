"""SQLite database schema and connection helpers."""

import sqlite3
from pathlib import Path

from config import DEFAULT_FORMAT, FORMATS

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / FORMATS[DEFAULT_FORMAT]["db_name"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_jp TEXT,
    set_code TEXT NOT NULL,
    set_name TEXT,
    set_number TEXT,
    regulation_mark TEXT,
    supertype TEXT,
    rarity TEXT,
    image_url TEXT,
    rotation_legal BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tournaments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    player_count INTEGER,
    country TEXT DEFAULT 'JP',
    division TEXT DEFAULT 'open',
    tournament_type TEXT DEFAULT 'city-league'
);

CREATE TABLE IF NOT EXISTS placements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id TEXT NOT NULL REFERENCES tournaments(id),
    standing INTEGER NOT NULL,
    player_name TEXT,
    archetype TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decklist_cards (
    placement_id INTEGER NOT NULL REFERENCES placements(id),
    card_id TEXT NOT NULL,
    card_name TEXT,
    count INTEGER NOT NULL,
    PRIMARY KEY (placement_id, card_id)
);

CREATE TABLE IF NOT EXISTS meta_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    tournament_count INTEGER,
    deck_count INTEGER
);

CREATE TABLE IF NOT EXISTS archetype_stats (
    snapshot_id INTEGER NOT NULL REFERENCES meta_snapshots(id),
    archetype TEXT NOT NULL,
    meta_share REAL NOT NULL,
    deck_count INTEGER NOT NULL,
    best_placement INTEGER,
    tier TEXT CHECK(tier IN ('S','A','B','C','Rogue')),
    PRIMARY KEY (snapshot_id, archetype)
);

-- JP-to-EN card ID mappings (from Limitless)
CREATE TABLE IF NOT EXISTS card_mappings (
    jp_card_id TEXT PRIMARY KEY,      -- e.g. "SV7-018"
    en_card_id TEXT NOT NULL,         -- e.g. "SCR-028"
    card_name_jp TEXT,
    card_name_en TEXT,
    jp_set_id TEXT,
    en_set_id TEXT
);

-- View: open-division placements only (used by meta/export queries)
CREATE VIEW IF NOT EXISTS open_placements AS
SELECT p.* FROM placements p
JOIN tournaments t ON t.id = p.tournament_id
WHERE t.division = 'open';

-- Champions League events and decklists
CREATE TABLE IF NOT EXISTS cl_events (
    id INTEGER PRIMARY KEY,           -- Official event ID (e.g. 903702)
    name TEXT NOT NULL,
    division TEXT NOT NULL,            -- juniors, seniors, masters
    date TEXT NOT NULL,
    player_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cl_placements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES cl_events(id),
    standing INTEGER NOT NULL,
    player_name TEXT,
    region TEXT,
    deck_code TEXT,
    deck_url TEXT
);

CREATE TABLE IF NOT EXISTS cl_decklist_cards (
    placement_id INTEGER NOT NULL REFERENCES cl_placements(id),
    card_name_jp TEXT NOT NULL,
    card_name_en TEXT,
    card_id TEXT,                      -- Resolved EN card ID
    set_code TEXT,
    count INTEGER NOT NULL,
    category TEXT,                     -- Pokemon, Trainer, Energy
    PRIMARY KEY (placement_id, card_name_jp)
);
"""


def get_format_connection(format_slug: str) -> sqlite3.Connection:
    """Get a SQLite connection for a specific format."""
    db_name = FORMATS[format_slug]["db_name"]
    db_path = DATA_DIR / db_name
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_connection() -> sqlite3.Connection:
    """Get a SQLite connection for the default format."""
    return get_format_connection(DEFAULT_FORMAT)


def init_db(conn: sqlite3.Connection | None = None) -> None:
    """Create all tables if they don't exist."""
    close = False
    if conn is None:
        conn = get_connection()
        close = True
    conn.executescript(SCHEMA)
    # Migration: ensure division column exists on older databases
    cols = {row[1] for row in conn.execute("PRAGMA table_info(tournaments)")}
    if "division" not in cols:
        conn.execute("ALTER TABLE tournaments ADD COLUMN division TEXT DEFAULT 'open'")
    # Migration: add tournament_type column (city-league, champions-league)
    if "tournament_type" not in cols:
        conn.execute(
            "ALTER TABLE tournaments ADD COLUMN tournament_type TEXT DEFAULT 'city-league'"
        )
    conn.commit()
    if close:
        conn.close()


def reset_db(format_slug: str | None = None) -> None:
    """Drop and recreate the database."""
    slug = format_slug or DEFAULT_FORMAT
    db_path = DATA_DIR / FORMATS[slug]["db_name"]
    if db_path.exists():
        db_path.unlink()
    conn = get_format_connection(slug)
    init_db(conn)
    conn.close()
