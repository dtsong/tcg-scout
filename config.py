"""Rotation Scout configuration constants."""

# Regulation marks that survive rotation (H = Temporal Forces onward)
ROTATION_LEGAL_REGULATION_MARKS = {"H", "I"}

# Fallback: explicit set codes if regulation marks are inconsistent
# SV5+ (Temporal Forces onward, including JP-only sets)
ROTATION_LEGAL_SETS = {
    # International sets
    "sv5", "sv5a", "sv6", "sv6a", "sv7", "sv7a", "sv8", "sv8a",
    # JP Mega Evolution sets
    "me01", "me02", "me02.5",
    # Promos
    "svp",
}

# --- Format registry ---
FORMATS = {
    "nihil-zero": {
        "name": "Nihil Zero",
        "name_en": "Perfect Order",
        "dataset_start": "2026-01-23",
        "dataset_end": "2026-03-13",
        "rotation_date": "2026-04-10",
        "description": "Temporal Forces through Perfect Order + Mega Evolution sets",
        "db_name": "nihil-zero.db",
    },
    "ninja-spinner": {
        "name": "Ninja Spinner",
        "name_en": "Chaos Rising",
        "dataset_start": "2026-03-14",
        "dataset_end": "2026-05-22",
        "rotation_date": "2026-04-10",
        "description": "Temporal Forces through Chaos Rising + Mega Evolution sets",
        "db_name": "ninja-spinner.db",
    },
}

DEFAULT_FORMAT = "nihil-zero"


def get_format_config(format_slug: str) -> dict:
    """Get configuration for a format by slug. Raises KeyError if not found."""
    if format_slug not in FORMATS:
        raise KeyError(f"Unknown format: {format_slug!r}. Available: {list(FORMATS.keys())}")
    return FORMATS[format_slug]


# Dataset window — JP City League results (backward compat, delegates to default format)
DATASET_START = FORMATS[DEFAULT_FORMAT]["dataset_start"]
DATASET_END = FORMATS[DEFAULT_FORMAT]["dataset_end"]
ROTATION_DATE = FORMATS[DEFAULT_FORMAT]["rotation_date"]

# Tier thresholds (meta share percentage)
TIER_THRESHOLDS = {
    "S": 15.0,
    "A": 8.0,
    "B": 3.0,
    "C": 1.0,
    # Below C = Rogue
}

# Tier weights for buy list priority scoring
TIER_WEIGHTS = {
    "S": 5,
    "A": 3,
    "B": 1,
    "C": 0,
    "Rogue": 0,
}

# Placement weights for performance-weighted tier scoring (City League, 64-player)
PLACEMENT_WEIGHTS = {
    1: 3.0,
    2: 2.5,
    3: 2.0,
    4: 2.0,
    5: 1.5,
    6: 1.5,
    7: 1.5,
    8: 1.5,
    9: 1.2,
    10: 1.2,
    11: 1.2,
    12: 1.2,
    13: 1.2,
    14: 1.2,
    15: 1.2,
    16: 1.2,
}
# Default weight for standings beyond top 16
PLACEMENT_WEIGHT_DEFAULT = 1.0

# Champions League weighting multiplier (7000-player field)
CL_WEIGHT_MULTIPLIER = {
    "masters": 5.0,
    "seniors": 2.0,
    "juniors": 2.0,
}

# Core card thresholds
CORE_INCLUSION_RATE = 0.75
CORE_AVG_COPIES_POKEMON = 3
CORE_AVG_COPIES_OTHER = 2  # Trainers and Energy

# Scraping
LIMITLESS_BASE_URL = "https://limitlesstcg.com"
LIMITLESS_REQUESTS_PER_MINUTE = 25
LIMITLESS_TIMEOUT = 30.0
LIMITLESS_MAX_RETRIES = 3

# TCGdex
TCGDEX_API_URL = "https://api.tcgdex.net/v2/en"

# Anchor cards for content-based archetype classification.
# Primary anchor -> secondary anchor -> archetype name.
# If primary matches but no secondary does, uses "_default".
ARCHETYPE_ANCHOR_CARDS: dict[str, dict[str, str] | str] = {
    "Charizard ex": {
        "_default": "Charizard ex",
        "Dusknoir": "Charizard Dusknoir",
    },
    "Dragapult ex": {
        "_default": "Dragapult ex",
        "Pidgeot ex": "Dragapult ex",
        "Dusknoir": "Dragapult Dusknoir",
        "Noctowl": "Dragapult Noctowl",
    },
    "Gardevoir ex": "Gardevoir ex",
    "Raging Bolt ex": "Raging Bolt ex",
    "Gholdengo ex": "Gholdengo ex",
    "Terapagos ex": "Terapagos ex",
    "Archaludon ex": "Archaludon ex",
    "Miraidon ex": "Miraidon ex",
    "Grimmsnarl ex": {
        "_default": "Grimmsnarl ex",
        "Munkidori": "Grimmsnarl Munkidori",
    },
    "Froslass ex": {
        "_default": "Froslass ex",
        "Munkidori": "Froslass Munkidori",
        "Grimmsnarl": "Froslass Grimmsnarl",
    },
    "Alakazam ex": {
        "_default": "Alakazam ex",
        "Dudunsparce": "Alakazam Dudunsparce",
    },
    "Lucario ex": {
        "_default": "Mega Lucario ex",
        "Solrock": "Mega Lucario Solrock",
    },
    "Starmie ex": {
        "_default": "Mega Starmie ex",
        "Greninja ex": "Mega Starmie Greninja",
        "Dusknoir": "Mega Starmie Dusknoir",
    },
    "Venusaur ex": {
        "_default": "Mega Venusaur ex",
        "Ogerpon ex": "Mega Venusaur",
    },
}
