"""Simplified archetype normalizer adapted from TrainerLab.

Uses sprite-based detection (sprite_lookup + auto_derive) only.
No DB, no signature card detection, no text label stage.
"""

import re

LIMITLESS_SPRITE_CDN = "https://r2.limitlesstcg.net/pokemon/gen9"

# Composite sprite keys that map to multiple filenames.
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
    "iron-valiant": ["iron-valiant"],
    "iron-hands": ["iron-hands"],
    "raging-bolt": ["raging-bolt"],
    "roaring-moon": ["roaring-moon"],
    "chien-pao": ["chien-pao"],
    "porygon-z": ["porygon-z"],
}

# Known sprite-key -> canonical archetype name
SPRITE_ARCHETYPE_MAP: dict[str, str] = {
    # Charizard variants
    "charizard": "Charizard ex",
    "charizard-pidgeot": "Charizard ex",
    "charizard-dusknoir": "Charizard ex",
    # Dragapult variants
    "dragapult": "Dragapult ex",
    "dragapult-pidgeot": "Dragapult ex",
    # Gardevoir
    "gardevoir": "Gardevoir ex",
    # Raging Bolt
    "raging-bolt": "Raging Bolt ex",
    "ogerpon-raging-bolt": "Raging Bolt ex",
    # Gholdengo
    "gholdengo": "Gholdengo ex",
    # Terapagos
    "terapagos": "Terapagos ex",
    # Archaludon
    "archaludon": "Archaludon ex",
    # Pidgeot Control
    "pidgeot": "Pidgeot ex Control",
    # Miraidon
    "miraidon": "Miraidon ex",
    # Koraidon
    "koraidon": "Koraidon ex",
    # Iron Hands
    "iron-hands": "Iron Hands ex",
    # Iron Valiant
    "iron-valiant": "Iron Valiant ex",
    # Roaring Moon
    "roaring-moon": "Roaring Moon ex",
    # Chien-Pao
    "chien-pao": "Chien-Pao ex",
    "baxcalibur-chien-pao": "Chien-Pao ex",
    # Lost Zone
    "comfey-giratina": "Lost Zone Giratina",
    "comfey-sableye": "Lost Zone Box",
    # Mega Evolution archetypes
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
    # Current JP meta
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
    # Multi-sprite composites (JP meta)
    "absol-mega-kangaskhan-mega": "Mega Absol Box",
    "noctowl-ogerpon-wellspring": "Tera Box",
    "joltik-pikachu": "Joltik Box",
    "armarouge-ho-oh": "Ho-Oh Armarouge",
    # JP post-rotation Mega composites
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
    # JP post-rotation non-Mega composites
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

_FILENAME_RE = re.compile(r"/([a-zA-Z0-9_-]+)\.png")


def _sprite_key_to_filenames(key: str) -> list[str]:
    """Convert a sprite key to a list of sprite filenames."""
    if not key:
        return []
    return _COMPOSITE_SPRITE_FILENAMES.get(key, [key])


def _split_mega_aware(sprite_key: str) -> list[str]:
    """Split an unknown composite sprite key using -mega as a boundary."""
    parts = sprite_key.split("-")
    if "mega" not in parts:
        return [sprite_key]

    filenames: list[str] = []
    i = 0
    while i < len(parts):
        if i + 1 < len(parts) and parts[i + 1] == "mega":
            filenames.append(f"{parts[i]}-mega")
            i += 2
        else:
            filenames.append(parts[i])
            i += 1
    return filenames


def build_sprite_key(sprite_urls: list[str]) -> str:
    """Build a canonical sprite key from image URLs.

    Extracts filename stems, lowercases, sorts alphabetically, joins with hyphens.
    """
    names: list[str] = []
    for url in sprite_urls:
        match = _FILENAME_RE.search(url)
        if match:
            name = match.group(1).lower().replace("_", "-")
            names.append(name)
    names.sort()
    return "-".join(names)


def _derive_name_from_key(sprite_key: str) -> str:
    """Derive a human-readable archetype name from a sprite key."""
    if not sprite_key:
        return ""

    filenames = _sprite_key_to_filenames(sprite_key)
    if len(filenames) == 1 and filenames[0] == sprite_key:
        filenames = _split_mega_aware(sprite_key)

    mega_names: list[str] = []
    regular_names: list[str] = []
    for fn in filenames:
        if fn.endswith("-mega"):
            base = fn[:-5]
            name = " ".join(p.capitalize() for p in base.split("-"))
            mega_names.append(f"Mega {name}")
        else:
            name = " ".join(p.capitalize() for p in fn.split("-"))
            regular_names.append(name)

    return " ".join(mega_names + regular_names)


def normalize_archetype(sprite_urls: list[str], html_archetype: str = "") -> str:
    """Resolve archetype name from sprite URLs with optional HTML text fallback.

    Priority: sprite_lookup -> auto_derive -> html_archetype -> "Unknown"
    """
    if sprite_urls:
        key = build_sprite_key(sprite_urls)
        if key:
            # Priority 1: known sprite mapping
            if key in SPRITE_ARCHETYPE_MAP:
                return SPRITE_ARCHETYPE_MAP[key]
            # Priority 2: auto-derive from key
            derived = _derive_name_from_key(key)
            if derived:
                return derived

    # Fallback to HTML text
    if html_archetype and html_archetype.strip():
        return html_archetype.strip()

    return "Unknown"


def classify_from_decklist(cards: list[dict]) -> str:
    """Classify archetype from decklist card contents.

    Uses content-based anchor card detection.
    Falls back to "Unknown" if no anchor cards match.
    """
    from analysis.archetype_classifier import classify_decklist

    return classify_decklist(cards)
