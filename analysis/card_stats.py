"""Card-level statistics analysis for individual card intelligence."""

import json
import re
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from config import (
    PLACEMENT_WEIGHT_DEFAULT,
    PLACEMENT_WEIGHTS,
)

# Authoritative Pokemon name set from tcgdex API (cached at build time)
_POKEMON_NAMES_FILE = Path(__file__).parent / "pokemon_names.json"
_POKEMON_NAMES: set[str] = set()
if _POKEMON_NAMES_FILE.exists():
    _POKEMON_NAMES = set(json.loads(_POKEMON_NAMES_FILE.read_text()))

# Basic energy card names to exclude from all analytics (canonical definition;
# also imported by json_export.py, synergy.py, evolution.py)
BASIC_ENERGY_NAMES = {
    "Basic Fire Energy",
    "Basic Water Energy",
    "Basic Lightning Energy",
    "Basic Psychic Energy",
    "Basic Fighting Energy",
    "Basic Darkness Energy",
    "Basic Metal Energy",
    "Basic Grass Energy",
    "Fire Energy",
    "Water Energy",
    "Lightning Energy",
    "Psychic Energy",
    "Fighting Energy",
    "Darkness Energy",
    "Metal Energy",
    "Grass Energy",
}


def _slugify(name: str) -> str:
    """Convert name to URL slug."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def build_category_lookup(conn: sqlite3.Connection) -> dict[str, str]:
    """Pre-load {card_name: category} from the cards table.

    Uses the authoritative supertype column populated by tcgdex API.
    """
    rows = conn.execute(
        "SELECT name_en, supertype FROM cards WHERE supertype IS NOT NULL"
    ).fetchall()
    return {row["name_en"]: row["supertype"] for row in rows}


def _classify_card(card_name: str, category_lookup: dict[str, str] | None = None) -> str:
    """Classify a card as Pokemon, Trainer, or Energy.

    Priority: DB lookup -> energy/trainer heuristics -> authoritative Pokemon
    name set from tcgdex -> default to Trainer (trainers have more diverse names).
    """
    if category_lookup:
        db_cat = category_lookup.get(card_name)
        if db_cat in ("Pokemon", "Trainer", "Energy"):
            return db_cat

    lower = card_name.lower()
    if lower in ("energy switch", "energy search", "energy retrieval", "energy recycler"):
        return "Trainer"
    if "energy" in lower:
        return "Energy"
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
        "vacuum",
        "board",
        "poffin",
        "determination",
        "fighting spirit",
        "watchtower",
    )
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
        "balloon",
        "morty",
        "wally",
        "premium power",
        "precious",
        "pokegear",
        "scoop up",
        "may's",
        "brock",
        "kofu",
        "hilda",
        "cipher",
        "steven's",
    )
    for kw in trainer_keywords:
        if kw in lower:
            return "Trainer"
    for name in trainer_names:
        if name in lower:
            return "Trainer"

    # Check against authoritative Pokemon name set from tcgdex
    if _POKEMON_NAMES:
        base_name = lower.removesuffix(" ex")
        if base_name in _POKEMON_NAMES or lower in _POKEMON_NAMES:
            return "Pokemon"
        # Unknown card not matching any known Pokemon — default to Trainer
        return "Trainer"

    return "Pokemon"


def _card_slug(card_name: str) -> str:
    """Generate a card slug from card name only.

    We aggregate stats across all printings of a card, so the slug is purely
    name-based. This avoids mismatches when multiple set printings exist.
    """
    return _slugify(card_name)


def compute_card_stats(conn: sqlite3.Connection) -> list[dict]:
    """Compute per-card statistics from decklist_cards + placements.

    Returns a list of card stat dicts, sorted by total_appearances descending.
    """
    total_decks = conn.execute("SELECT COUNT(*) FROM placements").fetchone()[0]
    if total_decks == 0:
        return []

    energy_names = sorted(BASIC_ENERGY_NAMES)
    energy_placeholders = ",".join("?" * len(energy_names))

    # Get per-card base stats
    rows = conn.execute(
        f"""
        SELECT dc.card_name,
               dc.card_id,
               COUNT(DISTINCT dc.placement_id) AS appearances,
               SUM(dc.count) AS total_copies,
               COUNT(DISTINCT p.archetype) AS unique_archetypes
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        WHERE dc.card_name NOT IN ({energy_placeholders})
        GROUP BY dc.card_name
        ORDER BY appearances DESC
        """,
        energy_names,
    ).fetchall()

    # Get card metadata from cards table
    card_meta = {}
    meta_rows = conn.execute(
        "SELECT id, name_en, set_code, set_number, supertype, rarity, image_url FROM cards"
    ).fetchall()
    for m in meta_rows:
        card_meta[m["name_en"]] = {
            "card_id": m["id"],
            "set_code": m["set_code"],
            "set_number": m["set_number"],
            "supertype": m["supertype"],
            "rarity": m["rarity"],
            "image_url": m["image_url"],
        }

    # Get archetype tiers from latest snapshot
    archetype_tiers = {}
    tier_rows = conn.execute(
        """
        SELECT archetype, tier FROM archetype_stats
        WHERE snapshot_id = (SELECT MAX(id) FROM meta_snapshots)
        """
    ).fetchall()
    for r in tier_rows:
        archetype_tiers[r["archetype"]] = r["tier"]

    # Get weighted scores per card
    weight_rows = conn.execute(
        f"""
        SELECT dc.card_name, p.standing
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        WHERE dc.card_name NOT IN ({energy_placeholders})
        """,
        energy_names,
    ).fetchall()

    weighted_scores: dict[str, float] = defaultdict(float)
    for wr in weight_rows:
        weight = PLACEMENT_WEIGHTS.get(wr["standing"], PLACEMENT_WEIGHT_DEFAULT)
        weighted_scores[wr["card_name"]] += weight

    # Build card stats
    cards = []
    for row in rows:
        name = row["card_name"]
        appearances = row["appearances"]
        avg_copies = round(row["total_copies"] / appearances, 1)

        meta = card_meta.get(name, {})
        supertype = meta.get("supertype")
        category = (
            supertype
            if supertype in ("Pokemon", "Trainer", "Energy")
            else _classify_card(name, None)
        )

        ws = weighted_scores.get(name, 0.0)
        win_rate_proxy = round(ws / appearances, 2) if appearances > 0 else 0

        card = {
            "card_name": name,
            "card_slug": _card_slug(name),
            "card_id": meta.get("card_id"),
            "set_code": meta.get("set_code"),
            "set_number": meta.get("set_number"),
            "image_url": meta.get("image_url"),
            "category": category,
            "rarity": meta.get("rarity"),
            "total_appearances": appearances,
            "usage_pct": round(appearances / total_decks * 100, 1),
            "avg_copies": avg_copies,
            "unique_archetypes": row["unique_archetypes"],
            "weighted_score": round(ws, 2),
            "win_rate_proxy": win_rate_proxy,
        }
        cards.append(card)

    return cards


def compute_card_detail(conn: sqlite3.Connection, card_name: str) -> dict | None:
    """Compute detailed stats for a single card including archetype breakdown,
    weekly usage, and copy distribution.
    """
    total_decks = conn.execute("SELECT COUNT(*) FROM placements").fetchone()[0]
    if total_decks == 0:
        return None

    # Base stats
    base = conn.execute(
        """
        SELECT COUNT(DISTINCT dc.placement_id) AS appearances,
               SUM(dc.count) AS total_copies,
               COUNT(DISTINCT p.archetype) AS unique_archetypes
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        WHERE dc.card_name = ?
        """,
        (card_name,),
    ).fetchone()

    if not base or base["appearances"] == 0:
        return None

    appearances = base["appearances"]
    avg_copies = round(base["total_copies"] / appearances, 1)

    # Card metadata
    meta = conn.execute(
        "SELECT id, set_code, set_number, supertype, rarity, image_url FROM cards WHERE name_en = ? LIMIT 1",
        (card_name,),
    ).fetchone()

    card_id = meta["id"] if meta else None
    set_code = meta["set_code"] if meta else None
    set_number = meta["set_number"] if meta else None
    image_url = meta["image_url"] if meta else None
    supertype = meta["supertype"] if meta else None
    rarity = meta["rarity"] if meta else None
    category = (
        supertype if supertype in ("Pokemon", "Trainer", "Energy") else _classify_card(card_name)
    )

    # Weighted score
    weight_rows = conn.execute(
        """
        SELECT p.standing
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        WHERE dc.card_name = ?
        """,
        (card_name,),
    ).fetchall()

    ws = sum(PLACEMENT_WEIGHTS.get(r["standing"], PLACEMENT_WEIGHT_DEFAULT) for r in weight_rows)
    win_rate_proxy = round(ws / appearances, 2)

    # Archetype breakdown
    archetype_tiers = {}
    tier_rows = conn.execute(
        """
        SELECT archetype, tier FROM archetype_stats
        WHERE snapshot_id = (SELECT MAX(id) FROM meta_snapshots)
        """
    ).fetchall()
    for r in tier_rows:
        archetype_tiers[r["archetype"]] = r["tier"]

    arch_rows = conn.execute(
        """
        SELECT p.archetype,
               COUNT(DISTINCT dc.placement_id) AS usage_count,
               ROUND(AVG(dc.count), 1) AS avg_copies
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        WHERE dc.card_name = ?
        GROUP BY p.archetype
        ORDER BY usage_count DESC
        """,
        (card_name,),
    ).fetchall()

    archetypes = []
    for ar in arch_rows:
        archetypes.append(
            {
                "name": ar["archetype"],
                "slug": _slugify(ar["archetype"]),
                "usage_count": ar["usage_count"],
                "avg_copies": ar["avg_copies"],
                "tier": archetype_tiers.get(ar["archetype"], "Rogue"),
            }
        )

    # Copy distribution
    copy_rows = conn.execute(
        """
        SELECT dc.count AS copies, COUNT(*) AS deck_count
        FROM decklist_cards dc
        WHERE dc.card_name = ?
        GROUP BY dc.count
        ORDER BY dc.count
        """,
        (card_name,),
    ).fetchall()

    copy_distribution = [{"copies": r["copies"], "count": r["deck_count"]} for r in copy_rows]

    # Weekly usage
    week_rows = conn.execute(
        """
        SELECT t.date, dc.count
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE dc.card_name = ?
        ORDER BY t.date
        """,
        (card_name,),
    ).fetchall()

    # Group by ISO week
    week_totals: dict[str, int] = defaultdict(int)
    week_card_appearances: dict[str, int] = defaultdict(int)
    week_card_copies: dict[str, int] = defaultdict(int)

    # Get all placements per week for denominator
    all_placements = conn.execute(
        """
        SELECT t.date FROM placements p
        JOIN tournaments t ON t.id = p.tournament_id
        ORDER BY t.date
        """
    ).fetchall()

    for ap in all_placements:
        d = date.fromisoformat(ap["date"])
        monday = d - timedelta(days=d.weekday())
        week_totals[monday.isoformat()] += 1

    for wr in week_rows:
        d = date.fromisoformat(wr["date"])
        monday = d - timedelta(days=d.weekday())
        wk = monday.isoformat()
        week_card_appearances[wk] += 1
        week_card_copies[wk] += wr["count"]

    weekly_usage = []
    for wk in sorted(week_totals):
        total = week_totals[wk]
        apps = week_card_appearances.get(wk, 0)
        copies = week_card_copies.get(wk, 0)
        weekly_usage.append(
            {
                "week": wk,
                "usage_pct": round(apps / total * 100, 1) if total > 0 else 0,
                "avg_copies": round(copies / apps, 1) if apps > 0 else 0,
            }
        )

    # Trend direction
    trend_direction = _compute_trend_direction(weekly_usage)

    # Top archetype name
    top_archetype = archetypes[0]["name"] if archetypes else None

    return {
        "card_name": card_name,
        "card_slug": _card_slug(card_name),
        "card_id": card_id,
        "set_code": set_code,
        "set_number": set_number,
        "image_url": image_url,
        "category": category,
        "rarity": rarity,
        "total_appearances": appearances,
        "usage_pct": round(appearances / total_decks * 100, 1),
        "avg_copies": avg_copies,
        "unique_archetypes": base["unique_archetypes"],
        "weighted_score": round(ws, 2),
        "win_rate_proxy": win_rate_proxy,
        "top_archetype": top_archetype,
        "trend_direction": trend_direction,
        "copy_distribution": copy_distribution,
        "archetypes": archetypes,
        "weekly_usage": weekly_usage,
    }


def _compute_trend_direction(weekly_usage: list[dict]) -> str:
    """Determine trend direction from weekly usage data."""
    if len(weekly_usage) < 2:
        return "stable"

    mid = len(weekly_usage) // 2
    early = weekly_usage[:mid]
    late = weekly_usage[mid:]

    early_avg = sum(w["usage_pct"] for w in early) / len(early) if early else 0
    late_avg = sum(w["usage_pct"] for w in late) / len(late) if late else 0

    delta = late_avg - early_avg
    if delta > 3:
        return "surging"
    elif delta < -3:
        return "declining"
    return "stable"


def generate_card_verdict(card: dict) -> str:
    """Generate a one-line verdict for a card."""
    appearances = card["total_appearances"]
    avg_copies = card["avg_copies"]
    archetypes = card.get("archetypes", [])

    # Count tier appearances
    tier_counts: dict[str, int] = defaultdict(int)
    for a in archetypes:
        tier_counts[a["tier"]] += 1

    s_count = tier_counts.get("S", 0)
    a_count = tier_counts.get("A", 0)
    top_tier_count = s_count + a_count

    is_four_of = avg_copies >= 3.5
    copy_label = "4-of" if is_four_of else f"{avg_copies:.0f}-of"

    if top_tier_count >= 2 and is_four_of:
        tiers = []
        if s_count:
            tiers.append(f"{s_count} S-tier")
        if a_count:
            tiers.append(f"{a_count} A-tier")
        return f"Core {copy_label} in {' and '.join(tiers)} archetypes"

    if top_tier_count >= 1:
        return f"Key card in {top_tier_count} top-tier archetype{'s' if top_tier_count > 1 else ''}"

    unique = card.get("unique_archetypes", len(archetypes))
    if unique >= 5:
        return f"Format staple across {unique} archetypes"
    elif unique >= 2:
        return f"Flex tech in {unique} archetypes"
    else:
        return f"Niche pick ({appearances} appearances)"
