"""Unit tests for db_postgres helpers + sanity checks on the init migration.

Schema is applied to live databases via ``supabase db push``; this file does
not run live SQL.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"


def test_migrations_directory_exists_at_supabase_path():
    assert MIGRATIONS_DIR.is_dir(), (
        f"expected migrations at {MIGRATIONS_DIR} (Supabase CLI convention)"
    )


def test_at_least_one_migration_present():
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    assert files, "expected at least one *.sql migration"
    assert all(f.suffix == ".sql" for f in files)


def test_init_migration_creates_labs_schema_and_core_tables():
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    init = files[0].read_text()
    assert "CREATE SCHEMA IF NOT EXISTS labs" in init
    for table in ("tournaments", "players", "placements", "decklists", "decklist_cards", "matches"):
        assert f"labs.{table}" in init, f"init migration should declare labs.{table}"


def test_init_migration_indexes_archetype_and_tournament():
    init = sorted(MIGRATIONS_DIR.glob("*.sql"))[0].read_text()
    # Spot-check the indexes that matter for matchup queries
    assert "matches_archetypes_idx" in init
    assert "placements_tourn_arch_idx" in init


def test_get_database_url_raises_when_unset(monkeypatch):
    from db_postgres import PostgresConfigError, get_database_url

    for key in ("SCOUT_DATABASE_URL", "DATABASE_URL", "SUPABASE_DB_URL"):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(PostgresConfigError):
        get_database_url()


def test_get_database_url_prefers_scout_var(monkeypatch):
    from db_postgres import get_database_url

    monkeypatch.setenv("SCOUT_DATABASE_URL", "postgresql://scout/x")
    monkeypatch.setenv("DATABASE_URL", "postgresql://other/y")
    assert get_database_url() == "postgresql://scout/x"


def test_get_database_url_falls_back_to_database_url(monkeypatch):
    from db_postgres import get_database_url

    monkeypatch.delenv("SCOUT_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://other/y")
    assert get_database_url() == "postgresql://other/y"
