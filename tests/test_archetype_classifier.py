"""Tests for analysis/archetype_classifier.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.archetype_classifier import classify_decklist


class TestClassifyDecklist:
    def test_charizard_pidgeot(self):
        cards = [
            {"card_name": "Charizard ex", "count": 2, "category": "Pokemon"},
            {"card_name": "Pidgeot ex", "count": 2, "category": "Pokemon"},
            {"card_name": "Charmander", "count": 3, "category": "Pokemon"},
            {"card_name": "Rare Candy", "count": 4, "category": "Trainer"},
        ]
        assert classify_decklist(cards) == "Charizard ex"

    def test_dragapult_dusknoir(self):
        cards = [
            {"card_name": "Dragapult ex", "count": 3, "category": "Pokemon"},
            {"card_name": "Dusknoir", "count": 2, "category": "Pokemon"},
            {"card_name": "Dreepy", "count": 4, "category": "Pokemon"},
        ]
        assert classify_decklist(cards) == "Dragapult Dusknoir"

    def test_single_anchor(self):
        cards = [
            {"card_name": "Gardevoir ex", "count": 3, "category": "Pokemon"},
            {"card_name": "Ralts", "count": 4, "category": "Pokemon"},
            {"card_name": "Kirlia", "count": 3, "category": "Pokemon"},
        ]
        assert classify_decklist(cards) == "Gardevoir ex"

    def test_unknown_deck(self):
        cards = [
            {"card_name": "Bidoof", "count": 4, "category": "Pokemon"},
            {"card_name": "Nest Ball", "count": 4, "category": "Trainer"},
        ]
        assert classify_decklist(cards) == "Unknown"

    def test_mega_archetype(self):
        cards = [
            {"card_name": "Lucario ex", "count": 3, "category": "Pokemon"},
            {"card_name": "Solrock", "count": 2, "category": "Pokemon"},
        ]
        assert classify_decklist(cards) == "Mega Lucario Solrock"

    def test_trainers_ignored(self):
        """Only Pokemon cards are considered for classification."""
        cards = [
            {"card_name": "Charizard ex", "count": 4, "category": "Trainer"},
            {"card_name": "Nest Ball", "count": 4, "category": "Trainer"},
        ]
        assert classify_decklist(cards) == "Unknown"

    def test_empty_list(self):
        assert classify_decklist([]) == "Unknown"


class TestClassifyFromDecklist:
    def test_content_based_takes_priority(self):
        from analysis.archetype import classify_from_decklist
        cards = [
            {"card_name": "Charizard ex", "count": 2, "category": "Pokemon"},
            {"card_name": "Pidgeot ex", "count": 2, "category": "Pokemon"},
        ]
        assert classify_from_decklist(cards) == "Charizard ex"

    def test_falls_back_to_unknown(self):
        from analysis.archetype import classify_from_decklist
        cards = [
            {"card_name": "Bidoof", "count": 4, "category": "Pokemon"},
        ]
        assert classify_from_decklist(cards) == "Unknown"
