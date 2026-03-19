"""JSON export for Scout Web — generates static data files for the Next.js dashboard."""

import json
import logging
import re
import sqlite3
import urllib.request
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from analysis.archetype import _COMPOSITE_SPRITE_FILENAMES, SPRITE_ARCHETYPE_MAP
from analysis.archetype_classifier import classify_decklist
from analysis.buylist import generate_buylist
from analysis.card_stats import (
    BASIC_ENERGY_NAMES,
    build_category_lookup,
    classify_card,
    compute_card_detail,
    compute_card_stats,
)
from analysis.evolution import compute_archetype_evolution, compute_meta_evolution
from analysis.matchup import compute_matchup_matrix
from analysis.meta import get_latest_snapshot
from analysis.synergy import compute_archetype_overlap_matrix, compute_synergy_pairs
from config import (
    DATASET_END,
    DATASET_START,
    DEFAULT_FORMAT,
    FORMATS,
    PLACEMENT_WEIGHT_DEFAULT,
    PLACEMENT_WEIGHTS,
    ROTATION_DATE,
    TIER_THRESHOLDS,
    get_format_config,
)

# Time windows for pre-computed date-filtered exports
TIME_WINDOWS = {"7d": 7, "30d": 30}

logger = logging.getLogger(__name__)

# Default output directory (web/public/data/)
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "web" / "public" / "data"


# BASIC_ENERGY_NAMES imported from analysis.card_stats (canonical definition)


def _basic_energy_exclusion_sql() -> str:
    """Return SQL WHERE clause fragment to exclude basic energy."""
    placeholders = ",".join("?" * len(BASIC_ENERGY_NAMES))
    return f"dc.card_name NOT IN ({placeholders})"


def _basic_energy_params() -> list[str]:
    """Return params list for basic energy exclusion."""
    return sorted(BASIC_ENERGY_NAMES)


# Known ACE SPEC card names
ACE_SPEC_CARDS = {
    "Prime Catcher",
    "Hero's Cape",
    "Master Ball",
    "Maximum Belt",
    "Reboot Pod",
    "Survival Brace",
    "Unfair Stamp",
    "Sparkling Crystal",
    "Deluxe Bomb",
    "Neo Upper Energy",
    "Legacy Energy",
    "Awakening Drum",
    "Grand Tree",
    "Dangerous Laser",
    "Secret Box",
    "Poké Vital A",
    "Miracle Headset",
    "Amulet of Hope",
    "Hyper Aroma",
}

# Base JP→EN card name map. Entries here are overridden by the cards table and card_mappings table at runtime in _build_jp_en_lookup.
JP_CARD_NAMES: dict[str, str] = {
    # --- Pokemon ---
    "イシズマイ": "Dwebble",
    "イベルタル": "Yveltal",
    "イワパレス": "Crustle",
    "イーブイ": "Eevee",
    "イーブイex": "Eevee ex",
    "エンペルトex": "Empoleon ex",
    "エーフィex": "Espeon ex",
    "オリーニョ": "Dolliv",
    "オリーヴァex": "Arboliva ex",
    "オーガポン いしずえのめんex": "Ogerpon ex",
    "オーガポン いどのめんex": "Ogerpon ex",
    "オーガポン かまどのめんex": "Ogerpon ex",
    "オーガポン みどりのめんex": "Ogerpon ex",
    "カプ・コケコex": "Tapu Koko ex",
    "ガチグマ アカツキex": "Ursaluna ex",
    "キチキギス": "Fezandipiti",
    "キチキギスex": "Fezandipiti ex",
    "キュレム": "Kyurem",
    "ケーシィ": "Abra",
    "ゲノセクト": "Genesect",
    "ゲノセクトex": "Genesect ex",
    "コダック": "Psyduck",
    "コノヨザル": "Annihilape",
    "サマヨール": "Dusclops",
    "シェイミ": "Shaymin",
    "シャリタツ": "Tatsugiri",
    "シロナのガバイト": "Cynthia's Gabite",
    "シロナのガブリアスex": "Cynthia's Garchomp ex",
    "シロナのフカマル": "Cynthia's Gible",
    "シロナのミカルゲ": "Cynthia's Spiritomb",
    "シロナのロズレイド": "Cynthia's Roserade",
    "シロナのロゼリア": "Cynthia's Roselia",
    "スピンロトム": "Fan Rotom",
    "スボミー": "Budew",
    "ソルロック": "Solrock",
    "ゾロアーク": "Zoroark",
    "タケルライコ": "Raging Bolt",
    "タケルライコex": "Raging Bolt ex",
    "ダイゴのダンバル": "Steven's Beldum",
    "ダイゴのメタグロスex": "Steven's Metagross ex",
    "ダイゴのメタング": "Steven's Metang",
    "チコリータ": "Chikorita",
    "テツノイサハex": "Iron Leaves ex",
    "テラパゴスex": "Terapagos ex",
    "ドラパルトex": "Dragapult ex",
    "ドラメシヤ": "Dreepy",
    "ドロンチ": "Drakloak",
    "ニャースex": "Meowth ex",
    "ノココッチ": "Dudunsparce",
    "ノコッチ": "Dunsparce",
    "ハリテヤマ": "Hariyama",
    "バチュル": "Joltik",
    "パオジアン": "Chien-Pao",
    "フーディン": "Alakazam",
    "ブースターex": "Flareon ex",
    "ベイリーフ": "Bayleef",
    "ホーホー": "Hoothoot",
    "ポッチャマ": "Piplup",
    "マクノシタ": "Makuhita",
    "マシマシラ": "Munkidori",
    "マリィのオーロンゲex": "Marnie's Grimmsnarl ex",
    "マリィのギモー": "Marnie's Morgrem",
    "マリィのベロバー": "Marnie's Impidimp",
    "ミニーブ": "Smoliv",
    "ムチュール": "Smoochum",
    "メガアブソルex": "Mega Absol ex",
    "メガエアームドex": "Mega Skarmory ex",
    "メガガルーラex": "Mega Kangaskhan ex",
    "メガジガルデex": "Mega Zygarde ex",
    "メガニウム": "Meganium",
    "メガヤドランex": "Mega Slowbro ex",
    "メガユキメノコex": "Mega Froslass ex",
    "メガルカリオex": "Mega Lucario ex",
    "ヤドキング": "Slowking",
    "ヤドン": "Slowpoke",
    "ユキメノコ": "Froslass",
    "ユキワラシ": "Snorunt",
    "ユンゲラー": "Kadabra",
    "ヨノワール": "Dusknoir",
    "ヨマワル": "Duskull",
    "ヨルノズク": "Noctowl",
    "ラティアスex": "Latias ex",
    "リオル": "Riolu",
    "リーフィアex": "Leafeon ex",
    "リーリエのピッピex": "Lillie's Clefairy ex",
    "ルナトーン": "Lunatone",
    "ロケット団のタマンチュラ": "Team Rocket's Tarountula",
    "ロケット団のドンカラス": "Team Rocket's Honchkrow",
    "ロケット団のフリーザー": "Team Rocket's Articuno",
    "ロケット団のポリゴン": "Team Rocket's Porygon",
    "ロケット団のポリゴン2": "Team Rocket's Porygon2",
    "ロケット団のミミッキュ": "Team Rocket's Mimikyu",
    "ロケット団のミュウツーex": "Team Rocket's Mewtwo ex",
    "ロケット団のヤミカラス": "Team Rocket's Murkrow",
    "ロケット団のワナイダー": "Team Rocket's Spidops",
    "ローブシン": "Conkeldurr",
    # --- Trainers ---
    "ネストボール": "Nest Ball",
    "ハイパーボール": "Ultra Ball",
    "なかよしポフィン": "Buddy-Buddy Poffin",
    "ボスの指令": "Boss's Orders",
    "ナンジャモ": "Iono",
    "博士の研究": "Professor's Research",
    "ふしぎなアメ": "Rare Candy",
    "夜のタンカ": "Night Stretcher",
    "すごいつりざお": "Super Rod",
    "大地の器": "Earthen Vessel",
    "カウンターキャッチャー": "Counter Catcher",
    "ポケモンいれかえ": "Switch",
    "あなぬけのヒモ": "Escape Rope",
    "エネルギー回収": "Energy Retrieval",
    "ジャッジマン": "Judge",
    "ペパー": "Pepper",
    "シロナの覇気": "Cynthia's Ambition",
    "ビワ": "Biwa",
    "ツツジ": "Roxanne",
    "セイボリー": "Avery",
    "ともだちてちょう": "Pal Pad",
    "リーリエのおねがい": "Lillie's Determination",
    "Nの筋書き": "N's Scenario",
    "からておうの稽古": "Karate Chop Training",
    "きらめく結晶(ACE SPEC)": "Sparkling Crystal",
    "せいなるはい": "Sacred Ash",
    "ふうせん": "Air Balloon",
    "むしとりセット": "Bug Catching Set",
    "アオキの手際": "Aoki's Skill",
    "アカマツ": "Akamatsu",
    "アクロマの執念": "Colress's Tenacity",
    "アンフェアスタンプ(ACE SPEC)": "Unfair Stamp",
    "エキサイトスタジアム": "Excite Stadium",
    "エネルギーつけかえ": "Energy Switch",
    "エネルギーリサイクル": "Energy Recycler",
    "エネルギー転送": "Energy Search",
    "ガラスのラッパ": "Glass Trumpet",
    "クセロシキのたくらみ": "Xerosic's Scheme",
    "クラウン": "Crown",
    "グラビティーマウンテン": "Gravity Mountain",
    "サーファー": "Surfer",
    "シアノ": "Ciano",
    "シークレットボックス(ACE SPEC)": "Secret Box",
    "ジャミングタワー": "Jamming Tower",
    "ジャンボアイス": "Jumbo Ice",
    "スイレンのお世話": "Lana's Care",
    "スグリ": "Kieran",
    "スパイクタウンジム": "Spikemuth Gym",
    "ゼイユ": "Carmine",
    "ゼロの大空洞": "Area Zero Underdepths",
    "タケシのスカウト": "Brock's Scout",
    "ツールスクラッパー": "Tool Scrapper",
    "テラスタルオーブ": "Tera Orb",
    "テレパス超エネルギー": "Telepathy Psychic Energy",
    "トウコ": "Hilda",
    "パワープロテイン": "Power Protein",
    "ヒカリ": "Dawn",
    "ヒーローマント(ACE SPEC)": "Hero's Cape",
    "ピュール": "Puelle",
    "ファイトゴング": "Fighting Gong",
    "ブライア": "Briar",
    "プレシャスキャリー(ACE SPEC)": "Precious Carry",
    "ポケギア3.0": "Pokegear 3.0",
    "ポケパッド": "Poke Pad",
    "ポケモン回収サイクロン(ACE SPEC)": "Scoop Up Cyclone",
    "マキシマムベルト(ACE SPEC)": "Maximum Belt",
    "マツバの確信": "Morty's Conviction",
    "ミストエネルギー": "Mist Energy",
    "ミツルの思いやり": "Wally's Compassion",
    "ミラクルインカム(ACE SPEC)": "Miracle Income",
    "メイのはげまし": "May's Encouragement",
    "ラッキーメット": "Lucky Helmet",
    "ロケット団のアテナ": "Team Rocket's Ariana",
    "ロケット団のアポロ": "Team Rocket's Archer",
    "ロケット団のサカキ": "Team Rocket's Giovanni",
    "ロケット団のファクトリー": "Team Rocket's Factory",
    "ロケット団のラムダ": "Team Rocket's Lambda",
    "ロケット団のランス": "Team Rocket's Lance",
    "ロケット団のレシーバー": "Team Rocket's Receiver",
    "ロケット団の監視塔": "Team Rocket's Watchtower",
    "ロケット団エネルギー": "Team Rocket Energy",
    "ロトりぼう": "Rotom Phone",
    "ワンダーパッチ": "Wonder Patch",
    "公民館": "Community Center",
    "危ない廃墟": "Dangerous Ruins",
    "夜のアカデミー": "Night Academy",
    "改造ハンマー": "Crushing Hammer",
    "暗号マニアの解読": "Cipher Admin's Decryption",
    "活力の森": "Vitality Forest",
    "鬼の仮面": "Ogre Mask",
    "ハイダイ": "Kofu",
    "リーリエの決心": "Lillie's Resolve",
    "シロナのパワーウエイト": "Cynthia's Power Weight",
    "バトルコロシアム": "Battle Colosseum",
    "プリズムエネルギー": "Prism Energy",
    "MBD": "MBD",
    # --- Energy ---
    "基本炎エネルギー": "Basic Fire Energy",
    "基本水エネルギー": "Basic Water Energy",
    "基本雷エネルギー": "Basic Lightning Energy",
    "基本超エネルギー": "Basic Psychic Energy",
    "基本闘エネルギー": "Basic Fighting Energy",
    "基本悪エネルギー": "Basic Darkness Energy",
    "基本鋼エネルギー": "Basic Metal Energy",
    "基本草エネルギー": "Basic Grass Energy",
    "基本無色エネルギー": "Basic Colorless Energy",
    "ダブルターボエネルギー": "Double Turbo Energy",
    "ジェットエネルギー": "Jet Energy",
    "ルミナスエネルギー": "Luminous Energy",
    "レガシーエネルギー": "Legacy Energy",
    "ネオアッパーエネルギー": "Neo Upper Energy",
    "イグニッションエネルギー": "Ignition Energy",
    "リッチエネルギー": "Rich Energy",
    "ロック闘エネルギー": "Rock Fighting Energy",
}


def _write_json(data: dict | list, path: Path) -> None:
    """Write data to a JSON file, creating directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote %s", path)


def _slugify(name: str) -> str:
    """Convert archetype name to URL slug."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def _get_sprite_filenames(archetype_name: str) -> list[str]:
    """Get sprite filenames for an archetype.

    Priority: exact reverse lookup in SPRITE_ARCHETYPE_MAP, then derive from name.
    """
    # Priority 1: Reverse lookup from canonical map
    for key, name in SPRITE_ARCHETYPE_MAP.items():
        if name == archetype_name:
            filenames = _COMPOSITE_SPRITE_FILENAMES.get(key, [key])
            return [f"{fn}.png" for fn in filenames]

    # Priority 2: Derive from archetype name by parsing Pokemon names
    # "Dragapult Meowth" -> ["dragapult.png", "meowth.png"]
    # "Mega Lucario Noctowl" -> ["lucario-mega.png", "noctowl.png"]
    # "Ceruledge ex" -> ["ceruledge.png"]
    parts = archetype_name.split()
    filenames: list[str] = []
    i = 0
    while i < len(parts):
        part = parts[i].lower()
        # Skip suffixes and non-Pokemon tokens
        if part in ("ex", "box", "stall", "control", "x", "y", "unknown"):
            i += 1
            continue
        # "Mega X" -> "x-mega", "Mega Charizard X" -> "charizard-mega-x"
        if part == "mega" and i + 1 < len(parts):
            next_part = parts[i + 1].lower()
            if next_part not in ("ex", "box", "stall", "control", "unknown"):
                # Check for "Mega Pokemon X/Y" variant (e.g. Mega Charizard X)
                if i + 2 < len(parts) and parts[i + 2].lower() in ("x", "y"):
                    filenames.append(f"{next_part}-mega-{parts[i + 2].lower()}.png")
                    i += 3
                    continue
                filenames.append(f"{next_part}-mega.png")
                i += 2
                continue
        # Handle hyphenated names (Porygon-Z, Raging Bolt, etc.)
        if i + 1 < len(parts) and parts[i + 1].lower() not in (
            "ex",
            "box",
            "stall",
            "control",
            "mega",
        ):
            # Check if this could be a two-word Pokemon name
            combined = f"{part}-{parts[i + 1].lower()}"
            # Known two-word Pokemon that use hyphens in sprite names
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

    return filenames[:2]  # Max 2 sprites per archetype


def _compute_weighted_shares(conn: sqlite3.Connection, snapshot: dict) -> dict[str, float]:
    """Compute performance-weighted meta share for each archetype.

    Weights placements by finish position (top 16 differentiated for 64-player City Leagues).
    Champions League results excluded from scoring -- archetype is classified at
    export time (export_champions_league) rather than stored in cl_placements.
    """
    rows = conn.execute(
        """
        SELECT p.archetype, p.standing
        FROM placements p
        JOIN tournaments t ON t.id = p.tournament_id
        """
    ).fetchall()

    weighted_sums: dict[str, float] = {}
    total_weight = 0.0
    for row in rows:
        standing = row["standing"]
        weight = PLACEMENT_WEIGHTS.get(standing, PLACEMENT_WEIGHT_DEFAULT)
        archetype = row["archetype"]
        weighted_sums[archetype] = weighted_sums.get(archetype, 0.0) + weight
        total_weight += weight

    if total_weight == 0:
        return {}

    return {arch: round(w / total_weight * 100, 2) for arch, w in weighted_sums.items()}


def _compute_archetype_trends(conn: sqlite3.Connection) -> dict[str, dict]:
    """Compute trend direction for each archetype by comparing recent vs earlier periods.

    Returns {archetype_name: {"trend": "up"|"down"|"new"|"stable", "trend_delta": float}}.
    """
    rows = conn.execute(
        """
        SELECT t.date, p.archetype
        FROM placements p
        JOIN tournaments t ON t.id = p.tournament_id
        ORDER BY t.date
        """
    ).fetchall()

    if not rows:
        return {}

    # Group by ISO week
    week_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    week_totals: dict[str, int] = defaultdict(int)

    for row in rows:
        d = date.fromisoformat(row["date"])
        monday = d - timedelta(days=d.weekday())
        wk = monday.isoformat()
        week_counts[wk][row["archetype"]] += 1
        week_totals[wk] += 1

    weeks = sorted(week_counts.keys())
    if len(weeks) < 2:
        return {}

    # Split into recent (last 1/3) vs earlier (first 2/3)
    split = max(1, len(weeks) * 2 // 3)
    early_weeks = weeks[:split]
    recent_weeks = weeks[split:]

    all_archetypes = set()
    for wk_data in week_counts.values():
        all_archetypes.update(wk_data.keys())

    early_total = sum(week_totals[w] for w in early_weeks) or 1
    recent_total = sum(week_totals[w] for w in recent_weeks) or 1

    result = {}
    for arch in all_archetypes:
        early_count = sum(week_counts[w].get(arch, 0) for w in early_weeks)
        recent_count = sum(week_counts[w].get(arch, 0) for w in recent_weeks)

        early_pct = early_count / early_total * 100
        recent_pct = recent_count / recent_total * 100
        delta = round(recent_pct - early_pct, 1)

        if early_count == 0 and recent_count > 0:
            trend = "new"
        elif delta > 2.0:
            trend = "up"
        elif delta < -2.0:
            trend = "down"
        else:
            trend = "stable"

        result[arch] = {"trend": trend, "trend_delta": delta}

    return result


def _get_latest_tournament_date(conn: sqlite3.Connection) -> str | None:
    """Get the most recent tournament date in the database."""
    row = conn.execute("SELECT MAX(date) as latest FROM tournaments").fetchone()
    return row["latest"] if row and row["latest"] else None


def _compute_windowed_meta(
    conn: sqlite3.Connection,
    date_from: str,
    date_to: str,
    format_slug: str | None = None,
) -> dict | None:
    """Compute meta data filtered to a specific date window."""
    fmt = get_format_config(format_slug) if format_slug else None
    rotation_date = fmt["rotation_date"] if fmt else ROTATION_DATE

    # Count tournaments and placements within the window
    rows = conn.execute(
        """
        SELECT p.archetype,
               COUNT(*) AS deck_count,
               MIN(p.standing) AS best_placement
        FROM placements p
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE t.date >= ? AND t.date <= ?
        GROUP BY p.archetype
        """,
        (date_from, date_to),
    ).fetchall()

    if not rows:
        return None

    total_decks = sum(r["deck_count"] for r in rows)
    tournament_count = conn.execute(
        """
        SELECT COUNT(DISTINCT t.id) AS cnt
        FROM tournaments t
        JOIN placements p ON p.tournament_id = t.id
        WHERE t.date >= ? AND t.date <= ?
        """,
        (date_from, date_to),
    ).fetchone()["cnt"]

    # Weighted shares within the window
    weight_rows = conn.execute(
        """
        SELECT p.archetype, p.standing
        FROM placements p
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE t.date >= ? AND t.date <= ?
        """,
        (date_from, date_to),
    ).fetchall()

    weighted_sums: dict[str, float] = {}
    total_weight = 0.0
    for row in weight_rows:
        weight = PLACEMENT_WEIGHTS.get(row["standing"], PLACEMENT_WEIGHT_DEFAULT)
        weighted_sums[row["archetype"]] = weighted_sums.get(row["archetype"], 0.0) + weight
        total_weight += weight

    weighted_shares = (
        {arch: round(w / total_weight * 100, 2) for arch, w in weighted_sums.items()}
        if total_weight > 0
        else {}
    )

    archetypes = []
    for row in rows:
        name = row["archetype"]
        meta_share = row["deck_count"] / total_decks * 100
        ws = weighted_shares.get(name, 0.0)

        # Assign tier based on meta share
        if meta_share >= TIER_THRESHOLDS["S"]:
            tier = "S"
        elif meta_share >= TIER_THRESHOLDS["A"]:
            tier = "A"
        elif meta_share >= TIER_THRESHOLDS["B"]:
            tier = "B"
        elif meta_share >= TIER_THRESHOLDS["C"]:
            tier = "C"
        else:
            tier = "Rogue"

        archetypes.append(
            {
                "archetype": name,
                "slug": _slugify(name),
                "meta_share": round(meta_share, 1),
                "weighted_share": round(ws, 1),
                "deck_count": row["deck_count"],
                "best_placement": row["best_placement"],
                "tier": tier,
                "sprite_filenames": _get_sprite_filenames(name),
            }
        )

    archetypes.sort(key=lambda a: a["weighted_share"], reverse=True)

    return {
        "generated_at": conn.execute("SELECT MAX(generated_at) FROM meta_snapshots").fetchone()[0]
        or "",
        "tournament_count": tournament_count,
        "deck_count": total_decks,
        "date_range": {"start": date_from, "end": date_to},
        "rotation_date": rotation_date,
        "tier_thresholds": TIER_THRESHOLDS,
        "archetypes": archetypes,
        "format": {
            "slug": format_slug,
            "name": fmt["name"],
            "name_en": fmt["name_en"],
        }
        if fmt
        else None,
    }


def _compute_windowed_trends(
    conn: sqlite3.Connection,
    date_from: str,
    date_to: str,
) -> dict:
    """Compute trends data filtered to a specific date window."""
    d_from = date.fromisoformat(date_from)
    d_to = date.fromisoformat(date_to)
    mid = d_from + (d_to - d_from) / 2
    midpoint = mid.isoformat()

    early_total = conn.execute(
        """
        SELECT COUNT(*) FROM placements p
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE t.date >= ? AND t.date < ?
        """,
        (date_from, midpoint),
    ).fetchone()[0]

    late_total = conn.execute(
        """
        SELECT COUNT(*) FROM placements p
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE t.date >= ? AND t.date <= ?
        """,
        (midpoint, date_to),
    ).fetchone()[0]

    if early_total == 0 or late_total == 0:
        return {
            "midpoint": midpoint,
            "early_decks": early_total,
            "late_decks": late_total,
            "surging": [],
            "declining": [],
        }

    rows = conn.execute(
        f"""
        SELECT dc.card_name,
               SUM(CASE WHEN t.date < ? THEN 1 ELSE 0 END) AS early_count,
               SUM(CASE WHEN t.date >= ? THEN 1 ELSE 0 END) AS late_count
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE t.date >= ? AND t.date <= ? AND {_basic_energy_exclusion_sql()} AND dc.card_name NOT LIKE '%Energy%'
        GROUP BY dc.card_name
        HAVING early_count >= 3 AND late_count >= 3
        """,
        (midpoint, midpoint, date_from, date_to, *_basic_energy_params()),
    ).fetchall()

    cards = []
    for row in rows:
        early_pct = round(row["early_count"] * 100.0 / early_total, 1)
        late_pct = round(row["late_count"] * 100.0 / late_total, 1)
        delta = round(late_pct - early_pct, 1)
        cards.append(
            {
                "card_name": row["card_name"],
                "early_count": row["early_count"],
                "late_count": row["late_count"],
                "early_pct": early_pct,
                "late_pct": late_pct,
                "delta": delta,
            }
        )

    cards.sort(key=lambda x: x["delta"], reverse=True)
    surging = [dict(c, direction="surging") for c in cards[:20]]
    cards.sort(key=lambda x: x["delta"])
    declining = [dict(c, direction="declining") for c in cards[:20]]

    return {
        "midpoint": midpoint,
        "early_decks": early_total,
        "late_decks": late_total,
        "surging": surging,
        "declining": declining,
    }


def _compute_windowed_winning_edge(
    conn: sqlite3.Connection,
    date_from: str,
    date_to: str,
    meta_data: dict,
) -> list[dict]:
    """Compute winning edge filtered to a specific date window."""
    sa_archetypes = [
        a["archetype"] for a in meta_data["archetypes"] if a["tier"] in ("S", "A", "B")
    ]
    if not sa_archetypes:
        return []

    placeholders = ",".join("?" * len(sa_archetypes))

    total_field = conn.execute(
        f"""
        SELECT COUNT(*) FROM placements p
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE p.archetype IN ({placeholders}) AND t.date >= ? AND t.date <= ?
        """,
        (*sa_archetypes, date_from, date_to),
    ).fetchone()[0]

    total_winners = conn.execute(
        f"""
        SELECT COUNT(*) FROM placements p
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE p.standing = 1 AND p.archetype IN ({placeholders})
          AND t.date >= ? AND t.date <= ?
        """,
        (*sa_archetypes, date_from, date_to),
    ).fetchone()[0]

    if total_field == 0 or total_winners == 0:
        return []

    field_rows = conn.execute(
        f"""
        SELECT dc.card_name,
               COUNT(DISTINCT dc.placement_id) AS field_decks
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE p.archetype IN ({placeholders})
          AND t.date >= ? AND t.date <= ?
          AND {_basic_energy_exclusion_sql()}
        GROUP BY dc.card_name
        HAVING field_decks >= 5
        """,
        (*sa_archetypes, date_from, date_to, *_basic_energy_params()),
    ).fetchall()

    field_usage = {row["card_name"]: row["field_decks"] for row in field_rows}

    winner_rows = conn.execute(
        f"""
        SELECT dc.card_name,
               COUNT(DISTINCT dc.placement_id) AS winner_decks
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE p.standing = 1 AND p.archetype IN ({placeholders})
          AND t.date >= ? AND t.date <= ?
          AND {_basic_energy_exclusion_sql()}
        GROUP BY dc.card_name
        """,
        (*sa_archetypes, date_from, date_to, *_basic_energy_params()),
    ).fetchall()

    cards = []
    for row in winner_rows:
        name = row["card_name"]
        if name not in field_usage:
            continue
        field_pct = round(field_usage[name] * 100.0 / total_field, 1)
        win_pct = round(row["winner_decks"] * 100.0 / total_winners, 1)
        edge = round(win_pct - field_pct, 1)
        cards.append(
            {
                "card_name": name,
                "field_pct": field_pct,
                "win_pct": win_pct,
                "edge": edge,
                "winner_decks": row["winner_decks"],
                "field_decks": field_usage[name],
            }
        )

    cards.sort(key=lambda x: x["edge"], reverse=True)
    return cards[:20]


def _compute_windowed_ace_specs(
    conn: sqlite3.Connection,
    date_from: str,
    date_to: str,
) -> list[dict]:
    """Compute ACE SPEC distribution filtered to a specific date window."""
    total_decks = conn.execute(
        """
        SELECT COUNT(*) FROM placements p
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE t.date >= ? AND t.date <= ?
        """,
        (date_from, date_to),
    ).fetchone()[0]

    if total_decks == 0:
        return []

    placeholders = ",".join("?" * len(ACE_SPEC_CARDS))

    rows = conn.execute(
        f"""
        SELECT dc.card_name,
               COUNT(DISTINCT dc.placement_id) AS deck_count
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE dc.card_name IN ({placeholders})
          AND t.date >= ? AND t.date <= ?
        GROUP BY dc.card_name
        ORDER BY deck_count DESC
        """,
        (*list(ACE_SPEC_CARDS), date_from, date_to),
    ).fetchall()

    return [
        {
            "card_name": row["card_name"],
            "deck_count": row["deck_count"],
            "usage_pct": round(row["deck_count"] * 100.0 / total_decks, 1),
        }
        for row in rows
    ]


def _compute_windowed_staples_flex(
    conn: sqlite3.Connection,
    date_from: str,
    date_to: str,
    threshold_min: float,
    threshold_max: float | None = None,
) -> list[dict]:
    """Compute staples or flex cards filtered to a date window.

    threshold_min/max are usage percentages (e.g. 40 for staples, 20-40 for flex).
    """
    total_decks = conn.execute(
        """
        SELECT COUNT(*) FROM placements p
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE t.date >= ? AND t.date <= ?
        """,
        (date_from, date_to),
    ).fetchone()[0]

    if total_decks == 0:
        return []

    rows = conn.execute(
        f"""
        SELECT dc.card_name,
               COUNT(DISTINCT dc.placement_id) AS deck_count,
               ROUND(AVG(dc.count), 1) AS avg_copies
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE t.date >= ? AND t.date <= ?
          AND {_basic_energy_exclusion_sql()}
        GROUP BY dc.card_name
        ORDER BY deck_count DESC
        """,
        (date_from, date_to, *_basic_energy_params()),
    ).fetchall()

    result = []
    for row in rows:
        pct = row["deck_count"] * 100.0 / total_decks
        if pct < threshold_min:
            continue
        if threshold_max is not None and pct >= threshold_max:
            continue
        result.append(
            {
                "card_name": row["card_name"],
                "deck_count": row["deck_count"],
                "usage_pct": round(pct, 1),
                "avg_copies": row["avg_copies"],
            }
        )

    return result


def _compute_windowed_buylist(
    conn: sqlite3.Connection,
    date_from: str,
    date_to: str,
    meta: dict,
) -> list[dict]:
    """Compute buylist filtered to a date window using windowed meta tiers."""
    sab_archetypes = {
        a["archetype"]: a["tier"]
        for a in meta.get("archetypes", [])
        if a["tier"] in ("S", "A", "B")
    }
    if not sab_archetypes:
        return []

    # Get placement IDs for S/A/B archetypes within the window
    arch_placeholders = ",".join("?" * len(sab_archetypes))
    placement_rows = conn.execute(
        f"""
        SELECT p.id, p.archetype
        FROM placements p
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE t.date >= ? AND t.date <= ?
          AND p.archetype IN ({arch_placeholders})
        """,
        (date_from, date_to, *list(sab_archetypes.keys())),
    ).fetchall()

    if not placement_rows:
        return []

    # Group placements by archetype
    arch_placements: dict[str, list[int]] = defaultdict(list)
    for row in placement_rows:
        arch_placements[row["archetype"]].append(row["id"])

    energy_names = sorted(BASIC_ENERGY_NAMES)
    energy_placeholders = ",".join("?" * len(energy_names))

    card_data: dict[str, dict] = defaultdict(
        lambda: {
            "card_name": None,
            "archetypes": [],
            "priority_score": 0.0,
            "max_inclusion_rate": 0.0,
            "max_avg_copies": 0.0,
        }
    )

    tier_weights = {"S": 3, "A": 2, "B": 1}

    for archetype, pids in arch_placements.items():
        tier = sab_archetypes[archetype]
        tier_weight = tier_weights.get(tier, 1)
        total_decks = len(pids)
        placeholders = ",".join("?" * len(pids))

        rows = conn.execute(
            f"""
            SELECT card_name,
                   COUNT(DISTINCT placement_id) AS deck_count,
                   ROUND(AVG(count), 1) AS avg_copies
            FROM decklist_cards
            WHERE placement_id IN ({placeholders})
              AND card_name NOT IN ({energy_placeholders})
            GROUP BY card_name
            """,
            (*pids, *energy_names),
        ).fetchall()

        for row in rows:
            name = row["card_name"]
            inclusion = row["deck_count"] / total_decks
            cd = card_data[name]
            cd["card_name"] = name
            if archetype not in cd["archetypes"]:
                cd["archetypes"].append(archetype)
            cd["priority_score"] += inclusion * tier_weight
            cd["max_inclusion_rate"] = max(cd["max_inclusion_rate"], inclusion)
            cd["max_avg_copies"] = max(cd["max_avg_copies"], row["avg_copies"])

    result = [
        {
            "card_name": cd["card_name"],
            "priority_score": round(cd["priority_score"], 2),
            "avg_copies": cd["max_avg_copies"],
            "inclusion_rate": round(cd["max_inclusion_rate"], 3),
            "archetypes": cd["archetypes"],
        }
        for cd in card_data.values()
        if cd["card_name"]
    ]
    result.sort(key=lambda c: c["priority_score"], reverse=True)
    return result


def export_windowed(
    conn: sqlite3.Connection, output_dir: Path, format_slug: str | None = None
) -> None:
    """Export time-windowed variants of meta, trends, winning-edge, ace-specs, buylist, staples, and flex."""
    latest_date = _get_latest_tournament_date(conn)
    if not latest_date:
        logger.warning("No tournaments found; skipping windowed exports")
        return

    d_latest = date.fromisoformat(latest_date)

    for suffix, days in TIME_WINDOWS.items():
        d_from = d_latest - timedelta(days=days)
        date_from = d_from.isoformat()
        date_to = latest_date

        logger.info("Exporting %s window: %s to %s", suffix, date_from, date_to)

        # Meta
        meta = _compute_windowed_meta(conn, date_from, date_to, format_slug)
        if meta:
            _write_json(meta, output_dir / f"meta-{suffix}.json")

            # Winning edge (depends on meta for tier filtering)
            edge = _compute_windowed_winning_edge(conn, date_from, date_to, meta)
            _write_json(edge, output_dir / f"winning-edge-{suffix}.json")

            # Buylist (depends on meta for tier filtering)
            buylist = _compute_windowed_buylist(conn, date_from, date_to, meta)
            _write_json(buylist, output_dir / f"buylist-{suffix}.json")
        else:
            logger.warning("No data for %s window", suffix)
            continue

        # Trends
        trends = _compute_windowed_trends(conn, date_from, date_to)
        _write_json(trends, output_dir / f"trends-{suffix}.json")

        # ACE SPECs
        specs = _compute_windowed_ace_specs(conn, date_from, date_to)
        _write_json(specs, output_dir / f"ace-specs-{suffix}.json")

        # Staples (40%+ usage)
        staples = _compute_windowed_staples_flex(conn, date_from, date_to, 40)
        _write_json(staples, output_dir / f"staples-{suffix}.json")

        # Flex (20-40% usage)
        flex = _compute_windowed_staples_flex(conn, date_from, date_to, 20, 40)
        _write_json(flex, output_dir / f"flex-{suffix}.json")


def export_meta(
    conn: sqlite3.Connection, output_dir: Path, format_slug: str | None = None
) -> dict | None:
    """Export meta.json — snapshot stats + tier list with weighted shares."""
    snapshot = get_latest_snapshot(conn)
    if not snapshot:
        logger.warning("No meta snapshot found")
        return None

    fmt = get_format_config(format_slug) if format_slug else None
    rotation_date = fmt["rotation_date"] if fmt else ROTATION_DATE
    dataset_start = fmt["dataset_start"] if fmt else DATASET_START
    dataset_end = fmt["dataset_end"] if fmt else DATASET_END

    weighted_shares = _compute_weighted_shares(conn, snapshot)

    # Get date range from tournaments
    date_range = conn.execute(
        "SELECT MIN(date) as earliest, MAX(date) as latest FROM tournaments"
    ).fetchone()

    # Compute trend data: compare recent vs earlier meta shares
    trend_data = _compute_archetype_trends(conn)

    archetypes = []
    for arch in snapshot["archetypes"]:
        name = arch["archetype"]
        ws = weighted_shares.get(name, 0.0)
        trend_info = trend_data.get(name, {"trend": "stable", "trend_delta": 0.0})
        archetypes.append(
            {
                "archetype": name,
                "slug": _slugify(name),
                "meta_share": round(arch["meta_share"], 1),
                "weighted_share": round(ws, 1),
                "deck_count": arch["deck_count"],
                "best_placement": arch["best_placement"],
                "tier": arch["tier"],
                "sprite_filenames": _get_sprite_filenames(name),
                "trend": trend_info["trend"],
                "trend_delta": trend_info["trend_delta"],
            }
        )

    # Re-sort by weighted_share for tier assignment display
    archetypes.sort(key=lambda a: a["weighted_share"], reverse=True)

    data = {
        "generated_at": snapshot["generated_at"],
        "tournament_count": snapshot["tournament_count"],
        "deck_count": snapshot["deck_count"],
        "date_range": {
            "start": date_range["earliest"] if date_range else dataset_start,
            "end": date_range["latest"] if date_range else dataset_end,
        },
        "rotation_date": rotation_date,
        "tier_thresholds": TIER_THRESHOLDS,
        "archetypes": archetypes,
    }

    if fmt:
        data["format"] = {
            "slug": format_slug,
            "name": fmt["name"],
            "name_en": fmt["name_en"],
        }

    _write_json(data, output_dir / "meta.json")
    return data


def export_buylist(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export buylist.json — full prioritized card list."""
    snapshot = get_latest_snapshot(conn)
    if not snapshot:
        return

    cards = generate_buylist(conn, snapshot["id"])
    if not cards:
        return

    _write_json(cards, output_dir / "buylist.json")


def export_staples(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export staples.json — format staples with 40%+ usage across all decks."""
    total_decks = conn.execute("SELECT COUNT(*) FROM placements").fetchone()[0]

    rows = conn.execute(
        f"""
        SELECT card_name,
               COUNT(DISTINCT placement_id) AS deck_count,
               ROUND(AVG(count), 1) AS avg_copies
        FROM decklist_cards dc
        WHERE {_basic_energy_exclusion_sql()}
        GROUP BY card_name
        HAVING COUNT(DISTINCT placement_id) * 100.0 / ? >= 40
        ORDER BY deck_count DESC
        """,
        (*_basic_energy_params(), total_decks),
    ).fetchall()

    staples = []
    for row in rows:
        pct = round(row["deck_count"] * 100.0 / total_decks, 1)
        staples.append(
            {
                "card_name": row["card_name"],
                "deck_count": row["deck_count"],
                "usage_pct": pct,
                "avg_copies": row["avg_copies"],
            }
        )

    _write_json(staples, output_dir / "staples.json")


def export_flex(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export flex.json — broad flex cards with 20-40% usage."""
    total_decks = conn.execute("SELECT COUNT(*) FROM placements").fetchone()[0]

    rows = conn.execute(
        f"""
        SELECT card_name,
               COUNT(DISTINCT placement_id) AS deck_count,
               ROUND(AVG(count), 1) AS avg_copies
        FROM decklist_cards dc
        WHERE {_basic_energy_exclusion_sql()}
        GROUP BY card_name
        HAVING COUNT(DISTINCT placement_id) * 100.0 / ? >= 20
           AND COUNT(DISTINCT placement_id) * 100.0 / ? < 40
        ORDER BY deck_count DESC
        """,
        (*_basic_energy_params(), total_decks, total_decks),
    ).fetchall()

    flex = []
    for row in rows:
        pct = round(row["deck_count"] * 100.0 / total_decks, 1)
        flex.append(
            {
                "card_name": row["card_name"],
                "deck_count": row["deck_count"],
                "usage_pct": pct,
                "avg_copies": row["avg_copies"],
            }
        )

    _write_json(flex, output_dir / "flex.json")


def _get_card_archetype_breakdown(
    conn: sqlite3.Connection, card_name: str, midpoint: str
) -> list[dict]:
    """Get per-archetype usage deltas for a trending card."""
    rows = conn.execute(
        f"""
        SELECT p.archetype,
               SUM(CASE WHEN t.date < ? THEN 1 ELSE 0 END) AS early_count,
               SUM(CASE WHEN t.date >= ? THEN 1 ELSE 0 END) AS late_count
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE dc.card_name = ? AND {_basic_energy_exclusion_sql()}
        GROUP BY p.archetype
        HAVING (early_count + late_count) >= 3
        ORDER BY (early_count + late_count) DESC
        LIMIT 5
        """,
        (midpoint, midpoint, card_name, *_basic_energy_params()),
    ).fetchall()

    # Get per-archetype totals for the periods
    arch_totals = conn.execute(
        """
        SELECT p.archetype,
               SUM(CASE WHEN t.date < ? THEN 1 ELSE 0 END) AS early_total,
               SUM(CASE WHEN t.date >= ? THEN 1 ELSE 0 END) AS late_total
        FROM placements p
        JOIN tournaments t ON t.id = p.tournament_id
        GROUP BY p.archetype
        """,
        (midpoint, midpoint),
    ).fetchall()
    totals = {r["archetype"]: (r["early_total"], r["late_total"]) for r in arch_totals}

    result = []
    for row in rows:
        arch = row["archetype"]
        et, lt = totals.get(arch, (0, 0))
        if et == 0 or lt == 0:
            continue
        early_pct = round(row["early_count"] * 100.0 / et, 1)
        late_pct = round(row["late_count"] * 100.0 / lt, 1)
        result.append(
            {
                "archetype": arch,
                "early_pct": early_pct,
                "late_pct": late_pct,
                "delta": round(late_pct - early_pct, 1),
            }
        )
    return result


def export_trends(
    conn: sqlite3.Connection, output_dir: Path, format_slug: str | None = None
) -> None:
    """Export trends.json — surging and declining cards with archetype breakdowns."""
    # Compute midpoint from actual tournament dates, not config dates
    # This handles cases where dataset_end is in the future
    actual_range = conn.execute(
        "SELECT MIN(t.date) as earliest, MAX(t.date) as latest FROM tournaments t"
    ).fetchone()

    if actual_range and actual_range["earliest"] and actual_range["latest"]:
        actual_start = date.fromisoformat(actual_range["earliest"])
        actual_end = date.fromisoformat(actual_range["latest"])
        mid = actual_start + (actual_end - actual_start) / 2
        midpoint = mid.isoformat()
    elif format_slug:
        fmt = get_format_config(format_slug)
        start = date.fromisoformat(fmt["dataset_start"])
        end = date.fromisoformat(fmt["dataset_end"])
        mid = start + (end - start) / 2
        midpoint = mid.isoformat()
    else:
        midpoint = "2026-02-15"

    early_total = conn.execute(
        "SELECT COUNT(*) FROM placements p JOIN tournaments t ON t.id = p.tournament_id WHERE t.date < ?",
        (midpoint,),
    ).fetchone()[0]

    late_total = conn.execute(
        "SELECT COUNT(*) FROM placements p JOIN tournaments t ON t.id = p.tournament_id WHERE t.date >= ?",
        (midpoint,),
    ).fetchone()[0]

    if early_total == 0 or late_total == 0:
        logger.warning("Insufficient data for trend analysis")
        _write_json(
            {
                "midpoint": midpoint,
                "early_decks": 0,
                "late_decks": 0,
                "surging": [],
                "declining": [],
            },
            output_dir / "trends.json",
        )
        return

    # Adaptive threshold: lower minimums for small datasets
    min_count = 2 if min(early_total, late_total) < 50 else 5

    rows = conn.execute(
        f"""
        SELECT dc.card_name,
               SUM(CASE WHEN t.date < ? THEN 1 ELSE 0 END) AS early_count,
               SUM(CASE WHEN t.date >= ? THEN 1 ELSE 0 END) AS late_count
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE {_basic_energy_exclusion_sql()} AND dc.card_name NOT LIKE '%Energy%'
        GROUP BY dc.card_name
        HAVING early_count >= ? AND late_count >= ?
        """,
        (midpoint, midpoint, *_basic_energy_params(), min_count, min_count),
    ).fetchall()

    cards = []
    for row in rows:
        early_pct = round(row["early_count"] * 100.0 / early_total, 1)
        late_pct = round(row["late_count"] * 100.0 / late_total, 1)
        delta = round(late_pct - early_pct, 1)
        cards.append(
            {
                "card_name": row["card_name"],
                "early_count": row["early_count"],
                "late_count": row["late_count"],
                "early_pct": early_pct,
                "late_pct": late_pct,
                "delta": delta,
            }
        )

    # Top 20 surging (positive delta) with archetype breakdowns
    cards.sort(key=lambda x: x["delta"], reverse=True)
    surging = cards[:20]
    for card in surging:
        card["direction"] = "surging"
        card["archetypes"] = _get_card_archetype_breakdown(conn, card["card_name"], midpoint)

    # Top 20 declining (negative delta) with archetype breakdowns
    cards.sort(key=lambda x: x["delta"])
    declining = cards[:20]
    for card in declining:
        card["direction"] = "declining"
        card["archetypes"] = _get_card_archetype_breakdown(conn, card["card_name"], midpoint)

    _write_json(
        {
            "midpoint": midpoint,
            "early_decks": early_total,
            "late_decks": late_total,
            "surging": surging,
            "declining": declining,
        },
        output_dir / "trends.json",
    )


def export_winning_edge(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export winning-edge.json — 1st place overrepresentation vs field for S/A/B decks."""
    snapshot = get_latest_snapshot(conn)
    if not snapshot:
        return

    # Get S/A/B archetype names
    sa_archetypes = [a["archetype"] for a in snapshot["archetypes"] if a["tier"] in ("S", "A", "B")]

    if not sa_archetypes:
        _write_json([], output_dir / "winning-edge.json")
        return

    placeholders = ",".join("?" * len(sa_archetypes))

    # Total decks in S/A/B
    total_field = conn.execute(
        f"SELECT COUNT(*) FROM placements WHERE archetype IN ({placeholders})",
        sa_archetypes,
    ).fetchone()[0]

    # Total 1st place decks in S/A/B
    total_winners = conn.execute(
        f"SELECT COUNT(*) FROM placements WHERE standing = 1 AND archetype IN ({placeholders})",
        sa_archetypes,
    ).fetchone()[0]

    if total_field == 0 or total_winners == 0:
        _write_json([], output_dir / "winning-edge.json")
        return

    # Per-card: field usage vs winner usage
    field_rows = conn.execute(
        f"""
        SELECT dc.card_name,
               COUNT(DISTINCT dc.placement_id) AS field_decks
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        WHERE p.archetype IN ({placeholders}) AND {_basic_energy_exclusion_sql()}
        GROUP BY dc.card_name
        HAVING field_decks >= 10
        """,
        (*sa_archetypes, *_basic_energy_params()),
    ).fetchall()

    field_usage = {row["card_name"]: row["field_decks"] for row in field_rows}

    winner_rows = conn.execute(
        f"""
        SELECT dc.card_name,
               COUNT(DISTINCT dc.placement_id) AS winner_decks
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        WHERE p.standing = 1 AND p.archetype IN ({placeholders}) AND {_basic_energy_exclusion_sql()}
        GROUP BY dc.card_name
        """,
        (*sa_archetypes, *_basic_energy_params()),
    ).fetchall()

    cards = []
    for row in winner_rows:
        name = row["card_name"]
        if name not in field_usage:
            continue
        field_pct = round(field_usage[name] * 100.0 / total_field, 1)
        win_pct = round(row["winner_decks"] * 100.0 / total_winners, 1)
        edge = round(win_pct - field_pct, 1)
        cards.append(
            {
                "card_name": name,
                "field_pct": field_pct,
                "win_pct": win_pct,
                "edge": edge,
                "winner_decks": row["winner_decks"],
                "field_decks": field_usage[name],
            }
        )

    cards.sort(key=lambda x: x["edge"], reverse=True)
    _write_json(cards[:20], output_dir / "winning-edge.json")


def export_ace_specs(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export ace-specs.json — ACE SPEC card distribution across decks."""
    total_decks = conn.execute("SELECT COUNT(*) FROM placements").fetchone()[0]
    placeholders = ",".join("?" * len(ACE_SPEC_CARDS))

    rows = conn.execute(
        f"""
        SELECT card_name,
               COUNT(DISTINCT placement_id) AS deck_count
        FROM decklist_cards
        WHERE card_name IN ({placeholders})
        GROUP BY card_name
        ORDER BY deck_count DESC
        """,
        list(ACE_SPEC_CARDS),
    ).fetchall()

    specs = []
    for row in rows:
        pct = round(row["deck_count"] * 100.0 / total_decks, 1)
        specs.append(
            {
                "card_name": row["card_name"],
                "deck_count": row["deck_count"],
                "usage_pct": pct,
            }
        )

    _write_json(specs, output_dir / "ace-specs.json")


def _compute_card_stats_for_ids(
    conn: sqlite3.Connection, placement_ids: list[int], total_decks: int
) -> list[dict]:
    """Compute per-card inclusion stats for a set of placement IDs.

    Returns a list of dicts with card_name, inclusion_pct, avg_copies, decks_with, category.
    """
    if not placement_ids or total_decks == 0:
        return []

    placeholders = ",".join("?" * len(placement_ids))
    rows = conn.execute(
        f"""
        SELECT card_name,
               COUNT(DISTINCT placement_id) AS decks_with,
               SUM(count) AS total_copies
        FROM decklist_cards dc
        WHERE placement_id IN ({placeholders}) AND {_basic_energy_exclusion_sql()}
        GROUP BY card_name
        ORDER BY decks_with DESC
        """,
        (*placement_ids, *_basic_energy_params()),
    ).fetchall()

    cards = []
    for row in rows:
        inclusion = round(row["decks_with"] / total_decks * 100, 1)
        avg_copies = round(row["total_copies"] / row["decks_with"], 1)
        cards.append(
            {
                "card_name": row["card_name"],
                "inclusion_pct": inclusion,
                "avg_copies": avg_copies,
                "decks_with": row["decks_with"],
                "category": _classify_card(row["card_name"]),
            }
        )
    return cards


def export_archetypes(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export per-archetype detail JSON files with core cards and tournament results."""
    snapshot = get_latest_snapshot(conn)
    if not snapshot:
        return

    weighted_shares = _compute_weighted_shares(conn, snapshot)
    category_lookup = build_category_lookup(conn)

    arch_dir = output_dir / "archetypes"
    arch_dir.mkdir(parents=True, exist_ok=True)

    # Compute max_deck_count across all archetypes for popularity normalization
    max_deck_count = max((a["deck_count"] for a in snapshot["archetypes"]), default=1)

    for arch in snapshot["archetypes"]:
        archetype_name = arch["archetype"]
        slug = _slugify(archetype_name)

        # Get all placements for this archetype
        placements = conn.execute(
            "SELECT id FROM placements WHERE archetype = ?",
            (archetype_name,),
        ).fetchall()

        if not placements:
            continue

        placement_ids = [p["id"] for p in placements]
        total_decks = len(placement_ids)

        # Get per-card stats using shared helper
        all_cards = _compute_card_stats_for_ids(conn, placement_ids, total_decks)
        core_cards = [c for c in all_cards if c["inclusion_pct"] >= 80]

        # Top-4 segmented card stats
        top4_placements = conn.execute(
            "SELECT p.id FROM placements p WHERE p.archetype = ? AND p.standing <= 4",
            (archetype_name,),
        ).fetchall()
        top4_ids = [p["id"] for p in top4_placements]
        top4_total = len(top4_ids)

        # Build field inclusion lookup for delta computation
        field_inclusion = {c["card_name"]: c["inclusion_pct"] for c in all_cards}

        top4_cards = _compute_card_stats_for_ids(conn, top4_ids, top4_total)
        for card in top4_cards:
            card["delta_vs_field"] = round(
                card["inclusion_pct"] - field_inclusion.get(card["card_name"], 0), 1
            )

        # Tournament results — top 16 by standing ASC, date DESC
        # (limited to 16 since each result now includes full decklists)
        results_rows = conn.execute(
            """
            SELECT p.id AS placement_id, t.name AS tournament_name, t.date,
                   p.standing, p.player_name
            FROM placements p
            JOIN tournaments t ON t.id = p.tournament_id
            WHERE p.archetype = ?
            ORDER BY p.standing ASC, t.date DESC
            LIMIT 16
            """,
            (archetype_name,),
        ).fetchall()

        # Category sort order for decklists
        _category_order = {"Pokemon": 0, "Trainer": 1, "Energy": 2}

        results = []
        for r in results_rows:
            entry: dict = {
                "tournament_name": r["tournament_name"],
                "date": r["date"],
                "standing": r["standing"],
                "player_name": r["player_name"],
            }
            # Attach decklist if available
            dl_rows = conn.execute(
                "SELECT card_name, count FROM decklist_cards WHERE placement_id = ?",
                (r["placement_id"],),
            ).fetchall()
            if dl_rows:
                decklist = [
                    {
                        "card_name": dl["card_name"],
                        "count": dl["count"],
                        "category": classify_card(dl["card_name"], category_lookup),
                    }
                    for dl in dl_rows
                ]
                decklist.sort(key=lambda c: (_category_order.get(c["category"], 99), -c["count"]))
                entry["decklist"] = decklist
            results.append(entry)

        # Radar metrics
        meta_share_val = arch["meta_share"]
        weighted_share_val = weighted_shares.get(archetype_name, 0.0)

        # Consistency: lower avg standing = higher score
        avg_row = conn.execute(
            "SELECT AVG(standing) as avg_standing FROM placements WHERE archetype = ?",
            (archetype_name,),
        ).fetchone()
        avg_standing = avg_row["avg_standing"] if avg_row and avg_row["avg_standing"] else 1
        consistency_score = max(0, 100 - (avg_standing - 1) * 5)

        # Ceiling: based on best placement
        bp = arch["best_placement"]
        if bp == 1:
            ceiling_score = 100
        elif bp == 2:
            ceiling_score = 90
        elif bp <= 4:
            ceiling_score = 75
        elif bp <= 8:
            ceiling_score = 50
        elif bp <= 16:
            ceiling_score = 25
        else:
            ceiling_score = 10

        # Popularity: relative to max deck count
        popularity_score = min(arch["deck_count"] / max_deck_count * 100, 100)

        # Core density: percentage of cards that are core (80%+ inclusion)
        core_density_score = len(core_cards) / len(all_cards) * 100 if all_cards else 0

        radar = {
            "meta_share": round(min(meta_share_val / 20 * 100, 100), 1),
            "weighted_share": round(min(weighted_share_val / 20 * 100, 100), 1),
            "consistency": round(consistency_score, 1),
            "ceiling": ceiling_score,
            "popularity": round(popularity_score, 1),
            "core_density": round(core_density_score, 1),
        }

        # Evolution events
        evolution = compute_archetype_evolution(conn, archetype_name)

        # Variant detection: group decklists by distinguishing Pokemon
        variants = _detect_variants(conn, archetype_name, placement_ids, all_cards)

        # Weekly meta shares for performance trendline
        weekly_shares = _compute_archetype_weekly_shares(conn, archetype_name)

        arch_data = {
            "archetype": archetype_name,
            "slug": slug,
            "tier": arch["tier"],
            "meta_share": round(arch["meta_share"], 1),
            "weighted_share": round(weighted_shares.get(archetype_name, 0.0), 1),
            "deck_count": arch["deck_count"],
            "best_placement": arch["best_placement"],
            "sprite_filenames": _get_sprite_filenames(archetype_name),
            "core_cards": core_cards,
            "all_cards": all_cards,
            "results": results,
            "radar": radar,
            "evolution": evolution,
            "variants": variants,
            "weekly_shares": weekly_shares,
            "top4_card_stats": top4_cards,
            "top4_sample_size": top4_total,
            "top4_low_sample": top4_total < 10,
        }

        _write_json(arch_data, arch_dir / f"{slug}.json")


def _detect_variants(
    conn: sqlite3.Connection,
    archetype_name: str,
    placement_ids: list[int],
    all_cards: list[dict],
) -> list[dict]:
    """Detect sub-variants within an archetype based on distinguishing Pokemon."""
    total_decks = len(placement_ids)
    if total_decks < 4:
        return []

    # Find Pokemon cards with 15-70% inclusion (variant markers)
    markers = [
        c["card_name"]
        for c in all_cards
        if c["category"] == "Pokemon" and 15 <= c["inclusion_pct"] <= 70
    ]

    if not markers:
        return []

    # For each placement, check which markers are present
    placeholders = ",".join("?" * len(placement_ids))
    marker_placeholders = ",".join("?" * len(markers))

    rows = conn.execute(
        f"""
        SELECT placement_id, card_name
        FROM decklist_cards
        WHERE placement_id IN ({placeholders})
          AND card_name IN ({marker_placeholders})
        """,
        (*placement_ids, *markers),
    ).fetchall()

    # Group placements by their marker set
    placement_markers: dict[int, set[str]] = defaultdict(set)
    for r in rows:
        placement_markers[r["placement_id"]].add(r["card_name"])

    # Cluster by primary distinguishing card (alphabetically first marker)
    variant_counts: dict[str, int] = defaultdict(int)
    for pid in placement_ids:
        marker_set = placement_markers.get(pid, set())
        if marker_set:
            # Use alphabetically first marker as variant key (deterministic tie-breaking)
            primary = sorted(marker_set)[0]
            variant_counts[primary] += 1
        else:
            variant_counts["Standard"] += 1

    # Only include variants with 10%+ representation
    variants = []
    for name, count in sorted(variant_counts.items(), key=lambda x: x[1], reverse=True):
        pct = round(count / total_decks * 100, 1)
        if pct >= 10:
            label = f"with {name}" if name != "Standard" else "Standard"
            variants.append(
                {
                    "name": label,
                    "deck_count": count,
                    "pct": pct,
                }
            )

    return variants if len(variants) >= 2 else []


def _compute_archetype_weekly_shares(conn: sqlite3.Connection, archetype_name: str) -> list[dict]:
    """Compute weekly meta share for a specific archetype."""
    rows = conn.execute(
        """
        SELECT t.date, p.archetype
        FROM placements p
        JOIN tournaments t ON t.id = p.tournament_id
        ORDER BY t.date
        """
    ).fetchall()

    if not rows:
        return []

    week_arch_count: dict[str, int] = defaultdict(int)
    week_total: dict[str, int] = defaultdict(int)

    for r in rows:
        d = date.fromisoformat(r["date"])
        monday = d - timedelta(days=d.weekday())
        wk = monday.isoformat()
        week_total[wk] += 1
        if r["archetype"] == archetype_name:
            week_arch_count[wk] += 1

    result = []
    for wk in sorted(week_total):
        total = week_total[wk]
        count = week_arch_count.get(wk, 0)
        result.append(
            {
                "week": wk,
                "meta_share": round(count / total * 100, 1) if total > 0 else 0,
                "deck_count": count,
            }
        )

    return result


def _build_jp_en_lookup(conn: sqlite3.Connection) -> dict[str, str]:
    """Build JP→EN card name lookup from hardcoded fallbacks, the cards table, and the card_mappings table."""
    lookup = dict(JP_CARD_NAMES)  # Start with hardcoded fallbacks
    rows = conn.execute(
        "SELECT name_jp, name_en FROM cards WHERE name_jp IS NOT NULL AND name_jp != ''"
    ).fetchall()
    if not rows:
        logger.warning("cards table returned 0 JP->EN mappings; translations will be degraded")
    for row in rows:
        lookup[row["name_jp"]] = row["name_en"]

    # From card_mappings table (scraped from Limitless)
    mapping_count = 0
    try:
        for row in conn.execute(
            "SELECT card_name_jp, card_name_en FROM card_mappings "
            "WHERE card_name_jp IS NOT NULL AND card_name_en IS NOT NULL"
        ):
            lookup[row["card_name_jp"]] = row["card_name_en"]
            mapping_count += 1
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            logger.info("card_mappings table not found, skipping")
        else:
            raise

    logger.info(
        "JP→EN lookup: %d entries (%d from cards table, %d from card_mappings)",
        len(lookup),
        len(rows),
        mapping_count,
    )
    return lookup


def export_champions_league(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export Champions League data by division with JP→EN translations."""

    cl_dir = output_dir / "champions-league"
    cl_dir.mkdir(parents=True, exist_ok=True)

    jp_en_lookup = _build_jp_en_lookup(conn)

    # Build image URL lookup: {name_en: image_url} (most recent set first)
    image_rows = conn.execute(
        "SELECT name_en, image_url FROM cards WHERE image_url IS NOT NULL ORDER BY set_code DESC"
    ).fetchall()
    image_lookup: dict[str, str] = {}
    for row in image_rows:
        if row["name_en"] not in image_lookup:
            image_lookup[row["name_en"]] = row["image_url"]

    # Build tier lookup from latest snapshot
    tier_lookup: dict[str, str] = {}
    tier_rows = conn.execute(
        "SELECT archetype, tier FROM archetype_stats "
        "WHERE snapshot_id = (SELECT MAX(id) FROM meta_snapshots)"
    ).fetchall()
    for row in tier_rows:
        tier_lookup[row["archetype"]] = row["tier"]
    if not tier_lookup:
        logger.warning("No tier data found (meta_snapshots may be empty)")

    events = conn.execute(
        "SELECT DISTINCT id, name, division, date FROM cl_events ORDER BY division"
    ).fetchall()

    if not events:
        logger.warning("No Champions League events found")
        return

    translated_count = 0
    untranslated_names: set[str] = set()

    for event in events:
        division = event["division"]

        placements = conn.execute(
            """
            SELECT DISTINCT standing, player_name, region, deck_code
            FROM cl_placements
            WHERE event_id = ?
            ORDER BY standing
            """,
            (event["id"],),
        ).fetchall()

        placement_list = []
        archetype_counts: dict[str, int] = {}

        for p in placements:
            decklist_rows = conn.execute(
                """
                SELECT DISTINCT c.card_name_jp, c.card_name_en, c.count, c.category
                FROM cl_placements cp
                JOIN cl_decklist_cards c ON c.placement_id = cp.id
                WHERE cp.event_id = ? AND cp.standing = ? AND cp.player_name = ?
                ORDER BY c.category, c.card_name_jp
                """,
                (event["id"], p["standing"], p["player_name"]),
            ).fetchall()

            decklist = []
            classifier_cards = []
            for card in decklist_rows:
                jp_name = card["card_name_jp"]
                # Use existing EN name, or translate via jp_en_lookup
                en_name = card["card_name_en"] or jp_en_lookup.get(jp_name)
                if en_name:
                    translated_count += 1
                elif jp_name:
                    untranslated_names.add(jp_name)

                raw_cat = card["category"]
                normalized_cat = raw_cat.strip().title() if raw_cat else None
                if normalized_cat in ("Pokemon", "Trainer", "Energy"):
                    category = normalized_cat
                else:
                    logger.warning(
                        "Unexpected card category %r for card %r, defaulting to Trainer",
                        raw_cat,
                        jp_name,
                    )
                    category = "Trainer"

                decklist.append(
                    {
                        "card_name_jp": jp_name,
                        "card_name_en": en_name,
                        "count": card["count"],
                        "category": category,
                        "image_url": image_lookup.get(en_name) if en_name else None,
                    }
                )

                if en_name:
                    classifier_cards.append(
                        {
                            "card_name": en_name,
                            "count": card["count"],
                            "category": category,
                        }
                    )

            # Classify archetype from EN-translated cards (untranslated-only decklists yield "Unknown")
            try:
                archetype_name = (
                    classify_decklist(classifier_cards) if classifier_cards else "Unknown"
                )
            except (ValueError, KeyError) as exc:
                logger.error(
                    "Failed to classify decklist for %s (standing %d): %s",
                    p["player_name"],
                    p["standing"],
                    exc,
                    exc_info=True,
                )
                archetype_name = "Unknown"
            is_known = archetype_name != "Unknown"

            if is_known:
                archetype_counts[archetype_name] = archetype_counts.get(archetype_name, 0) + 1

            if is_known:
                raw_tier = tier_lookup.get(archetype_name)
                tier = raw_tier if raw_tier in ("S", "A", "B", "C", "Rogue") else None
                try:
                    sprite_filenames = _get_sprite_filenames(archetype_name)
                except (KeyError, ValueError) as exc:
                    logger.warning(
                        "Failed to get sprite filenames for archetype %r: %s",
                        archetype_name,
                        exc,
                        exc_info=True,
                    )
                    sprite_filenames = []
            else:
                tier = None
                sprite_filenames = None

            placement_list.append(
                {
                    "standing": p["standing"],
                    "player_name": p["player_name"],
                    "region": p["region"],
                    "deck_code": p["deck_code"],
                    "archetype": archetype_name if is_known else None,
                    "tier": tier,
                    "sprite_filenames": sprite_filenames,
                    "decklist": decklist,
                }
            )

        # Build archetype summary (exclude Unknown, sort by count desc)
        summary_entries = []
        for name, count in archetype_counts.items():
            try:
                sprites = _get_sprite_filenames(name)
            except (KeyError, ValueError) as exc:
                logger.warning(
                    "Failed to get sprite filenames for archetype summary %r: %s",
                    name,
                    exc,
                    exc_info=True,
                )
                sprites = []
            summary_entries.append({"archetype": name, "count": count, "sprite_filenames": sprites})
        archetype_summary = sorted(summary_entries, key=lambda x: x["count"], reverse=True)

        division_data = {
            "event_id": event["id"],
            "event_name": event["name"],
            "division": division,
            "date": event["date"],
            "archetype_summary": archetype_summary,
            "placements": placement_list,
        }

        _write_json(division_data, cl_dir / f"{division}.json")

    if untranslated_names:
        logger.warning(
            "CL cards without EN translation (%d): %s",
            len(untranslated_names),
            ", ".join(sorted(untranslated_names)[:10]),
        )
    logger.info("CL translation: %d cards translated", translated_count)


def export_images(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Download Pokemon sprites and card images as static assets."""
    sprite_dir = output_dir.parent / "images" / "sprites"
    sprite_dir.mkdir(parents=True, exist_ok=True)

    card_dir = output_dir.parent / "images" / "cards"
    card_dir.mkdir(parents=True, exist_ok=True)

    # Collect all unique sprite filenames from all archetypes
    snapshot = get_latest_snapshot(conn)
    if not snapshot:
        return

    sprite_files: set[str] = set()
    for arch in snapshot["archetypes"]:
        filenames = _get_sprite_filenames(arch["archetype"])
        for fn in filenames:
            sprite_files.add(fn)

    # Download sprites
    downloaded = 0
    for filename in sorted(sprite_files):
        dest = sprite_dir / filename
        if dest.exists():
            continue
        name = filename.replace(".png", "")
        url = f"https://r2.limitlesstcg.net/pokemon/gen9/{name}.png"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Scout/1.0"})
            with urllib.request.urlopen(req) as resp:
                dest.write_bytes(resp.read())
            downloaded += 1
        except Exception as e:
            logger.warning("Failed to download sprite %s: %s", filename, e)

    logger.info(
        "Sprites: %d downloaded, %d already cached", downloaded, len(sprite_files) - downloaded
    )

    # Download card images for top 50 buylist cards
    buylist = generate_buylist(conn, snapshot["id"])
    if not buylist:
        return

    card_rows = conn.execute(
        "SELECT id, name_en, set_code, set_number, image_url FROM cards WHERE image_url IS NOT NULL"
    ).fetchall()
    card_by_name: dict[str, dict] = {}
    for row in card_rows:
        card_by_name[row["name_en"]] = {
            "id": row["id"],
            "set_code": row["set_code"],
            "set_number": row["set_number"],
            "image_url": row["image_url"],
        }

    card_downloaded = 0
    for card in buylist[:50]:
        info = card_by_name.get(card["card_name"])
        if not info or not info["image_url"]:
            continue
        safe_name = re.sub(r"[^a-z0-9-]", "-", card["card_name"].lower()).strip("-")
        dest = card_dir / f"{safe_name}.png"
        if dest.exists():
            continue
        try:
            req = urllib.request.Request(
                info["image_url"], headers={"User-Agent": "Mozilla/5.0 Scout/1.0"}
            )
            with urllib.request.urlopen(req) as resp:
                dest.write_bytes(resp.read())
            card_downloaded += 1
        except Exception as e:
            logger.warning("Failed to download card image %s: %s", card["card_name"], e)

    logger.info("Card images: %d downloaded for top buylist cards", card_downloaded)


def export_timeline(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export weekly meta share timeline for the top 12 archetypes."""
    # Get all placements with tournament info, ordered by date
    rows = conn.execute(
        """
        SELECT t.id as tid, t.date, p.archetype
        FROM placements p
        JOIN tournaments t ON t.id = p.tournament_id
        ORDER BY t.date
        """
    ).fetchall()

    if not rows:
        return

    # Group placements into ISO weeks (Monday-based)
    week_data: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    week_totals: dict[str, int] = defaultdict(int)
    week_tournament_ids: dict[str, set[str]] = defaultdict(set)
    archetype_totals: dict[str, int] = defaultdict(int)

    for row in rows:
        # Compute Monday of the week for this date
        d = date.fromisoformat(row["date"])
        monday = d - timedelta(days=d.weekday())
        week_key = monday.isoformat()

        week_data[week_key][row["archetype"]] += 1
        week_totals[week_key] += 1
        week_tournament_ids[week_key].add(row["tid"])
        archetype_totals[row["archetype"]] += 1

    # Determine top 12 archetypes by total deck count
    top_archetypes = sorted(archetype_totals, key=archetype_totals.get, reverse=True)[:12]

    # Build output
    weeks = []
    for week_key in sorted(week_data):
        total = week_totals[week_key]
        archetypes_shares = {}
        for arch_name in top_archetypes:
            count = week_data[week_key].get(arch_name, 0)
            share = round(count / total * 100, 1) if total > 0 else 0
            archetypes_shares[arch_name] = share

        weeks.append(
            {
                "week": week_key,
                "tournament_count": len(week_tournament_ids[week_key]),
                "deck_count": total,
                "archetypes": archetypes_shares,
            }
        )

    timeline = {
        "weeks": weeks,
        "archetype_order": top_archetypes,
    }

    _write_json(timeline, output_dir / "timeline.json")


def export_cards(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export card index, individual card detail JSON files, and synergy data."""
    cards = compute_card_stats(conn)
    if not cards:
        logger.warning("No card stats to export")
        return

    cards_dir = output_dir / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)

    # Compute synergy data
    synergy_data = compute_synergy_pairs(conn)
    per_card_synergy = synergy_data.get("per_card", {})

    # Export synergy pairs file
    if synergy_data["pairs"]:
        _write_json(synergy_data["pairs"], cards_dir / "synergy.json")
        logger.info("Exported %d synergy pairs", len(synergy_data["pairs"]))

    index_entries = []
    detail_count = 0
    min_appearances_for_detail = 3

    for card in cards:
        name = card["card_name"]

        # For index: compute trend direction from the detail if available
        trend_direction = "stable"
        if card["total_appearances"] >= min_appearances_for_detail:
            detail = compute_card_detail(conn, name)
            if detail:
                trend_direction = detail["trend_direction"]

                # Attach synergy partners to detail
                if name in per_card_synergy:
                    detail["synergy_partners"] = per_card_synergy[name]

                # Write individual detail file
                _write_json(detail, cards_dir / f"{detail['card_slug']}.json")
                detail_count += 1

        index_entries.append(
            {
                "card_name": name,
                "card_slug": card["card_slug"],
                "card_id": card.get("card_id"),
                "set_code": card.get("set_code"),
                "set_number": card.get("set_number"),
                "image_url": card.get("image_url"),
                "category": card["category"],
                "rarity": card.get("rarity"),
                "usage_pct": card["usage_pct"],
                "avg_copies": card["avg_copies"],
                "top_archetype": None,
                "trend_direction": trend_direction,
            }
        )

    # Populate top_archetype from detail data where available
    for entry in index_entries:
        if entry["top_archetype"] is None:
            row = conn.execute(
                """
                SELECT p.archetype, COUNT(*) as cnt
                FROM decklist_cards dc
                JOIN placements p ON p.id = dc.placement_id
                WHERE dc.card_name = ?
                GROUP BY p.archetype
                ORDER BY cnt DESC
                LIMIT 1
                """,
                (entry["card_name"],),
            ).fetchone()
            if row:
                entry["top_archetype"] = row["archetype"]

    _write_json(index_entries, cards_dir / "index.json")
    logger.info(
        "Exported card index (%d cards) and %d detail files", len(index_entries), detail_count
    )


def export_meta_evolution(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export format-wide meta evolution — top card movements across all archetypes."""
    movements = compute_meta_evolution(conn)
    _write_json(movements, output_dir / "meta-evolution.json")
    logger.info("Exported %d meta evolution movements", len(movements))


def export_matchup_matrix(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export archetype performance matchup matrix."""
    data = compute_matchup_matrix(conn)
    if data["archetypes"]:
        _write_json(data, output_dir / "matchup.json")
        logger.info("Exported matchup matrix (%d archetypes)", len(data["archetypes"]))


def export_archetype_overlap(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export archetype card overlap matrix for heat map visualization."""
    data = compute_archetype_overlap_matrix(conn)
    if data["archetypes"]:
        _write_json(data, output_dir / "archetype-overlap.json")
        logger.info("Exported archetype overlap matrix (%d archetypes)", len(data["archetypes"]))


def export_all(
    conn: sqlite3.Connection, output_dir: Path | None = None, format_slug: str | None = None
) -> Path:
    """Run all exports. Returns the output directory."""
    base = output_dir or DEFAULT_OUTPUT_DIR
    # Write to format subdirectory
    slug = format_slug or DEFAULT_FORMAT
    out = base / slug
    out.mkdir(parents=True, exist_ok=True)

    logger.info("Exporting web data to %s", out)

    export_meta(conn, out, format_slug=slug)
    export_buylist(conn, out)
    export_staples(conn, out)
    export_flex(conn, out)
    export_trends(conn, out, format_slug=slug)
    export_winning_edge(conn, out)
    export_ace_specs(conn, out)
    export_archetypes(conn, out)
    export_champions_league(conn, out)
    export_images(conn, out)
    export_timeline(conn, out)
    for export_fn, name in [
        (export_cards, "cards"),
        (export_archetype_overlap, "archetype overlap"),
        (export_matchup_matrix, "matchup matrix"),
        (export_meta_evolution, "meta evolution"),
    ]:
        try:
            export_fn(conn, out)
        except (sqlite3.OperationalError, ValueError) as exc:
            logger.warning("Skipping %s export (data unavailable): %s", name, exc)
    export_windowed(conn, out, format_slug=slug)

    logger.info("Export complete")
    return out


def export_formats(output_dir: Path | None = None) -> None:
    """Export formats.json manifest with all format metadata and status."""
    base = output_dir or DEFAULT_OUTPUT_DIR
    base.mkdir(parents=True, exist_ok=True)

    formats = []
    for slug, fmt in FORMATS.items():
        # Check if data exists for this format
        meta_path = base / slug / "meta.json"
        status = "active" if meta_path.exists() else "upcoming"

        # Read stats from meta.json if it exists
        tournament_count = 0
        deck_count = 0
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                tournament_count = meta.get("tournament_count", 0)
                deck_count = meta.get("deck_count", 0)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to read meta.json for %s: %s", slug, exc)

        formats.append(
            {
                "slug": slug,
                "name": fmt["name"],
                "name_en": fmt["name_en"],
                "description": fmt["description"],
                "dataset_start": fmt["dataset_start"],
                "dataset_end": fmt["dataset_end"],
                "status": status,
                "tournament_count": tournament_count,
                "deck_count": deck_count,
            }
        )

    _write_json(formats, base / "formats.json")
