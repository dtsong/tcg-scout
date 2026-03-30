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

# Breakout score thresholds for Rogue Spotlight
BREAKOUT_THRESHOLD = 50  # Minimum score (0-100) to qualify for Rogue Spotlight
BREAKOUT_DISPLAY_COUNT = 3  # Max rogues shown in spotlight

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

# Limitless tournament URLs for Champions League events
CL_TOURNAMENT_IDS = {
    "https://limitlesstcg.com/tournaments/547",  # Fukuoka CL 2026
    "https://limitlesstcg.com/tournaments/548",  # Osaka CL 2026
}

# CL boost factor for Optimal 60 computation
CL_BOOST_FACTOR = CL_WEIGHT_MULTIPLIER["masters"]  # 5.0

# Core card thresholds
CORE_INCLUSION_RATE = 0.75
CORE_AVG_COPIES_POKEMON = 3
CORE_AVG_COPIES_OTHER = 2  # Trainers and Energy

# Scraping — JP City League (limitlesstcg.com)
LIMITLESS_BASE_URL = "https://limitlesstcg.com"
LIMITLESS_REQUESTS_PER_MINUTE = 25
LIMITLESS_TIMEOUT = 30.0
LIMITLESS_MAX_RETRIES = 3

# Scraping — Labs Limitless (international tournament data)
LABS_BASE_URL = "https://limitlesstcg.com"  # Main site for metadata + decklists; Labs standings use labs.limitlesstcg.com
LABS_REQUESTS_PER_MINUTE = 20
LABS_TIMEOUT = 30.0
LABS_MAX_RETRIES = 3

# Labs matchup analysis thresholds
LABS_MIN_MATCHES_TO_PUBLISH = 30  # Minimum H2H matches for credible win rate
LABS_MIN_ENCOUNTERS_TO_PUBLISH = 5  # Minimum weighted encounters for record-based fallback
LABS_CI_Z = 1.96  # z-score for 95% confidence interval (used in Wilson and Wald CIs)

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
    # --- Mega Greninja (must precede Dragapult ex — Greninja line is primary attacker) ---
    "Mega Greninja ex": {
        "_default": "Greninja-Mega",
        "Dragapult ex": "Dragapult / Greninja-Mega",
        "Dudunsparce": "Dudunsparce / Greninja-Mega",
        "Dusknoir": "Dusknoir / Greninja-Mega",
        "Mega Starmie ex": "Greninja-Mega / Starmie-Mega",
        "Noctowl": "Greninja-Mega / Noctowl",
        "Mega Kangaskhan ex": "Greninja-Mega / Kangaskhan-Mega",
        "Munkidori": "Greninja-Mega / Munkidori",
    },
    # --- Standard archetypes ---
    "Charizard ex": {
        "_default": "Charizard",
        "Pidgeot ex": "Charizard / Pidgeot",
        "Dusknoir": "Charizard / Dusknoir",
    },
    "Dragapult ex": {
        "_default": "Dragapult",
        "Pidgeot ex": "Dragapult / Pidgeot",
        "Dusknoir": "Dragapult / Dusknoir",
        "Noctowl": "Dragapult / Noctowl",
        "Blaziken ex": "Blaziken / Dragapult",
        "Typhlosion": "Dragapult / Typhlosion",
    },
    "Gardevoir ex": "Gardevoir",
    "Raging Bolt ex": "Ogerpon / Raging-Bolt",
    "Gholdengo ex": "Gholdengo",
    "Terapagos ex": "Terapagos",
    "Archaludon ex": "Archaludon",
    "Miraidon ex": "Miraidon",
    "Grimmsnarl ex": {
        "_default": "Grimmsnarl",
        "Munkidori": "Grimmsnarl / Munkidori",
    },
    "Froslass ex": {
        "_default": "Froslass",
        "Munkidori": "Froslass / Munkidori",
        "Grimmsnarl ex": "Froslass / Grimmsnarl",
        "Grimmsnarl": "Froslass / Grimmsnarl",
    },
    "Alakazam ex": {
        "_default": "Alakazam",
        "Dudunsparce": "Alakazam / Dudunsparce",
    },
    # --- Mega Evolution archetypes (CL card names include "Mega" prefix) ---
    "Mega Froslass ex": {
        "_default": "Froslass-Mega",
        "Grimmsnarl ex": "Froslass-Mega / Grimmsnarl",
        "Marnie's Grimmsnarl ex": "Froslass-Mega / Grimmsnarl",
        "Grimmsnarl": "Froslass-Mega / Grimmsnarl",
    },
    "Mega Absol ex": {
        "_default": "Absol-Mega",
        "Mega Kangaskhan ex": "Absol-Mega / Kangaskhan-Mega",
    },
    "Mega Kangaskhan ex": {
        "_default": "Kangaskhan-Mega",
        "Latias ex": "Kangaskhan-Mega / Latias",
        "Teal Mask Ogerpon ex": "Kangaskhan-Mega / Ogerpon",
    },
    "Mega Lucario ex": {
        "_default": "Lucario-Mega",
        "Solrock": "Lucario-Mega / Solrock",
        "Hariyama": "Hariyama / Lucario-Mega",
    },
    "Mega Starmie ex": {
        "_default": "Starmie-Mega",
        "Greninja ex": "Greninja / Starmie-Mega",
        "Dusknoir": "Dusknoir / Starmie-Mega",
    },
    "Mega Venusaur ex": {
        "_default": "Venusaur-Mega",
        "Ogerpon ex": "Ogerpon / Venusaur-Mega",
    },
    "Mega Slowbro ex": "Slowbro-Mega",
    "Mega Skarmory ex": "Skarmory-Mega",
    # --- Trainer-owned Pokemon (CL uses "Trainer's Pokemon" naming) ---
    "Marnie's Grimmsnarl ex": {
        "_default": "Grimmsnarl",
        "Munkidori": "Grimmsnarl / Munkidori",
        "Froslass": "Froslass / Grimmsnarl",
    },
    "Cynthia's Garchomp ex": {
        "_default": "Garchomp / Roserade",
        "Cynthia's Roserade": "Garchomp / Roserade",
    },
    # --- Team Rocket archetypes ---
    "Team Rocket's Mewtwo ex": {
        "_default": "Mewtwo / Spidops",
        "Team Rocket's Spidops": "Mewtwo / Spidops",
    },
    "Team Rocket's Honchkrow": {
        "_default": "Honchkrow / Porygon-Z",
    },
    "N's Zoroark ex": {
        "_default": "Darmanitan / Zoroark",
        "N's Darmanitan": "Darmanitan / Zoroark",
    },
    # --- Non-ex variants (CL decklists may use non-ex forms) ---
    "Flareon ex": {
        "_default": "Flareon",
        "Noctowl": "Flareon / Noctowl",
    },
    "Empoleon ex": {
        "_default": "Empoleon",
        "Steven's Metagross ex": "Empoleon / Metagross",
    },
    "Alakazam": {
        "_default": "Alakazam",
        "Dudunsparce": "Alakazam / Dudunsparce",
    },
    "Froslass": {
        "_default": "Froslass",
        "Munkidori": "Froslass / Munkidori",
        "Grimmsnarl ex": "Froslass / Grimmsnarl",
        "Marnie's Grimmsnarl ex": "Froslass / Grimmsnarl",
        "Grimmsnarl": "Froslass / Grimmsnarl",
    },
    "Zoroark": "Zoroark",
    # --- Support/rogue archetypes ---
    "Dipplin": {
        "_default": "Dipplin / Thwackey",
        "Thwackey": "Dipplin / Thwackey",
        "Rillaboom": "Dipplin / Rillaboom",
    },
    "Arboliva ex": {
        "_default": "Arboliva",
        "Meganium": "Arboliva / Meganium",
        "Beedrill ex": "Arboliva / Beedrill",
    },
    "Crustle": "Crustle",
    "Dwebble": "Crustle",
    # --- Ninja Spinner format anchors ---
    "Ceruledge ex": {
        "_default": "Ceruledge",
        "Solrock": "Ceruledge / Solrock",
    },
    "Barbaracle": "Barbaracle / Okidogi",
    "Mega Diancie ex": {
        "_default": "Diancie-Mega",
        "Dusknoir": "Diancie-Mega / Dusknoir",
        "Mega Slowbro ex": "Diancie-Mega / Slowbro-Mega",
    },
    "Jellicent ex": "Jellicent",
    "Cornerstone Mask Ogerpon ex": "Ogerpon-Cornerstone",
    "Teal Mask Ogerpon ex": {
        "_default": "Ogerpon-Teal",
        "Hydrapple ex": "Hydrapple / Ogerpon-Teal",
    },
    "Slowking": "Slowking",
    "Hop's Zacian ex": "Hop's Zacian ex",
    "Mega Sharpedo ex": "Sharpedo-Mega",
    "Mega Lopunny ex": "Lopunny-Mega",
    "Mega Yanmega ex": "Yanmega-Mega",
    "Mega Gardevoir ex": "Gardevoir-Mega",
    "Mega Mawile ex": "Mawile-Mega",
    "Mega Heracross ex": "Heracross-Mega",
    "Mega Gengar ex": "Gengar-Mega",
    "Mega Dragalge ex": "Dragalge-Mega",
    "Mega Clefable ex": "Clefable-Mega",
    "Mega Meganium ex": "Meganium-Mega",
    "Ethan's Typhlosion": "Ethan's Typhlosion",
    "Genesect ex": {
        "_default": "Genesect",
        "Metagross": "Genesect / Metagross",
    },
    "Decidueye ex": "Decidueye",
    "Pikachu ex": "Pikachu",
    "Aegislash": "Aegislash",
    "Regigigas": "Regigigas",
    "Hydrapple ex": "Hydrapple",
    "Leafeon ex": "Leafeon",
    "Flygon ex": "Flygon",
    "Cinccino ex": "Cinccino",
    "Gourgeist ex": "Gourgeist",
    "Farigiraf ex": "Farigiraf",
    "Hydreigon ex": "Hydreigon",
    "Reshiram ex": "Reshiram",
    "Misty's Gyarados": "Misty's Gyarados",
}

# JP card name -> EN card name mapping for classifying JP City League decklists.
# Only includes names that appear in ARCHETYPE_ANCHOR_CARDS (primary + secondary).
JP_CARD_NAME_MAP: dict[str, str] = {
    # --- Primary anchor cards (ex Pokemon) ---
    "リザードンex": "Charizard ex",
    "ドラパルトex": "Dragapult ex",
    "タケルライコex": "Raging Bolt ex",
    "テラパゴスex": "Terapagos ex",
    "ブリジュラスex": "Archaludon ex",
    "ミライドンex": "Miraidon ex",
    "サーナイトex": "Gardevoir ex",
    "サーフゴーex": "Gholdengo ex",
    "ブースターex": "Flareon ex",
    "ソウブレイズex": "Ceruledge ex",
    "エンペルトex": "Empoleon ex",
    "オリーヴァex": "Arboliva ex",
    "バシャーモex": "Blaziken ex",
    # Mega anchors
    "メガユキメノコex": "Mega Froslass ex",
    "メガアブソルex": "Mega Absol ex",
    "メガガルーラex": "Mega Kangaskhan ex",
    "メガルカリオex": "Mega Lucario ex",
    "メガゲッコウガex": "Mega Greninja ex",
    "メガスターミーex": "Mega Starmie ex",
    "メガフシギバナex": "Mega Venusaur ex",
    "メガヤドランex": "Mega Slowbro ex",
    "メガエアームドex": "Mega Skarmory ex",
    "メガミミロップex": "Mega Lopunny ex",
    "メガサーナイトex": "Mega Gardevoir ex",
    "メガサメハダーex": "Mega Sharpedo ex",
    "メガディアンシーex": "Mega Diancie ex",
    "メガメガニウムex": "Mega Meganium ex",
    # Trainer-owned anchors
    "マリィのオーロンゲex": "Marnie's Grimmsnarl ex",
    "シロナのガブリアスex": "Cynthia's Garchomp ex",
    "ロケット団のミュウツーex": "Team Rocket's Mewtwo ex",
    "ダイゴのメタグロスex": "Steven's Metagross ex",
    "ロケット団のドンカラス": "Team Rocket's Honchkrow",
    "Nのゾロアークex": "N's Zoroark ex",
    "Nのヒヒダルマ": "N's Darmanitan",
    # Ninja Spinner format anchors
    "モモワロウex": "Pecharunt ex",
    "ブルンゲルex": "Jellicent ex",
    "カジッチュ": "Dipplin",
    "メガヤンマex": "Mega Yanmega ex",
    "メガクチートex": "Mega Mawile ex",
    "メガヘラクロスex": "Mega Heracross ex",
    "メガゲンガーex": "Mega Gengar ex",
    "カミッチュex": "Hydrapple ex",
    "リーフィアex": "Leafeon ex",
    "ホップのザシアンex": "Hop's Zacian ex",
    "カプ・コケコex": "Tapu Koko ex",
    "ピカチュウex": "Pikachu ex",
    "ゲノセクトex": "Genesect ex",
    "ヤドキング": "Slowking",
    "キチキギスex": "Fezandipiti ex",
    "スピアーex": "Beedrill ex",
    "ラティアスex": "Latias ex",
    "オーガポン いしずえのめんex": "Cornerstone Mask Ogerpon ex",
    "イツキのバクフーン": "Ethan's Typhlosion",
    "ジュナイパーex": "Decidueye ex",
    "ドラミドロex": "Mega Dragalge ex",
    "ピッピex": "Mega Clefable ex",
    "チンチラex": "Cinccino ex",
    "カボチャex": "Gourgeist ex",
    "レシラムex": "Reshiram ex",
    "カスミのギャラドス": "Misty's Gyarados",
    # --- Secondary cards (non-ex, used in composite detection) ---
    "ヨノワール": "Dusknoir",
    "ヨルノズク": "Noctowl",
    "ピジョットex": "Pidgeot ex",  # Not in Ninja Spinner; only Nihil Zero
    "ノココッチ": "Dudunsparce",
    "マシマシラ": "Munkidori",
    "ソルロック": "Solrock",
    "ハリテヤマ": "Hariyama",
    "ゲッコウガex": "Greninja ex",
    "オーガポン みどりのめんex": "Teal Mask Ogerpon ex",
    "シロナのロズレイド": "Cynthia's Roserade",
    "ロケット団のワナイダー": "Team Rocket's Spidops",
    "ロケット団のポリゴンZ": "Porygon-Z",
    "メガニウム": "Meganium",
    "バチンキー": "Thwackey",
    "ゴリランダー": "Rillaboom",
    "メタグロス": "Metagross",
    "ガケガニ": "Klawf",
    # Non-ex anchor variants
    "ユキメノコ": "Froslass",
    "ユキメノコex": "Froslass ex",
    "オーロンゲ": "Grimmsnarl",
    "オーロンゲex": "Grimmsnarl ex",
    "ゾロアーク": "Zoroark",
    "フーディン": "Alakazam",
    "フーディンex": "Alakazam ex",
    "イワパレス": "Crustle",
    "イシズマイ": "Dwebble",
}

# LLM configuration for auto-generated reports
REPORT_LLM_MODEL = "claude-haiku-4-5-20251001"
REPORT_LLM_TEMPERATURE = 0.3
REPORT_LLM_MAX_TOKENS = 2048
