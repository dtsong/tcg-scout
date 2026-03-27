"""Tests for archetype name migration mapping."""

import sqlite3
import tempfile

from scripts.migrate_archetype_names import (
    apply_migration,
    build_full_mapping,
    build_migration_mapping,
    limitless_name_from_filenames,
)


class TestLimitlessNameFromFilenames:
    def test_single_pokemon(self):
        assert limitless_name_from_filenames(["dragapult.png"]) == "Dragapult"

    def test_two_pokemon_alphabetical(self):
        assert (
            limitless_name_from_filenames(["dusknoir.png", "dragapult.png"])
            == "Dragapult / Dusknoir"
        )

    def test_mega_pokemon(self):
        assert limitless_name_from_filenames(["lucario-mega.png"]) == "Lucario-Mega"

    def test_mega_combo(self):
        assert (
            limitless_name_from_filenames(["hariyama.png", "lucario-mega.png"])
            == "Hariyama / Lucario-Mega"
        )

    def test_double_mega(self):
        assert (
            limitless_name_from_filenames(["froslass-mega.png", "starmie-mega.png"])
            == "Froslass-Mega / Starmie-Mega"
        )

    def test_hyphenated_pokemon(self):
        assert limitless_name_from_filenames(["raging-bolt.png"]) == "Raging-Bolt"

    def test_hyphenated_combo(self):
        assert (
            limitless_name_from_filenames(["ogerpon.png", "raging-bolt.png"])
            == "Ogerpon / Raging-Bolt"
        )

    def test_form_variant(self):
        assert (
            limitless_name_from_filenames(["noctowl.png", "ogerpon-wellspring.png"])
            == "Noctowl / Ogerpon-Wellspring"
        )

    def test_empty_returns_unknown(self):
        assert limitless_name_from_filenames([]) == "Unknown"


class TestBuildMigrationMapping:
    def test_returns_dict(self):
        mapping = build_migration_mapping()
        assert isinstance(mapping, dict)
        assert len(mapping) > 0

    def test_known_renames(self):
        mapping = build_migration_mapping()
        # Multi-sprite composites map correctly
        assert mapping["Mega Lucario"] == "Hariyama / Lucario-Mega"
        assert mapping["Dragapult Dusknoir"] == "Dragapult / Dusknoir"
        assert mapping["Raging Bolt ex"] == "Ogerpon / Raging-Bolt"
        assert mapping["Mega Venusaur"] == "Ogerpon / Venusaur-Mega"
        assert mapping["Mega Meganium"] == "Meganium-Mega / Ogerpon"
        assert mapping["Tera Box"] == "Noctowl / Ogerpon-Wellspring"
        assert mapping["Mega Absol Box"] == "Absol-Mega / Kangaskhan-Mega"

    def test_single_sprite_renames(self):
        mapping = build_migration_mapping()
        # Single-sprite names that strip "ex" suffix
        assert mapping["Zoroark ex"] == "Zoroark"
        assert mapping["Archaludon ex"] == "Archaludon"

    def test_merged_names_pick_most_filenames(self):
        # "Dragapult ex" has two keys: "dragapult" (1 file) and "dragapult-pidgeot" (2 files).
        # The most-filenames key wins -> "Dragapult / Pidgeot"
        mapping = build_migration_mapping()
        assert mapping["Dragapult ex"] == "Dragapult / Pidgeot"

    def test_composite_renames(self):
        mapping = build_migration_mapping()
        assert mapping["Alakazam Dudunsparce"] == "Alakazam / Dudunsparce"
        assert mapping["Garchomp Roserade"] == "Garchomp / Roserade"

    def test_no_collisions(self):
        mapping = build_migration_mapping()
        new_names = list(mapping.values())
        # Exclude "Unknown" from collision check
        non_unknown = [n for n in new_names if n != "Unknown"]
        assert len(non_unknown) == len(set(non_unknown)), "Collision detected in new names"


class TestBuildFullMapping:
    def _make_db(self, archetypes: list[str]) -> str:
        """Create a temp SQLite DB with the given archetype names in placements."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        conn = sqlite3.connect(tmp.name)
        conn.execute(
            """CREATE TABLE placements (
                id INTEGER PRIMARY KEY,
                archetype TEXT,
                tournament_id INTEGER,
                standing INTEGER
            )"""
        )
        for i, arch in enumerate(archetypes):
            conn.execute(
                "INSERT INTO placements (id, archetype, tournament_id, standing) VALUES (?, ?, 1, 1)",
                (i, arch),
            )
        conn.commit()
        conn.close()
        return tmp.name

    def test_unknown_preserved(self):
        db = self._make_db(["Unknown"])
        mapping = build_full_mapping(db)
        assert mapping["Unknown"] == "Unknown"

    def test_mapped_name_converted(self):
        db = self._make_db(["Mega Lucario", "Dragapult Dusknoir"])
        mapping = build_full_mapping(db)
        assert mapping["Mega Lucario"] == "Hariyama / Lucario-Mega"
        assert mapping["Dragapult Dusknoir"] == "Dragapult / Dusknoir"

    def test_auto_derived_name_converted(self):
        # "Gardevoir ex" is in SPRITE_ARCHETYPE_MAP -> single sprite -> "Gardevoir"
        db = self._make_db(["Gardevoir ex"])
        mapping = build_full_mapping(db)
        assert mapping["Gardevoir ex"] == "Gardevoir"

    def test_returns_all_archetypes(self):
        archetypes = ["Unknown", "Mega Lucario", "Gardevoir ex"]
        db = self._make_db(archetypes)
        mapping = build_full_mapping(db)
        assert set(mapping.keys()) == set(archetypes)


class TestApplyMigration:
    def _make_db(self, archetypes: list[str]) -> str:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        conn = sqlite3.connect(tmp.name)
        conn.execute(
            """CREATE TABLE placements (
                id INTEGER PRIMARY KEY,
                archetype TEXT,
                tournament_id INTEGER,
                standing INTEGER
            )"""
        )
        for i, arch in enumerate(archetypes):
            conn.execute(
                "INSERT INTO placements (id, archetype, tournament_id, standing) VALUES (?, ?, 1, 1)",
                (i, arch),
            )
        conn.commit()
        conn.close()
        return tmp.name

    def test_dry_run_makes_no_changes(self):
        db = self._make_db(["Mega Lucario"])
        apply_migration(db, dry_run=True)
        conn = sqlite3.connect(db)
        rows = conn.execute("SELECT archetype FROM placements").fetchall()
        conn.close()
        assert rows[0][0] == "Mega Lucario"

    def test_apply_renames_archetypes(self):
        db = self._make_db(["Mega Lucario", "Unknown"])
        apply_migration(db, dry_run=False)
        conn = sqlite3.connect(db)
        archetypes = {
            r[0] for r in conn.execute("SELECT DISTINCT archetype FROM placements").fetchall()
        }
        conn.close()
        assert "Hariyama / Lucario-Mega" in archetypes
        assert "Unknown" in archetypes
        assert "Mega Lucario" not in archetypes
