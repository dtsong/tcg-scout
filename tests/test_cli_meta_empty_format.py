"""`scout meta` on a format with no placements must warn and exit 0.

The scheduled build runs `meta` for every active format under `set -eu`. A new
season's format is registered before its first event publishes, so a hard
failure here would take down the whole pipeline (as it did in 2026-07).
"""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

from click.testing import CliRunner

from cli import cli
from db import init_db


def _empty_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def test_meta_on_empty_format_warns_and_exits_zero():
    conn = _empty_conn()
    with patch("cli.get_format_connection", return_value=conn):
        result = CliRunner().invoke(
            cli, ["--format", "storm-emeralda", "meta"], catch_exceptions=False
        )

    assert result.exit_code == 0, result.output
    assert "No placements yet for format storm-emeralda" in result.output
