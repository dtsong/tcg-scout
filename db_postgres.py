"""Postgres connection helpers for Scout's labs data.

Reads the connection URL from ``SCOUT_DATABASE_URL`` (preferred) or
``DATABASE_URL`` (fallback). For Supabase, use the project's Session
Pooler URI for the scrape pipeline (long-lived connections, prepared
statements, COPY); use the Transaction Pooler URI for short serverless
work.

Schema is managed via Supabase CLI migrations in ``supabase/migrations/``
— run ``supabase db push`` to apply.
"""

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

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
    *, autocommit: bool = False, row_factory=dict_row
) -> Iterator[psycopg.Connection]:
    """Context-managed Postgres connection.

    Commits on clean exit (unless ``autocommit``); rolls back on exception.
    """
    url = get_database_url()
    conn = psycopg.connect(url, autocommit=autocommit, row_factory=row_factory)
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
