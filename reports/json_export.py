"""JSON export for Scout Web — generates static data files for the Next.js dashboard."""

import json
import logging
import re
import sqlite3
import urllib.request
from pathlib import Path

from analysis.archetype import SPRITE_ARCHETYPE_MAP, _COMPOSITE_SPRITE_FILENAMES
from analysis.buylist import generate_buylist
from analysis.meta import get_latest_snapshot
from config import (
    CL_WEIGHT_MULTIPLIER,
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

logger = logging.getLogger(__name__)

# Default output directory (web/public/data/)
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "web" / "public" / "data"

# Basic energy card names to exclude from all analytics
BASIC_ENERGY_NAMES = {
    "Basic Fire Energy", "Basic Water Energy", "Basic Lightning Energy",
    "Basic Psychic Energy", "Basic Fighting Energy", "Basic Darkness Energy",
    "Basic Metal Energy", "Basic Grass Energy", "Basic Colorless Energy",
    "Basic Fairy Energy",
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
        if i + 1 < len(parts) and parts[i + 1].lower() not in ("ex", "box", "stall", "control", "mega"):
            # Check if this could be a two-word Pokemon name
            combined = f"{part}-{parts[i + 1].lower()}"
            # Known two-word Pokemon that use hyphens in sprite names
            if combined in (
                "raging-bolt", "iron-hands", "iron-valiant", "roaring-moon",
                "chien-pao", "porygon-z", "ogerpon-wellspring", "ogerpon-cornerstone",
                "ho-oh", "zacian-crowned",
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
    if "energy" in lower:
        return "Energy"
    # Common trainer keywords
    trainer_keywords = (
        "ball", "catcher", "switch", "rope", "rod", "stretcher", "candy",
        "cape", "belt", "brace", "stamp", "drum", "tree", "laser", "box",
        "headset", "amulet", "aroma", "pod", "crystal", "pad", "vital",
        "tower", "gong", "scrapper", "balloon", "board", "poffin",
        "determination", "fighting spirit", "watchtower",
    )
    # Trainer supporter names (people)
    trainer_names = (
        "boss", "iono", "professor", "judge", "pepper", "cynthia", "biwa",
        "roxanne", "avery", "lillie", "crispin", "dawn", "iris", "marnie",
        "team rocket", "petrel", "arven", "penny", "jacq", "turo", "sada",
        "kieran", "carmine", "briar", "drayton", "lacey", "hassel",
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

    return {
        arch: round(w / total_weight * 100, 2)
        for arch, w in weighted_sums.items()
    }


def export_meta(conn: sqlite3.Connection, output_dir: Path,
                format_slug: str | None = None) -> dict | None:
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
        archetypes.append({
            "archetype": name,
            "slug": _slugify(name),
            "meta_share": round(arch["meta_share"], 1),
            "weighted_share": round(ws, 1),
            "deck_count": arch["deck_count"],
            "best_placement": arch["best_placement"],
            "tier": arch["tier"],
            "sprite_filenames": _get_sprite_filenames(name),
        })

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
        staples.append({
            "card_name": row["card_name"],
            "deck_count": row["deck_count"],
            "usage_pct": pct,
            "avg_copies": row["avg_copies"],
        })

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
        flex.append({
            "card_name": row["card_name"],
            "deck_count": row["deck_count"],
            "usage_pct": pct,
            "avg_copies": row["avg_copies"],
        })

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
        result.append({
            "archetype": arch,
            "early_pct": early_pct,
            "late_pct": late_pct,
            "delta": round(late_pct - early_pct, 1),
        })
    return result


def export_trends(conn: sqlite3.Connection, output_dir: Path,
                  format_slug: str | None = None) -> None:
    """Export trends.json — surging and declining cards with archetype breakdowns."""
    if format_slug:
        fmt = get_format_config(format_slug)
        from datetime import date
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
        _write_json({
            "midpoint": midpoint, "early_decks": 0, "late_decks": 0,
            "surging": [], "declining": [],
        }, output_dir / "trends.json")
        return

    rows = conn.execute(
        f"""
        SELECT dc.card_name,
               SUM(CASE WHEN t.date < ? THEN 1 ELSE 0 END) AS early_count,
               SUM(CASE WHEN t.date >= ? THEN 1 ELSE 0 END) AS late_count
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE {_basic_energy_exclusion_sql()}
        GROUP BY dc.card_name
        HAVING early_count >= 5 AND late_count >= 5
        """,
        (midpoint, midpoint, *_basic_energy_params()),
    ).fetchall()

    cards = []
    for row in rows:
        early_pct = round(row["early_count"] * 100.0 / early_total, 1)
        late_pct = round(row["late_count"] * 100.0 / late_total, 1)
        delta = round(late_pct - early_pct, 1)
        cards.append({
            "card_name": row["card_name"],
            "early_count": row["early_count"],
            "late_count": row["late_count"],
            "early_pct": early_pct,
            "late_pct": late_pct,
            "delta": delta,
        })

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

    _write_json({
        "midpoint": midpoint,
        "early_decks": early_total,
        "late_decks": late_total,
        "surging": surging,
        "declining": declining,
    }, output_dir / "trends.json")


def export_winning_edge(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export winning-edge.json — 1st place overrepresentation vs field for S/A/B decks."""
    snapshot = get_latest_snapshot(conn)
    if not snapshot:
        return

    # Get S/A/B archetype names
    sa_archetypes = [
        a["archetype"] for a in snapshot["archetypes"]
        if a["tier"] in ("S", "A", "B")
    ]

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
        cards.append({
            "card_name": name,
            "field_pct": field_pct,
            "win_pct": win_pct,
            "edge": edge,
            "winner_decks": row["winner_decks"],
            "field_decks": field_usage[name],
        })

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
        specs.append({
            "card_name": row["card_name"],
            "deck_count": row["deck_count"],
            "usage_pct": pct,
        })

    _write_json(specs, output_dir / "ace-specs.json")


def export_archetypes(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export per-archetype detail JSON files with core cards and tournament results."""
    snapshot = get_latest_snapshot(conn)
    if not snapshot:
        return

    weighted_shares = _compute_weighted_shares(conn, snapshot)

    arch_dir = output_dir / "archetypes"
    arch_dir.mkdir(parents=True, exist_ok=True)

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

        # Tournament results — top 50 by standing ASC, date DESC
        results_rows = conn.execute(
            """
            SELECT t.name AS tournament_name, t.date, p.standing, p.player_name
            FROM placements p
            JOIN tournaments t ON t.id = p.tournament_id
            WHERE p.archetype = ?
            ORDER BY p.standing ASC, t.date DESC
            LIMIT 50
            """,
            (archetype_name,),
        ).fetchall()

        results = [
            {
                "tournament_name": r["tournament_name"],
                "date": r["date"],
                "standing": r["standing"],
                "player_name": r["player_name"],
            }
            for r in results_rows
        ]

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

                decklist.append({
                    "card_name_jp": jp_name,
                    "card_name_en": en_name,
                    "count": card["count"],
                    "category": card["category"],
                })

            placement_list.append({
                "standing": p["standing"],
                "player_name": p["player_name"],
                "region": p["region"],
                "deck_code": p["deck_code"],
                "decklist": decklist,
            })

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

    logger.info("Sprites: %d downloaded, %d already cached", downloaded, len(sprite_files) - downloaded)

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
            req = urllib.request.Request(info["image_url"], headers={"User-Agent": "Mozilla/5.0 Scout/1.0"})
            with urllib.request.urlopen(req) as resp:
                dest.write_bytes(resp.read())
            card_downloaded += 1
        except Exception as e:
            logger.warning("Failed to download card image %s: %s", card["card_name"], e)

    logger.info("Card images: %d downloaded for top buylist cards", card_downloaded)


def export_all(conn: sqlite3.Connection, output_dir: Path | None = None,
               format_slug: str | None = None) -> Path:
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

        formats.append({
            "slug": slug,
            "name": fmt["name"],
            "name_en": fmt["name_en"],
            "description": fmt["description"],
            "dataset_start": fmt["dataset_start"],
            "dataset_end": fmt["dataset_end"],
            "status": status,
            "tournament_count": tournament_count,
            "deck_count": deck_count,
        })

    _write_json(formats, base / "formats.json")
