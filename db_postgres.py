"""Postgres connection + write layer for Scout's labs data.

Reads the connection URL from ``SCOUT_DATABASE_URL`` (preferred) or
``DATABASE_URL`` / ``SUPABASE_DB_URL`` (fallbacks). For Supabase, use the
project's Session Pooler URI for the scrape pipeline (long-lived connections,
prepared statements, COPY); use the Transaction Pooler URI for short
serverless work.

Schema is managed via Supabase CLI migrations in ``supabase/migrations/``
— run ``supabase db push`` to apply.

``psycopg`` is imported lazily so this module (and its env-var resolution
helpers) import cleanly in environments where the driver isn't installed
(e.g. CI that only checks migration content).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    import psycopg

logger = logging.getLogger(__name__)

# Env var names — primary then fallback. Prefer the SCOUT-prefixed var so this
# code doesn't accidentally hijack a frontend-only DATABASE_URL.
_ENV_KEYS = ("SCOUT_DATABASE_URL", "DATABASE_URL", "SUPABASE_DB_URL")


class PostgresConfigError(RuntimeError):
    """Raised when no Postgres connection URL can be resolved."""


def get_database_url() -> str:
    """Return the configured Postgres connection URL."""
    for key in _ENV_KEYS:
        value = os.environ.get(key)
        if value:
            return value
    raise PostgresConfigError("No Postgres URL configured. Set one of: " + ", ".join(_ENV_KEYS))


@contextmanager
def get_pg_connection(
    *, autocommit: bool = False, row_factory: Any = None
) -> Iterator[psycopg.Connection]:
    """Context-managed Postgres connection.

    Commits on clean exit (unless ``autocommit``); rolls back on exception.
    """
    import psycopg
    from psycopg.rows import dict_row

    url = get_database_url()
    conn = psycopg.connect(url, autocommit=autocommit, row_factory=row_factory or dict_row)
    try:
        yield conn
        if not autocommit:
            conn.commit()
    except Exception:
        if not autocommit:
            conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Write layer — idempotent upserts on the labs.* schema.
#
# All functions take an open psycopg connection and run within the caller's
# transaction (one transaction per tournament). Player rows MUST be upserted
# before matches (FK player_low_id/high_id -> labs.players).
# ---------------------------------------------------------------------------


def upsert_tournament(
    conn: psycopg.Connection,
    *,
    tournament_id: str,
    name: str,
    date: str,
    labs_id: str | None = None,
    rk9_id: str | None = None,
    country: str | None = None,
    city: str | None = None,
    region: str | None = None,
    fmt: str | None = None,
    tournament_type: str | None = None,
    player_count: int | None = None,
    total_rounds: int | None = None,
    division: str = "open",
    updated_at_src: str | None = None,
) -> None:
    """Insert/refresh one row in labs.tournaments (PK = main-site tournament id)."""
    conn.execute(
        """
        INSERT INTO labs.tournaments
            (id, labs_id, rk9_id, name, date, country, city, region, format,
             tournament_type, player_count, total_rounds, division, source,
             updated_at_src, refreshed_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                'limitless-labs', %s, now())
        ON CONFLICT (id) DO UPDATE SET
            labs_id=excluded.labs_id, rk9_id=excluded.rk9_id, name=excluded.name,
            date=excluded.date, country=excluded.country, city=excluded.city,
            region=excluded.region, format=excluded.format,
            tournament_type=excluded.tournament_type,
            player_count=excluded.player_count, total_rounds=excluded.total_rounds,
            division=excluded.division, updated_at_src=excluded.updated_at_src,
            refreshed_at=now()
        """,
        (
            tournament_id,
            labs_id,
            rk9_id,
            name,
            date,
            country,
            city,
            region,
            fmt,
            tournament_type,
            player_count,
            total_rounds,
            division,
            updated_at_src,
        ),
    )


def upsert_player(
    conn: psycopg.Connection, *, player_id: str, name: str, country: str | None
) -> None:
    """Insert/refresh one row in labs.players (id is tournament-namespaced)."""
    conn.execute(
        """
        INSERT INTO labs.players (id, name, country) VALUES (%s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET name=excluded.name, country=excluded.country
        """,
        (player_id, name, country),
    )


def upsert_placement(
    conn: psycopg.Connection,
    *,
    tournament_id: str,
    player_id: str,
    player_name: str,
    standing: int,
    archetype: str | None,
    archetype_slug: str | None = None,
    sprite_key: str | None = None,
    record_w: int = 0,
    record_l: int = 0,
    record_t: int = 0,
    decklist_url: str | None = None,
    has_decklist: bool = False,
) -> int:
    """Upsert a placement; return its stable id (for decklist FK)."""
    row = conn.execute(
        """
        INSERT INTO labs.placements
            (tournament_id, player_id, player_name, standing, archetype,
             archetype_slug, sprite_key, record_w, record_l, record_t,
             decklist_url, has_decklist)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tournament_id, player_id) DO UPDATE SET
            player_name=excluded.player_name, standing=excluded.standing,
            archetype=excluded.archetype, archetype_slug=excluded.archetype_slug,
            sprite_key=excluded.sprite_key, record_w=excluded.record_w,
            record_l=excluded.record_l, record_t=excluded.record_t,
            decklist_url=excluded.decklist_url, has_decklist=excluded.has_decklist
        RETURNING id
        """,
        (
            tournament_id,
            player_id,
            player_name,
            standing,
            archetype,
            archetype_slug,
            sprite_key,
            record_w,
            record_l,
            record_t,
            decklist_url,
            has_decklist,
        ),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"placement upsert returned no id for ({tournament_id}, {player_id})")
    return row["id"] if isinstance(row, dict) else row[0]


def upsert_decklist(
    conn: psycopg.Connection,
    *,
    placement_id: int,
    source_url: str | None,
    cards: Sequence[dict],
) -> int:
    """Upsert a decklist header (keyed on placement_id) and replace its cards."""
    row = conn.execute(
        """
        INSERT INTO labs.decklists (placement_id, source_url, card_count, fetched_at)
        VALUES (%s, %s, %s, now())
        ON CONFLICT (placement_id) DO UPDATE SET
            source_url=excluded.source_url, card_count=excluded.card_count,
            fetched_at=now()
        RETURNING id
        """,
        (placement_id, source_url, len(cards)),
    ).fetchone()
    decklist_id = row["id"] if isinstance(row, dict) else row[0]

    conn.execute("DELETE FROM labs.decklist_cards WHERE decklist_id=%s", (decklist_id,))
    if cards:
        conn.cursor().executemany(
            """
            INSERT INTO labs.decklist_cards
                (decklist_id, card_id, card_name, set_code, card_number, count, category)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (decklist_id, card_id) DO NOTHING
            """,
            [
                (
                    decklist_id,
                    str(c.get("card_id") or c.get("name")),
                    str(c.get("name")),
                    c.get("set_code") or None,
                    c.get("card_number") or None,
                    int(c.get("count", 1)),
                    c.get("category"),
                )
                for c in cards
            ],
        )
    return decklist_id


def insert_matches(conn: psycopg.Connection, rows: Sequence[dict]) -> int:
    """Batch-insert match rows; idempotent via ON CONFLICT(id) DO NOTHING.

    Each row dict must carry: id, tournament_id, round, player_low_id,
    player_high_id, player_low_archetype, player_high_archetype, winner_id,
    result, is_bye.
    """
    if not rows:
        return 0
    conn.cursor().executemany(
        """
        INSERT INTO labs.matches
            (id, tournament_id, round, player_low_id, player_high_id,
             player_low_archetype, player_high_archetype, winner_id, result, is_bye)
        VALUES (%(id)s, %(tournament_id)s, %(round)s, %(player_low_id)s,
                %(player_high_id)s, %(player_low_archetype)s,
                %(player_high_archetype)s, %(winner_id)s, %(result)s, %(is_bye)s)
        ON CONFLICT (id) DO NOTHING
        """,
        list(rows),
    )
    return len(rows)


def backfill_match_archetypes(conn: psycopg.Connection, tournament_id: str) -> None:
    """Overwrite match archetypes from labs.placements (sprite-normalized truth).

    Trust placements.archetype over the pairings-row deck label so the matchup
    matrix reconciles with the standings-derived archetype names.
    """
    for side in ("low", "high"):
        conn.execute(
            f"""
            UPDATE labs.matches m
            SET player_{side}_archetype = p.archetype
            FROM labs.placements p
            WHERE p.tournament_id = m.tournament_id
              AND p.player_id = m.player_{side}_id
              AND m.tournament_id = %s
              AND p.archetype IS NOT NULL
              AND p.archetype <> 'Unknown'
            """,
            (tournament_id,),
        )


def get_ingested_rounds(conn: psycopg.Connection, tournament_id: str) -> set[int]:
    """Rounds already present in labs.matches for a tournament (for resumability)."""
    rows = conn.execute(
        "SELECT DISTINCT round FROM labs.matches WHERE tournament_id=%s",
        (tournament_id,),
    ).fetchall()
    return {(r["round"] if isinstance(r, dict) else r[0]) for r in rows}


def refresh_matchup_matrix(conn: psycopg.Connection) -> None:
    """Refresh the matchup matrix materialized view after ingestion."""
    # CONCURRENTLY requires the unique index (present) and a committed prior
    # populate; fall back to a plain refresh on first build.
    try:
        conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY labs.matchup_matrix_agg")
    except Exception:  # noqa: BLE001 - first refresh can't be concurrent
        conn.rollback()
        conn.execute("REFRESH MATERIALIZED VIEW labs.matchup_matrix_agg")
