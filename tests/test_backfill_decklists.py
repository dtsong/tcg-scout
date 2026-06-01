"""Tests for the backfill-decklists CLI command and its helpers."""

import sqlite3
from unittest.mock import patch

import pytest

from cli import (
    _backfill_jp_decklists,
    _backfill_limitless_decklists,
    _select_missing_decklist_placements,
)
from db import SCHEMA


@pytest.fixture()
def db_missing_decklists() -> sqlite3.Connection:
    """In-memory DB with placements that have decklist_url but no decklist_cards."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)

    conn.executemany(
        "INSERT INTO tournaments (id, name, date, player_count, division) VALUES (?, ?, ?, ?, ?)",
        [
            ("jp-1001", "JP Event 1", "2026-04-15", 16, "open"),
            ("jp-1002", "JP Event 2", "2026-04-20", 16, "open"),
            (
                "https://limitlesstcg.com/tournaments/jp/5001",
                "Limitless Event",
                "2026-04-18",
                16,
                "open",
            ),
            # Senior division: must be excluded by open_placements view
            ("jp-2001", "JP Senior Cup", "2026-04-19", 16, "senior"),
            # TPCI/Labs major: integer id, decklists on labs.limitlesstcg.com
            ("700", "Regional Labsville", "2026-05-01", 100, "open"),
        ],
    )

    deck_base = "https://www.pokemon-card.com/deck/confirm.html/deckID/"
    conn.executemany(
        "INSERT INTO placements (id, tournament_id, standing, player_name, archetype, decklist_url) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            # Missing cards (target for backfill)
            (1, "jp-1001", 1, "Alice", "Charizard ex", deck_base + "code-A"),
            (2, "jp-1001", 2, "Bob", "Dragapult ex", deck_base + "code-B"),
            # Already has cards (should be skipped)
            (3, "jp-1002", 1, "Charlie", "Charizard ex", deck_base + "code-C"),
            # Limitless missing
            (
                4,
                "https://limitlesstcg.com/tournaments/jp/5001",
                1,
                "Dora",
                "Charizard ex",
                "https://limitlesstcg.com/decks/list/5001/abc",
            ),
            # Senior division (must be excluded)
            (5, "jp-2001", 1, "Eve", "Charizard ex", deck_base + "code-E"),
            # No decklist_url (skipped by query)
            (6, "jp-1002", 2, "Frank", "Charizard ex", None),
            # Labs placements (target for the labs source backfill)
            (
                7,
                "700",
                1,
                "Gina",
                "Charizard ex",
                "https://labs.limitlesstcg.com/0070/player/11/decklist",
            ),
            (
                8,
                "700",
                2,
                "Hank",
                "Dragapult ex",
                "https://labs.limitlesstcg.com/0070/player/12/decklist",
            ),
        ],
    )

    # Placement 3 already has cards
    conn.execute(
        "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) "
        "VALUES (3, 'sv5-001', 'Charizard ex', 2)"
    )
    conn.commit()
    return conn


class TestSelectMissingDecklistPlacements:
    def test_jp_pattern_only_returns_jp(self, db_missing_decklists):
        rows = _select_missing_decklist_placements(db_missing_decklists, "jp-%", None, None)
        ids = [r["id"] for r in rows]
        assert 1 in ids
        assert 2 in ids
        assert 3 not in ids  # has decklist_cards
        assert 4 not in ids  # not jp-%
        assert 5 not in ids  # senior, excluded by open_placements view
        assert 6 not in ids  # no decklist_url

    def test_limitless_pattern(self, db_missing_decklists):
        rows = _select_missing_decklist_placements(
            db_missing_decklists, "https://limitlesstcg.com/%", None, None
        )
        ids = [r["id"] for r in rows]
        assert ids == [4]

    def test_since_filters_older(self, db_missing_decklists):
        rows = _select_missing_decklist_placements(db_missing_decklists, "jp-%", None, "2026-04-19")
        # Only jp-1001 (2026-04-15) is excluded; jp-1002 only has placement 3 (already has cards)
        ids = [r["id"] for r in rows]
        assert 1 not in ids
        assert 2 not in ids

    def test_limit_caps_results(self, db_missing_decklists):
        rows = _select_missing_decklist_placements(db_missing_decklists, "jp-%", 1, None)
        assert len(rows) == 1

    def test_max_standing_excludes_deeper_finishes(self, db_missing_decklists):
        # jp-1001 has placement 1 (standing 1) and placement 2 (standing 2).
        # max_standing=1 keeps only the top finish.
        rows = _select_missing_decklist_placements(
            db_missing_decklists, "jp-%", None, None, max_standing=1
        )
        ids = [r["id"] for r in rows]
        assert ids == [1]

    def test_max_standing_none_returns_all(self, db_missing_decklists):
        rows = _select_missing_decklist_placements(
            db_missing_decklists, "jp-%", None, None, max_standing=None
        )
        ids = sorted(r["id"] for r in rows)
        assert ids == [1, 2]

    def test_match_column_decklist_url_selects_labs(self, db_missing_decklists):
        # TPCI tournament ids are bare integers, so labs placements must be
        # matched by their decklist_url host, not by t.id.
        rows = _select_missing_decklist_placements(
            db_missing_decklists,
            "https://labs.limitlesstcg.com/%",
            None,
            None,
            match_column="p.decklist_url",
        )
        ids = sorted(r["id"] for r in rows)
        assert ids == [7, 8]

    def test_match_column_rejects_unknown_column(self, db_missing_decklists):
        with pytest.raises(ValueError):
            _select_missing_decklist_placements(
                db_missing_decklists, "%", None, None, match_column="p.player_name; DROP TABLE"
            )


class TestBackfillJp:
    def test_stores_decklists(self, db_missing_decklists, monkeypatch):
        from scraper.pokemon_jp import JPDeckCard

        fake_cards = [
            JPDeckCard(
                name_jp="リザードンex",
                count=2,
                set_code="SV5",
                card_number="001",
                category="Pokemon",
            ),
            JPDeckCard(
                name_jp="ネストボール",
                count=4,
                set_code="SV1",
                card_number="123",
                category="Trainer",
            ),
        ]

        def fake_batch(deck_entries, pool_size):
            return {code: fake_cards for code, _ in deck_entries}

        monkeypatch.setattr("cli._fetch_decklists_batch", fake_batch)

        n = _backfill_jp_decklists(db_missing_decklists, None, None, pool_size=2)
        assert n == 2  # placements 1 and 2

        for pid in (1, 2):
            count = db_missing_decklists.execute(
                "SELECT COUNT(*) FROM decklist_cards WHERE placement_id = ?", (pid,)
            ).fetchone()[0]
            assert count == 2

        # Placement 3 untouched
        existing = db_missing_decklists.execute(
            "SELECT card_id FROM decklist_cards WHERE placement_id = 3"
        ).fetchone()
        assert existing["card_id"] == "sv5-001"

    def test_max_standing_limits_backfill(self, db_missing_decklists, monkeypatch):
        from scraper.pokemon_jp import JPDeckCard

        fake_cards = [
            JPDeckCard(
                name_jp="ネストボール",
                count=4,
                set_code="SV1",
                card_number="123",
                category="Trainer",
            ),
        ]

        def fake_batch(deck_entries, pool_size):
            return {code: fake_cards for code, _ in deck_entries}

        monkeypatch.setattr("cli._fetch_decklists_batch", fake_batch)

        # jp-1001 placements: id 1 (standing 1), id 2 (standing 2). Top-1 only.
        n = _backfill_jp_decklists(db_missing_decklists, None, None, pool_size=2, max_standing=1)
        assert n == 1

        stored_2 = db_missing_decklists.execute(
            "SELECT COUNT(*) FROM decklist_cards WHERE placement_id = 2"
        ).fetchone()[0]
        assert stored_2 == 0  # standing 2 excluded by max_standing

    def test_no_missing_returns_zero(self, db_missing_decklists, monkeypatch):
        # Insert cards for every JP placement so nothing is missing
        for pid in (1, 2):
            db_missing_decklists.execute(
                "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) "
                "VALUES (?, 'x', 'X', 1)",
                (pid,),
            )
        db_missing_decklists.commit()

        called = []
        monkeypatch.setattr("cli._fetch_decklists_batch", lambda *a, **k: called.append(1) or {})
        n = _backfill_jp_decklists(db_missing_decklists, None, None, pool_size=2)
        assert n == 0
        assert called == []  # batch fetch should be skipped

    def test_empty_fetch_result_does_not_store(self, db_missing_decklists, monkeypatch):
        monkeypatch.setattr("cli._fetch_decklists_batch", lambda *a, **k: {})
        n = _backfill_jp_decklists(db_missing_decklists, None, None, pool_size=2)
        assert n == 0
        for pid in (1, 2):
            count = db_missing_decklists.execute(
                "SELECT COUNT(*) FROM decklist_cards WHERE placement_id = ?", (pid,)
            ).fetchone()[0]
            assert count == 0


class TestBackfillLimitless:
    def test_stores_decklists(self, db_missing_decklists, monkeypatch):
        from scraper.limitless import LimitlessDecklist

        fake_decklist = LimitlessDecklist(
            cards=[
                {"count": 2, "name": "Charizard ex", "card_id": "SV5-001"},
                {"count": 4, "name": "Nest Ball", "card_id": "SV1-123"},
            ]
        )

        class _StubClient:
            def fetch_decklist(self, url):
                return fake_decklist

            def close(self):
                pass

        monkeypatch.setattr("scraper.limitless.LimitlessClient", lambda: _StubClient())

        n = _backfill_limitless_decklists(db_missing_decklists, None, None)
        assert n == 1
        rows = db_missing_decklists.execute(
            "SELECT card_id, count FROM decklist_cards WHERE placement_id = 4 ORDER BY card_id"
        ).fetchall()
        assert len(rows) == 2
        assert rows[0]["card_id"] == "SV1-123"
        assert rows[0]["count"] == 4

    def test_skips_when_no_cards(self, db_missing_decklists, monkeypatch):
        class _StubClient:
            def fetch_decklist(self, url):
                return None

            def close(self):
                pass

        monkeypatch.setattr("scraper.limitless.LimitlessClient", lambda: _StubClient())
        n = _backfill_limitless_decklists(db_missing_decklists, None, None)
        assert n == 0


class TestBackfillLabs:
    def _stub(self, monkeypatch, decklist):
        class _StubClient:
            def fetch_decklist(self, url):
                return decklist

            def close(self):
                pass

        monkeypatch.setattr("scraper.labs_limitless.LabsLimitlessClient", lambda: _StubClient())

    def test_stores_decklists(self, db_missing_decklists, monkeypatch):
        from cli import _backfill_labs_decklists
        from scraper.labs_limitless import LabsDecklist

        self._stub(
            monkeypatch,
            LabsDecklist(
                cards=[
                    {
                        "count": 3,
                        "name": "Charizard ex",
                        "card_id": "SV5-001",
                        "set_code": "SV5",
                        "card_number": "001",
                    }
                ]
            ),
        )

        n = _backfill_labs_decklists(db_missing_decklists, None, None)
        assert n == 2  # labs placements 7 and 8
        for pid in (7, 8):
            count = db_missing_decklists.execute(
                "SELECT COUNT(*) FROM decklist_cards WHERE placement_id = ?", (pid,)
            ).fetchone()[0]
            assert count == 1

    def test_max_standing_bounds_depth(self, db_missing_decklists, monkeypatch):
        from cli import _backfill_labs_decklists
        from scraper.labs_limitless import LabsDecklist

        self._stub(
            monkeypatch,
            LabsDecklist(
                cards=[{"count": 1, "name": "X", "card_id": "x", "set_code": "", "card_number": ""}]
            ),
        )

        n = _backfill_labs_decklists(db_missing_decklists, None, None, max_standing=1)
        assert n == 1  # only placement 7 (standing 1)
        stored_8 = db_missing_decklists.execute(
            "SELECT COUNT(*) FROM decklist_cards WHERE placement_id = 8"
        ).fetchone()[0]
        assert stored_8 == 0

    def test_skips_when_no_cards(self, db_missing_decklists, monkeypatch):
        from cli import _backfill_labs_decklists

        self._stub(monkeypatch, None)
        n = _backfill_labs_decklists(db_missing_decklists, None, None)
        assert n == 0


class TestBackfillCli:
    def test_command_runs(self, db_missing_decklists, monkeypatch, tmp_path):
        from click.testing import CliRunner

        from cli import cli

        monkeypatch.setattr("cli._fetch_decklists_batch", lambda *a, **k: {})

        class _StubClient:
            def fetch_decklist(self, url):
                return None

            def close(self):
                pass

        monkeypatch.setattr("scraper.limitless.LimitlessClient", lambda: _StubClient())

        # Wrap connection to no-op close (CLI command closes its own conn)
        class _ConnProxy:
            def __init__(self, conn):
                self._conn = conn

            def __getattr__(self, name):
                return getattr(self._conn, name)

            def close(self):
                pass

        proxy = _ConnProxy(db_missing_decklists)

        with (
            patch("cli.get_format_connection", return_value=proxy),
            patch("cli.init_db", lambda conn: None),
        ):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["--format", "ninja-spinner", "backfill-decklists", "--source", "all"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0, result.output

    def test_source_labs_with_max_standing(self, db_missing_decklists, monkeypatch):
        from click.testing import CliRunner

        from cli import cli
        from scraper.labs_limitless import LabsDecklist

        class _StubClient:
            def fetch_decklist(self, url):
                return LabsDecklist(
                    cards=[
                        {
                            "count": 4,
                            "name": "Nest Ball",
                            "card_id": "SV1-123",
                            "set_code": "SV1",
                            "card_number": "123",
                        }
                    ]
                )

            def close(self):
                pass

        monkeypatch.setattr("scraper.labs_limitless.LabsLimitlessClient", lambda: _StubClient())

        class _ConnProxy:
            def __init__(self, conn):
                self._conn = conn

            def __getattr__(self, name):
                return getattr(self._conn, name)

            def close(self):
                pass

        proxy = _ConnProxy(db_missing_decklists)

        with (
            patch("cli.get_format_connection", return_value=proxy),
            patch("cli.init_db", lambda conn: None),
        ):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "--format",
                    "tpci-standard",
                    "backfill-decklists",
                    "--source",
                    "labs",
                    "--max-standing",
                    "1",
                ],
                catch_exceptions=False,
            )
            assert result.exit_code == 0, result.output

        # Only placement 7 (standing 1) backfilled; placement 8 (standing 2) skipped.
        assert (
            db_missing_decklists.execute(
                "SELECT COUNT(*) FROM decklist_cards WHERE placement_id = 7"
            ).fetchone()[0]
            == 1
        )
        assert (
            db_missing_decklists.execute(
                "SELECT COUNT(*) FROM decklist_cards WHERE placement_id = 8"
            ).fetchone()[0]
            == 0
        )
