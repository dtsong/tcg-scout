"""Tests for reports/json_export.py — JSON data exports for the web dashboard."""

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_format_config
from reports.json_export import (
    _build_jp_en_lookup,
    _compute_card_stats_for_ids,
    _compute_weighted_shares,
    _compute_windowed_ace_specs,
    _compute_windowed_meta,
    _compute_windowed_trends,
    _compute_windowed_winning_edge,
    _detect_variants,
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

    def test_returns_cached_values_when_available(self, db):
        snapshot = {
            "archetypes": [
                {"archetype": "Charizard ex", "weighted_share": 55.0},
                {"archetype": "Dragapult ex", "weighted_share": 35.0},
                {"archetype": "Raging Bolt ex", "weighted_share": 10.0},
            ]
        }
        shares = _compute_weighted_shares(db, snapshot)
        assert shares == {"Charizard ex": 55.0, "Dragapult ex": 35.0, "Raging Bolt ex": 10.0}

    def test_falls_back_when_weighted_share_is_none(self, db):
        snapshot = {
            "archetypes": [
                {"archetype": "Charizard ex", "weighted_share": None},
                {"archetype": "Dragapult ex", "weighted_share": None},
            ]
        }
        shares = _compute_weighted_shares(db, snapshot)
        # Should fall back to computation — all 3 archetypes present
        assert "Charizard ex" in shares
        assert "Raging Bolt ex" in shares

    def test_falls_back_when_weighted_share_is_zero(self, db):
        snapshot = {
            "archetypes": [
                {"archetype": "Charizard ex", "weighted_share": 0.0},
                {"archetype": "Dragapult ex", "weighted_share": 0.0},
                {"archetype": "Raging Bolt ex", "weighted_share": 0.0},
            ]
        }
        shares = _compute_weighted_shares(db, snapshot)
        # Should fall back to computation — all 3 archetypes with non-zero values
        assert "Charizard ex" in shares
        assert all(v > 0 for v in shares.values())
        assert abs(sum(shares.values()) - 100.0) < 0.5

    def test_uses_cache_with_mixed_zero_and_nonzero(self, db):
        snapshot = {
            "archetypes": [
                {"archetype": "Charizard ex", "weighted_share": 45.0},
                {"archetype": "Dragapult ex", "weighted_share": 0.0},
                {"archetype": "Raging Bolt ex", "weighted_share": 55.0},
            ]
        }
        shares = _compute_weighted_shares(db, snapshot)
        # Cache path taken; zero-share archetype excluded
        assert shares == {"Charizard ex": 45.0, "Raging Bolt ex": 55.0}
        assert "Dragapult ex" not in shares

    def test_falls_back_when_weighted_share_key_missing(self, db):
        snapshot = {
            "archetypes": [
                {"archetype": "Charizard ex"},
            ]
        }
        shares = _compute_weighted_shares(db, snapshot)
        # Should fall back gracefully
        assert "Charizard ex" in shares
        assert abs(sum(shares.values()) - 100.0) < 0.5


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
        assert "tournament_url" in result
        assert "standing" in result
        assert "player_name" in result

    def test_archetype_results_include_tournament_url(self, db, tmp_path):
        export_archetypes(db, tmp_path)
        charizard_file = tmp_path / "archetypes" / "charizard-ex.json"
        data = json.loads(charizard_file.read_text())
        for result in data["results"]:
            assert "tournament_url" in result
            assert result["tournament_url"] in ("t1", "t2", "t3")

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
        assert len(data["placements"]) == 3

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
        assert cfg["db_name"] == "scout.db"

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
        out, _skipped = export_all(db, output_dir=tmp_path, format_slug="nihil-zero")
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
        assert nz["status"] == "frozen"  # dataset_end is in the past
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
        assert isinstance(data, dict)
        assert "highlights" in data
        assert "movements" in data

    def test_movements_have_required_fields(self, db, tmp_path):
        export_meta_evolution(db, tmp_path)
        data = json.loads((tmp_path / "meta-evolution.json").read_text())
        for m in data["movements"]:
            assert "card" in m
            assert "archetype" in m
            assert "archetype_slug" in m
            assert "deck_count" in m
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
        # Verify that translated cards actually get their image URLs populated
        charizard = next(c for c in p["decklist"] if c["card_name_en"] == "Charizard ex")
        assert charizard["image_url"] == "https://images.pokemontcg.io/sv5/001.png"

    def test_has_archetype_summary(self, db, tmp_path):
        export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        assert "archetype_summary" in data
        assert isinstance(data["archetype_summary"], list)

    def test_unknown_archetype_fields_are_null(self, db, tmp_path):
        """Placement with only untranslatable trainers should have null archetype fields."""
        export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        # Jiro (standing 3) has only untranslatable trainer cards
        jiro = next(p for p in data["placements"] if p["standing"] == 3)
        assert jiro["archetype"] is None
        assert jiro["tier"] is None
        assert jiro["sprite_filenames"] is None

    def test_archetype_summary_excludes_unknown(self, db, tmp_path):
        """Unknown archetypes should not appear in archetype_summary."""
        export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        archetype_names = [entry["archetype"] for entry in data["archetype_summary"]]
        assert "Unknown" not in archetype_names
        # Known archetypes should still be present
        assert len(archetype_names) > 0

    def test_known_placement_has_correct_archetype(self, db, tmp_path):
        """Placement with translatable Pokemon should classify to the correct archetype."""
        export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        taro = next(p for p in data["placements"] if p["standing"] == 1)
        assert taro["archetype"] == "Charizard ex"

    def test_archetype_summary_has_required_fields(self, db, tmp_path):
        """Each summary entry should have archetype, count, and sprite_filenames."""
        export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        for entry in data["archetype_summary"]:
            assert isinstance(entry["archetype"], str)
            assert isinstance(entry["count"], int)
            assert entry["count"] > 0
            assert isinstance(entry["sprite_filenames"], list)

    def test_known_archetype_has_tier_value(self, db, tmp_path):
        """When a placement has a known archetype, tier should be the actual tier string."""
        export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        # Ensure at least one placement has a non-null archetype (prevents vacuous pass)
        known = [p for p in data["placements"] if p["archetype"] is not None]
        assert len(known) > 0, "Expected at least one classified placement"
        for p in known:
            assert p["tier"] is not None
            assert p["tier"] in ("S", "A", "B", "C", "Rogue")

    def test_archetype_summary_sorted_by_count_desc(self, db, tmp_path):
        """Archetype summary should be sorted by count descending."""
        export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        summary = data["archetype_summary"]
        if len(summary) > 1:
            counts = [e["count"] for e in summary]
            assert counts == sorted(counts, reverse=True)


class TestExportChampionsLeagueClassifyError:
    def test_classify_exception_produces_null_archetype(self, db, tmp_path):
        """When classify_decklist raises ValueError, placement should have null archetype fields."""
        with patch(
            "reports.json_export.classify_decklist",
            side_effect=ValueError("classifier broke"),
        ):
            export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        # All placements should still be exported (none dropped)
        assert len(data["placements"]) == 3
        # All should have null archetype since classifier always fails
        for p in data["placements"]:
            if p["standing"] != 3:  # standing 3 (Jiro) has no translatable cards anyway
                assert p["archetype"] is None
                assert p["tier"] is None
                assert p["sprite_filenames"] is None

    def test_classify_exception_does_not_abort_export(self, db, tmp_path):
        """Export should complete even when classifier raises for some placements."""
        call_count = [0]

        def flaky_classify(cards):
            call_count[0] += 1
            if call_count[0] == 1:
                raise KeyError("missing key")
            return "Charizard ex"

        with patch("reports.json_export.classify_decklist", side_effect=flaky_classify):
            export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        assert len(data["placements"]) == 3


class TestExportChampionsLeagueCategorySanitization:
    def test_unexpected_category_defaults_to_trainer(self, db, tmp_path):
        """Cards with non-standard category values should be exported as 'Trainer'."""
        # Insert a card with a Japanese category string
        db.execute(
            "INSERT INTO cl_decklist_cards (placement_id, card_name_jp, card_name_en, count, category) "
            "VALUES (?, ?, ?, ?, ?)",
            (101, "テストカード", None, 1, "アイテム"),
        )
        db.commit()
        export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        taro = next(p for p in data["placements"] if p["standing"] == 1)
        weird_card = next(c for c in taro["decklist"] if c["card_name_jp"] == "テストカード")
        assert weird_card["category"] == "Trainer"

    def test_null_category_defaults_to_trainer(self, db, tmp_path):
        """Cards with NULL category should be exported as 'Trainer'."""
        db.execute(
            "INSERT INTO cl_decklist_cards (placement_id, card_name_jp, card_name_en, count, category) "
            "VALUES (?, ?, ?, ?, ?)",
            (101, "ヌルカード", None, 1, None),
        )
        db.commit()
        export_champions_league(db, tmp_path)
        data = json.loads((tmp_path / "champions-league" / "masters.json").read_text())
        taro = next(p for p in data["placements"] if p["standing"] == 1)
        null_card = next(c for c in taro["decklist"] if c["card_name_jp"] == "ヌルカード")
        assert null_card["category"] == "Trainer"


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
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        # Minimal schema without card_mappings
        conn.execute("CREATE TABLE cards (id TEXT, name_en TEXT, name_jp TEXT, set_code TEXT)")
        lookup = _build_jp_en_lookup(conn)
        # Should still have hardcoded entries
        assert "ネストボール" in lookup
        conn.close()

    def test_non_table_operational_error_is_reraised(self):
        """OperationalErrors unrelated to missing table should propagate."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE cards (id TEXT, name_en TEXT, name_jp TEXT, set_code TEXT)")
        # Create card_mappings with wrong columns so the SELECT for
        # card_name_jp/card_name_en triggers "no such column", not "no such table"
        conn.execute("CREATE TABLE card_mappings (id TEXT)")

        with pytest.raises(sqlite3.OperationalError, match="no such column"):
            _build_jp_en_lookup(conn)
        conn.close()


# --- _compute_card_stats_for_ids ---


class TestComputeCardStatsForIds:
    def test_returns_cards_for_valid_ids(self, db):
        # Placement IDs 1, 3, 5 are Charizard ex
        stats = _compute_card_stats_for_ids(db, [1, 3, 5])
        card_names = [c["card_name"] for c in stats]
        assert "Nest Ball" in card_names
        assert "Ultra Ball" in card_names

    def test_inclusion_pct_correct(self, db):
        # All 3 Charizard placements have Nest Ball
        stats = _compute_card_stats_for_ids(db, [1, 3, 5])
        nest = next(c for c in stats if c["card_name"] == "Nest Ball")
        assert nest["inclusion_pct"] == 100.0
        assert nest["decks_with"] == 3

    def test_avg_copies_correct(self, db):
        stats = _compute_card_stats_for_ids(db, [1, 3, 5])
        nest = next(c for c in stats if c["card_name"] == "Nest Ball")
        assert nest["avg_copies"] == 4.0

    def test_empty_ids_returns_empty(self, db):
        assert _compute_card_stats_for_ids(db, []) == []

    def test_has_category(self, db):
        stats = _compute_card_stats_for_ids(db, [1])
        for card in stats:
            assert "category" in card


# --- Top-4 segmented stats in export_archetypes ---


class TestTop4SegmentedStats:
    def test_top4_fields_present(self, db, tmp_path):
        export_archetypes(db, tmp_path)
        data = json.loads((tmp_path / "archetypes" / "charizard-ex.json").read_text())
        assert "top4_card_stats" in data
        assert "top4_sample_size" in data
        assert "top4_low_sample" in data

    def test_top4_sample_size_correct(self, db, tmp_path):
        """Charizard has placements at 1st and 4th (standings <= 4)."""
        export_archetypes(db, tmp_path)
        data = json.loads((tmp_path / "archetypes" / "charizard-ex.json").read_text())
        assert data["top4_sample_size"] == 2

    def test_top4_low_sample_flag(self, db, tmp_path):
        """With only 2 top-4 decks, low_sample should be True."""
        export_archetypes(db, tmp_path)
        data = json.loads((tmp_path / "archetypes" / "charizard-ex.json").read_text())
        assert data["top4_low_sample"] is True

    def test_delta_vs_field_present(self, db, tmp_path):
        export_archetypes(db, tmp_path)
        data = json.loads((tmp_path / "archetypes" / "charizard-ex.json").read_text())
        for card in data["top4_card_stats"]:
            assert "delta_vs_field" in card

    def test_delta_vs_field_zero(self, db, tmp_path):
        """Cards present in all decks should have delta 0."""
        export_archetypes(db, tmp_path)
        data = json.loads((tmp_path / "archetypes" / "charizard-ex.json").read_text())
        nest = next(c for c in data["top4_card_stats"] if c["card_name"] == "Nest Ball")
        # 100% in top4, 100% in field -> delta = 0
        assert nest["delta_vs_field"] == 0.0

    def test_delta_vs_field_positive(self, db, tmp_path):
        """Card in top-4 more than field should have positive delta."""
        export_archetypes(db, tmp_path)
        data = json.loads((tmp_path / "archetypes" / "charizard-ex.json").read_text())
        # Arven is in placements 1 (1st) and 3 (4th) but not 5 (9th)
        # top-4 inclusion: 2/2 = 100%, field inclusion: 2/3 = 66.7%
        arven = next(c for c in data["top4_card_stats"] if c["card_name"] == "Arven")
        assert arven["delta_vs_field"] == 33.3

    def test_delta_vs_field_negative(self, db, tmp_path):
        """Card in field but absent from top-4 should have negative delta."""
        export_archetypes(db, tmp_path)
        data = json.loads((tmp_path / "archetypes" / "charizard-ex.json").read_text())
        # Iono is in placement 5 (9th place) but not 1 (1st) or 3 (4th)
        # top-4 inclusion: 0%, field inclusion: 1/3 = 33.3%
        iono = next(c for c in data["top4_card_stats"] if c["card_name"] == "Iono")
        assert iono["delta_vs_field"] == -33.3
        assert iono["inclusion_pct"] == 0
        assert iono["decks_with"] == 0

    def test_no_top4_returns_empty_card_stats(self, db, tmp_path):
        """Raging Bolt has only 16th place -- top4_card_stats should be empty."""
        export_archetypes(db, tmp_path)
        data = json.loads((tmp_path / "archetypes" / "raging-bolt-ex.json").read_text())
        assert data["top4_sample_size"] == 0
        assert data["top4_low_sample"] is True
        assert data["top4_card_stats"] == []


# --- _get_sprite_filenames (extended coverage) ---


class TestGetSpriteFilenamesMega:
    def test_mega_archetype(self):
        result = _get_sprite_filenames("Mega Lucario ex")
        assert "lucario-mega.png" in result

    def test_mega_with_secondary(self):
        result = _get_sprite_filenames("Mega Lucario Solrock")
        assert "lucario-mega.png" in result
        assert "solrock.png" in result

    def test_hyphenated_pokemon(self):
        result = _get_sprite_filenames("Chien-Pao ex")
        assert "chien-pao.png" in result


# --- _detect_variants ---


class TestDetectVariants:
    def _make_variant_db(self):
        """Create a DB with enough placements for variant detection."""
        import sqlite3

        from db import SCHEMA

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT INTO tournaments (id, name, date, player_count) VALUES ('t1', 'Test', '2026-01-25', 64)"
        )
        # 6 placements for same archetype
        for i in range(1, 7):
            conn.execute(
                "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
                "VALUES (?, 't1', ?, ?, 'Charizard ex')",
                (i, i, f"Player{i}"),
            )
        # All have Charizard ex (core card)
        for pid in range(1, 7):
            conn.execute(
                "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) "
                "VALUES (?, 'c-zard', 'Charizard ex', 3)",
                (pid,),
            )
            conn.execute(
                "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) "
                "VALUES (?, 'c-nest', 'Nest Ball', 4)",
                (pid,),
            )
        # 3 of 6 have Pidgeot ex (50% — within 15-70% variant marker range)
        for pid in [1, 2, 3]:
            conn.execute(
                "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) "
                "VALUES (?, 'c-pidg', 'Pidgeot ex', 2)",
                (pid,),
            )
        conn.commit()
        return conn

    def test_detects_variants(self):
        conn = self._make_variant_db()
        placement_ids = list(range(1, 7))
        all_cards = [
            {"card_name": "Charizard ex", "inclusion_pct": 100.0, "category": "Pokemon"},
            {"card_name": "Pidgeot ex", "inclusion_pct": 50.0, "category": "Pokemon"},
            {"card_name": "Nest Ball", "inclusion_pct": 100.0, "category": "Trainer"},
        ]
        variants = _detect_variants(conn, "Charizard ex", placement_ids, all_cards)
        assert len(variants) >= 2
        names = [v["name"] for v in variants]
        assert "with Pidgeot ex" in names
        assert "Standard" in names
        conn.close()

    def test_too_few_decks_returns_empty(self, db):
        all_cards = [{"card_name": "Charizard ex", "inclusion_pct": 100.0, "category": "Pokemon"}]
        result = _detect_variants(db, "Charizard ex", [1, 2, 3], all_cards)
        assert result == []

    def test_no_markers_returns_empty(self):
        conn = self._make_variant_db()
        # All cards are either 100% (core) or not Pokemon — no markers
        all_cards = [
            {"card_name": "Charizard ex", "inclusion_pct": 100.0, "category": "Pokemon"},
            {"card_name": "Nest Ball", "inclusion_pct": 100.0, "category": "Trainer"},
        ]
        result = _detect_variants(conn, "Charizard ex", list(range(1, 7)), all_cards)
        assert result == []
        conn.close()


# --- _compute_windowed_winning_edge ---


class TestComputeWindowedWinningEdge:
    def test_returns_list(self, db):
        meta_data = {
            "archetypes": [
                {"archetype": "Charizard ex", "tier": "S"},
                {"archetype": "Dragapult ex", "tier": "A"},
            ]
        }
        result = _compute_windowed_winning_edge(db, "2026-01-01", "2026-12-31", meta_data)
        assert isinstance(result, list)

    def test_empty_when_no_sa_archetypes(self, db):
        meta_data = {"archetypes": [{"archetype": "Foo", "tier": "Rogue"}]}
        result = _compute_windowed_winning_edge(db, "2026-01-01", "2026-12-31", meta_data)
        assert result == []

    def test_cards_have_edge_field(self, db):
        meta_data = {
            "archetypes": [
                {"archetype": "Charizard ex", "tier": "S"},
                {"archetype": "Dragapult ex", "tier": "S"},
            ]
        }
        result = _compute_windowed_winning_edge(db, "2026-01-01", "2026-12-31", meta_data)
        for card in result:
            assert "edge" in card
            assert "field_pct" in card
            assert "win_pct" in card


# --- export_trends (empty data) ---


class TestExportTrendsEdgeCases:
    def test_empty_db_writes_empty_trends(self, tmp_path):
        """An empty DB should produce an empty trends file."""
        import sqlite3

        from db import SCHEMA

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        export_trends(conn, tmp_path)
        data = json.loads((tmp_path / "trends.json").read_text())
        assert data["surging"] == []
        assert data["declining"] == []
        conn.close()

    def test_one_sided_data_writes_empty(self, tmp_path):
        """Data only in early period should produce empty trends."""
        import sqlite3

        from db import SCHEMA

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT INTO tournaments (id, name, date, player_count) VALUES ('t1', 'Early', '2026-01-15', 64)"
        )
        conn.execute(
            "INSERT INTO placements (tournament_id, standing, player_name, archetype) "
            "VALUES ('t1', 1, 'Alice', 'Charizard ex')"
        )
        conn.execute(
            "INSERT INTO meta_snapshots (id, generated_at, tournament_count, deck_count) "
            "VALUES (1, '2026-03-10', 1, 1)"
        )
        conn.commit()
        export_trends(conn, tmp_path)
        data = json.loads((tmp_path / "trends.json").read_text())
        assert data["early_decks"] == 0 or data["late_decks"] == 0
        conn.close()


class TestExportMatchupData:
    def test_exports_labs_matchup_json(self, tmp_path, labs_db, db_single_tournament):
        from reports.json_export import export_matchup_data

        export_matchup_data(db_single_tournament, tmp_path, labs_conn=labs_db)
        output = tmp_path / "matchup.json"
        assert output.exists()

        import json

        data = json.loads(output.read_text())
        assert "archetypes" in data
        assert "matrix" in data
        assert "sample_sizes" in data
        assert "source" in data

    def test_falls_back_to_co_occurrence_without_labs(self, tmp_path, db):
        from reports.json_export import export_matchup_data

        export_matchup_data(db, tmp_path, labs_conn=None)
        output = tmp_path / "matchup.json"
        assert output.exists()

        import json

        data = json.loads(output.read_text())
        assert data.get("source") == "co-occurrence"


class TestExportAllLabsIntegration:
    def test_export_all_with_labs_conn_produces_matchup(
        self, db_single_tournament, tmp_path, labs_db
    ):
        from reports.json_export import export_all

        out, skipped = export_all(db_single_tournament, output_dir=tmp_path, labs_conn=labs_db)
        assert (out / "matchup.json").exists()

    def test_export_all_without_labs_conn_still_produces_matchup(
        self, db_single_tournament, tmp_path
    ):
        from reports.json_export import export_all

        out, skipped = export_all(db_single_tournament, output_dir=tmp_path, labs_conn=None)
        # Co-occurrence fallback should still produce matchup.json
        assert (out / "matchup.json").exists()

    def test_export_all_broken_labs_falls_through_to_co_occurrence(
        self, db_single_tournament, tmp_path
    ):
        """A broken Labs conn should not crash; cascade falls through to co-occurrence."""
        import json
        import sqlite3

        from reports.json_export import export_all

        broken_conn = sqlite3.connect(":memory:")
        out, skipped = export_all(
            db_single_tournament,
            output_dir=tmp_path,
            labs_conn=broken_conn,
            strict=False,
        )
        # Should still produce matchup.json via co-occurrence fallback
        matchup_file = out / "matchup.json"
        assert matchup_file.exists()
        data = json.loads(matchup_file.read_text())
        assert data.get("source") == "co-occurrence"
        broken_conn.close()
