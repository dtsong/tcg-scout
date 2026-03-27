"""Build old->new archetype name mapping for Limitless-style naming.

Usage:
    python -m scripts.migrate_archetype_names [--dry-run] [--db PATH]
"""

import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Inlined from analysis.archetype (removed in Task 4 refactor).
# This migration script has already been run; data preserved here for reference.
_COMPOSITE_SPRITE_FILENAMES: dict[str, list[str]] = {
    "charizard-pidgeot": ["charizard", "pidgeot"],
    "charizard-dusknoir": ["charizard", "dusknoir"],
    "dragapult-pidgeot": ["dragapult", "pidgeot"],
    "dragapult-dusknoir": ["dragapult", "dusknoir"],
    "dragapult-noctowl": ["dragapult", "noctowl"],
    "joltik-pikachu": ["joltik", "pikachu"],
    "froslass-munkidori": ["froslass", "munkidori"],
    "froslass-grimmsnarl": ["froslass", "grimmsnarl"],
    "garchomp-roserade": ["garchomp", "roserade"],
    "alakazam-dudunsparce": ["alakazam", "dudunsparce"],
    "dipplin-thwackey": ["dipplin", "thwackey"],
    "dipplin-rillaboom": ["dipplin", "rillaboom"],
    "mewtwo-spidops": ["mewtwo", "spidops"],
    "darmanitan-zoroark": ["darmanitan", "zoroark"],
    "blaziken-dragapult": ["blaziken", "dragapult"],
    "barbaracle-okidogi": ["barbaracle", "okidogi"],
    "grimmsnarl-munkidori": ["grimmsnarl", "munkidori"],
    "flareon-noctowl": ["flareon", "noctowl"],
    "empoleon-metagross": ["empoleon", "metagross"],
    "noctowl-ogerpon": ["noctowl", "ogerpon"],
    "crobat-dragapult": ["crobat", "dragapult"],
    "dusknoir-jellicent": ["dusknoir", "jellicent"],
    "comfey-giratina": ["comfey", "giratina"],
    "comfey-sableye": ["comfey", "sableye"],
    "ogerpon-raging-bolt": ["ogerpon", "raging-bolt"],
    "baxcalibur-chien-pao": ["baxcalibur", "chien-pao"],
    "noctowl-ogerpon-wellspring": ["noctowl", "ogerpon-wellspring"],
    "armarouge-ho-oh": ["armarouge", "ho-oh"],
    "honchkrow-porygon-z": ["honchkrow", "porygon-z"],
    "absol-mega-kangaskhan-mega": ["absol-mega", "kangaskhan-mega"],
    "hariyama-lucario-mega": ["hariyama", "lucario-mega"],
    "froslass-mega-starmie-mega": ["froslass-mega", "starmie-mega"],
    "ogerpon-venusaur-mega": ["ogerpon", "venusaur-mega"],
    "lucario-mega-solrock": ["lucario-mega", "solrock"],
    "diancie-mega-dusknoir": ["diancie-mega", "dusknoir"],
    "meganium-mega-ogerpon": ["meganium-mega", "ogerpon"],
    "sharpedo-mega-toxtricity": ["sharpedo-mega", "toxtricity"],
    "greninja-starmie-mega": ["greninja", "starmie-mega"],
    "dusknoir-starmie-mega": ["dusknoir", "starmie-mega"],
    "froslass-mega-grimmsnarl": ["froslass-mega", "grimmsnarl"],
    "meganium-mega-venusaur-mega": ["meganium-mega", "venusaur-mega"],
    "meganium-venusaur-mega": ["meganium", "venusaur-mega"],
    "iron-valiant": ["iron-valiant"],
    "iron-hands": ["iron-hands"],
    "raging-bolt": ["raging-bolt"],
    "roaring-moon": ["roaring-moon"],
    "chien-pao": ["chien-pao"],
    "porygon-z": ["porygon-z"],
}

SPRITE_ARCHETYPE_MAP: dict[str, str] = {
    "charizard": "Charizard ex",
    "charizard-pidgeot": "Charizard ex",
    "charizard-dusknoir": "Charizard ex",
    "dragapult": "Dragapult ex",
    "dragapult-pidgeot": "Dragapult ex",
    "gardevoir": "Gardevoir ex",
    "raging-bolt": "Raging Bolt ex",
    "ogerpon-raging-bolt": "Raging Bolt ex",
    "gholdengo": "Gholdengo ex",
    "terapagos": "Terapagos ex",
    "archaludon": "Archaludon ex",
    "pidgeot": "Pidgeot ex Control",
    "miraidon": "Miraidon ex",
    "koraidon": "Koraidon ex",
    "iron-hands": "Iron Hands ex",
    "iron-valiant": "Iron Valiant ex",
    "roaring-moon": "Roaring Moon ex",
    "chien-pao": "Chien-Pao ex",
    "baxcalibur-chien-pao": "Chien-Pao ex",
    "porygon-z": "Porygon-Z",
    "comfey-giratina": "Lost Zone Giratina",
    "comfey-sableye": "Lost Zone Box",
    "absol-mega": "Mega Absol ex",
    "kangaskhan-mega": "Mega Kangaskhan ex",
    "starmie-mega": "Mega Starmie ex",
    "froslass-mega": "Mega Froslass ex",
    "mewtwo-mega": "Mega Mewtwo ex",
    "gengar-mega": "Mega Gengar ex",
    "gardevoir-mega": "Mega Gardevoir ex",
    "sableye-mega": "Mega Sableye ex",
    "lopunny-mega": "Mega Lopunny ex",
    "lucario-mega": "Mega Lucario ex",
    "venusaur-mega": "Mega Venusaur ex",
    "diancie-mega": "Mega Diancie ex",
    "meganium-mega": "Mega Meganium ex",
    "sharpedo-mega": "Mega Sharpedo ex",
    "grimmsnarl": "Grimmsnarl ex",
    "noctowl": "Noctowl Box",
    "zoroark": "Zoroark ex",
    "ceruledge": "Ceruledge ex",
    "flareon": "Flareon ex",
    "joltik": "Joltik Box",
    "alakazam": "Alakazam ex",
    "crustle": "Crustle ex",
    "greninja": "Greninja ex",
    "froslass": "Froslass ex",
    "froslass-munkidori": "Froslass Munkidori",
    "snorlax": "Snorlax Stall",
    "cinderace": "Cinderace ex",
    "klawf": "Klawf ex",
    "absol-mega-kangaskhan-mega": "Mega Absol Box",
    "noctowl-ogerpon-wellspring": "Tera Box",
    "joltik-pikachu": "Joltik Box",
    "armarouge-ho-oh": "Ho-Oh Armarouge",
    "hariyama-lucario-mega": "Mega Lucario",
    "froslass-mega-starmie-mega": "Mega Froslass Mega Starmie",
    "ogerpon-venusaur-mega": "Mega Venusaur",
    "lucario-mega-solrock": "Mega Lucario Solrock",
    "diancie-mega-dusknoir": "Mega Diancie Dusknoir",
    "meganium-mega-ogerpon": "Mega Meganium",
    "sharpedo-mega-toxtricity": "Mega Sharpedo Toxtricity",
    "greninja-starmie-mega": "Mega Starmie Greninja",
    "dusknoir-starmie-mega": "Mega Starmie Dusknoir",
    "froslass-mega-grimmsnarl": "Mega Froslass Grimmsnarl",
    "meganium-mega-venusaur-mega": "Mega Venusaur Meganium",
    "meganium-venusaur-mega": "Mega Venusaur Meganium",
    "dragapult-dusknoir": "Dragapult Dusknoir",
    "dragapult-noctowl": "Dragapult Noctowl",
    "froslass-grimmsnarl": "Froslass Grimmsnarl",
    "garchomp-roserade": "Garchomp Roserade",
    "honchkrow-porygon-z": "Honchkrow Porygon-Z",
    "alakazam-dudunsparce": "Alakazam Dudunsparce",
    "dipplin-thwackey": "Dipplin Thwackey",
    "dipplin-rillaboom": "Dipplin Rillaboom",
    "mewtwo-spidops": "Mewtwo Spidops",
    "darmanitan-zoroark": "Darmanitan Zoroark",
    "blaziken-dragapult": "Blaziken Dragapult",
    "barbaracle-okidogi": "Barbaracle Okidogi",
    "grimmsnarl-munkidori": "Grimmsnarl Munkidori",
    "flareon-noctowl": "Flareon Noctowl",
    "empoleon-metagross": "Empoleon Metagross",
    "noctowl-ogerpon": "Noctowl Ogerpon",
    "crobat-dragapult": "Crobat Dragapult",
    "dusknoir-jellicent": "Dusknoir Jellicent",
}


def _get_sprite_filenames_legacy(archetype_name: str) -> list[str]:
    """Legacy sprite filename derivation for old-style archetype names.

    Used only by this migration script to reverse old names to filenames.
    """
    parts = archetype_name.split()
    filenames: list[str] = []
    i = 0
    while i < len(parts):
        part = parts[i].lower()
        if part in ("ex", "box", "stall", "control", "x", "y", "unknown"):
            i += 1
            continue
        if part == "mega" and i + 1 < len(parts):
            next_part = parts[i + 1].lower()
            if next_part not in ("ex", "box", "stall", "control", "unknown"):
                if i + 2 < len(parts) and parts[i + 2].lower() in ("x", "y"):
                    filenames.append(f"{next_part}-mega-{parts[i + 2].lower()}.png")
                    i += 3
                    continue
                filenames.append(f"{next_part}-mega.png")
                i += 2
                continue
        if i + 1 < len(parts) and parts[i + 1].lower() not in (
            "ex",
            "box",
            "stall",
            "control",
            "mega",
        ):
            combined = f"{part}-{parts[i + 1].lower()}"
            if combined in (
                "raging-bolt",
                "iron-hands",
                "iron-valiant",
                "roaring-moon",
                "chien-pao",
                "porygon-z",
                "ogerpon-wellspring",
                "ogerpon-cornerstone",
                "ho-oh",
                "zacian-crowned",
            ):
                filenames.append(f"{combined}.png")
                i += 2
                continue
        filenames.append(f"{part}.png")
        i += 1
    return filenames[:2]


def limitless_name_from_filenames(png_filenames: list[str]) -> str:
    """Convert sprite filenames to Limitless-style archetype name.

    ['lucario-mega.png', 'hariyama.png'] -> 'Hariyama / Lucario-Mega'
    ['dragapult.png'] -> 'Dragapult'
    [] -> 'Unknown'
    """
    if not png_filenames:
        return "Unknown"
    parts = []
    for fn in png_filenames:
        stem = fn.removesuffix(".png")
        titled = "-".join(p.capitalize() for p in stem.split("-"))
        parts.append(titled)
    parts.sort()
    if len(parts) > 1:
        return " / ".join(parts)
    return parts[0]


def build_migration_mapping() -> dict[str, str]:
    """Build old_name -> new_name mapping for all archetypes in SPRITE_ARCHETYPE_MAP.

    For merged names (multiple sprite keys -> same old name), picks the key with
    the most sprite components (most filenames).
    """
    mapping: dict[str, str] = {}

    # Group keys by old name
    name_to_keys: dict[str, list[str]] = defaultdict(list)
    for key, name in SPRITE_ARCHETYPE_MAP.items():
        name_to_keys[name].append(key)

    for old_name, keys in name_to_keys.items():
        # For merged names, pick the key with the most sprite components
        best_key = max(keys, key=lambda k: len(_COMPOSITE_SPRITE_FILENAMES.get(k, [k])))
        filenames = _COMPOSITE_SPRITE_FILENAMES.get(best_key, [best_key])
        png_fns = [f"{fn}.png" for fn in filenames]
        mapping[old_name] = limitless_name_from_filenames(png_fns)

    return mapping


def build_full_mapping(db_path: str) -> dict[str, str]:
    """Build mapping for ALL archetypes in a database.

    For mapped names: uses build_migration_mapping().
    For auto-derived names: uses _get_sprite_filenames() to reverse the name to
    filenames, then converts to Limitless style.
    'Unknown' stays 'Unknown'.
    """
    conn = sqlite3.connect(db_path)
    archetypes = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT archetype FROM placements ORDER BY archetype"
        ).fetchall()
    ]
    conn.close()

    base_mapping = build_migration_mapping()
    full: dict[str, str] = {}

    for old_name in archetypes:
        if old_name == "Unknown":
            full[old_name] = "Unknown"
        elif " / " in old_name:
            # Already in Limitless format — skip
            full[old_name] = old_name
        elif old_name in base_mapping:
            full[old_name] = base_mapping[old_name]
        else:
            # Auto-derived: reverse via legacy sprite filename derivation
            sprite_fns = _get_sprite_filenames_legacy(old_name)
            if sprite_fns:
                full[old_name] = limitless_name_from_filenames(sprite_fns)
            else:
                full[old_name] = old_name  # Keep as-is

    return full


def apply_migration(db_path: str, dry_run: bool = True) -> None:
    """Apply archetype name migration to a database."""
    mapping = build_full_mapping(db_path)
    conn = sqlite3.connect(db_path)

    changes = {old: new for old, new in mapping.items() if old != new}
    print(f"Database: {db_path}")
    print(f"Total archetypes: {len(mapping)}, changing: {len(changes)}")

    for old_name, new_name in sorted(changes.items()):
        count = conn.execute(
            "SELECT COUNT(*) FROM placements WHERE archetype = ?", (old_name,)
        ).fetchone()[0]
        print(f"  {old_name:<40} -> {new_name:<40} ({count})")

        if not dry_run:
            conn.execute(
                "UPDATE placements SET archetype = ? WHERE archetype = ?",
                (new_name, old_name),
            )

    if not dry_run:
        conn.commit()
        print(f"\nApplied {len(changes)} renames.")
    else:
        print("\nDry run -- no changes applied. Use --apply to execute.")

    conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate archetype names to Limitless style")
    parser.add_argument("--db", default="data/scout.db", help="Database path")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry run)")
    args = parser.parse_args()

    apply_migration(args.db, dry_run=not args.apply)
