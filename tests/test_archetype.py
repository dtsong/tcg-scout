"""Tests for analysis/archetype.py — sprite key building and archetype normalization."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.archetype import (
    _COMPOSITE_SPRITE_FILENAMES,
    SPRITE_ARCHETYPE_MAP,
    _derive_name_from_key,
    _sprite_key_to_filenames,
    build_sprite_key,
    normalize_archetype,
)

# --- build_sprite_key ---


class TestBuildSpriteKey:
    def test_single_sprite(self):
        urls = ["https://r2.limitlesstcg.net/pokemon/gen9/charizard.png"]
        assert build_sprite_key(urls) == "charizard"

    def test_multiple_sprites_sorted(self):
        urls = [
            "https://r2.limitlesstcg.net/pokemon/gen9/pidgeot.png",
            "https://r2.limitlesstcg.net/pokemon/gen9/charizard.png",
        ]
        assert build_sprite_key(urls) == "charizard-pidgeot"

    def test_underscore_converted_to_hyphen(self):
        urls = ["https://r2.limitlesstcg.net/pokemon/gen9/Iron_Hands.png"]
        assert build_sprite_key(urls) == "iron-hands"

    def test_empty_list(self):
        assert build_sprite_key([]) == ""

    def test_no_match_url(self):
        assert build_sprite_key(["https://example.com/no-png-here"]) == ""

    def test_mixed_case(self):
        urls = ["https://r2.limitlesstcg.net/pokemon/gen9/Charizard.png"]
        assert build_sprite_key(urls) == "charizard"


# --- normalize_archetype ---


class TestNormalizeArchetype:
    def test_known_sprite_mapping(self):
        urls = ["https://r2.limitlesstcg.net/pokemon/gen9/charizard.png"]
        assert normalize_archetype(urls) == "Charizard ex"

    def test_composite_known_mapping(self):
        urls = [
            "https://r2.limitlesstcg.net/pokemon/gen9/pidgeot.png",
            "https://r2.limitlesstcg.net/pokemon/gen9/charizard.png",
        ]
        assert normalize_archetype(urls) == "Charizard ex"

    def test_auto_derived_name(self):
        # A key NOT in SPRITE_ARCHETYPE_MAP -> auto-derive
        urls = ["https://r2.limitlesstcg.net/pokemon/gen9/wobuffet.png"]
        assert normalize_archetype(urls) == "Wobuffet"

    def test_html_fallback(self):
        assert normalize_archetype([], html_archetype="  Some Deck  ") == "Some Deck"

    def test_unknown_fallback(self):
        assert normalize_archetype([]) == "Unknown"

    def test_empty_html_still_unknown(self):
        assert normalize_archetype([], html_archetype="   ") == "Unknown"


# --- _derive_name_from_key ---


class TestDeriveNameFromKey:
    def test_simple_name(self):
        assert _derive_name_from_key("charizard") == "Charizard"

    def test_hyphenated_name(self):
        assert _derive_name_from_key("iron-hands") == "Iron Hands"

    def test_mega_suffix(self):
        assert _derive_name_from_key("absol-mega") == "Mega Absol"

    def test_composite_mega(self):
        # "hariyama-lucario-mega" is in _COMPOSITE_SPRITE_FILENAMES
        result = _derive_name_from_key("hariyama-lucario-mega")
        assert "Mega Lucario" in result
        assert "Hariyama" in result

    def test_empty_key(self):
        assert _derive_name_from_key("") == ""


# --- _sprite_key_to_filenames ---


class TestSpriteKeyToFilenames:
    def test_composite_key(self):
        result = _sprite_key_to_filenames("charizard-pidgeot")
        assert result == ["charizard", "pidgeot"]

    def test_simple_key_passthrough(self):
        # A key NOT in the composite map falls back to [key]
        result = _sprite_key_to_filenames("wobuffet")
        assert result == ["wobuffet"]

    def test_hyphenated_single_entry(self):
        result = _sprite_key_to_filenames("iron-valiant")
        assert result == ["iron-valiant"]

    def test_empty_key(self):
        assert _sprite_key_to_filenames("") == []


# --- Sprite map consistency ---


class TestSpriteMapConsistency:
    """Guard against data entry errors in the manually-maintained sprite map."""

    KEY_PATTERN = re.compile(r"^[a-z0-9-]+$")

    def test_multi_sprite_composites_in_sprite_map(self):
        """Multi-sprite composite keys (2+ filenames) should have an entry in SPRITE_ARCHETYPE_MAP."""
        multi_keys = {k for k, v in _COMPOSITE_SPRITE_FILENAMES.items() if len(v) >= 2}
        missing = multi_keys - set(SPRITE_ARCHETYPE_MAP.keys())
        assert not missing, (
            f"Multi-sprite composite keys missing from SPRITE_ARCHETYPE_MAP: {missing}"
        )

    def test_all_keys_match_slug_pattern(self):
        for key in SPRITE_ARCHETYPE_MAP:
            assert self.KEY_PATTERN.match(key), f"Key does not match slug pattern: {key!r}"

    def test_no_empty_archetype_names(self):
        for key, name in SPRITE_ARCHETYPE_MAP.items():
            assert name.strip(), f"Empty archetype name for key: {key!r}"

    def test_composite_filenames_are_valid(self):
        for key, filenames in _COMPOSITE_SPRITE_FILENAMES.items():
            assert len(filenames) >= 1, f"Composite key {key!r} should have >= 1 filename"
            for fn in filenames:
                assert self.KEY_PATTERN.match(fn), (
                    f"Invalid filename {fn!r} in composite key {key!r}"
                )
