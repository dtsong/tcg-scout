-- Phase 1 fixes for the labs schema (see plan: full-depth labs base data).
--
-- 1. labs.placements UNIQUE(tournament_id, standing) is wrong: standings repeat
--    across divisions (open/SR/JR) and the ingest upserts on (tournament_id,
--    player_id) the way the SQLite labs_db does. Re-key the constraint.
-- 2. Add labs.matchup_matrix_agg materialized view so the export query over
--    head-to-head matches stays trivial and cheap to read at build time.

-- --- 1. placements unique key -------------------------------------------------

-- The original constraint was created inline, so Postgres named it after the
-- table (no schema prefix): placements_tournament_id_standing_key.
ALTER TABLE labs.placements
    DROP CONSTRAINT IF EXISTS placements_tournament_id_standing_key;

-- Idempotent: drop the new constraint too so re-application (e.g. db push after
-- a direct apply) is harmless.
ALTER TABLE labs.placements
    DROP CONSTRAINT IF EXISTS labs_placements_tournament_id_player_id_key;

ALTER TABLE labs.placements
    ADD CONSTRAINT labs_placements_tournament_id_player_id_key
    UNIQUE (tournament_id, player_id);

-- --- 2. matchup matrix materialized view -------------------------------------
-- Directed by player-id ordering (low/high), not by archetype. Consumers that
-- want a symmetric A-vs-B matrix must aggregate the (arch_a, arch_b) and
-- (arch_b, arch_a) buckets together (the export does this in Python).

DROP MATERIALIZED VIEW IF EXISTS labs.matchup_matrix_agg;

CREATE MATERIALIZED VIEW labs.matchup_matrix_agg AS
SELECT
    player_low_archetype  AS arch_a,
    player_high_archetype AS arch_b,
    COUNT(*) FILTER (WHERE winner_id = 'low')                        AS wins_a,
    COUNT(*) FILTER (WHERE winner_id = 'high')                       AS wins_b,
    COUNT(*) FILTER (WHERE winner_id IS NULL AND NOT is_bye)         AS ties,
    COUNT(*) FILTER (WHERE NOT is_bye)                               AS total
FROM labs.matches
WHERE NOT is_bye
  AND player_low_archetype  IS NOT NULL
  AND player_high_archetype IS NOT NULL
GROUP BY 1, 2;

CREATE UNIQUE INDEX matchup_matrix_agg_pair_idx
    ON labs.matchup_matrix_agg (arch_a, arch_b);
