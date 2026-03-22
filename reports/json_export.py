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
    EN_CARD_ALIASES,
    build_category_lookup,
    build_jp_en_lookup,
    classify_card,
    compute_card_detail,
    compute_card_stats,
)
from analysis.deep_dive import (
    compute_notable_techs,
    compute_placement_distribution,
    compute_weekly_card_timeline,
    compute_weighted_consensus_60,
)
from analysis.evolution import compute_archetype_evolution, compute_meta_evolution
from analysis.matchup import compute_matchup_matrix
from analysis.meta import get_latest_snapshot
from analysis.optimal_60 import compute_optimal_60
from analysis.synergy import compute_archetype_overlap_matrix, compute_synergy_pairs
from analysis.tech_forecast import compute_tech_forecast
from config import (
    DATASET_END,
    DATASET_START,
    DEFAULT_FORMAT,
    FORMATS,
    PLACEMENT_WEIGHT_DEFAULT,
    PLACEMENT_WEIGHTS,
    ROTATION_DATE,
    TECH_CARD_WATCHLIST,
    TIER_THRESHOLDS,
    get_format_config,
)
from scraper.card_mappings import tcgdex_to_limitless

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


def _normalize_card_name(name: str) -> str:
    """Normalize a card name via EN_CARD_ALIASES."""
    return EN_CARD_ALIASES.get(name, name)


def _merge_aliased_card_rows(
    rows: list[dict],
    name_key: str = "card_name",
    sum_keys: tuple[str, ...] = ("early_count", "late_count"),
) -> list[dict]:
    """Merge rows that map to the same canonical card name via EN_CARD_ALIASES.

    Sums numeric fields in sum_keys; keeps the first row's other values.
    """
    merged: dict[str, dict] = {}
    for row in rows:
        canonical = _normalize_card_name(row[name_key])
        if canonical in merged:
            for k in sum_keys:
                if k in merged[canonical] and k in row:
                    merged[canonical][k] += row[k]
        else:
            merged[canonical] = dict(row)
            merged[canonical][name_key] = canonical
    return list(merged.values())


def build_card_set_lookup(conn: sqlite3.Connection) -> dict[str, tuple[str, str]]:
    """Build a card_name -> (limitless_set_code, set_number) mapping.

    For each card_name, picks the most frequently used card_id from decklist_cards,
    parses its TCGdex set code, and maps to the Limitless equivalent.
    """
    rows = conn.execute(
        """
        SELECT dc.card_name, dc.card_id, COUNT(*) AS freq
        FROM decklist_cards dc
        WHERE dc.card_id IS NOT NULL AND dc.card_id != ''
        GROUP BY dc.card_name, dc.card_id
        ORDER BY dc.card_name, freq DESC
        """
    ).fetchall()

    lookup: dict[str, tuple[str, str]] = {}
    for row in rows:
        card_name = row["card_name"]
        if card_name in lookup:
            continue  # already have the most frequent card_id for this name
        card_id = row["card_id"]
        # card_id format: "SET-NUMBER" (e.g., "sv08-028", "me01-114")
        parts = card_id.rsplit("-", 1)
        if len(parts) != 2:
            continue
        tcgdex_set, number = parts
        limitless_set = tcgdex_to_limitless(tcgdex_set)
        # Strip leading zeros from number for display (028 -> 28)
        display_number = number.lstrip("0") or "0"
        lookup[card_name] = (limitless_set, display_number)
    return lookup


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
    "オーガポン いしずえのめんex": "Cornerstone Mask Ogerpon ex",
    "オーガポン いどのめんex": "Wellspring Mask Ogerpon ex",
    "オーガポン かまどのめんex": "Hearthflame Mask Ogerpon ex",
    "オーガポン みどりのめんex": "Teal Mask Ogerpon ex",
    "カプ・コケコex": "Tapu Koko ex",
    "ガチグマ アカツキex": "Bloodmoon Ursaluna ex",
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
    "グロウ草エネルギー": "Grow Grass Energy",
    "ニトロ炎エネルギー": "Nitro Fire Energy",
    "バブル水エネルギー": "Bubble Water Energy",
    "マグネット鋼エネルギー": "Magnet Steel Energy",
    "ブーメランエネルギー": "Boomerang Energy",
    # --- Mega Pokemon ---
    "メガカイリューex": "Mega Dragonite ex",
    "メガクチートex": "Mega Mawile ex",
    "メガゲッコウガex": "Mega Greninja ex",
    "メガゲンガーex": "Mega Gengar ex",
    "メガサメハダーex": "Mega Sharpedo ex",
    "メガサーナイトex": "Mega Gardevoir ex",
    "メガスターミーex": "Mega Starmie ex",
    "メガタブンネex": "Mega Audino ex",
    "メガディアンシーex": "Mega Diancie ex",
    "メガドラミドロex": "Mega Dragalge ex",
    "メガピクシーex": "Mega Clefable ex",
    "メガフシギバナex": "Mega Venusaur ex",
    "メガフラエッテex": "Mega Floette ex",
    "メガヘラクロスex": "Mega Heracross ex",
    "メガミミロップex": "Mega Lopunny ex",
    "メガメガニウムex": "Mega Meganium ex",
    "メガヤンマex": "Mega Yanmega ex",
    "メガリザードンXex": "Mega Charizard X ex",
    # --- Pokemon (additional) ---
    "アズマオウ": "Seaking",
    "アチャモ": "Torchic",
    "アマルルガ": "Aurorus",
    "アラブルタケ": "Brute Bonnet",
    "アンジュフラエッテ": "Anzu Floette",
    "イイネイヌ": "Okidogi",
    "イベルタルex": "Yveltal ex",
    "イーユイ": "Chi-Yu",
    "ウガツホムラ": "Gouging Fire",
    "ウガツホムラex": "Gouging Fire ex",
    "ウネルミナモex": "Walking Wake ex",
    "エモンガ": "Emolga",
    "エレズン": "Toxel",
    "エースバーン": "Cinderace",
    "オニゴーリ": "Glalie",
    "オノノクス": "Haxorus",
    "カジッチュ": "Applin",
    "カミッチュ": "Dipplin",
    "カミツオロチex": "Hydrapple ex",
    "カメテテ": "Binacle",
    "カルボウ": "Charcadet",
    "カプ・ブルル": "Tapu Bulu",
    "ガチグマ アカツキ": "Bloodmoon Ursaluna",
    "ガメノデス": "Barbaracle",
    "キバニア": "Carvanha",
    "キリンリキ": "Girafarig",
    "キルリア": "Kirlia",
    "ギルガルド": "Aegislash",
    "クズモー": "Skrelp",
    "グレイシアex": "Glaceon ex",
    "ケロマツ": "Froakie",
    "ゲコガシラ": "Frogadier",
    "ゲッコウガex": "Greninja ex",
    "ゲンガー": "Gengar",
    "コクーン": "Kakuna",
    "コフキムシ": "Scatterbug",
    "コフーライ": "Spewpa",
    "コライドン": "Koraidon",
    "コライドンex": "Koraidon ex",
    "ゴリランダー": "Rillaboom",
    "ゴルバット": "Golbat",
    "ゴース": "Gastly",
    "ゴースト": "Haunter",
    "サケブシッポex": "Scream Tail ex",
    "サザンドラex": "Hydreigon ex",
    "サルノリ": "Grookey",
    "サンダー": "Zapdos",
    "サンダースex": "Jolteon ex",
    "ザルード": "Zarude",
    "シガロコ": "Rellor",
    "シュシュプ": "Spritzee",
    "ジヘッド": "Zweilous",
    "ジュナイパーex": "Decidueye ex",
    "ジュラルドン": "Duraludon",
    "ジーランス": "Relicanth",
    "ストリンダー": "Toxtricity",
    "スナノケガワ": "Sandy Shocks",
    "スピアーex": "Beedrill ex",
    "ズバット": "Zubat",
    "セレビィ": "Celebi",
    "ゼラオラ": "Zeraora",
    "ゼルネアス": "Xerneas",
    "ソウブレイズex": "Ceruledge ex",
    "ダンバル": "Beldum",
    "チュリネ": "Petilil",
    "チラチーノex": "Cinccino ex",
    "チラーミィ": "Minccino",
    "テツノカシラex": "Iron Crown ex",
    "ディアルガ": "Dialga",
    "ディンルー": "Ting-Lu",
    "デオキシス": "Deoxys",
    "デカグース": "Gumshoos",
    "デンチュラ": "Galvantula",
    "デンチュラex": "Galvantula ex",
    "トゲキッス": "Togekiss",
    "トゲチック": "Togetic",
    "トゲピー": "Togepi",
    "トサキント": "Goldeen",
    "ドレディア": "Lilligant",
    "ドータクン": "Bronzong",
    "ドーミラー": "Bronzor",
    "ナゲツケサル": "Passimian",
    "ナックラー": "Trapinch",
    "ニダンギル": "Doublade",
    "ニンフィア": "Sylveon",
    "ニンフィアex": "Sylveon ex",
    "ノココッチex": "Dudunsparce ex",
    "ハクリュー": "Dragonair",
    "ハバタクカミ": "Flutter Mane",
    "バケッチャ": "Pumpkaboo",
    "バシャーモ": "Blaziken",
    "バシャーモex": "Blaziken ex",
    "バチンキー": "Thwackey",
    "バッフロン": "Bouffalant",
    "パルデア ケンタロス": "Paldean Tauros",
    "パンプジンex": "Gourgeist ex",
    "ヒトカゲ": "Charmander",
    "ヒトツキ": "Honedge",
    "ヒトデマン": "Staryu",
    "ヒバニー": "Scorbunny",
    "ヒンバス": "Feebas",
    "ヒードラン": "Heatran",
    "ビクティニ": "Victini",
    "ビビヨン": "Vivillon",
    "ビブラーバ": "Vibrava",
    "ビードル": "Weedle",
    "ピカチュウex": "Pikachu ex",
    "ピクシー": "Clefable",
    "ピッピ": "Clefairy",
    "ファイヤー": "Moltres",
    "フクスロー": "Dartrix",
    "フシギソウ": "Ivysaur",
    "フシギダネ": "Bulbasaur",
    "フライゴンex": "Flygon ex",
    "フレフワン": "Aromatisse",
    "ブラックキュレムex": "Black Kyurem ex",
    "ブリジュラス": "Archaludon",
    "ブリジュラスex": "Archaludon ex",
    "ブルンゲルex": "Jellicent ex",
    "プルリル": "Frillish",
    "ベラカス": "Rabsca",
    "ホウオウ": "Ho-Oh",
    "ホルビー": "Bunnelby",
    "ホルード": "Diggersby",
    "ママンボウ": "Alomomola",
    "マラカッチ": "Maractus",
    "ミニリュウ": "Dratini",
    "ミネズミ": "Patrat",
    "ミミロル": "Buneary",
    "ミロカロスex": "Milotic ex",
    "メタグロス": "Metagross",
    "メタング": "Metang",
    "メレシー": "Carbink",
    "モクロー": "Rowlet",
    "モグリュー": "Drilbur",
    "モノズ": "Deino",
    "モモワロウ": "Pecharunt",
    "モモワロウex": "Pecharunt ex",
    "ヤングース": "Yungoos",
    "ヤンヤンマ": "Yanma",
    "ユクシー": "Uxie",
    "ラブトロス": "Enamorus",
    "ラルトス": "Ralts",
    "リキキリンex": "Farigiraf ex",
    "リーリエのしんじゅ": "Lillie's Pearl",
    "ルチャブル": "Hawlucha",
    "レイスポス": "Spectrier",
    "レシラムex": "Reshiram ex",
    "レジギガス": "Regigigas",
    "ワカシャモ": "Combusken",
    "ワニノコ": "Totodile",
    # --- Character Pokemon ---
    "Nのシンボラー": "N's Sigilyph",
    "Nのゼクロム": "N's Zekrom",
    "Nのゾロア": "N's Zorua",
    "Nのゾロアークex": "N's Zoroark ex",
    "Nのダルマッカ": "N's Darumaka",
    "Nのヒヒダルマ": "N's Darmanitan",
    "Nのレシラム": "N's Reshiram",
    "ナンジャモのカイデン": "Iono's Wattrel",
    "ナンジャモのズピカ": "Iono's Bellibolt",
    "ナンジャモのタイカイデン": "Iono's Kilowattrel",
    "ナンジャモのハラバリーex": "Iono's Bellibolt ex",
    "ナンジャモのビリリダマ": "Iono's Voltorb",
    "カスミのギャラドス": "Misty's Gyarados",
    "カスミのコイキング": "Misty's Magikarp",
    "カスミのコダック": "Misty's Psyduck",
    "カスミのスターミー": "Misty's Starmie",
    "カスミのヒトデマン": "Misty's Staryu",
    "ホップのウッウ": "Hop's Cramorant",
    "ホップのウールー": "Hop's Wooloo",
    "ホップのオーロット": "Hop's Trevenant",
    "ホップのカビゴン": "Hop's Snorlax",
    "ホップのザシアンex": "Hop's Zacian ex",
    "ホップのバイウールー": "Hop's Dubwool",
    "ホップのボクレー": "Hop's Phantump",
    "ヒビキのウソッキー": "Ethan's Sudowoodo",
    "ヒビキのバクフーン": "Ethan's Typhlosion",
    "ヒビキのヒノアラシ": "Ethan's Cyndaquil",
    "ヒビキのピチュー": "Ethan's Pichu",
    "ヒビキのマグマラシ": "Ethan's Quilava",
    "マリィのモルペコ": "Marnie's Morpeko",
    "ロケット団のガルーラex": "Team Rocket's Kangaskhan ex",
    "ロケット団のクロバットex": "Team Rocket's Crobat ex",
    "ロケット団のゴルバット": "Team Rocket's Golbat",
    "ロケット団のズバット": "Team Rocket's Zubat",
    "ロケット団のソーナンス": "Team Rocket's Wobbuffet",
    "ロケット団のニューラ": "Team Rocket's Sneasel",
    "ロケット団のポリゴンZ": "Team Rocket's Porygon-Z",
    # --- Character Trainers ---
    "アセロラのいたずら": "Acerola's Prank",
    "AZの安らぎ": "AZ's Serenity",
    "Nの城": "N's Castle",
    "Nのポイントアップ": "N's Power Up",
    "アイリスの闘志": "Iris's Fighting Spirit",
    "アンズの秘技": "Janine's Secret Art",
    "カキツバタ": "Kakitsubata",
    "カシオペア": "Cassiopeia",
    "カナリィ": "Canary",
    "ギーマの一手": "Grimsley's Move",
    "ゴヨウ": "Lucian",
    "サザレ": "Sazare",
    "ジプソ": "Gypso",
    "セイジ": "Sage",
    "タラゴン": "Tarragon",
    "タロ": "Talo",
    "ハッサク": "Hassel",
    "ヒビキの冒険": "Ethan's Adventure",
    "ビリオとネア": "Bilio and Nea",
    "ホップのバッグ": "Hop's Bag",
    "ホップのこだわりハチマキ": "Hop's Choice Band",
    "ホミカの演奏": "Roxie's Performance",
    "マコモ": "Fennel",
    "マチスの取引": "Lt. Surge's Deal",
    "ユカリ": "Yukari",
    "ルチアのアピール": "Lucia's Appeal",
    "ロケット団のスーパーボール": "Team Rocket's Great Ball",
    "ロケット団のびっくりボム": "Team Rocket's Surprise Bomb",
    # --- Trainers (additional) ---
    "あやしい時計": "Suspicious Clock",
    "いいきずぐすり": "Potion",
    "おとりよせボックス": "Order Box",
    "お祭り会場": "Festival Grounds",
    "くさりもち": "Leftovers",
    "つりざおMAX(ACE SPEC)": "Super Rod MAX",
    "でんきだま": "Light Ball",
    "とりかえチケット": "Switch Ticket",
    "なみのりビーチ": "Surfing Beach",
    "ぼうがいレター": "Interference Letter",
    "むしよけスプレー": "Repel",
    "エネはたき": "Energy Removal",
    "カウンターゲイン": "Counter Gain",
    "クラッシュハンマー": "Crushing Hammer",
    "コアメモリ": "Core Memory",
    "コック": "Chef",
    "サバイブギプス(ACE SPEC)": "Survival Cast",
    "スペシャルレッドカード": "Special Red Card",
    "ダークボール": "Dusk Ball",
    "デラックスボム(ACE SPEC)": "Deluxe Bomb",
    "ニュートラルセンター(ACE SPEC)": "Neutral Center",
    "ハイパーアロマ(ACE SPEC)": "Hyper Aroma",
    "ハッコウシティ": "Levincia",
    "ハバンのみ": "Haban Berry",
    "ハロンタウン": "Haron Town",
    "ハンディサーキュレーター": "Handy Circulator",
    "ハンドトリマー": "Hand Trimmer",
    "パンクメット": "Punk Helmet",
    "パーフェクトミキサー(ACE SPEC)": "Perfect Mixer",
    "ヒートバーナー": "Heat Burner",
    "フルメタルラボ": "Full Metal Lab",
    "ブレイブバングル": "Brave Bangle",
    "プライムキャッチャー(ACE SPEC)": "Prime Catcher",
    "プリズムタワー": "Prism Tower",
    "ポケモンキャッチャー": "Pokemon Catcher",
    "メガシグナル": "Mega Signal",
    "ミアレシティ": "Lumiose City",
    "ミステリーガーデン": "Mystery Garden",
    "偉大な大樹(ACE SPEC)": "Great Tree",
    "力の砂時計": "Power Hourglass",
    "危険な密林": "Dangerous Jungle",
    "夜の鉱山": "Night Mine",
    "大漁ネット": "Fishing Net",
    "探検家の先導": "Explorer's Guide",
    "推理セット": "Detective Set",
    "緊急ボード": "Emergency Board",
    "重力玉": "Gravity Ball",
    # --- Missing translations (low-frequency) ---
    "Nのバイバニラ": "N's Vanilluxe",
    "アバゴーラ": "Carracosta",
    "イイネイヌex": "Okidogi ex",
    "ウエートレス": "Waitress",
    "オーダイル": "Feraligatr",
    "きずぐすり": "Potion",
    "ぶあついうろこ": "Thick Scales",
    "スクランブルスイッチ(ACE SPEC)": "Scramble Switch",
    "デリバード": "Delibird",
    "フォッコ": "Fennekin",
    "プロトーガ": "Tirtouga",
    "マフォクシー": "Delphox",
    "マリル": "Marill",
    "マリルリ": "Azumarill",
    "メガラティアスex": "Mega Latias ex",
    "ミライドンex": "Miraidon ex",
    "モルペコ": "Morpeko",
    "リグレー": "Elgyem",
    "古びたふたの化石": "Old Dome Fossil",
    # --- Accent normalization (Limitless uses accented, we normalize to ASCII) ---
    "Poké Pad": "Poke Pad",
    "Pokégear 3.0": "Pokegear 3.0",
    "Pokémon Catcher": "Pokemon Catcher",
}

_CARD_NAME_KEYS = frozenset({"card_name", "card", "card_a", "card_b"})

_JP_RE = re.compile(r"[\u3000-\u9fff\uff00-\uffef]")


def _translate_card_names(data: dict | list, lookup: dict[str, str]) -> dict | list:
    """Recursively translate JP card names in exported data using lookup.

    For card names with official translations, replaces with EN name.
    For JP names without a translation, keeps the original name.
    """
    if isinstance(data, list):
        return [_translate_card_names(item, lookup) for item in data]
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key in _CARD_NAME_KEYS and isinstance(value, str) and _JP_RE.search(value):
                en = lookup.get(value)
                if en:
                    result[key] = en
                    result[f"{key}_jp"] = value
                else:
                    result[key] = value
            elif isinstance(value, (dict, list)):
                result[key] = _translate_card_names(value, lookup)
            else:
                result[key] = value
        return result
    return data


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
    """Return performance-weighted meta share for each archetype.

    Uses cached weighted_share from archetype_stats if available (computed during
    meta snapshot). Falls back to computing from scratch for older snapshots.
    """
    # Try cached values first (handle both dict and sqlite3.Row objects)
    archetypes = snapshot.get("archetypes", [])
    try:
        cached = {
            a["archetype"]: a["weighted_share"]
            for a in archetypes
            if a["weighted_share"] is not None
        }
        if cached:
            return cached
    except (KeyError, IndexError):
        # KeyError: dict archetypes missing weighted_share key (pre-migration data)
        # IndexError: sqlite3.Row objects without weighted_share column
        logger.info(
            "weighted_share not in snapshot archetypes (pre-migration data), computing from scratch"
        )

    # Fallback: compute from scratch (for snapshots without cached values)
    rows = conn.execute(
        """
        SELECT p.archetype, p.standing
        FROM open_placements p
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
        FROM open_placements p
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


def _bulk_fetch_archetype_placements(
    conn: sqlite3.Connection,
) -> dict[str, list[dict]]:
    """Fetch all open placements grouped by archetype in a single query.

    Returns {archetype_name: [{"id": int, "standing": int}, ...]}.
    """
    rows = conn.execute(
        "SELECT id, standing, archetype FROM open_placements ORDER BY archetype"
    ).fetchall()
    result: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        result[row["archetype"]].append({"id": row["id"], "standing": row["standing"]})
    return dict(result)


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
        FROM open_placements p
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
        JOIN open_placements p ON p.tournament_id = t.id
        WHERE t.date >= ? AND t.date <= ?
        """,
        (date_from, date_to),
    ).fetchone()["cnt"]

    # Weighted shares within the window
    weight_rows = conn.execute(
        """
        SELECT p.archetype, p.standing
        FROM open_placements p
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
        SELECT COUNT(*) FROM open_placements p
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE t.date >= ? AND t.date < ?
        """,
        (date_from, midpoint),
    ).fetchone()[0]

    late_total = conn.execute(
        """
        SELECT COUNT(*) FROM open_placements p
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
        JOIN open_placements p ON p.id = dc.placement_id
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE t.date >= ? AND t.date <= ? AND {_basic_energy_exclusion_sql()} AND dc.card_name NOT LIKE '%Energy%'
        GROUP BY dc.card_name
        HAVING early_count >= 3 AND late_count >= 3
        """,
        (midpoint, midpoint, date_from, date_to, *_basic_energy_params()),
    ).fetchall()

    # Merge aliased card names before computing percentages
    raw_rows = [
        {
            "card_name": row["card_name"],
            "early_count": row["early_count"],
            "late_count": row["late_count"],
        }
        for row in rows
    ]
    merged_rows = _merge_aliased_card_rows(raw_rows, sum_keys=("early_count", "late_count"))

    cards = []
    for row in merged_rows:
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
        SELECT COUNT(*) FROM open_placements p
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE p.archetype IN ({placeholders}) AND t.date >= ? AND t.date <= ?
        """,
        (*sa_archetypes, date_from, date_to),
    ).fetchone()[0]

    total_winners = conn.execute(
        f"""
        SELECT COUNT(*) FROM open_placements p
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
        JOIN open_placements p ON p.id = dc.placement_id
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE p.archetype IN ({placeholders})
          AND t.date >= ? AND t.date <= ?
          AND {_basic_energy_exclusion_sql()}
        GROUP BY dc.card_name
        HAVING field_decks >= 5
        """,
        (*sa_archetypes, date_from, date_to, *_basic_energy_params()),
    ).fetchall()

    # Merge aliased card names in field usage
    field_usage: dict[str, int] = {}
    for row in field_rows:
        canonical = _normalize_card_name(row["card_name"])
        field_usage[canonical] = field_usage.get(canonical, 0) + row["field_decks"]

    winner_rows = conn.execute(
        f"""
        SELECT dc.card_name,
               COUNT(DISTINCT dc.placement_id) AS winner_decks
        FROM decklist_cards dc
        JOIN open_placements p ON p.id = dc.placement_id
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE p.standing = 1 AND p.archetype IN ({placeholders})
          AND t.date >= ? AND t.date <= ?
          AND {_basic_energy_exclusion_sql()}
        GROUP BY dc.card_name
        """,
        (*sa_archetypes, date_from, date_to, *_basic_energy_params()),
    ).fetchall()

    # Merge aliased winner card names
    winner_usage: dict[str, int] = {}
    for row in winner_rows:
        canonical = _normalize_card_name(row["card_name"])
        winner_usage[canonical] = winner_usage.get(canonical, 0) + row["winner_decks"]

    cards = []
    for name, winner_decks in winner_usage.items():
        if name not in field_usage:
            continue
        field_pct = round(field_usage[name] * 100.0 / total_field, 1)
        win_pct = round(winner_decks * 100.0 / total_winners, 1)
        edge = round(win_pct - field_pct, 1)
        cards.append(
            {
                "card_name": name,
                "field_pct": field_pct,
                "win_pct": win_pct,
                "edge": edge,
                "winner_decks": winner_decks,
                "field_decks": field_usage[name],
            }
        )

    cards.sort(key=lambda x: x["edge"], reverse=True)
    return cards[:20]


def _compute_windowed_ace_specs(
    conn: sqlite3.Connection,
    date_from: str,
    date_to: str,
    total_decks: int | None = None,
) -> list[dict]:
    """Compute ACE SPEC distribution filtered to a specific date window."""
    if total_decks is None:
        total_decks = conn.execute(
            """
            SELECT COUNT(*) FROM open_placements p
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
        JOIN open_placements p ON p.id = dc.placement_id
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


def _compute_windowed_card_usage(
    conn: sqlite3.Connection,
    date_from: str,
    date_to: str,
    total_decks: int | None = None,
) -> list[dict]:
    """Compute per-card usage stats filtered to a date window.

    Returns list of {card_name, deck_count, usage_pct, avg_copies} sorted by deck_count DESC.
    """
    if total_decks is None:
        total_decks = conn.execute(
            """
            SELECT COUNT(*) FROM open_placements p
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
        JOIN open_placements p ON p.id = dc.placement_id
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE t.date >= ? AND t.date <= ?
          AND {_basic_energy_exclusion_sql()}
        GROUP BY dc.card_name
        ORDER BY deck_count DESC
        """,
        (date_from, date_to, *_basic_energy_params()),
    ).fetchall()

    return [
        {
            "card_name": row["card_name"],
            "deck_count": row["deck_count"],
            "usage_pct": round(row["deck_count"] * 100.0 / total_decks, 1),
            "avg_copies": row["avg_copies"],
        }
        for row in rows
    ]


def _filter_by_usage(
    cards: list[dict], threshold_min: float, threshold_max: float | None = None
) -> list[dict]:
    """Filter card usage list by usage_pct thresholds."""
    return [
        c
        for c in cards
        if c["usage_pct"] >= threshold_min
        and (threshold_max is None or c["usage_pct"] < threshold_max)
    ]


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
        FROM open_placements p
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

        # Pre-compute windowed deck count and card usage (shared by ace-specs, staples, flex)
        windowed_total = meta["deck_count"] or 0

        # ACE SPECs
        specs = _compute_windowed_ace_specs(conn, date_from, date_to, total_decks=windowed_total)
        _write_json(specs, output_dir / f"ace-specs-{suffix}.json")

        # Card usage query (run once, used for both staples and flex)
        card_usage = _compute_windowed_card_usage(
            conn, date_from, date_to, total_decks=windowed_total
        )

        # Staples (40%+ usage)
        staples = _filter_by_usage(card_usage, 40)
        _write_json(staples, output_dir / f"staples-{suffix}.json")

        # Flex (20-40% usage)
        flex = _filter_by_usage(card_usage, 20, 40)
        _write_json(flex, output_dir / f"flex-{suffix}.json")

        # City League Index
        cl_index = _compute_city_league_index(conn, date_from, date_to)
        _write_json(cl_index, output_dir / f"city-league-index-{suffix}.json")


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
    total_decks = conn.execute("SELECT COUNT(*) FROM open_placements").fetchone()[0]

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
    total_decks = conn.execute("SELECT COUNT(*) FROM open_placements").fetchone()[0]

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
        JOIN open_placements p ON p.id = dc.placement_id
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
        FROM open_placements p
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
        "SELECT COUNT(*) FROM open_placements p JOIN tournaments t ON t.id = p.tournament_id WHERE t.date < ?",
        (midpoint,),
    ).fetchone()[0]

    late_total = conn.execute(
        "SELECT COUNT(*) FROM open_placements p JOIN tournaments t ON t.id = p.tournament_id WHERE t.date >= ?",
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
        JOIN open_placements p ON p.id = dc.placement_id
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE {_basic_energy_exclusion_sql()} AND dc.card_name NOT LIKE '%Energy%'
        GROUP BY dc.card_name
        HAVING early_count >= ? AND late_count >= ?
        """,
        (midpoint, midpoint, *_basic_energy_params(), min_count, min_count),
    ).fetchall()

    # Merge aliased card names before computing percentages
    raw_rows = [
        {
            "card_name": row["card_name"],
            "early_count": row["early_count"],
            "late_count": row["late_count"],
        }
        for row in rows
    ]
    merged_rows = _merge_aliased_card_rows(raw_rows, sum_keys=("early_count", "late_count"))

    cards = []
    for row in merged_rows:
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
        f"SELECT COUNT(*) FROM open_placements WHERE archetype IN ({placeholders})",
        sa_archetypes,
    ).fetchone()[0]

    # Total 1st place decks in S/A/B
    total_winners = conn.execute(
        f"SELECT COUNT(*) FROM open_placements WHERE standing = 1 AND archetype IN ({placeholders})",
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
        JOIN open_placements p ON p.id = dc.placement_id
        WHERE p.archetype IN ({placeholders}) AND {_basic_energy_exclusion_sql()}
        GROUP BY dc.card_name
        HAVING field_decks >= 10
        """,
        (*sa_archetypes, *_basic_energy_params()),
    ).fetchall()

    # Merge aliased card names in field usage
    field_usage: dict[str, int] = {}
    for row in field_rows:
        canonical = _normalize_card_name(row["card_name"])
        field_usage[canonical] = field_usage.get(canonical, 0) + row["field_decks"]

    winner_rows = conn.execute(
        f"""
        SELECT dc.card_name,
               COUNT(DISTINCT dc.placement_id) AS winner_decks
        FROM decklist_cards dc
        JOIN open_placements p ON p.id = dc.placement_id
        WHERE p.standing = 1 AND p.archetype IN ({placeholders}) AND {_basic_energy_exclusion_sql()}
        GROUP BY dc.card_name
        """,
        (*sa_archetypes, *_basic_energy_params()),
    ).fetchall()

    # Merge aliased winner card names
    winner_usage: dict[str, int] = {}
    for row in winner_rows:
        canonical = _normalize_card_name(row["card_name"])
        winner_usage[canonical] = winner_usage.get(canonical, 0) + row["winner_decks"]

    cards = []
    for name, winner_decks in winner_usage.items():
        if name not in field_usage:
            continue
        field_pct = round(field_usage[name] * 100.0 / total_field, 1)
        win_pct = round(winner_decks * 100.0 / total_winners, 1)
        edge = round(win_pct - field_pct, 1)
        cards.append(
            {
                "card_name": name,
                "field_pct": field_pct,
                "win_pct": win_pct,
                "edge": edge,
                "winner_decks": winner_decks,
                "field_decks": field_usage[name],
            }
        )

    cards.sort(key=lambda x: x["edge"], reverse=True)
    _write_json(cards[:20], output_dir / "winning-edge.json")


def export_ace_specs(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export ace-specs.json — ACE SPEC card distribution across decks."""
    total_decks = conn.execute("SELECT COUNT(*) FROM open_placements").fetchone()[0]
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
    conn: sqlite3.Connection,
    placement_ids: list[int],
    category_lookup: dict[str, str] | None = None,
    include_basic_energy: bool = False,
) -> list[dict]:
    """Compute per-card inclusion stats for a set of placement IDs.

    Returns a list of dicts with card_name, inclusion_pct, avg_copies, decks_with, category.
    """
    if not placement_ids:
        return []

    total_decks = len(placement_ids)
    placeholders = ",".join("?" * len(placement_ids))
    if include_basic_energy:
        energy_clause = ""
        energy_params: tuple = ()
    else:
        energy_clause = f"AND {_basic_energy_exclusion_sql()}"
        energy_params = tuple(_basic_energy_params())
    rows = conn.execute(
        f"""
        SELECT card_name,
               COUNT(DISTINCT placement_id) AS decks_with,
               SUM(count) AS total_copies
        FROM decklist_cards dc
        WHERE placement_id IN ({placeholders}) {energy_clause}
        GROUP BY card_name
        ORDER BY decks_with DESC
        """,
        (*placement_ids, *energy_params),
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
                "category": classify_card(row["card_name"], category_lookup),
            }
        )
    return cards


def export_archetypes(
    conn: sqlite3.Connection, output_dir: Path, format_slug: str | None = None
) -> None:
    """Export per-archetype detail JSON files with core cards and tournament results."""
    format_start = None
    if format_slug:
        from config import FORMATS

        fmt_cfg = FORMATS.get(format_slug, {})
        format_start = fmt_cfg.get("dataset_start")

    snapshot = get_latest_snapshot(conn)
    if not snapshot:
        return

    weighted_shares = _compute_weighted_shares(conn, snapshot)
    category_lookup = build_category_lookup(conn)
    card_set_lookup = build_card_set_lookup(conn)
    all_placements = _bulk_fetch_archetype_placements(conn)

    arch_dir = output_dir / "archetypes"
    arch_dir.mkdir(parents=True, exist_ok=True)

    # Build JP->EN lookup once for evolution tracking across all archetypes
    jp_en_lookup = _build_jp_en_lookup(conn)

    # Compute max_deck_count across all archetypes for popularity normalization
    max_deck_count = max((a["deck_count"] for a in snapshot["archetypes"]), default=1)

    for arch in snapshot["archetypes"]:
        archetype_name = arch["archetype"]
        slug = _slugify(archetype_name)

        # Get all placements for this archetype (from bulk-fetched data)
        placements = all_placements.get(archetype_name, [])

        if not placements:
            continue

        placement_ids = [p["id"] for p in placements]

        all_cards = _compute_card_stats_for_ids(
            conn, placement_ids, category_lookup, include_basic_energy=True
        )
        core_cards = [c for c in all_cards if c["inclusion_pct"] >= 80]

        # Top-4 segmented card stats (derived from already-fetched placements)
        top4_ids = [p["id"] for p in placements if p["standing"] <= 4]
        top4_total = len(top4_ids)

        # Build field inclusion lookup for delta computation
        field_inclusion = {c["card_name"]: c["inclusion_pct"] for c in all_cards}

        top4_cards = _compute_card_stats_for_ids(
            conn, top4_ids, category_lookup, include_basic_energy=True
        )
        top4_names = {c["card_name"] for c in top4_cards}
        for card in top4_cards:
            field_pct = field_inclusion.get(card["card_name"])
            if field_pct is None:
                logger.error(
                    "Card %r found in top-4 but missing from field for archetype %s "
                    "-- this indicates a data integrity bug (top4_ids should be a subset of all placement_ids)",
                    card["card_name"],
                    archetype_name,
                )
                continue
            card["delta_vs_field"] = round(card["inclusion_pct"] - field_pct, 1)
        # Remove any cards that were skipped due to data inconsistency
        top4_cards = [c for c in top4_cards if "delta_vs_field" in c]

        # Append field-only cards absent from top-4 (negative deltas)
        if top4_ids:
            for card in all_cards:
                if card["card_name"] not in top4_names:
                    top4_cards.append(
                        {
                            **card,
                            "inclusion_pct": 0,
                            "avg_copies": 0,
                            "decks_with": 0,
                            "delta_vs_field": round(-card["inclusion_pct"], 1),
                        }
                    )

        # Tournament results — top 16 by standing ASC, date DESC
        # (limited to 16 since each result now includes full decklists)
        results_rows = conn.execute(
            """
            SELECT p.id AS placement_id, t.id AS tournament_url,
                   t.name AS tournament_name, t.date,
                   p.standing, p.player_name
            FROM open_placements p
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
                "tournament_url": r["tournament_url"],
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
                decklist = []
                for dl in dl_rows:
                    card_name = dl["card_name"]
                    set_info = card_set_lookup.get(card_name)
                    decklist.append(
                        {
                            "card_name": card_name,
                            "count": dl["count"],
                            "category": classify_card(card_name, category_lookup),
                            "set_code": set_info[0] if set_info else None,
                            "set_number": set_info[1] if set_info else None,
                        }
                    )
                decklist.sort(key=lambda c: (_category_order.get(c["category"], 99), -c["count"]))
                entry["decklist"] = decklist
            results.append(entry)

        # Radar metrics
        meta_share_val = arch["meta_share"]
        weighted_share_val = weighted_shares.get(archetype_name, 0.0)

        # Consistency: lower avg standing = higher score
        avg_row = conn.execute(
            "SELECT AVG(standing) as avg_standing FROM open_placements WHERE archetype = ?",
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
        evolution = compute_archetype_evolution(
            conn, archetype_name, jp_en_lookup=jp_en_lookup, format_start=format_start
        )

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


def export_card_analysis(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export cross-archetype card analysis aggregating top-4 deltas."""
    snapshot = get_latest_snapshot(conn)
    if not snapshot:
        return

    category_lookup = build_category_lookup(conn)
    all_placements = _bulk_fetch_archetype_placements(conn)

    archetype_tiers = {}
    for arch in snapshot["archetypes"]:
        archetype_tiers[arch["archetype"]] = arch["tier"]

    card_archetypes: dict[str, list[dict]] = defaultdict(list)

    for arch in snapshot["archetypes"]:
        archetype_name = arch["archetype"]
        placements = all_placements.get(archetype_name, [])

        placement_ids = [p["id"] for p in placements]
        top4_ids = [p["id"] for p in placements if p["standing"] <= 4]

        if len(placement_ids) < 4 or len(top4_ids) < 2:
            continue

        all_cards = _compute_card_stats_for_ids(conn, placement_ids, category_lookup)
        field_inclusion = {c["card_name"]: c["inclusion_pct"] for c in all_cards}

        top4_cards = _compute_card_stats_for_ids(conn, top4_ids, category_lookup)

        for card in top4_cards:
            field_pct = field_inclusion.get(card["card_name"], 0)
            delta = round(card["inclusion_pct"] - field_pct, 1)
            if delta == 0:
                continue
            card_archetypes[card["card_name"]].append(
                {
                    "archetype": archetype_name,
                    "slug": _slugify(archetype_name),
                    "tier": archetype_tiers.get(archetype_name, "Rogue"),
                    "delta_vs_field": delta,
                    "top4_inclusion_pct": card["inclusion_pct"],
                    "field_inclusion_pct": field_pct,
                    "avg_copies": card["avg_copies"],
                    "top4_sample_size": len(top4_ids),
                }
            )

        top4_names = {c["card_name"] for c in top4_cards}
        for card in all_cards:
            if card["card_name"] not in top4_names and card["inclusion_pct"] > 0:
                delta = round(-card["inclusion_pct"], 1)
                card_archetypes[card["card_name"]].append(
                    {
                        "archetype": archetype_name,
                        "slug": _slugify(archetype_name),
                        "tier": archetype_tiers.get(archetype_name, "Rogue"),
                        "delta_vs_field": delta,
                        "top4_inclusion_pct": 0,
                        "field_inclusion_pct": card["inclusion_pct"],
                        "avg_copies": 0,
                        "top4_sample_size": len(top4_ids),
                    }
                )

    cards = []
    for card_name, archetypes in card_archetypes.items():
        deltas = [a["delta_vs_field"] for a in archetypes]
        avg_delta = round(sum(deltas) / len(deltas), 1)
        max_entry = max(archetypes, key=lambda a: a["delta_vs_field"])
        cards.append(
            {
                "card_name": card_name,
                "category": classify_card(card_name, category_lookup),
                "archetypes": sorted(archetypes, key=lambda a: a["delta_vs_field"], reverse=True),
                "avg_delta": avg_delta,
                "archetype_count": len(archetypes),
                "max_delta": max_entry["delta_vs_field"],
                "best_archetype": max_entry["archetype"],
            }
        )

    cards.sort(key=lambda c: c["avg_delta"], reverse=True)

    _write_json(
        {"cards": cards, "generated_at": snapshot["generated_at"]},
        output_dir / "card-analysis.json",
    )


def export_card_decklists(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export per-card JSON files with top-4 placement details for drill-down.

    Creates card-decklists/{slug}.json for each card that appears in top-4
    placements, containing the tournament results where the card was used.
    """
    snapshot = get_latest_snapshot(conn)
    if not snapshot:
        logger.warning("Skipping card decklists export: no meta snapshot found")
        return

    archetype_slugs: dict[str, str] = {}
    for arch in snapshot["archetypes"]:
        archetype_slugs[arch["archetype"]] = _slugify(arch["archetype"])

    # Query all top-4 placements with their card data
    rows = conn.execute(
        """
        SELECT p.id AS placement_id, p.standing, p.archetype,
               p.decklist_url, t.name AS tournament_name, t.date
        FROM open_placements p
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE p.standing <= 4
        ORDER BY t.date DESC, p.standing ASC
        """
    ).fetchall()

    if not rows:
        logger.warning("Skipping card decklists export: no top-4 placements found")
        return

    # Build placement_id -> placement info lookup
    placement_info: dict[int, dict] = {}
    placement_ids: list[int] = []
    for r in rows:
        pid = r["placement_id"]
        placement_ids.append(pid)
        placement_info[pid] = {
            "archetype": r["archetype"],
            "archetype_slug": archetype_slugs.get(r["archetype"], _slugify(r["archetype"])),
            "tournament_name": r["tournament_name"],
            "date": r["date"],
            "standing": r["standing"],
            "decklist_url": r["decklist_url"],
        }

    # SQLite has a variable limit; batch if needed
    card_placements: dict[str, list[dict]] = defaultdict(list)
    batch_size = 500
    for i in range(0, len(placement_ids), batch_size):
        batch = placement_ids[i : i + batch_size]
        placeholders = ",".join("?" * len(batch))
        card_rows = conn.execute(
            f"SELECT placement_id, card_name, count FROM decklist_cards "
            f"WHERE placement_id IN ({placeholders})",
            batch,
        ).fetchall()
        for cr in card_rows:
            info = placement_info[cr["placement_id"]]
            card_placements[cr["card_name"]].append(
                {
                    "archetype": info["archetype"],
                    "archetype_slug": info["archetype_slug"],
                    "tournament_name": info["tournament_name"],
                    "date": info["date"],
                    "standing": info["standing"],
                    "copies": cr["count"],
                    "decklist_url": info["decklist_url"],
                }
            )

    # Write per-card JSON files
    out_dir = output_dir / "card-decklists"
    out_dir.mkdir(parents=True, exist_ok=True)

    for card_name, results in card_placements.items():
        slug = _slugify(card_name)
        if not slug:
            # Skip cards with non-ASCII-only names (e.g. JP card names)
            # that produce empty slugs -- they can't be fetched by the frontend
            continue
        _write_json(
            {
                "card_name": card_name,
                "top4_results": results,
            },
            out_dir / f"{slug}.json",
        )

    logger.info("Exported %d card decklist files to %s", len(card_placements), out_dir)


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
        FROM open_placements p
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
    """Build JP->EN card name lookup, delegating to shared builder with hardcoded fallbacks."""
    return build_jp_en_lookup(conn, fallback=JP_CARD_NAMES)


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
        FROM open_placements p
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


def export_tech_forecast(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export tech card weather forecast JSON."""
    data = compute_tech_forecast(conn, TECH_CARD_WATCHLIST)
    _write_json(data, output_dir / "tech-forecast.json")


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
                JOIN open_placements p ON p.id = dc.placement_id
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


def export_meta_evolution(
    conn: sqlite3.Connection, output_dir: Path, format_slug: str | None = None
) -> None:
    """Export format-wide meta evolution — highlights + all movements."""
    format_start = None
    if format_slug:
        from config import FORMATS

        fmt_cfg = FORMATS.get(format_slug, {})
        format_start = fmt_cfg.get("dataset_start")
    data = compute_meta_evolution(conn, format_start=format_start)
    _write_json(data, output_dir / "meta-evolution.json")
    logger.info(
        "Exported meta evolution (%d highlights, %d total movements)",
        len(data["highlights"]),
        len(data["movements"]),
    )


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


def export_deep_dive(conn: sqlite3.Connection, output_dir: Path, *, format_slug: str = "") -> None:
    """Export per-archetype deep dive report JSON files."""
    from datetime import UTC, datetime

    snapshot = get_latest_snapshot(conn)
    if not snapshot:
        logger.warning("Skipping deep dive export: no snapshot available")
        return

    category_lookup = build_category_lookup(conn)
    card_set_lookup = build_card_set_lookup(conn)
    weighted_shares = _compute_weighted_shares(conn, snapshot)
    all_placements = _bulk_fetch_archetype_placements(conn)
    report_dir = output_dir / "archetype-reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for arch in snapshot["archetypes"]:
        archetype_name = arch["archetype"]
        slug = _slugify(archetype_name)

        # Get placements (from bulk-fetched data)
        placements = all_placements.get(archetype_name, [])

        if not placements:
            logger.debug("Skipping %s: no placements found", archetype_name)
            continue

        placement_ids = [p["id"] for p in placements]
        deck_count = len(placement_ids)

        # Check minimum decklists
        has_decklists = conn.execute(
            "SELECT COUNT(DISTINCT placement_id) FROM decklist_cards WHERE placement_id IN ({})".format(
                ",".join("?" * len(placement_ids))
            ),
            placement_ids,
        ).fetchone()[0]

        if has_decklists < 3:
            logger.debug("Skipping %s: only %d decklists", archetype_name, has_decklists)
            continue

        # Compute analyses
        consensus = compute_weighted_consensus_60(
            conn, archetype_name, category_lookup, card_set_lookup=card_set_lookup
        )
        timeline = compute_weekly_card_timeline(conn, archetype_name)
        notable_techs = compute_notable_techs(timeline)
        placement_dist = compute_placement_distribution(
            [{"standing": p["standing"]} for p in placements]
        )

        # Tournament count
        tournament_count = conn.execute(
            """
            SELECT COUNT(DISTINCT t.id)
            FROM open_placements p
            JOIN tournaments t ON t.id = p.tournament_id
            WHERE p.archetype = ?
            """,
            (archetype_name,),
        ).fetchone()[0]

        best_placement = min(p["standing"] for p in placements)
        sprite_filenames = _get_sprite_filenames(archetype_name)

        report = {
            "archetype": archetype_name,
            "slug": slug,
            "format": format_slug or "",
            "generated_at": datetime.now(UTC).isoformat(),
            "tier": arch["tier"],
            "meta_share": arch["meta_share"],
            "weighted_share": weighted_shares.get(archetype_name, arch["meta_share"]),
            "deck_count": deck_count,
            "best_placement": best_placement,
            "sprite_filenames": sprite_filenames,
            "consensus_60": consensus,
            "tech_evolution": timeline,
            "notable_techs": notable_techs,
            "placement_distribution": placement_dist,
            "tournament_count": tournament_count,
            "narrative": {},
        }

        _write_json(report, report_dir / f"{slug}.json")
        count += 1

    if count == 0:
        logger.warning(
            "No deep dive reports exported (%d archetypes in snapshot, none qualified)",
            len(snapshot["archetypes"]),
        )
    else:
        logger.info("Exported %d archetype deep dive reports", count)


def export_optimal_60(conn: sqlite3.Connection, output_dir: Path, *, format_slug: str = "") -> None:
    """Export per-archetype Optimal 60 JSON files with CL-boosted consensus."""
    from datetime import UTC, datetime

    snapshot = get_latest_snapshot(conn)
    if not snapshot:
        logger.warning("Skipping optimal 60 export: no snapshot available")
        return

    category_lookup = build_category_lookup(conn)
    card_set_lookup = build_card_set_lookup(conn)
    weighted_shares = _compute_weighted_shares(conn, snapshot)
    optimal_dir = output_dir / "optimal-60"
    # Clean stale files from previous exports
    if optimal_dir.exists():
        for f in optimal_dir.glob("*.json"):
            f.unlink()
    optimal_dir.mkdir(parents=True, exist_ok=True)

    # Get CL event metadata (if any)
    cl_event = conn.execute(
        "SELECT name, player_count FROM tournaments WHERE tournament_type = 'champions-league' LIMIT 1"
    ).fetchone()
    cl_event_name = cl_event["name"] if cl_event else None
    cl_player_count = cl_event["player_count"] if cl_event else 0

    index_entries = []
    count = 0

    # S/A/B/C tiers + any archetype with CL representation
    eligible_tiers = {"S", "A", "B", "C"}
    cl_archetypes = {
        row[0]
        for row in conn.execute(
            """
            SELECT DISTINCT p.archetype
            FROM placements p
            JOIN tournaments t ON t.id = p.tournament_id
            WHERE t.tournament_type = 'champions-league'
            """
        ).fetchall()
    }

    for arch in snapshot["archetypes"]:
        if arch["tier"] not in eligible_tiers and arch["archetype"] not in cl_archetypes:
            continue

        archetype_name = arch["archetype"]
        slug = _slugify(archetype_name)

        result = compute_optimal_60(
            conn, archetype_name, category_lookup, card_set_lookup=card_set_lookup
        )
        if result is None:
            continue

        sprite_filenames = _get_sprite_filenames(archetype_name)

        # Get CL placement standings for this archetype
        cl_placements = [
            row["standing"]
            for row in conn.execute(
                """
                SELECT p.standing
                FROM placements p
                JOIN tournaments t ON t.id = p.tournament_id
                WHERE t.tournament_type = 'champions-league'
                  AND p.archetype = ?
                ORDER BY p.standing
                """,
                (archetype_name,),
            ).fetchall()
        ]
        cl_best_finish = min(cl_placements) if cl_placements else None

        detail = {
            "archetype": archetype_name,
            "slug": slug,
            "format": format_slug or "",
            "generated_at": datetime.now(UTC).isoformat(),
            "tier": arch["tier"],
            "meta_share": arch["meta_share"],
            "weighted_share": weighted_shares.get(archetype_name, arch["meta_share"]),
            "sprite_filenames": sprite_filenames,
            "quality_score": result["quality_score"],
            "cl_deck_count": result["cl_deck_count"],
            "city_league_deck_count": result["city_league_deck_count"],
            "has_cl_data": result["has_cl_data"],
            "cl_placements": cl_placements,
            "cl_best_finish": cl_best_finish,
            "total_pokemon": result["total_pokemon"],
            "total_trainer": result["total_trainer"],
            "total_energy": result["total_energy"],
            "core_lock_rate": result["core_lock_rate"],
            "innovation_index": result["innovation_index"],
            "cards": result["cards"],
            "narrative": {},
        }

        _write_json(detail, optimal_dir / f"{slug}.json")
        count += 1

        index_entries.append(
            {
                "archetype": archetype_name,
                "slug": slug,
                "tier": arch["tier"],
                "meta_share": arch["meta_share"],
                "sprite_filenames": sprite_filenames,
                "quality_score": result["quality_score"],
                "cl_deck_count": result["cl_deck_count"],
                "city_league_deck_count": result["city_league_deck_count"],
                "has_cl_data": result["has_cl_data"],
                "cl_placements": cl_placements,
                "cl_best_finish": cl_best_finish,
                "innovation_index": result["innovation_index"],
                "core_lock_rate": result["core_lock_rate"],
            }
        )

    # Write hub index
    index = {
        "format": format_slug or "",
        "generated_at": datetime.now(UTC).isoformat(),
        "cl_event": cl_event_name,
        "cl_player_count": cl_player_count,
        "format_note": "All data sources are Japanese BO1 events. See narrative for BO3 context.",
        "archetypes": index_entries,
    }
    _write_json(index, optimal_dir / "index.json")
    logger.info("Exported %d optimal 60 reports", count)


def _build_tier_lookup(conn: sqlite3.Connection) -> dict[str, str]:
    """Build archetype -> tier mapping from the latest meta snapshot."""
    rows = conn.execute(
        "SELECT archetype, tier FROM archetype_stats "
        "WHERE snapshot_id = (SELECT MAX(id) FROM meta_snapshots)"
    ).fetchall()
    return {row["archetype"]: row["tier"] for row in rows}


def _compute_city_league_index(
    conn: sqlite3.Connection,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """Compute city league tournament index data.

    If date_from/date_to are provided, filters tournaments to that window.
    """
    tier_lookup = _build_tier_lookup(conn)

    # Fetch open-division tournaments
    date_filter = ""
    params: list[str] = []
    if date_from and date_to:
        date_filter = "AND t.date >= ? AND t.date <= ?"
        params = [date_from, date_to]

    tournaments = conn.execute(
        f"""
        SELECT t.id, t.name, t.date, t.prefecture, t.player_count,
               COUNT(p.id) as deck_count
        FROM tournaments t
        LEFT JOIN placements p ON p.tournament_id = t.id
        WHERE t.division = 'open' {date_filter}
        GROUP BY t.id
        ORDER BY t.date DESC
        """,
        params,
    ).fetchall()

    if not tournaments:
        return {
            "generated_at": date.today().isoformat() + "T00:00:00Z",
            "tournament_count": 0,
            "deck_count": 0,
            "date_range": {"start": "", "end": ""},
            "rising_archetypes": [],
            "recent_winners": [],
            "tournaments": [],
        }

    t_ids = [t["id"] for t in tournaments]
    total_decks = sum(t["deck_count"] for t in tournaments)
    date_range = {
        "start": min(t["date"] for t in tournaments),
        "end": max(t["date"] for t in tournaments),
    }

    # Batch fetch top 4 finishers for all tournaments
    placeholders = ",".join("?" * len(t_ids))
    top_finishers_rows = conn.execute(
        f"""
        SELECT p.tournament_id, p.standing, p.player_name, p.archetype
        FROM placements p
        WHERE p.tournament_id IN ({placeholders}) AND p.standing <= 4
        ORDER BY p.tournament_id, p.standing
        """,
        t_ids,
    ).fetchall()

    finishers_by_tid: dict[str, list[dict]] = defaultdict(list)
    for row in top_finishers_rows:
        archetype = row["archetype"] or "Unknown"
        finishers_by_tid[row["tournament_id"]].append(
            {
                "standing": row["standing"],
                "player_name": row["player_name"] or "",
                "archetype": archetype,
                "slug": _slugify(archetype),
                "sprite_filenames": _get_sprite_filenames(archetype),
                "tier": tier_lookup.get(archetype),
            }
        )

    # Batch fetch archetype distribution
    dist_rows = conn.execute(
        f"""
        SELECT p.tournament_id, p.archetype, COUNT(*) as count
        FROM placements p
        WHERE p.tournament_id IN ({placeholders})
        GROUP BY p.tournament_id, p.archetype
        ORDER BY p.tournament_id, count DESC
        """,
        t_ids,
    ).fetchall()

    dist_by_tid: dict[str, list[dict]] = defaultdict(list)
    tid_totals: dict[str, int] = defaultdict(int)
    for row in dist_rows:
        tid_totals[row["tournament_id"]] += row["count"]

    for row in dist_rows:
        archetype = row["archetype"] or "Unknown"
        total = tid_totals[row["tournament_id"]] or 1
        dist_by_tid[row["tournament_id"]].append(
            {
                "archetype": archetype,
                "slug": _slugify(archetype),
                "count": row["count"],
                "share": round(row["count"] / total, 4),
                "sprite_filenames": _get_sprite_filenames(archetype),
            }
        )

    # Build tournament list
    tournament_list = []
    for t in tournaments:
        tournament_list.append(
            {
                "id": t["id"],
                "name": t["name"],
                "date": t["date"],
                "prefecture": t["prefecture"],
                "player_count": t["player_count"] or t["deck_count"],
                "source_url": t["id"] if t["id"].startswith("http") else None,
                "top_finishers": finishers_by_tid.get(t["id"], []),
                "archetype_distribution": dist_by_tid.get(t["id"], []),
            }
        )

    # Rising archetypes from trend computation
    trends = _compute_archetype_trends(conn)
    rising = []
    for arch, info in sorted(
        trends.items(), key=lambda x: x[1].get("trend_delta", 0), reverse=True
    ):
        if info.get("trend") in ("up", "new"):
            rising.append(
                {
                    "archetype": arch,
                    "slug": _slugify(arch),
                    "trend": info["trend"],
                    "trend_delta": info.get("trend_delta", 0),
                    "sprite_filenames": _get_sprite_filenames(arch),
                    "tier": tier_lookup.get(arch),
                }
            )
        if len(rising) >= 5:
            break

    # Recent winners (5 most recent 1st-place finishers)
    recent_winners_rows = conn.execute(
        """
        SELECT t.name, t.date, p.archetype, p.player_name
        FROM placements p
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE t.division = 'open' AND p.standing = 1
        ORDER BY t.date DESC
        LIMIT 5
        """
    ).fetchall()
    recent_winners = []
    for row in recent_winners_rows:
        archetype = row["archetype"] or "Unknown"
        recent_winners.append(
            {
                "archetype": archetype,
                "slug": _slugify(archetype),
                "sprite_filenames": _get_sprite_filenames(archetype),
                "date": row["date"],
                "tournament_name": row["name"],
                "player_name": row["player_name"] or "",
            }
        )

    return {
        "generated_at": date.today().isoformat() + "T00:00:00Z",
        "tournament_count": len(tournaments),
        "deck_count": total_decks,
        "date_range": date_range,
        "rising_archetypes": rising,
        "recent_winners": recent_winners,
        "tournaments": tournament_list,
    }


def export_city_league_index(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export city-league-index.json with tournament listing and meta metrics."""
    data = _compute_city_league_index(conn)
    _write_json(data, output_dir / "city-league-index.json")
    logger.info(
        "Exported city league index: %d tournaments, %d decks",
        data["tournament_count"],
        data["deck_count"],
    )


def export_all(
    conn: sqlite3.Connection,
    output_dir: Path | None = None,
    format_slug: str | None = None,
    strict: bool = False,
) -> tuple[Path, list[str]]:
    """Run all exports. Returns (output_directory, skipped_export_names).

    Core exports always propagate errors. When strict=True, optional exports
    (cards, overlap, matchup, evolution, tech forecast, deep dive, optimal 60)
    also propagate instead of being caught and logged.
    """
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
    export_archetypes(conn, out, format_slug=slug)
    export_card_analysis(conn, out)
    skipped: list[str] = []
    try:
        export_card_decklists(conn, out)
    except (sqlite3.OperationalError, ValueError) as exc:
        if strict:
            raise
        logger.warning("Skipping card decklists export (data unavailable): %s", exc)
        skipped.append("card decklists")
    export_champions_league(conn, out)
    export_images(conn, out)
    export_timeline(conn, out)
    try:
        export_city_league_index(conn, out)
    except (sqlite3.OperationalError, ValueError) as exc:
        if strict:
            raise
        logger.warning("Skipping city league index export: %s", exc)
        skipped.append("city league index")
    for export_fn, name in [
        (export_cards, "cards"),
        (export_archetype_overlap, "archetype overlap"),
        (export_matchup_matrix, "matchup matrix"),
        (export_tech_forecast, "tech forecast"),
    ]:
        try:
            export_fn(conn, out)
        except (sqlite3.OperationalError, ValueError) as exc:
            if strict:
                raise
            logger.warning("Skipping %s export (data unavailable): %s", name, exc)
            skipped.append(name)
    try:
        export_meta_evolution(conn, out, format_slug=slug)
    except (sqlite3.OperationalError, ValueError) as exc:
        if strict:
            raise
        logger.warning("Skipping meta evolution export (data unavailable): %s", exc)
        skipped.append("meta evolution")
    try:
        export_deep_dive(conn, out, format_slug=slug)
    except sqlite3.OperationalError as exc:
        if strict:
            raise
        logger.warning("Skipping deep dive reports export (table missing): %s", exc)
        skipped.append("deep dive")
    export_windowed(conn, out, format_slug=slug)
    try:
        export_optimal_60(conn, out, format_slug=slug)
    except sqlite3.OperationalError as exc:
        if strict:
            raise
        logger.warning("Skipping optimal 60 export: %s", exc)
        skipped.append("optimal 60")

    if skipped:
        logger.info("Skipped %d optional exports: %s", len(skipped), ", ".join(skipped))

    # Post-process: translate JP card names in all exported JSON files
    jp_en = _build_jp_en_lookup(conn)
    _translate_all_json(out, jp_en)

    logger.info("Export complete")
    return out, skipped


def _translate_all_json(directory: Path, lookup: dict[str, str]) -> None:
    """Walk all JSON files in directory and translate JP card names."""
    translated_files = 0
    failed_files = 0
    for json_path in directory.rglob("*.json"):
        try:
            raw = json_path.read_text(encoding="utf-8")
            if not _JP_RE.search(raw):
                continue
            data = json.loads(raw)
            translated = _translate_card_names(data, lookup)
            json_path.write_text(
                json.dumps(translated, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            translated_files += 1
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.error(
                "Failed to translate JP card names in %s: %s",
                json_path.relative_to(directory),
                exc,
            )
            failed_files += 1
    logger.info("Translated JP card names in %d JSON files", translated_files)
    if failed_files:
        logger.warning("JP translation incomplete: %d file(s) could not be processed", failed_files)


def export_narrative(format_slug: str, output_dir: Path | None = None) -> Path | None:
    """Generate an LLM narrative meta report for the given format (opt-in).

    Reads the exported JSON files from output_dir and writes report.json and
    report-thread.json alongside them. Requires ANTHROPIC_API_KEY in the environment.

    Returns the path to report.json, or None if generation fails.
    """
    from reports.narrative import generate_report

    base = output_dir or DEFAULT_OUTPUT_DIR
    try:
        report_path = generate_report(
            format_slug=format_slug,
            data_dir=base,
            output_dir=base,
        )
        logger.info("Narrative report written to %s", report_path)
        return report_path
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("Narrative report generation skipped for %s: %s", format_slug, exc)
        return None
    except Exception as exc:
        logger.error(
            "Narrative report generation failed for %s: %s", format_slug, exc, exc_info=True
        )
        return None


def export_formats(output_dir: Path | None = None) -> None:
    """Export formats.json manifest with all format metadata and status."""
    base = output_dir or DEFAULT_OUTPUT_DIR
    base.mkdir(parents=True, exist_ok=True)

    formats = []
    for slug, fmt in FORMATS.items():
        # Check if data exists for this format
        meta_path = base / slug / "meta.json"
        if not meta_path.exists():
            status = "upcoming"
        elif fmt["dataset_end"] < date.today().isoformat():
            status = "frozen"
        else:
            status = "active"

        # Read stats from meta.json if it exists
        tournament_count = 0
        deck_count = 0
        generated_at = ""
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                tournament_count = meta.get("tournament_count", 0)
                deck_count = meta.get("deck_count", 0)
                generated_at = meta.get("generated_at", "")
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
                "generated_at": generated_at,
            }
        )

    _write_json(formats, base / "formats.json")
