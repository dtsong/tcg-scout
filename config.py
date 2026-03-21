"""Rotation Scout configuration constants."""

# Regulation marks that survive rotation (H = Temporal Forces onward)
ROTATION_LEGAL_REGULATION_MARKS = {"H", "I"}

# Fallback: explicit set codes if regulation marks are inconsistent
# SV5+ (Temporal Forces onward, including JP-only sets)
ROTATION_LEGAL_SETS = {
    # International sets
    "sv5",
    "sv5a",
    "sv6",
    "sv6a",
    "sv7",
    "sv7a",
    "sv8",
    "sv8a",
    # JP Mega Evolution sets
    "me01",
    "me02",
    "me02.5",
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
        "description": "Temporal Forces through Mega Evolution: Perfect Order",
        "db_name": "scout.db",
    },
    "ninja-spinner": {
        "name": "Ninja Spinner",
        "name_en": "Chaos Rising",
        "dataset_start": "2026-03-14",
        "dataset_end": "2026-05-22",
        "rotation_date": "2026-06-05",
        "description": "Temporal Forces through Mega Evolution: Chaos Rising",
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

# Minimum adoption percentage change (week-over-week) to classify as rising/falling.
TECH_TREND_THRESHOLD = 2.0

# Tech/meta cards tracked in the Weather Forecast.
# Non-archetype-defining cards whose adoption rates signal meta shifts.
TECH_CARD_WATCHLIST = {
    # Draw / search
    "Ultra Ball",
    "Buddy-Buddy Poffin",
    "Rare Candy",
    "Night Stretcher",
    "Pokégear 3.0",
    "Bug Catching Set",
    # Supporters
    "Boss's Orders",
    "Judge",
    "Crispin",
    "Lillie's Determination",
    "Dawn",
    "Cyrano",
    "Briar",
    "Hilda",
    "Lana's Aid",
    "Brock's Scouting",
    "Rosa's Encouragement",
    "Team Rocket's Petrel",
    "Ciphermaniac's Codebreaking",
    # Tools / Items
    "Poké Pad",
    "Energy Switch",
    "Switch",
    "Air Balloon",
    "Fighting Gong",
    # Stadiums
    "Jamming Tower",
    "Team Rocket's Watchtower",
    "Area Zero Underdepths",
    "Risky Ruins",
    "Battle Cage",
    # Energy
    "Unfair Stamp",  # ACE SPEC
    "Legacy Energy",  # ACE SPEC
    "Neo Upper Energy",  # ACE SPEC
    "Prime Catcher",  # ACE SPEC
    "Mist Energy",
    # Tech Pokemon
    "Shaymin",
    "Munkidori",
    "Solrock",
    "Lunatone",
    "Fezandipiti ex",
}

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

# Pokemon JP API: City League event_type values (3:N = City League Season N)
# Each season maps to a different competitive period within the championship year.
POKEMON_JP_CITY_LEAGUE_EVENT_TYPES = [
    "3:1",
    "3:2",
    "3:3",
    "3:4",
    "3:5",
    "3:6",
    "3:7",
    "3:8",
]

# TCGdex
TCGDEX_API_URL = "https://api.tcgdex.net/v2/en"

# Anchor cards for content-based archetype classification.
# Primary anchor -> secondary anchor -> archetype name.
# If primary matches but no secondary does, uses "_default".
ARCHETYPE_ANCHOR_CARDS: dict[str, dict[str, str] | str] = {
    # --- Standard archetypes ---
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
        "Grimmsnarl ex": "Froslass Grimmsnarl",
        "Grimmsnarl": "Froslass Grimmsnarl",
    },
    "Alakazam ex": {
        "_default": "Alakazam ex",
        "Dudunsparce": "Alakazam Dudunsparce",
    },
    # --- Mega Evolution archetypes (CL card names include "Mega" prefix) ---
    "Mega Froslass ex": {
        "_default": "Mega Froslass ex",
        "Grimmsnarl ex": "Mega Froslass Grimmsnarl",
        "Marnie's Grimmsnarl ex": "Mega Froslass Grimmsnarl",
        "Grimmsnarl": "Mega Froslass Grimmsnarl",
    },
    "Mega Absol ex": {
        "_default": "Mega Absol ex",
        "Mega Kangaskhan ex": "Mega Absol Box",
    },
    "Mega Kangaskhan ex": "Mega Kangaskhan ex",
    "Mega Lucario ex": {
        "_default": "Mega Lucario ex",
        "Solrock": "Mega Lucario Solrock",
        "Hariyama": "Mega Lucario",
    },
    "Mega Starmie ex": {
        "_default": "Mega Starmie ex",
        "Greninja ex": "Mega Starmie Greninja",
        "Dusknoir": "Mega Starmie Dusknoir",
    },
    "Mega Venusaur ex": {
        "_default": "Mega Venusaur ex",
        "Ogerpon ex": "Mega Venusaur",
    },
    "Mega Slowbro ex": "Mega Slowbro ex",
    "Mega Skarmory ex": "Mega Skarmory ex",
    # --- Trainer-owned Pokemon (CL uses "Trainer's Pokemon" naming) ---
    "Marnie's Grimmsnarl ex": {
        "_default": "Grimmsnarl ex",
        "Munkidori": "Grimmsnarl Munkidori",
        "Froslass": "Froslass Grimmsnarl",
    },
    "Cynthia's Garchomp ex": {
        "_default": "Garchomp Roserade",
        "Cynthia's Roserade": "Garchomp Roserade",
    },
    # --- Team Rocket archetypes ---
    "Team Rocket's Mewtwo ex": {
        "_default": "Mewtwo Spidops",
        "Team Rocket's Spidops": "Mewtwo Spidops",
    },
    "Team Rocket's Honchkrow": {
        "_default": "Honchkrow Porygon-Z",
    },
    # --- Non-ex variants (CL decklists may use non-ex forms) ---
    "Flareon ex": {
        "_default": "Flareon ex",
        "Noctowl": "Flareon Noctowl",
    },
    "Empoleon ex": {
        "_default": "Empoleon ex",
        "Steven's Metagross ex": "Empoleon Metagross",
    },
    "Alakazam": {
        "_default": "Alakazam ex",
        "Dudunsparce": "Alakazam Dudunsparce",
    },
    "Froslass": {
        "_default": "Froslass ex",
        "Munkidori": "Froslass Munkidori",
        "Grimmsnarl ex": "Froslass Grimmsnarl",
        "Marnie's Grimmsnarl ex": "Froslass Grimmsnarl",
        "Grimmsnarl": "Froslass Grimmsnarl",
    },
    "Zoroark": "Zoroark ex",
    # --- Support/rogue archetypes ---
    "Arboliva ex": {
        "_default": "Arboliva ex",
        "Meganium": "Arboliva Meganium",
    },
    "Crustle": "Crustle",
    "Dwebble": "Crustle",
}

# LLM configuration for auto-generated reports
REPORT_LLM_MODEL = "claude-haiku-4-5-20251001"
REPORT_LLM_TEMPERATURE = 0.3
REPORT_LLM_MAX_TOKENS = 2048
