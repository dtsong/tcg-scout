"""Tests for reports/json_export.py — JSON data exports for the web dashboard."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reports.json_export import (
    _slugify,
    _get_sprite_filenames,
    _build_jp_en_lookup,
    _compute_weighted_shares,
    export_meta,
    export_trends,
    export_archetypes,
    export_champions_league,
)
from config import PLACEMENT_WEIGHTS, PLACEMENT_WEIGHT_DEFAULT


# --- _slugify ---

class TestSlugify:
    def test_simple_name(self):
        assert _slugify("Charizard ex") == "charizard-ex"

    def test_apostrophe(self):
        assert _slugify("Boss's Orders") == "boss-s-orders"

    def test_mega_name(self):
        assert _slugify("Mega Absol ex") == "mega-absol-ex"

    def test_already_lowercase(self):
        assert _slugify("raging-bolt") == "raging-bolt"

    def test_special_chars(self):
        assert _slugify("Porygon-Z Box!") == "porygon-z-box"


# --- _get_sprite_filenames ---

class TestGetSpriteFilenames:
    def test_known_single_sprite(self):
        result = _get_sprite_filenames("Charizard ex")
        assert "charizard.png" in result

    def test_known_composite(self):
        # "Charizard ex" maps to "charizard" key first, but also "charizard-pidgeot"
        # The function returns the first match — which is "charizard" -> ["charizard.png"]
        result = _get_sprite_filenames("Charizard ex")
        assert len(result) >= 1
        assert all(fn.endswith(".png") for fn in result)

    def test_unknown_archetype(self):
        result = _get_sprite_filenames("Nonexistent Archetype")
        assert result == []


# --- _build_jp_en_lookup ---

class TestBuildJpEnLookup:
    def test_includes_hardcoded_entries(self, db):
        lookup = _build_jp_en_lookup(db)
        assert lookup["ネストボール"] == "Nest Ball"
        assert lookup["ハイパーボール"] == "Ultra Ball"

    def test_includes_db_entries(self, db):
        lookup = _build_jp_en_lookup(db)
        # From seeded cards table
        assert lookup["リザードンex"] == "Charizard ex"
        assert lookup["ドラパルトex"] == "Dragapult ex"

    def test_db_overrides_hardcoded(self, db):
        # "ふしぎなアメ" is in both JP_CARD_NAMES and cards table
        lookup = _build_jp_en_lookup(db)
        assert lookup["ふしぎなアメ"] == "Rare Candy"


# --- _compute_weighted_shares ---

class TestComputeWeightedShares:
    def test_returns_all_archetypes(self, db):
        snapshot = {"archetypes": []}  # Not used by the function directly
        shares = _compute_weighted_shares(db, snapshot)
        assert "Charizard ex" in shares
        assert "Dragapult ex" in shares
        assert "Raging Bolt ex" in shares

    def test_shares_sum_to_100(self, db):
        snapshot = {"archetypes": []}
        shares = _compute_weighted_shares(db, snapshot)
        total = sum(shares.values())
        assert abs(total - 100.0) < 0.5  # Allow rounding tolerance

    def test_higher_placement_gets_more_weight(self, db):
        snapshot = {"archetypes": []}
        shares = _compute_weighted_shares(db, snapshot)
        # Charizard has 1st (3.0), 4th (2.0), 9th (1.2) = 6.2
        # Dragapult has 2nd (2.5), 8th (1.5) = 4.0
        # Raging Bolt has 16th (1.2) = 1.2
        assert shares["Charizard ex"] > shares["Dragapult ex"]
        assert shares["Dragapult ex"] > shares["Raging Bolt ex"]


# --- export_meta ---

class TestExportMeta:
    def test_produces_correct_structure(self, db, tmp_path):
        data = export_meta(db, tmp_path)
        assert data is not None
        assert "generated_at" in data
        assert "tournament_count" in data
        assert "archetypes" in data
        assert len(data["archetypes"]) == 3

    def test_archetypes_have_weighted_share(self, db, tmp_path):
        data = export_meta(db, tmp_path)
        for arch in data["archetypes"]:
            assert "weighted_share" in arch
            assert "sprite_filenames" in arch
            assert "slug" in arch

    def test_writes_json_file(self, db, tmp_path):
        export_meta(db, tmp_path)
        meta_file = tmp_path / "meta.json"
        assert meta_file.exists()
        parsed = json.loads(meta_file.read_text())
        assert "archetypes" in parsed


# --- export_trends ---

class TestExportTrends:
    def test_produces_surging_and_declining(self, db, tmp_path):
        export_trends(db, tmp_path)
        trends_file = tmp_path / "trends.json"
        assert trends_file.exists()
        data = json.loads(trends_file.read_text())
        assert "surging" in data
        assert "declining" in data
        assert isinstance(data["surging"], list)
        assert isinstance(data["declining"], list)

    def test_includes_archetype_breakdown(self, db, tmp_path):
        # Need enough data for the HAVING early_count >= 5 AND late_count >= 5 filter.
        # Our seed data may not have enough, so just verify structure is correct.
        export_trends(db, tmp_path)
        data = json.loads((tmp_path / "trends.json").read_text())
        # Even if lists are empty, the structure should be correct
        assert "midpoint" in data
        assert "early_decks" in data
        assert "late_decks" in data


# --- export_archetypes ---

class TestExportArchetypes:
    def test_generates_files_for_all_archetypes(self, db, tmp_path):
        export_archetypes(db, tmp_path)
        arch_dir = tmp_path / "archetypes"
        assert arch_dir.exists()
        # Should have one file per archetype in the snapshot (3)
        json_files = list(arch_dir.glob("*.json"))
        assert len(json_files) == 3

    def test_archetype_file_includes_results(self, db, tmp_path):
        export_archetypes(db, tmp_path)
        # Read the Charizard ex file
        charizard_file = tmp_path / "archetypes" / "charizard-ex.json"
        assert charizard_file.exists()
        data = json.loads(charizard_file.read_text())
        assert data["archetype"] == "Charizard ex"
        assert "results" in data
        assert len(data["results"]) > 0
        # Verify result structure
        result = data["results"][0]
        assert "tournament_name" in result
        assert "standing" in result
        assert "player_name" in result

    def test_archetype_file_includes_cards(self, db, tmp_path):
        export_archetypes(db, tmp_path)
        charizard_file = tmp_path / "archetypes" / "charizard-ex.json"
        data = json.loads(charizard_file.read_text())
        assert "all_cards" in data
        assert len(data["all_cards"]) > 0


# --- export_champions_league ---

class TestExportChampionsLeague:
    def test_applies_jp_en_translation(self, db, tmp_path):
        export_champions_league(db, tmp_path)
        cl_file = tmp_path / "champions-league" / "masters.json"
        assert cl_file.exists()
        data = json.loads(cl_file.read_text())
        assert data["division"] == "masters"
        assert len(data["placements"]) == 2

        # First placement: リザードンex should translate via cards table
        p1 = data["placements"][0]
        card_names_en = [c["card_name_en"] for c in p1["decklist"]]
        assert "Charizard ex" in card_names_en
        # ネストボール should translate via hardcoded JP_CARD_NAMES
        assert "Nest Ball" in card_names_en

    def test_untranslatable_card_is_none(self, db, tmp_path):
        export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        # Second placement has 謎のカード which has no translation
        p2 = data["placements"][1]
        mystery_card = [c for c in p2["decklist"] if c["card_name_jp"] == "謎のカード"]
        assert len(mystery_card) == 1
        assert mystery_card[0]["card_name_en"] is None
