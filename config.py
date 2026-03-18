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

# Dataset window — JP City League results
DATASET_START = "2026-01-23"
DATASET_END = "2026-03-13"
ROTATION_DATE = "2026-04-10"

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
