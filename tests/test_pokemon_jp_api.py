"""Tests for scraper/pokemon_jp.py — store_cl_city_league_results function."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from scraper.pokemon_jp import (
        JPDeckCard,
        JPEventResult,
        JPPlacement,
        classify_jp_decklist,
        store_cl_city_league_results,
    )

    _POKEMON_JP_AVAILABLE = True
except ImportError:
    _POKEMON_JP_AVAILABLE = False

try:
    from scraper.pokemon_jp_api import PokemonJPAPIClient  # noqa: F401

    _POKEMON_JP_API_AVAILABLE = True
except ImportError:
    _POKEMON_JP_API_AVAILABLE = False


@pytest.mark.skipif(not _POKEMON_JP_AVAILABLE, reason="scraper.pokemon_jp requires 'kernel' module")
class TestStoreCLResults:
    def test_stores_placement_with_jp_event_id(self, db):
        """store_cl_city_league_results inserts tournament and placements correctly."""
        event = JPEventResult(
            event_id=12345,
            event_name="City League Sapporo",
            division="masters",
            date="2026-02-15",
            placements=[
                JPPlacement(standing=1, player_name="Yuki", region="Hokkaido"),
                JPPlacement(standing=2, player_name="Kenji", region="Tokyo"),
            ],
        )

        store_cl_city_league_results(db, event, decklists={})

        # Tournament should be stored with prefixed ID
        tournament = db.execute("SELECT * FROM tournaments WHERE id = ?", ("jp-12345",)).fetchone()
        assert tournament is not None
        assert tournament["name"] == "City League Sapporo"
        assert tournament["date"] == "2026-02-15"

        # Placements should be stored with archetype="Unknown"
        placements = db.execute(
            "SELECT * FROM placements WHERE tournament_id = ? ORDER BY standing",
            ("jp-12345",),
        ).fetchall()
        assert len(placements) == 2

        assert placements[0]["standing"] == 1
        assert placements[0]["player_name"] == "Yuki"
        assert placements[0]["archetype"] == "Unknown"

        assert placements[1]["standing"] == 2
        assert placements[1]["player_name"] == "Kenji"
        assert placements[1]["archetype"] == "Unknown"

    def test_stores_decklist_cards(self, db):
        """store_cl_city_league_results inserts decklist cards when available."""
        event = JPEventResult(
            event_id=99999,
            event_name="City League Fukuoka",
            division="masters",
            date="2026-03-10",
            placements=[
                JPPlacement(
                    standing=1,
                    player_name="Haruka",
                    region="Fukuoka",
                    deck_code="deck-abc",
                ),
                JPPlacement(
                    standing=2,
                    player_name="Satoshi",
                    region="Osaka",
                    deck_code=None,  # No deck code — no cards should be stored
                ),
            ],
        )

        cards = [
            JPDeckCard(
                name_jp="リザードンex",
                set_code="sv5",
                card_number="001",
                count=2,
                category="Pokemon",
            ),
            JPDeckCard(
                name_jp="ネストボール", set_code="sv5", card_number="", count=4, category="Trainer"
            ),
            JPDeckCard(
                name_jp="基本炎エネルギー", set_code="", card_number="", count=10, category="Energy"
            ),
        ]

        store_cl_city_league_results(db, event, decklists={"deck-abc": cards})

        # Retrieve the placement_id for standing=1
        placement = db.execute(
            "SELECT id FROM placements WHERE tournament_id = ? AND standing = 1",
            ("jp-99999",),
        ).fetchone()
        assert placement is not None
        placement_id = placement["id"]

        # Cards for placement with deck_code should be stored
        stored_cards = db.execute(
            "SELECT * FROM decklist_cards WHERE placement_id = ? ORDER BY card_id",
            (placement_id,),
        ).fetchall()
        assert len(stored_cards) == 3

        # Card with set_code + card_number -> "sv5-001"
        card_ids = {row["card_id"] for row in stored_cards}
        assert "sv5-001" in card_ids

        # Card with set_code but no card_number -> falls back to name_jp
        assert "ネストボール" in card_ids

        # Card with no set_code -> falls back to name_jp
        assert "基本炎エネルギー" in card_ids

        # Placement with no deck_code should have no cards
        placement2 = db.execute(
            "SELECT id FROM placements WHERE tournament_id = ? AND standing = 2",
            ("jp-99999",),
        ).fetchone()
        assert placement2 is not None
        cards_for_p2 = db.execute(
            "SELECT * FROM decklist_cards WHERE placement_id = ?",
            (placement2["id"],),
        ).fetchall()
        assert len(cards_for_p2) == 0

    def test_classifies_archetype_from_decklist(self, db):
        """store_cl_city_league_results classifies archetype when decklist has known cards."""
        # Seed card_mappings for JP->EN translation
        db.executemany(
            "INSERT INTO card_mappings (jp_card_id, en_card_id, card_name_jp, card_name_en, jp_set_id, en_set_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("SV5-001", "sv5-001", "リザードンex", "Charizard ex", "SV5", "sv5"),
                ("SV5-010", "sv5-010", "ヒトカゲ", "Charmander", "SV5", "sv5"),
            ],
        )
        db.commit()

        event = JPEventResult(
            event_id=77777,
            event_name="City League Test",
            division="masters",
            date="2026-03-15",
            placements=[
                JPPlacement(standing=1, player_name="Taro", region="Tokyo", deck_code="deck-zz"),
                JPPlacement(standing=2, player_name="Hanako", region="Osaka"),  # No decklist
            ],
        )

        cards = [
            JPDeckCard(
                name_jp="リザードンex",
                set_code="SV5",
                card_number="001",
                count=2,
                category="Pokemon",
            ),
            JPDeckCard(
                name_jp="ヒトカゲ", set_code="SV5", card_number="010", count=3, category="Pokemon"
            ),
            JPDeckCard(
                name_jp="基本炎エネルギー", set_code="", card_number="", count=10, category="Energy"
            ),
        ]

        store_cl_city_league_results(db, event, decklists={"deck-zz": cards})

        # Placement with decklist should be classified
        p1 = db.execute(
            "SELECT archetype FROM placements WHERE tournament_id = ? AND standing = 1",
            ("jp-77777",),
        ).fetchone()
        assert p1["archetype"] == "Charizard ex"

        # Placement without decklist stays Unknown
        p2 = db.execute(
            "SELECT archetype FROM placements WHERE tournament_id = ? AND standing = 2",
            ("jp-77777",),
        ).fetchone()
        assert p2["archetype"] == "Unknown"


@pytest.mark.skipif(not _POKEMON_JP_AVAILABLE, reason="scraper.pokemon_jp requires 'kernel' module")
class TestClassifyJPDecklist:
    def test_translates_and_classifies(self, db):
        """classify_jp_decklist translates JP names and returns archetype."""
        db.executemany(
            "INSERT INTO card_mappings (jp_card_id, en_card_id, card_name_jp, card_name_en, jp_set_id, en_set_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("SV5-001", "sv5-001", "リザードンex", "Charizard ex", "SV5", "sv5"),
            ],
        )
        db.commit()

        cards = [
            JPDeckCard(
                name_jp="リザードンex",
                set_code="SV5",
                card_number="001",
                count=2,
                category="Pokemon",
            ),
            JPDeckCard(
                name_jp="基本炎エネルギー", set_code="", card_number="", count=10, category="Energy"
            ),
        ]
        result = classify_jp_decklist(db, cards)
        assert result == "Charizard ex"

    def test_unknown_when_no_mappings(self, db):
        """classify_jp_decklist returns Unknown when cards can't be translated to known anchors."""
        cards = [
            JPDeckCard(
                name_jp="謎のポケモン",
                set_code="XX",
                card_number="001",
                count=4,
                category="Pokemon",
            ),
        ]
        result = classify_jp_decklist(db, cards)
        assert result == "Unknown"

    def test_energy_translated_via_jp_energy_map(self, db):
        """JP energy names are translated even without card_mappings entries."""
        cards = [
            JPDeckCard(name_jp="基本炎エネルギー", count=10, category="Energy"),
            JPDeckCard(name_jp="基本水エネルギー", count=6, category="Energy"),
        ]
        result = classify_jp_decklist(db, cards)
        # No Pokemon cards, so should be Unknown, but energies should translate
        assert result == "Unknown"


class TestEventTypeConfig:
    def test_all_city_league_seasons_included(self):
        """Ensure all City League seasons 1-8 are included in event types."""
        from config import POKEMON_JP_CITY_LEAGUE_EVENT_TYPES

        for season in range(1, 9):
            assert f"3:{season}" in POKEMON_JP_CITY_LEAGUE_EVENT_TYPES, (
                f"Missing City League season 3:{season}"
            )

    @pytest.mark.skipif(not _POKEMON_JP_API_AVAILABLE, reason="httpx not installed")
    def test_scraper_uses_config_event_types(self):
        """PokemonJPAPIClient should reference config for event types."""
        import inspect

        from scraper.pokemon_jp_api import PokemonJPAPIClient

        source = inspect.getsource(PokemonJPAPIClient.fetch_cl_events)
        # Should not have hardcoded event types
        assert "3:1" not in source, "Event types should come from config, not be hardcoded"
        assert "POKEMON_JP_CITY_LEAGUE_EVENT_TYPES" in source


class TestArchetypeCrossRef:
    def test_matches_by_date_and_standing(self):
        from scraper.limitless import match_archetype_labels

        limitless_data = [
            {"date": "2026-03-17", "standing": 1, "archetype": "Dragapult ex"},
            {"date": "2026-03-17", "standing": 2, "archetype": "Charizard ex"},
        ]
        jp_placements = [
            {"date": "2026-03-17", "standing": 1, "player_name": "Taro"},
            {"date": "2026-03-17", "standing": 2, "player_name": "Hanako"},
        ]
        matched = match_archetype_labels(jp_placements, limitless_data)
        assert matched[0]["archetype"] == "Dragapult ex"
        assert matched[1]["archetype"] == "Charizard ex"

    def test_unmatched_stays_unknown(self):
        from scraper.limitless import match_archetype_labels

        limitless_data = [
            {"date": "2026-03-17", "standing": 1, "archetype": "Dragapult ex"},
        ]
        jp_placements = [
            {"date": "2026-03-17", "standing": 1, "player_name": "Taro"},
            {"date": "2026-03-17", "standing": 3, "player_name": "Eve"},
        ]
        matched = match_archetype_labels(jp_placements, limitless_data)
        assert matched[0]["archetype"] == "Dragapult ex"
        assert matched[1]["archetype"] == "Unknown"

    def test_does_not_mutate_input(self):
        from scraper.limitless import match_archetype_labels

        jp = [{"date": "2026-03-17", "standing": 1, "player_name": "Taro"}]
        matched = match_archetype_labels(jp, [])
        assert "archetype" not in jp[0]  # Original not mutated
        assert matched[0]["archetype"] == "Unknown"


class TestTranslateCLDecklist:
    def test_translates_known_cards(self, db):
        """JP card names are translated to EN using card_mappings table."""
        from scraper.card_mappings import translate_decklist

        # Seed card_mappings table (conftest only seeds `cards`, not `card_mappings`)
        db.executemany(
            "INSERT INTO card_mappings (jp_card_id, en_card_id, card_name_jp, card_name_en, jp_set_id, en_set_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("SV5-001", "sv5-001", "リザードンex", "Charizard ex", "SV5", "sv5"),
                ("SV5-100", "sv5-100", "ネストボール", "Nest Ball", "SV5", "sv5"),
            ],
        )
        db.commit()

        jp_cards = [
            {"name_jp": "リザードンex", "set_code": "SV5", "count": 2},
            {"name_jp": "ネストボール", "set_code": "SV5", "count": 4},
        ]
        result = translate_decklist(db, jp_cards)
        assert result[0]["card_name_en"] == "Charizard ex"
        assert result[1]["card_name_en"] == "Nest Ball"

    def test_untranslatable_returns_none(self, db):
        """Cards not in card_mappings get card_name_en=None."""
        from scraper.card_mappings import translate_decklist

        jp_cards = [
            {"name_jp": "謎のカード", "set_code": "XX", "count": 1},
        ]
        result = translate_decklist(db, jp_cards)
        assert result[0]["card_name_en"] is None
