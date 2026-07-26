"""SQLite database schema and connection helpers."""

import logging
import sqlite3
from pathlib import Path

from config import DEFAULT_FORMAT, FORMATS

logger = logging.getLogger(__name__)

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
    tournament_type TEXT DEFAULT 'city-league',
    prefecture TEXT,
    store_name TEXT,
    capacity INTEGER
);

CREATE TABLE IF NOT EXISTS placements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id TEXT NOT NULL REFERENCES tournaments(id),
    standing INTEGER NOT NULL,
    player_name TEXT,
    archetype TEXT NOT NULL,
    decklist_url TEXT
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
    weighted_share REAL,
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

-- View: open-division placements only (used by meta/export queries).
-- Deduplicates cross-source copies of the same physical event without dropping
-- unrelated same-day City League stores. A non-JP event is excluded only when a
-- JP API event on the same date/division has matching event identity or matching
-- placement rows.
CREATE VIEW IF NOT EXISTS open_placements AS
SELECT p.* FROM placements p
JOIN tournaments t ON t.id = p.tournament_id
WHERE t.division = 'open'
AND (
    t.id LIKE 'jp-%'
    OR NOT EXISTS (
        SELECT 1 FROM tournaments t2
        LEFT JOIN placements p2 ON p2.tournament_id = t2.id
        WHERE t2.id LIKE 'jp-%'
        AND t2.date = t.date
        AND t2.division = t.division
        AND (
            (
                t.store_name IS NOT NULL
                AND t2.store_name IS NOT NULL
                AND lower(t2.store_name) = lower(t.store_name)
            )
            OR (
                t.prefecture IS NOT NULL
                AND t2.prefecture IS NOT NULL
                AND lower(t2.prefecture) = lower(t.prefecture)
                AND coalesce(t.capacity, -1) = coalesce(t2.capacity, -1)
            )
            OR (
                p2.standing = p.standing
                AND coalesce(p2.player_name, '') = coalesce(p.player_name, '')
                AND p2.archetype = p.archetype
            )
        )
    )
);

-- View: open-division tournaments only, deduplicated across scrapers.
-- Mirrors open_placements at the tournament level so queries that list or
-- count events (rather than placements) also avoid cross-source duplicates.
CREATE VIEW IF NOT EXISTS open_tournaments AS
SELECT t.* FROM tournaments t
WHERE t.division = 'open'
AND (
    t.id LIKE 'jp-%'
    OR NOT EXISTS (
        SELECT 1 FROM tournaments t2
        WHERE t2.id LIKE 'jp-%'
        AND t2.date = t.date
        AND t2.division = t.division
        AND (
            (
                t.store_name IS NOT NULL
                AND t2.store_name IS NOT NULL
                AND lower(t2.store_name) = lower(t.store_name)
            )
            OR (
                t.prefecture IS NOT NULL
                AND t2.prefecture IS NOT NULL
                AND lower(t2.prefecture) = lower(t.prefecture)
                AND coalesce(t.capacity, -1) = coalesce(t2.capacity, -1)
            )
            OR EXISTS (
                SELECT 1
                FROM placements p
                JOIN placements p2 ON p2.tournament_id = t2.id
                WHERE p.tournament_id = t.id
                AND p2.standing = p.standing
                AND coalesce(p2.player_name, '') = coalesce(p.player_name, '')
                AND p2.archetype = p.archetype
            )
        )
    )
);

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

-- Player identity (manual curation)
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL,
    country TEXT DEFAULT 'JP',
    notes TEXT,
    twitter_handle TEXT,
    youtube_url TEXT,
    blog_url TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Maps raw tournament names to player IDs (many-to-one)
CREATE TABLE IF NOT EXISTS player_aliases (
    id INTEGER PRIMARY KEY,
    alias TEXT NOT NULL,
    player_id INTEGER NOT NULL REFERENCES players(id),
    source TEXT,                       -- 'limitless', 'pokemon_jp', 'pokekameshi', etc.
    UNIQUE(alias, source)
);

-- Bridge: links existing placements to player identities (non-destructive)
CREATE TABLE IF NOT EXISTS placement_players (
    placement_id INTEGER NOT NULL REFERENCES placements(id),
    player_id INTEGER NOT NULL REFERENCES players(id),
    confidence REAL DEFAULT 1.0 CHECK(confidence >= 0.0 AND confidence <= 1.0),
    PRIMARY KEY (placement_id, player_id)
);

-- Indexes.
--
-- The dedup views (open_placements, open_tournaments) run a correlated
-- NOT EXISTS against tournaments. Without these, SQLite scans all of
-- tournaments once per placement row, which is what pushed the scrape
-- pipeline past its build timeout.
CREATE INDEX IF NOT EXISTS idx_placements_tournament
    ON placements(tournament_id);
CREATE INDEX IF NOT EXISTS idx_tournaments_date_div
    ON tournaments(date, division);
CREATE INDEX IF NOT EXISTS idx_placements_dedup
    ON placements(standing, archetype, player_name);
CREATE INDEX IF NOT EXISTS idx_decklist_cards_card
    ON decklist_cards(card_id);
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


def _backfill_prefecture(conn: sqlite3.Connection) -> None:
    """Best-effort backfill of prefecture from tournament name where NULL."""
    rows = conn.execute("SELECT id, name FROM tournaments WHERE prefecture IS NULL").fetchall()
    if not rows:
        return
    updated = 0
    for row in rows:
        tid, name = row["id"], row["name"]
        prefecture = None
        if "City League " in name:
            # Limitless format: "City League Osaka" -> "Osaka"
            prefecture = name.split("City League ", 1)[1].strip() or None
        if prefecture:
            conn.execute(
                "UPDATE tournaments SET prefecture = ? WHERE id = ?",
                (prefecture, tid),
            )
            updated += 1
    if updated:
        logger.info("Backfill: set prefecture on %d tournaments", updated)


def init_db(conn: sqlite3.Connection | None = None) -> None:
    """Create all tables if they don't exist."""
    close = False
    if conn is None:
        conn = get_connection()
        close = True
    # Required because CREATE VIEW IF NOT EXISTS won't update existing definitions.
    conn.execute("DROP VIEW IF EXISTS open_placements")
    conn.execute("DROP VIEW IF EXISTS open_tournaments")
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
    # Migration: add city-league metadata columns
    if "prefecture" not in cols:
        conn.execute("ALTER TABLE tournaments ADD COLUMN prefecture TEXT")
        logger.info("Migration: added prefecture column to tournaments")
    if "store_name" not in cols:
        conn.execute("ALTER TABLE tournaments ADD COLUMN store_name TEXT")
        logger.info("Migration: added store_name column to tournaments")
    if "capacity" not in cols:
        conn.execute("ALTER TABLE tournaments ADD COLUMN capacity INTEGER")
        logger.info("Migration: added capacity column to tournaments")
    # Backfill prefecture from tournament name where missing
    _backfill_prefecture(conn)
    # Migration: add decklist_url column to placements
    p_cols = {row[1] for row in conn.execute("PRAGMA table_info(placements)")}
    if "decklist_url" not in p_cols:
        conn.execute("ALTER TABLE placements ADD COLUMN decklist_url TEXT")
        logger.info("Migration: added decklist_url column to placements")
    # Migration: ensure weighted_share column exists on archetype_stats
    as_cols = {row[1] for row in conn.execute("PRAGMA table_info(archetype_stats)")}
    if "weighted_share" not in as_cols:
        conn.execute("ALTER TABLE archetype_stats ADD COLUMN weighted_share REAL")
        logger.info("Migration: added weighted_share column to archetype_stats")
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
