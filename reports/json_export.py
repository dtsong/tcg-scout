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
from analysis.buylist import generate_buylist
from analysis.meta import get_latest_snapshot
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

# Basic energy card names to exclude from all analytics
BASIC_ENERGY_NAMES = {
    "Basic Fire Energy",
    "Basic Water Energy",
    "Basic Lightning Energy",
    "Basic Psychic Energy",
    "Basic Fighting Energy",
    "Basic Darkness Energy",
    "Basic Metal Energy",
    "Basic Grass Energy",
    # DB stores without "Basic" prefix
    "Fire Energy",
    "Water Energy",
    "Lightning Energy",
    "Psychic Energy",
    "Fighting Energy",
    "Darkness Energy",
    "Metal Energy",
    "Grass Energy",
}


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

# Fallback JP→EN card name map for common cards not in the cards table
JP_CARD_NAMES: dict[str, str] = {
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


def _classify_card(card_name: str) -> str:
    """Classify a card as Pokemon, Trainer, or Energy by name heuristics."""
    lower = card_name.lower()
    # Trainer items that contain "energy" in the name
    if lower in ("energy switch", "energy search", "energy retrieval", "energy recycler"):
        return "Trainer"
    if "energy" in lower:
        return "Energy"
    # Common trainer keywords
    trainer_keywords = (
        "ball",
        "catcher",
        "switch",
        "rope",
        "rod",
        "stretcher",
        "candy",
        "cape",
        "belt",
        "brace",
        "stamp",
        "drum",
        "tree",
        "laser",
        "box",
        "headset",
        "amulet",
        "aroma",
        "pod",
        "crystal",
        "pad",
        "vital",
        "tower",
        "gong",
        "scrapper",
        "balloon",
        "board",
        "poffin",
        "determination",
        "fighting spirit",
        "watchtower",
    )
    # Trainer supporter names (people)
    trainer_names = (
        "boss",
        "iono",
        "professor",
        "judge",
        "pepper",
        "cynthia",
        "biwa",
        "roxanne",
        "avery",
        "lillie",
        "crispin",
        "dawn",
        "iris",
        "marnie",
        "team rocket",
        "petrel",
        "arven",
        "penny",
        "jacq",
        "turo",
        "sada",
        "kieran",
        "carmine",
        "briar",
        "drayton",
        "lacey",
        "hassel",
    )
    for kw in trainer_keywords:
        if kw in lower:
            return "Trainer"
    for name in trainer_names:
        if name in lower:
            return "Trainer"
    # Check DB supertype as last resort (most are empty but try)
    return "Pokemon"


def _compute_weighted_shares(conn: sqlite3.Connection, snapshot: dict) -> dict[str, float]:
    """Compute performance-weighted meta share for each archetype.

    Weights placements by finish position (top 16 differentiated for 64-player CLs).
    CL results not included here since cl_placements lack archetype classification.
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

    archetypes = []
    for arch in snapshot["archetypes"]:
        name = arch["archetype"]
        ws = weighted_shares.get(name, 0.0)
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


def export_archetypes(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export per-archetype detail JSON files with core cards and tournament results."""
    snapshot = get_latest_snapshot(conn)
    if not snapshot:
        return

    weighted_shares = _compute_weighted_shares(conn, snapshot)

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
        placeholders = ",".join("?" * len(placement_ids))

        # Get per-card stats
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

        core_cards = []
        all_cards = []
        for row in rows:
            inclusion = round(row["decks_with"] / total_decks * 100, 1)
            avg_copies = round(row["total_copies"] / row["decks_with"], 1)
            card_data = {
                "card_name": row["card_name"],
                "inclusion_pct": inclusion,
                "avg_copies": avg_copies,
                "decks_with": row["decks_with"],
                "category": _classify_card(row["card_name"]),
            }
            all_cards.append(card_data)
            if inclusion >= 80:
                core_cards.append(card_data)

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
                        "category": _classify_card(dl["card_name"]),
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
        }

        _write_json(arch_data, arch_dir / f"{slug}.json")


def _build_jp_en_lookup(conn: sqlite3.Connection) -> dict[str, str]:
    """Build JP→EN card name lookup from the cards table + fallback dict."""
    lookup = dict(JP_CARD_NAMES)  # Start with hardcoded fallbacks
    rows = conn.execute(
        "SELECT name_jp, name_en FROM cards WHERE name_jp IS NOT NULL AND name_jp != ''"
    ).fetchall()
    for row in rows:
        lookup[row["name_jp"]] = row["name_en"]
    logger.info("JP→EN lookup: %d entries (%d from cards table)", len(lookup), len(rows))
    return lookup


def export_champions_league(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export Champions League data by division with JP→EN translations."""
    cl_dir = output_dir / "champions-league"
    cl_dir.mkdir(parents=True, exist_ok=True)

    jp_en_lookup = _build_jp_en_lookup(conn)

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
            for card in decklist_rows:
                jp_name = card["card_name_jp"]
                # Use existing EN name, or look up from cards table / fallback dict
                en_name = card["card_name_en"] or jp_en_lookup.get(jp_name)
                if en_name:
                    translated_count += 1
                elif jp_name:
                    untranslated_names.add(jp_name)

                decklist.append(
                    {
                        "card_name_jp": jp_name,
                        "card_name_en": en_name,
                        "count": card["count"],
                        "category": card["category"],
                    }
                )

            placement_list.append(
                {
                    "standing": p["standing"],
                    "player_name": p["player_name"],
                    "region": p["region"],
                    "deck_code": p["deck_code"],
                    "decklist": decklist,
                }
            )

        division_data = {
            "event_id": event["id"],
            "event_name": event["name"],
            "division": division,
            "date": event["date"],
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
            import json as _json

            try:
                meta = _json.loads(meta_path.read_text(encoding="utf-8"))
                tournament_count = meta.get("tournament_count", 0)
                deck_count = meta.get("deck_count", 0)
            except Exception:
                pass

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
