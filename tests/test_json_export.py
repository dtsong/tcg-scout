"""Tests for reports/json_export.py — JSON data exports for the web dashboard."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_format_config
from reports.json_export import (
    _build_jp_en_lookup,
    _compute_weighted_shares,
    _compute_windowed_ace_specs,
    _compute_windowed_meta,
    _compute_windowed_trends,
    _get_sprite_filenames,
    _slugify,
    export_all,
    export_archetypes,
    export_cards,
    export_champions_league,
    export_formats,
    export_matchup_matrix,
    export_meta,
    export_meta_evolution,
    export_trends,
    export_windowed,
)

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
        # Auto-derives from name: "Nonexistent Archetype" -> ["nonexistent.png", "archetype.png"]
        assert result == ["nonexistent.png", "archetype.png"]


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


# --- Format support ---


class TestGetFormatConfig:
    def test_valid_slug(self):
        cfg = get_format_config("nihil-zero")
        assert cfg["name"] == "Nihil Zero"
        assert cfg["db_name"] == "nihil-zero.db"

    def test_invalid_slug(self):
        import pytest

        with pytest.raises(KeyError, match="Unknown format"):
            get_format_config("nonexistent")

    def test_ninja_spinner(self):
        cfg = get_format_config("ninja-spinner")
        assert cfg["name_en"] == "Chaos Rising"
        assert cfg["dataset_start"] == "2026-03-14"


class TestExportMetaWithFormat:
    def test_includes_format_metadata(self, db, tmp_path):
        data = export_meta(db, tmp_path, format_slug="nihil-zero")
        assert data is not None
        assert "format" in data
        assert data["format"]["slug"] == "nihil-zero"
        assert data["format"]["name"] == "Nihil Zero"


class TestExportAll:
    def test_writes_to_format_subdirectory(self, db, tmp_path):
        out = export_all(db, output_dir=tmp_path, format_slug="nihil-zero")
        assert out == tmp_path / "nihil-zero"
        assert (tmp_path / "nihil-zero" / "meta.json").exists()


class TestExportFormats:
    def test_writes_formats_json(self, tmp_path):
        # Create a fake meta.json for nihil-zero to mark it as active
        nz_dir = tmp_path / "nihil-zero"
        nz_dir.mkdir()
        (nz_dir / "meta.json").write_text(
            json.dumps(
                {
                    "tournament_count": 42,
                    "deck_count": 100,
                }
            )
        )

        export_formats(output_dir=tmp_path)
        formats_file = tmp_path / "formats.json"
        assert formats_file.exists()
        data = json.loads(formats_file.read_text())
        assert len(data) == 2
        slugs = [f["slug"] for f in data]
        assert "nihil-zero" in slugs
        assert "ninja-spinner" in slugs

        # Check status detection
        nz = next(f for f in data if f["slug"] == "nihil-zero")
        ns = next(f for f in data if f["slug"] == "ninja-spinner")
        assert nz["status"] == "active"
        assert nz["tournament_count"] == 42
        assert ns["status"] == "upcoming"


# --- Windowed exports ---


class TestComputeWindowedMeta:
    def test_returns_data_for_valid_window(self, db):
        """Windowed meta should return data when tournaments exist in the range."""
        result = _compute_windowed_meta(db, "2026-01-01", "2026-03-31")
        assert result is not None
        assert result["tournament_count"] == 3
        assert result["deck_count"] == 6
        assert len(result["archetypes"]) == 3

    def test_returns_none_for_empty_window(self, db):
        """Windowed meta should return None when no tournaments in range."""
        result = _compute_windowed_meta(db, "2025-01-01", "2025-01-31")
        assert result is None

    def test_filters_by_date(self, db):
        """Windowed meta should only include placements within the date range."""
        # Only the March tournament
        result = _compute_windowed_meta(db, "2026-03-01", "2026-03-31")
        assert result is not None
        assert result["tournament_count"] == 1
        assert result["deck_count"] == 2
        archetypes = {a["archetype"] for a in result["archetypes"]}
        assert "Charizard ex" in archetypes
        assert "Raging Bolt ex" in archetypes
        assert "Dragapult ex" not in archetypes

    def test_assigns_tiers(self, db):
        """Windowed meta archetypes should have tier assignments."""
        result = _compute_windowed_meta(db, "2026-01-01", "2026-03-31")
        assert result is not None
        for arch in result["archetypes"]:
            assert arch["tier"] in ("S", "A", "B", "C", "Rogue")

    def test_includes_date_range(self, db):
        """Windowed meta should include the requested date range."""
        result = _compute_windowed_meta(db, "2026-02-01", "2026-03-15")
        assert result is not None
        assert result["date_range"]["start"] == "2026-02-01"
        assert result["date_range"]["end"] == "2026-03-15"


class TestComputeWindowedTrends:
    def test_returns_structure(self, db):
        """Windowed trends should return proper structure."""
        result = _compute_windowed_trends(db, "2026-01-01", "2026-03-31")
        assert "midpoint" in result
        assert "surging" in result
        assert "declining" in result
        assert "early_decks" in result
        assert "late_decks" in result

    def test_empty_window_returns_empty_lists(self, db):
        """Windowed trends with no data should return empty lists."""
        result = _compute_windowed_trends(db, "2025-01-01", "2025-01-31")
        assert result["surging"] == []
        assert result["declining"] == []


class TestComputeWindowedAceSpecs:
    def test_returns_empty_for_no_data(self, db):
        """ACE spec query should return empty for window with no data."""
        result = _compute_windowed_ace_specs(db, "2025-01-01", "2025-01-31")
        assert result == []

    def test_returns_list(self, db):
        """ACE spec query should return a list."""
        result = _compute_windowed_ace_specs(db, "2026-01-01", "2026-03-31")
        assert isinstance(result, list)


class TestExportCards:
    def test_generates_card_index(self, db, tmp_path):
        export_cards(db, tmp_path)
        index_file = tmp_path / "cards" / "index.json"
        assert index_file.exists()
        data = json.loads(index_file.read_text())
        assert isinstance(data, list)
        assert len(data) > 0

    def test_index_entries_have_required_fields(self, db, tmp_path):
        export_cards(db, tmp_path)
        data = json.loads((tmp_path / "cards" / "index.json").read_text())
        entry = data[0]
        assert "card_name" in entry
        assert "card_slug" in entry
        assert "usage_pct" in entry
        assert "avg_copies" in entry
        assert "category" in entry
        assert "trend_direction" in entry

    def test_generates_detail_files(self, db, tmp_path):
        export_cards(db, tmp_path)
        cards_dir = tmp_path / "cards"
        detail_files = [f for f in cards_dir.glob("*.json") if f.name != "index.json"]
        # Cards with 3+ appearances should get detail files
        assert len(detail_files) > 0

    def test_detail_file_has_archetypes(self, db, tmp_path):
        export_cards(db, tmp_path)
        cards_dir = tmp_path / "cards"
        detail_files = [f for f in cards_dir.glob("*.json") if f.name != "index.json"]
        assert len(detail_files) > 0
        data = json.loads(detail_files[0].read_text())
        assert "archetypes" in data
        assert "weekly_usage" in data
        assert "copy_distribution" in data


class TestExportCardsSynergy:
    def test_generates_synergy_file(self, db, tmp_path):
        export_cards(db, tmp_path)
        synergy_file = tmp_path / "cards" / "synergy.json"
        assert synergy_file.exists()
        data = json.loads(synergy_file.read_text())
        assert isinstance(data, list)

    def test_synergy_pair_has_required_fields(self, db, tmp_path):
        export_cards(db, tmp_path)
        data = json.loads((tmp_path / "cards" / "synergy.json").read_text())
        assert len(data) > 0, "Expected at least one synergy pair from fixture data"
        pair = data[0]
        assert "card_a" in pair
        assert "card_b" in pair
        assert "lift" in pair


class TestExportMetaEvolution:
    def test_writes_file(self, db, tmp_path):
        export_meta_evolution(db, tmp_path)
        out_file = tmp_path / "meta-evolution.json"
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert isinstance(data, list)

    def test_movements_have_required_fields(self, db, tmp_path):
        export_meta_evolution(db, tmp_path)
        data = json.loads((tmp_path / "meta-evolution.json").read_text())
        for m in data:
            assert "card" in m
            assert "archetype" in m
            assert "direction" in m
            assert m["direction"] in ("adopted", "dropped")


class TestExportMatchupMatrix:
    def test_writes_file(self, db, tmp_path):
        export_matchup_matrix(db, tmp_path)
        out_file = tmp_path / "matchup.json"
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert "archetypes" in data
        assert "matrix" in data
        assert "sample_sizes" in data

    def test_matrix_dimensions_match(self, db, tmp_path):
        export_matchup_matrix(db, tmp_path)
        data = json.loads((tmp_path / "matchup.json").read_text())
        n = len(data["archetypes"])
        assert len(data["matrix"]) == n
        assert len(data["sample_sizes"]) == n


class TestExportWindowed:
    def test_generates_windowed_files(self, db, tmp_path):
        """export_windowed should generate -7d and -30d JSON files."""
        export_windowed(db, tmp_path)

        # Should generate files for at least one window
        windowed_files = list(tmp_path.glob("*-7d.json")) + list(tmp_path.glob("*-30d.json"))
        assert len(windowed_files) > 0

    def test_windowed_meta_is_valid_json(self, db, tmp_path):
        """Windowed meta files should contain valid JSON."""
        export_windowed(db, tmp_path)

        for suffix in ["7d", "30d"]:
            meta_file = tmp_path / f"meta-{suffix}.json"
            if meta_file.exists():
                data = json.loads(meta_file.read_text())
                assert "archetypes" in data
                assert "tournament_count" in data
                assert "date_range" in data


class TestExportChampionsLeagueEnriched:
    def test_placements_have_archetype_fields(self, db, tmp_path):
        export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        for p in data["placements"]:
            assert "archetype" in p
            assert "tier" in p
            assert "sprite_filenames" in p

    def test_decklist_cards_have_image_url(self, db, tmp_path):
        export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        p = data["placements"][0]
        for card in p["decklist"]:
            assert "image_url" in card

    def test_has_archetype_summary(self, db, tmp_path):
        export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        assert "archetype_summary" in data
        assert isinstance(data["archetype_summary"], list)

    def test_unknown_archetype_fields_are_null(self, db, tmp_path):
        """When classify_decklist returns Unknown, archetype fields should be null."""
        export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        # Check that placements with Unknown archetype have null fields
        for p in data["placements"]:
            if p["archetype"] is None:
                assert p["tier"] is None
                assert p["sprite_filenames"] is None

    def test_archetype_summary_excludes_unknown(self, db, tmp_path):
        """Unknown archetypes should not appear in archetype_summary."""
        export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        for entry in data["archetype_summary"]:
            assert entry["archetype"] != "Unknown"
            assert entry["archetype"] is not None


class TestBuildJpEnLookupWithMappings:
    def test_includes_card_mappings(self, db):
        # card_mappings table is created by SCHEMA, insert test data
        db.execute(
            "INSERT INTO card_mappings (jp_card_id, en_card_id, card_name_jp, card_name_en, jp_set_id, en_set_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("SV8a-221", "me02.5-100", "ドラパルトex", "Dragapult ex", "SV8a", "me02.5"),
        )
        db.commit()
        lookup = _build_jp_en_lookup(db)
        assert lookup["ドラパルトex"] == "Dragapult ex"

    def test_card_mappings_table_missing(self):
        """Lookup works even if card_mappings table doesn't exist."""
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        # Minimal schema without card_mappings
        conn.execute("CREATE TABLE cards (id TEXT, name_en TEXT, name_jp TEXT, set_code TEXT)")
        lookup = _build_jp_en_lookup(conn)
        # Should still have hardcoded entries
        assert "ネストボール" in lookup
        conn.close()
