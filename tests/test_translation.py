"""Tests for JP-to-EN translation functions in reports/json_export.py."""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.card_stats import EN_CARD_ALIASES, build_jp_en_lookup
from db import SCHEMA
from reports.json_export import (
    _JP_RE,
    JP_CARD_NAMES,
    _build_jp_en_lookup,
    _normalize_card_name,
    _translate_all_json,
    _translate_card_names,
)

# ---------------------------------------------------------------------------
# _normalize_card_name
# ---------------------------------------------------------------------------


class TestNormalizeCardName:
    def test_known_alias_resolves(self) -> None:
        """A name present in EN_CARD_ALIASES maps to its canonical form."""
        assert _normalize_card_name("Lillie's Resolve") == "Lillie's Determination"
        assert _normalize_card_name("Power Protein") == "Premium Power Pro"

    def test_unknown_name_passes_through(self) -> None:
        """A name not in EN_CARD_ALIASES is returned unchanged."""
        assert _normalize_card_name("Nest Ball") == "Nest Ball"
        assert _normalize_card_name("Charizard ex") == "Charizard ex"

    def test_all_aliases_are_resolved(self) -> None:
        """Every key in EN_CARD_ALIASES produces its corresponding value."""
        for alias, canonical in EN_CARD_ALIASES.items():
            assert _normalize_card_name(alias) == canonical


# ---------------------------------------------------------------------------
# _JP_RE regex
# ---------------------------------------------------------------------------


class TestJpRegex:
    def test_matches_katakana(self) -> None:
        assert _JP_RE.search("リザードンex") is not None

    def test_matches_kanji(self) -> None:
        assert _JP_RE.search("謎のカード") is not None

    def test_no_match_on_english(self) -> None:
        assert _JP_RE.search("Charizard ex") is None

    def test_no_match_on_empty(self) -> None:
        assert _JP_RE.search("") is None


# ---------------------------------------------------------------------------
# _build_jp_en_lookup (thin wrapper) and build_jp_en_lookup (shared builder)
# ---------------------------------------------------------------------------


class TestBuildJpEnLookup:
    def test_cards_table_entries(self, db: sqlite3.Connection) -> None:
        """Lookup includes JP->EN pairs from the cards table."""
        lookup = _build_jp_en_lookup(db)
        assert lookup["リザードンex"] == "Charizard ex"
        assert lookup["ドラパルトex"] == "Dragapult ex"
        assert lookup["ふしぎなアメ"] == "Rare Candy"

    def test_hardcoded_fallbacks_included(self, db: sqlite3.Connection) -> None:
        """Lookup includes JP_CARD_NAMES fallback entries not in the DB."""
        lookup = _build_jp_en_lookup(db)
        # Pick a fallback entry that is NOT in the seed cards table
        assert "イーブイ" in JP_CARD_NAMES, "Test assumption: Eevee is in JP_CARD_NAMES"
        assert lookup["イーブイ"] == "Eevee"

    def test_db_overrides_fallback(self) -> None:
        """DB entries take priority over fallback dict."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT INTO cards (id, name_en, name_jp, set_code, image_url, supertype, rotation_legal) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("test-001", "DB Eevee", "イーブイ", "sv9", "https://img/test.png", "Pokemon", 1),
        )
        conn.commit()

        lookup = build_jp_en_lookup(conn, fallback={"イーブイ": "Fallback Eevee"})
        assert lookup["イーブイ"] == "DB Eevee"
        conn.close()

    def test_card_mappings_override_cards_table(self, db_integration: sqlite3.Connection) -> None:
        """card_mappings entries override cards table entries."""
        # db_integration has both cards table and card_mappings rows for リザードンex
        lookup = build_jp_en_lookup(db_integration)
        assert lookup["リザードンex"] == "Charizard ex"

    def test_missing_card_mappings_table_handled(self) -> None:
        """Gracefully handles missing card_mappings table."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        # Minimal schema: cards table only, no card_mappings
        conn.execute(
            "CREATE TABLE cards ("
            "  id TEXT PRIMARY KEY, name_en TEXT, name_jp TEXT,"
            "  set_code TEXT, image_url TEXT, supertype TEXT, rotation_legal INTEGER)"
        )
        conn.execute(
            "INSERT INTO cards (id, name_en, name_jp, set_code, image_url, supertype, rotation_legal) "
            "VALUES ('t1', 'Pikachu', 'ピカチュウ', 'sv1', 'https://img.png', 'Pokemon', 1)"
        )
        conn.commit()

        lookup = build_jp_en_lookup(conn)
        assert lookup["ピカチュウ"] == "Pikachu"
        conn.close()

    def test_empty_db_returns_fallback_only(self) -> None:
        """Empty cards table still returns fallback entries."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.commit()

        fallback = {"テスト": "Test Card"}
        lookup = build_jp_en_lookup(conn, fallback=fallback)
        assert lookup["テスト"] == "Test Card"
        conn.close()


# ---------------------------------------------------------------------------
# _translate_card_names
# ---------------------------------------------------------------------------


class TestTranslateCardNames:
    """Tests for recursive JP card name translation in data structures."""

    def setup_method(self) -> None:
        self.lookup = {
            "リザードンex": "Charizard ex",
            "ドラパルトex": "Dragapult ex",
        }

    def test_translates_card_name_key(self) -> None:
        data = {"card_name": "リザードンex", "count": 2}
        result = _translate_card_names(data, self.lookup)
        assert result["card_name"] == "Charizard ex"
        assert result["card_name_jp"] == "リザードンex"
        assert result["count"] == 2

    def test_translates_card_key(self) -> None:
        data = {"card": "ドラパルトex"}
        result = _translate_card_names(data, self.lookup)
        assert result["card"] == "Dragapult ex"
        assert result["card_jp"] == "ドラパルトex"

    def test_translates_card_a_and_card_b(self) -> None:
        data = {"card_a": "リザードンex", "card_b": "ドラパルトex"}
        result = _translate_card_names(data, self.lookup)
        assert result["card_a"] == "Charizard ex"
        assert result["card_b"] == "Dragapult ex"
        assert result["card_a_jp"] == "リザードンex"
        assert result["card_b_jp"] == "ドラパルトex"

    def test_untranslatable_jp_name_unchanged(self) -> None:
        """JP name not in lookup stays as-is, no _jp suffix key added."""
        data = {"card_name": "謎のカード"}
        result = _translate_card_names(data, self.lookup)
        assert result["card_name"] == "謎のカード"
        assert "card_name_jp" not in result

    def test_english_name_unchanged(self) -> None:
        """English card names are not touched (no JP chars detected)."""
        data = {"card_name": "Nest Ball", "count": 4}
        result = _translate_card_names(data, self.lookup)
        assert result["card_name"] == "Nest Ball"
        assert "card_name_jp" not in result

    def test_non_card_key_with_jp_value_unchanged(self) -> None:
        """Keys not in _CARD_NAME_KEYS are not translated even if value has JP chars."""
        data = {"archetype": "リザードンex", "card_name": "リザードンex"}
        result = _translate_card_names(data, self.lookup)
        assert result["archetype"] == "リザードンex"
        assert result["card_name"] == "Charizard ex"

    def test_recursive_list(self) -> None:
        data = [
            {"card_name": "リザードンex"},
            {"card_name": "ドラパルトex"},
        ]
        result = _translate_card_names(data, self.lookup)
        assert result[0]["card_name"] == "Charizard ex"
        assert result[1]["card_name"] == "Dragapult ex"

    def test_nested_dicts(self) -> None:
        data = {
            "archetype": "test",
            "cards": [{"card_name": "リザードンex", "count": 2}],
        }
        result = _translate_card_names(data, self.lookup)
        assert result["cards"][0]["card_name"] == "Charizard ex"
        assert result["cards"][0]["card_name_jp"] == "リザードンex"

    def test_non_dict_non_list_passthrough(self) -> None:
        """Scalar values pass through unchanged."""
        assert _translate_card_names("hello", self.lookup) == "hello"
        assert _translate_card_names(42, self.lookup) == 42
        assert _translate_card_names(None, self.lookup) is None


# ---------------------------------------------------------------------------
# _translate_all_json (file-level translation)
# ---------------------------------------------------------------------------


class TestTranslateAllJson:
    """Tests for the file-walking JP translation post-pass."""

    def setup_method(self) -> None:
        self.lookup = {
            "リザードンex": "Charizard ex",
            "ふしぎなアメ": "Rare Candy",
        }

    def test_translates_json_with_jp_content(self, tmp_path: Path) -> None:
        """JSON files containing JP card names get translated."""
        data = [{"card_name": "リザードンex", "count": 2}]
        json_file = tmp_path / "cards.json"
        json_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        _translate_all_json(tmp_path, self.lookup)

        result = json.loads(json_file.read_text(encoding="utf-8"))
        assert result[0]["card_name"] == "Charizard ex"
        assert result[0]["card_name_jp"] == "リザードンex"

    def test_skips_json_without_jp_content(self, tmp_path: Path) -> None:
        """JSON files with only English content are not modified."""
        data = [{"card_name": "Nest Ball", "count": 4}]
        json_file = tmp_path / "english.json"
        original = json.dumps(data, ensure_ascii=False, indent=2)
        json_file.write_text(original, encoding="utf-8")

        _translate_all_json(tmp_path, self.lookup)

        # File should not be rewritten (content unchanged)
        assert json_file.read_text(encoding="utf-8") == original

    def test_handles_nested_subdirectories(self, tmp_path: Path) -> None:
        """Recursively finds JSON in subdirectories."""
        sub = tmp_path / "deep" / "nested"
        sub.mkdir(parents=True)
        data = {"cards": [{"card_name": "ふしぎなアメ"}]}
        json_file = sub / "data.json"
        json_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        _translate_all_json(tmp_path, self.lookup)

        result = json.loads(json_file.read_text(encoding="utf-8"))
        assert result["cards"][0]["card_name"] == "Rare Candy"

    def test_ignores_non_json_files(self, tmp_path: Path) -> None:
        """Non-JSON files are not touched."""
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("リザードンex is cool", encoding="utf-8")

        _translate_all_json(tmp_path, self.lookup)

        assert txt_file.read_text(encoding="utf-8") == "リザードンex is cool"

    def test_handles_invalid_json_gracefully(self, tmp_path: Path) -> None:
        """Malformed JSON files log an error but do not raise."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{リザードンex: broken}", encoding="utf-8")

        # Should not raise
        _translate_all_json(tmp_path, self.lookup)

        # File content unchanged (write was skipped)
        assert bad_file.read_text(encoding="utf-8") == "{リザードンex: broken}"

    def test_empty_directory(self, tmp_path: Path) -> None:
        """No error on empty directory."""
        _translate_all_json(tmp_path, self.lookup)
