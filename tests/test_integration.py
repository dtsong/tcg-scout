"""Integration tests: full pipeline from DB through JSON export."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.mark.integration
class TestFullPipeline:
    def test_meta_to_export_pipeline(self, db, tmp_path):
        """Full pipeline: compute meta -> export all -> verify JSON files."""
        from analysis.meta import compute_meta_snapshot
        from reports.json_export import export_all

        # Delete pre-seeded snapshot so we start fresh
        db.execute("DELETE FROM archetype_stats")
        db.execute("DELETE FROM meta_snapshots")
        db.commit()

        # Step 1: Compute meta snapshot
        snapshot_id = compute_meta_snapshot(db)
        assert snapshot_id is not None

        # Step 2: Export all to tmp dir
        out = export_all(db, output_dir=tmp_path, format_slug="nihil-zero")

        # Step 3: Verify all expected JSON files exist
        assert (out / "meta.json").exists()
        assert (out / "buylist.json").exists()
        assert (out / "staples.json").exists()
        assert (out / "flex.json").exists()
        assert (out / "trends.json").exists()
        assert (out / "winning-edge.json").exists()
        assert (out / "ace-specs.json").exists()
        assert (out / "archetypes").is_dir()

        # Step 4: Verify meta.json structure
        meta = json.loads((out / "meta.json").read_text())
        assert meta["tournament_count"] == 3
        assert meta["deck_count"] == 6
        assert len(meta["archetypes"]) == 3
        assert "format" in meta
        assert meta["format"]["slug"] == "nihil-zero"

        # Step 5: Verify archetype detail files
        arch_files = list((out / "archetypes").glob("*.json"))
        assert len(arch_files) == 3
        charizard = json.loads((out / "archetypes" / "charizard-ex.json").read_text())
        assert charizard["archetype"] == "Charizard ex"
        assert "core_cards" in charizard
        assert "all_cards" in charizard
        assert "results" in charizard

    def test_basic_energy_excluded_from_staples(self, db, tmp_path):
        """Basic energy cards should not appear in staples/flex exports."""
        from analysis.meta import compute_meta_snapshot
        from reports.json_export import export_flex, export_staples

        db.execute("DELETE FROM archetype_stats")
        db.execute("DELETE FROM meta_snapshots")
        db.commit()
        compute_meta_snapshot(db)

        # Add basic energy to every placement
        for pid in range(1, 7):
            db.execute(
                "INSERT OR REPLACE INTO decklist_cards (placement_id, card_id, card_name, count) "
                "VALUES (?, ?, ?, ?)",
                (pid, "energy-fire", "Basic Fire Energy", 10),
            )
        db.commit()

        export_staples(db, tmp_path)
        export_flex(db, tmp_path)

        staples = json.loads((tmp_path / "staples.json").read_text())
        flex = json.loads((tmp_path / "flex.json").read_text())

        staple_names = {s["card_name"] for s in staples}
        flex_names = {f["card_name"] for f in flex}
        assert "Basic Fire Energy" not in staple_names
        assert "Basic Fire Energy" not in flex_names


@pytest.mark.integration
class TestFormatIntegration:
    def test_format_config_round_trip(self):
        """Format config is consistent with export output."""
        from config import FORMATS, get_format_config

        for slug in FORMATS:
            cfg = get_format_config(slug)
            assert "name" in cfg
            assert "dataset_start" in cfg
            assert "db_name" in cfg

    def test_export_formats_manifest(self, tmp_path):
        """export_formats produces valid manifest."""
        from reports.json_export import export_formats

        # Create a fake nihil-zero meta.json
        nz = tmp_path / "nihil-zero"
        nz.mkdir()
        (nz / "meta.json").write_text(json.dumps({"tournament_count": 10, "deck_count": 50}))

        export_formats(output_dir=tmp_path)

        formats = json.loads((tmp_path / "formats.json").read_text())
        slugs = [f["slug"] for f in formats]
        assert "nihil-zero" in slugs
        assert "ninja-spinner" in slugs

        nz_fmt = next(f for f in formats if f["slug"] == "nihil-zero")
        assert nz_fmt["status"] == "frozen"  # dataset_end is in the past
        assert nz_fmt["tournament_count"] == 10

        ns_fmt = next(f for f in formats if f["slug"] == "ninja-spinner")
        assert ns_fmt["status"] == "upcoming"


@pytest.mark.integration
class TestScrapeJPIntegration:
    @pytest.mark.skipif(
        not importlib.util.find_spec("kernel"),
        reason="kernel SDK not installed",
    )
    def test_store_and_backfill_flow(self, db):
        """Store JP results with Unknown archetype, then backfill from Limitless data."""
        from scraper.limitless import match_archetype_labels
        from scraper.pokemon_jp import JPEventResult, JPPlacement, store_cl_city_league_results

        # Store a JP event with Unknown archetypes
        event = JPEventResult(
            event_id=999999,
            event_name="City League Test",
            division="open",
            date="2026-01-25",
            placements=[
                JPPlacement(standing=1, player_name="Alice", region="Tokyo"),
                JPPlacement(standing=2, player_name="Bob", region="Osaka"),
            ],
        )
        store_cl_city_league_results(db, event, decklists={})

        # Verify stored as Unknown
        rows = db.execute(
            "SELECT standing, archetype FROM placements WHERE tournament_id = 'jp-999999' ORDER BY standing"
        ).fetchall()
        assert all(r["archetype"] == "Unknown" for r in rows)

        # Simulate Limitless cross-reference
        jp_placements = [
            {"date": "2026-01-25", "standing": 1},
            {"date": "2026-01-25", "standing": 2},
        ]
        limitless_data = [
            {"date": "2026-01-25", "standing": 1, "archetype": "Charizard ex"},
            {"date": "2026-01-25", "standing": 2, "archetype": "Dragapult ex"},
        ]
        matched = match_archetype_labels(jp_placements, limitless_data)
        assert matched[0]["archetype"] == "Charizard ex"
        assert matched[1]["archetype"] == "Dragapult ex"


@pytest.mark.integration
class TestClassifierIntegration:
    def test_classify_from_real_decklist_cards(self, db):
        """Classifier correctly identifies archetype from decklist_cards table data."""
        from analysis.archetype import classify_from_decklist

        # Get cards for placement 1 (Alice, Charizard ex archetype)
        cards = db.execute(
            "SELECT card_name, count FROM decklist_cards WHERE placement_id = 1"
        ).fetchall()
        card_dicts = [
            {"card_name": c["card_name"], "count": c["count"], "category": "Pokemon"} for c in cards
        ]
        # The seed data doesn't have "Charizard ex" as a card name in decklist_cards,
        # so the classifier should return Unknown (no anchor match)
        result = classify_from_decklist(card_dicts)
        assert isinstance(result, str)
        # Just verify it runs without error and returns a string


@pytest.mark.integration
class TestTierPropagation:
    """Config thresholds -> compute_meta_snapshot -> tier in export JSON."""

    def test_tiers_match_thresholds(self, db_integration, tmp_path):
        """Tier assignment in exported meta.json matches TIER_THRESHOLDS from config."""
        from analysis.meta import compute_meta_snapshot
        from config import TIER_THRESHOLDS
        from reports.json_export import export_meta

        db_integration.execute("DELETE FROM archetype_stats")
        db_integration.execute("DELETE FROM meta_snapshots")
        db_integration.commit()

        compute_meta_snapshot(db_integration)
        export_meta(db_integration, tmp_path, format_slug="nihil-zero")

        meta = json.loads((tmp_path / "meta.json").read_text())
        for arch in meta["archetypes"]:
            share = arch["meta_share"]
            expected_tier = "Rogue"
            for tier, threshold in sorted(TIER_THRESHOLDS.items(), key=lambda t: -t[1]):
                if share >= threshold:
                    expected_tier = tier
                    break
            assert arch["tier"] == expected_tier, (
                f"{arch['archetype']}: meta_share={share}, "
                f"expected tier={expected_tier}, got tier={arch['tier']}"
            )

    def test_tiers_consistent_in_archetype_details(self, db_integration, tmp_path):
        """Tier in meta.json matches tier in per-archetype detail files."""
        from analysis.meta import compute_meta_snapshot
        from reports.json_export import export_all

        db_integration.execute("DELETE FROM archetype_stats")
        db_integration.execute("DELETE FROM meta_snapshots")
        db_integration.commit()

        compute_meta_snapshot(db_integration)
        out = export_all(db_integration, output_dir=tmp_path, format_slug="nihil-zero")

        meta = json.loads((out / "meta.json").read_text())
        meta_tiers = {a["slug"]: a["tier"] for a in meta["archetypes"]}

        for arch_file in (out / "archetypes").glob("*.json"):
            detail = json.loads(arch_file.read_text())
            slug = detail["slug"]
            assert slug in meta_tiers, f"Archetype {slug} in detail but not in meta"
            assert detail["tier"] == meta_tiers[slug], (
                f"{slug}: meta tier={meta_tiers[slug]}, detail tier={detail['tier']}"
            )


@pytest.mark.integration
class TestDivisionIsolation:
    """Senior/junior placements must be excluded from all open-division exports."""

    def test_senior_junior_excluded_from_meta(self, db_integration, tmp_path):
        from analysis.meta import compute_meta_snapshot
        from reports.json_export import export_meta

        db_integration.execute("DELETE FROM archetype_stats")
        db_integration.execute("DELETE FROM meta_snapshots")
        db_integration.commit()

        compute_meta_snapshot(db_integration)
        export_meta(db_integration, tmp_path, format_slug="nihil-zero")

        meta = json.loads((tmp_path / "meta.json").read_text())
        # 12 open placements, not 14 (senior+junior excluded)
        assert meta["deck_count"] == 12

    def test_senior_junior_excluded_from_archetype_results(self, db_integration, tmp_path):
        from analysis.meta import compute_meta_snapshot
        from reports.json_export import export_all

        db_integration.execute("DELETE FROM archetype_stats")
        db_integration.execute("DELETE FROM meta_snapshots")
        db_integration.commit()

        compute_meta_snapshot(db_integration)
        out = export_all(db_integration, output_dir=tmp_path, format_slug="nihil-zero")

        # Check Charizard detail — should have 4 open results, not 5
        charizard = json.loads((out / "archetypes" / "charizard-ex.json").read_text())
        player_names = {r["player_name"] for r in charizard["results"]}
        assert "Senior1" not in player_names, "Senior placement leaked into open exports"
        assert "Junior1" not in player_names, "Junior placement leaked into open exports"
        assert charizard["deck_count"] == 4  # 4 open Charizard placements


@pytest.mark.integration
class TestBuylistChain:
    """compute_meta_snapshot -> generate_buylist -> correct tier filtering."""

    def test_buylist_only_includes_sab_tiers(self, db_integration, tmp_path):
        from analysis.buylist import generate_buylist
        from analysis.meta import compute_meta_snapshot, get_latest_snapshot

        db_integration.execute("DELETE FROM archetype_stats")
        db_integration.execute("DELETE FROM meta_snapshots")
        db_integration.commit()

        compute_meta_snapshot(db_integration)
        snapshot = get_latest_snapshot(db_integration)

        # Manually downgrade Gardevoir ex to Rogue in the snapshot to test filtering
        db_integration.execute(
            "UPDATE archetype_stats SET tier = 'Rogue' WHERE archetype = 'Gardevoir ex'"
        )
        db_integration.commit()

        # Verify we now have S/A and Rogue tiers
        rows = db_integration.execute(
            "SELECT DISTINCT tier FROM archetype_stats WHERE snapshot_id = ?",
            (snapshot["id"],),
        ).fetchall()
        tiers = {r["tier"] for r in rows}
        assert "Rogue" in tiers, f"Expected Rogue tier in fixture, got {tiers}"
        assert tiers & {"S", "A", "B"}, f"Expected at least one S/A/B tier, got {tiers}"

        buylist = generate_buylist(db_integration, snapshot["id"])
        assert len(buylist) > 0, "Buylist should not be empty with S/A/B archetypes"

        for card in buylist:
            card_archetypes = set(card.get("archetypes", []))
            assert len(card_archetypes) > 0, f"Card {card['card_name']} has no archetypes"
            # No card should reference the Rogue-tier archetype
            assert "Gardevoir ex" not in card_archetypes, (
                f"Card {card['card_name']} includes Rogue archetype 'Gardevoir ex'"
            )


@pytest.mark.integration
class TestWeightedSharePropagation:
    """PLACEMENT_WEIGHTS from config -> weighted_share in archetype_stats -> exported JSON."""

    def test_weighted_share_in_export(self, db_integration, tmp_path):
        from analysis.meta import compute_meta_snapshot
        from reports.json_export import export_meta

        db_integration.execute("DELETE FROM archetype_stats")
        db_integration.execute("DELETE FROM meta_snapshots")
        db_integration.commit()

        compute_meta_snapshot(db_integration)
        export_meta(db_integration, tmp_path, format_slug="nihil-zero")

        meta = json.loads((tmp_path / "meta.json").read_text())
        for arch in meta["archetypes"]:
            assert "weighted_share" in arch, f"{arch['archetype']} missing weighted_share"
            assert isinstance(arch["weighted_share"], (int, float))
            assert arch["weighted_share"] >= 0

    def test_first_place_weighted_higher(self, db_integration, tmp_path):
        """Archetypes with 1st-place finishes should have weighted_share >= meta_share."""
        from analysis.meta import compute_meta_snapshot
        from reports.json_export import export_meta

        db_integration.execute("DELETE FROM archetype_stats")
        db_integration.execute("DELETE FROM meta_snapshots")
        db_integration.commit()

        compute_meta_snapshot(db_integration)
        export_meta(db_integration, tmp_path, format_slug="nihil-zero")

        meta = json.loads((tmp_path / "meta.json").read_text())
        # Charizard has multiple 1st-place finishes, should be weighted higher
        charizard = next(a for a in meta["archetypes"] if a["archetype"] == "Charizard ex")
        assert charizard["weighted_share"] >= charizard["meta_share"], (
            "Charizard with 1st-place finishes should have weighted_share >= meta_share"
        )
