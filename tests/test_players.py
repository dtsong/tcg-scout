"""Tests for player intelligence features."""

import sqlite3

import pytest

from analysis.players import (
    create_player,
    get_player_profile,
    link_alias,
    link_placements_by_alias,
    list_top_performers,
)


@pytest.fixture()
def db_players() -> sqlite3.Connection:
    """In-memory database with player-relevant seed data.

    Seed data:
    - 3 open tournaments across different dates
    - 8 placements: Alice appears in 3 tournaments, Bob in 2, others once
    - Alice plays Charizard ex consistently (loyal player)
    - Bob switches between Dragapult ex and Charizard ex (meta reader)
    """
    from db import SCHEMA

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)

    conn.executemany(
        "INSERT INTO tournaments (id, name, date, player_count, division) VALUES (?, ?, ?, ?, ?)",
        [
            ("t1", "City League Osaka", "2026-02-01", 64, "open"),
            ("t2", "City League Tokyo", "2026-02-15", 64, "open"),
            ("t3", "City League Nagoya", "2026-03-01", 64, "open"),
        ],
    )

    conn.executemany(
        "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            # Alice: 3 tournaments, consistent Charizard player
            (1, "t1", 1, "Alice", "Charizard ex"),
            (2, "t2", 4, "Alice", "Charizard ex"),
            (3, "t3", 2, "Alice", "Charizard ex"),
            # Bob: 2 tournaments, switches archetypes
            (4, "t1", 2, "Bob", "Dragapult ex"),
            (5, "t2", 8, "Bob", "Charizard ex"),
            # One-time appearances
            (6, "t1", 8, "Charlie", "Raging Bolt ex"),
            (7, "t2", 16, "Diana", "Gardevoir ex"),
            (8, "t3", 9, "Eve", "Dragapult ex"),
        ],
    )

    conn.commit()
    yield conn
    conn.close()


class TestListTopPerformers:
    def test_returns_players_above_min_appearances(self, db_players):
        results = list_top_performers(db_players, min_appearances=2)
        names = [r.player_name for r in results]
        assert "Alice" in names
        assert "Bob" in names
        # One-time players excluded
        assert "Charlie" not in names
        assert "Diana" not in names

    def test_alice_ranked_above_bob(self, db_players):
        results = list_top_performers(db_players, min_appearances=2)
        names = [r.player_name for r in results]
        assert names.index("Alice") < names.index("Bob")

    def test_alice_has_correct_stats(self, db_players):
        results = list_top_performers(db_players, min_appearances=2)
        alice = next(r for r in results if r.player_name == "Alice")
        assert alice.tournament_count == 3
        assert alice.best_placement == 1
        assert alice.archetypes == ["Charizard ex"]

    def test_bob_has_multiple_archetypes(self, db_players):
        results = list_top_performers(db_players, min_appearances=2)
        bob = next(r for r in results if r.player_name == "Bob")
        assert bob.tournament_count == 2
        assert set(bob.archetypes) == {"Dragapult ex", "Charizard ex"}

    def test_min_appearances_filters_correctly(self, db_players):
        results = list_top_performers(db_players, min_appearances=3)
        names = [r.player_name for r in results]
        assert names == ["Alice"]  # Only Alice has 3+ appearances

    def test_limit_respected(self, db_players):
        results = list_top_performers(db_players, min_appearances=1, limit=3)
        assert len(results) <= 3

    def test_empty_database(self, db_players):
        db_players.execute("DELETE FROM placements")
        db_players.commit()
        results = list_top_performers(db_players)
        assert results == []

    def test_weighted_score_uses_placement_weights(self, db_players):
        results = list_top_performers(db_players, min_appearances=2)
        alice = next(r for r in results if r.player_name == "Alice")
        # Alice: 1st (3.0) + 4th (2.0) + 2nd (2.5) = 7.5
        assert alice.weighted_score == 7.5


class TestCreatePlayer:
    def test_creates_player(self, db_players):
        player_id = create_player(db_players, "Taro Yamada")
        assert player_id is not None
        row = db_players.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
        assert row["display_name"] == "Taro Yamada"
        assert row["country"] == "JP"

    def test_creates_with_options(self, db_players):
        player_id = create_player(
            db_players, "John Smith", country="US", notes="Top NA player"
        )
        row = db_players.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
        assert row["country"] == "US"
        assert row["notes"] == "Top NA player"


class TestLinkAlias:
    def test_links_alias_to_player(self, db_players):
        player_id = create_player(db_players, "Alice Player")
        link_alias(db_players, "Alice", player_id, source="limitless")

        row = db_players.execute(
            "SELECT * FROM player_aliases WHERE alias = 'Alice'"
        ).fetchone()
        assert row["player_id"] == player_id
        assert row["source"] == "limitless"

    def test_upserts_on_duplicate(self, db_players):
        p1 = create_player(db_players, "Player 1")
        p2 = create_player(db_players, "Player 2")
        link_alias(db_players, "SomeName", p1, source="limitless")
        link_alias(db_players, "SomeName", p2, source="limitless")  # Should replace

        row = db_players.execute(
            "SELECT * FROM player_aliases WHERE alias = 'SomeName' AND source = 'limitless'"
        ).fetchone()
        assert row["player_id"] == p2


class TestLinkPlacementsByAlias:
    def test_links_matching_placements(self, db_players):
        player_id = create_player(db_players, "Alice Player")
        linked = link_placements_by_alias(db_players, player_id, "Alice")
        assert linked == 3  # Alice has 3 placements

        bridge_rows = db_players.execute(
            "SELECT * FROM placement_players WHERE player_id = ?", (player_id,)
        ).fetchall()
        assert len(bridge_rows) == 3

    def test_confidence_stored(self, db_players):
        player_id = create_player(db_players, "Bob Player")
        link_placements_by_alias(db_players, player_id, "Bob", confidence=0.8)

        row = db_players.execute(
            "SELECT confidence FROM placement_players WHERE player_id = ?", (player_id,)
        ).fetchone()
        assert row["confidence"] == 0.8

    def test_no_match_returns_zero(self, db_players):
        player_id = create_player(db_players, "Nobody")
        linked = link_placements_by_alias(db_players, player_id, "NonexistentPlayer")
        assert linked == 0


class TestGetPlayerProfile:
    def test_returns_none_for_missing_player(self, db_players):
        assert get_player_profile(db_players, 999) is None

    def test_returns_profile_with_placements(self, db_players):
        player_id = create_player(db_players, "Alice Player")
        link_alias(db_players, "Alice", player_id, source="limitless")
        link_placements_by_alias(db_players, player_id, "Alice")

        profile = get_player_profile(db_players, player_id)
        assert profile is not None
        assert profile.display_name == "Alice Player"
        assert profile.tournament_count == 3
        assert len(profile.placements) == 3
        assert len(profile.deck_timeline) == 3
        assert profile.weighted_score == 7.5  # 3.0 + 2.0 + 2.5

    def test_deck_timeline_ordered_by_date_desc(self, db_players):
        player_id = create_player(db_players, "Alice Player")
        link_alias(db_players, "Alice", player_id)
        link_placements_by_alias(db_players, player_id, "Alice")

        profile = get_player_profile(db_players, player_id)
        dates = [e.date for e in profile.deck_timeline]
        assert dates == sorted(dates, reverse=True)

    def test_aliases_included(self, db_players):
        player_id = create_player(db_players, "Alice Player")
        link_alias(db_players, "Alice", player_id, source="limitless")
        link_alias(db_players, "アリス", player_id, source="pokemon_jp")

        profile = get_player_profile(db_players, player_id)
        assert set(profile.aliases) == {"Alice", "アリス"}

    def test_empty_profile_for_unlinked_player(self, db_players):
        player_id = create_player(db_players, "New Player")
        profile = get_player_profile(db_players, player_id)
        assert profile is not None
        assert profile.tournament_count == 0
        assert profile.placements == []
        assert profile.weighted_score == 0.0
