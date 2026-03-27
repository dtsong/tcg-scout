"""Tests for analysis/archetype.py — sprite key building and archetype normalization."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.archetype import (
    build_sprite_key,
    normalize_archetype,
)

# --- build_sprite_key ---


class TestBuildSpriteKey:
    def test_single_sprite(self):
        urls = ["https://r2.limitlesstcg.net/pokemon/gen9/dragapult.png"]
        assert build_sprite_key(urls) == "dragapult"

    def test_multiple_sorted(self):
        urls = [
            "https://r2.limitlesstcg.net/pokemon/gen9/pidgeot.png",
            "https://r2.limitlesstcg.net/pokemon/gen9/charizard.png",
        ]
        assert build_sprite_key(urls) == "charizard-pidgeot"

    def test_empty(self):
        assert build_sprite_key([]) == ""


# --- normalize_archetype ---


class TestNormalizeArchetype:
    def test_single_sprite(self):
        urls = ["https://r2.limitlesstcg.net/pokemon/gen9/dragapult.png"]
        assert normalize_archetype(urls) == "Dragapult"

    def test_two_sprites_alphabetical(self):
        urls = [
            "https://r2.limitlesstcg.net/pokemon/gen9/dusknoir.png",
            "https://r2.limitlesstcg.net/pokemon/gen9/dragapult.png",
        ]
        assert normalize_archetype(urls) == "Dragapult / Dusknoir"

    def test_mega_sprite(self):
        urls = ["https://r2.limitlesstcg.net/pokemon/gen9/lucario-mega.png"]
        assert normalize_archetype(urls) == "Lucario-Mega"

    def test_mega_combo(self):
        urls = [
            "https://r2.limitlesstcg.net/pokemon/gen9/hariyama.png",
            "https://r2.limitlesstcg.net/pokemon/gen9/lucario-mega.png",
        ]
        assert normalize_archetype(urls) == "Hariyama / Lucario-Mega"

    def test_double_mega(self):
        urls = [
            "https://r2.limitlesstcg.net/pokemon/gen9/starmie-mega.png",
            "https://r2.limitlesstcg.net/pokemon/gen9/froslass-mega.png",
        ]
        assert normalize_archetype(urls) == "Froslass-Mega / Starmie-Mega"

    def test_hyphenated_pokemon(self):
        urls = ["https://r2.limitlesstcg.net/pokemon/gen9/raging-bolt.png"]
        assert normalize_archetype(urls) == "Raging-Bolt"

    def test_hyphenated_combo(self):
        urls = [
            "https://r2.limitlesstcg.net/pokemon/gen9/ogerpon.png",
            "https://r2.limitlesstcg.net/pokemon/gen9/raging-bolt.png",
        ]
        assert normalize_archetype(urls) == "Ogerpon / Raging-Bolt"

    def test_underscore_in_url(self):
        urls = ["https://r2.limitlesstcg.net/pokemon/gen9/Iron_Hands.png"]
        assert normalize_archetype(urls) == "Iron-Hands"

    def test_html_fallback(self):
        assert normalize_archetype([], html_archetype="Custom Deck") == "Custom Deck"

    def test_unknown_fallback(self):
        assert normalize_archetype([]) == "Unknown"

    def test_empty_urls_with_html(self):
        assert normalize_archetype([], html_archetype="  Rogue  ") == "Rogue"
