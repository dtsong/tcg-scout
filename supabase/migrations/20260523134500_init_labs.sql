-- Phase 1: initial labs schema for international (TPCi) tournament data ingested
-- from limitless / labs.limitlesstcg.com.
--
-- All tables are namespaced under the `labs` schema so we can co-locate them
-- with other Scout data without name collisions if we move more onto Postgres
-- later.

CREATE SCHEMA IF NOT EXISTS labs;

CREATE TABLE IF NOT EXISTS labs.tournaments (
    id              TEXT PRIMARY KEY,                       -- limitlesstcg.com tournament_id (numeric string)
    labs_id         TEXT UNIQUE,                            -- labs.limitlesstcg.com zero-padded id (e.g. "0065")
    rk9_id          TEXT,                                   -- upstream RK9 id (e.g. "CA01wQsCrDh1mbLzRAcv")
    name            TEXT NOT NULL,
    date            DATE NOT NULL,
    country         TEXT,
    city            TEXT,
    region          TEXT,
    format          TEXT,                                   -- "STANDARD", "EXPANDED", etc.
    tournament_type TEXT,                                   -- "regional", "international", "worlds", "special"
    player_count    INTEGER,
    total_rounds    INTEGER,
    division        TEXT DEFAULT 'open',
    source          TEXT DEFAULT 'limitless-labs',
    updated_at_src  TIMESTAMPTZ,                            -- "updated_at" reported by labs payload
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    refreshed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS tournaments_date_idx  ON labs.tournaments (date DESC);
CREATE INDEX IF NOT EXISTS tournaments_format_idx ON labs.tournaments (format, date DESC);
CREATE INDEX IF NOT EXISTS tournaments_type_idx   ON labs.tournaments (tournament_type, date DESC);

CREATE TABLE IF NOT EXISTS labs.players (
    id           TEXT PRIMARY KEY,                          -- limitless global player id (e.g. "4993")
    name         TEXT NOT NULL,
    country      TEXT,
    ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS labs.placements (
    id              BIGSERIAL PRIMARY KEY,
    tournament_id   TEXT NOT NULL REFERENCES labs.tournaments(id) ON DELETE CASCADE,
    player_id       TEXT REFERENCES labs.players(id),       -- nullable for synthetic IDs (no link found)
    player_name     TEXT NOT NULL,
    standing        INTEGER NOT NULL,
    archetype       TEXT,
    archetype_slug  TEXT,                                   -- normalized slug (lowercase, hyphenated)
    sprite_key      TEXT,
    record_w        INTEGER DEFAULT 0,
    record_l        INTEGER DEFAULT 0,
    record_t        INTEGER DEFAULT 0,
    decklist_url    TEXT,
    has_decklist    BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (tournament_id, standing)
);

CREATE INDEX IF NOT EXISTS placements_tournament_idx  ON labs.placements (tournament_id);
CREATE INDEX IF NOT EXISTS placements_player_idx      ON labs.placements (player_id);
CREATE INDEX IF NOT EXISTS placements_archetype_idx   ON labs.placements (archetype_slug);
CREATE INDEX IF NOT EXISTS placements_tourn_arch_idx  ON labs.placements (tournament_id, archetype_slug);

CREATE TABLE IF NOT EXISTS labs.decklists (
    id              BIGSERIAL PRIMARY KEY,
    placement_id    BIGINT NOT NULL UNIQUE REFERENCES labs.placements(id) ON DELETE CASCADE,
    source_url      TEXT,
    card_count      INTEGER NOT NULL DEFAULT 0,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS labs.decklist_cards (
    decklist_id   BIGINT  NOT NULL REFERENCES labs.decklists(id) ON DELETE CASCADE,
    card_id       TEXT    NOT NULL,                         -- "SET-NUMBER" or fallback to name
    card_name     TEXT    NOT NULL,
    set_code      TEXT,
    card_number   TEXT,
    count         INTEGER NOT NULL,
    category      TEXT,                                     -- "pokemon" | "trainer" | "energy"
    PRIMARY KEY (decklist_id, card_id)
);

CREATE INDEX IF NOT EXISTS decklist_cards_card_idx ON labs.decklist_cards (card_id);
CREATE INDEX IF NOT EXISTS decklist_cards_name_idx ON labs.decklist_cards (card_name);

-- Round-by-round match data scraped from /<tid>/player/<pid> pages.
-- The same physical match is observed twice (once from each player's page);
-- (tournament_id, round, lower(player_id), higher(player_id)) deduplicates.
CREATE TABLE IF NOT EXISTS labs.matches (
    id                  TEXT PRIMARY KEY,                   -- "<tid>:r<round>:<low>:<high>"
    tournament_id       TEXT NOT NULL REFERENCES labs.tournaments(id) ON DELETE CASCADE,
    round               INTEGER NOT NULL,
    player_low_id       TEXT NOT NULL REFERENCES labs.players(id),
    player_high_id      TEXT NOT NULL REFERENCES labs.players(id),
    player_low_archetype  TEXT,
    player_high_archetype TEXT,
    winner_id           TEXT,                               -- "low" / "high" / NULL for tie
    result              TEXT,                               -- "win-low" | "win-high" | "tie" | "bye"
    is_bye              BOOLEAN NOT NULL DEFAULT FALSE,
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS matches_tournament_idx     ON labs.matches (tournament_id);
CREATE INDEX IF NOT EXISTS matches_archetypes_idx     ON labs.matches (player_low_archetype, player_high_archetype);
CREATE INDEX IF NOT EXISTS matches_player_low_idx     ON labs.matches (player_low_id);
CREATE INDEX IF NOT EXISTS matches_player_high_idx    ON labs.matches (player_high_id);

CREATE TABLE IF NOT EXISTS labs.archetype_mapping (
    labs_label   TEXT PRIMARY KEY,
    scout_slug   TEXT NOT NULL,
    scout_name   TEXT NOT NULL,
    sprite_key   TEXT
);

