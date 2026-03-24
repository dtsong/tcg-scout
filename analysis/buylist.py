"""Buy list generation with priority scoring."""

import logging
import sqlite3
from collections import defaultdict

from config import (
    CORE_AVG_COPIES_OTHER,
    CORE_AVG_COPIES_POKEMON,
    CORE_INCLUSION_RATE,
    TIER_WEIGHTS,
)

logger = logging.getLogger(__name__)

# Basic energy card names to exclude from buy list analytics
BASIC_ENERGY_NAMES = {
    "Basic Fire Energy",
    "Basic Water Energy",
    "Basic Lightning Energy",
    "Basic Psychic Energy",
    "Basic Fighting Energy",
    "Basic Darkness Energy",
    "Basic Metal Energy",
    "Basic Grass Energy",
    "Basic Colorless Energy",
    "Basic Fairy Energy",
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


def generate_buylist(conn: sqlite3.Connection, snapshot_id: int) -> list[dict]:
    """Generate prioritized buy list from meta data. Returns list of card dicts."""
    conn.row_factory = sqlite3.Row

    # Step 1: Get all S/A/B tier archetypes for the snapshot
    archetypes = conn.execute(
        """
        SELECT archetype, tier
        FROM archetype_stats
        WHERE snapshot_id = ? AND tier IN ('S', 'A', 'B')
        ORDER BY meta_share DESC
        """,
        (snapshot_id,),
    ).fetchall()

    if not archetypes:
        logger.warning("No S/A/B tier archetypes found for snapshot %d", snapshot_id)
        return []

    logger.info(
        "Processing %d S/A/B archetypes for buylist (snapshot %d)",
        len(archetypes),
        snapshot_id,
    )

    # Build a lookup of card supertype from the cards table
    card_supertype: dict[str, str] = {}
    card_info: dict[str, dict] = {}  # card_id -> {set_code, set_number, rotation_legal}
    for row in conn.execute(
        "SELECT id, supertype, set_code, set_number, rotation_legal FROM cards"
    ).fetchall():
        card_supertype[row["id"]] = row["supertype"] or ""
        card_info[row["id"]] = {
            "set_code": row["set_code"],
            "set_number": row["set_number"],
            "rotation_legal": bool(row["rotation_legal"]),
        }

    # Per-card cross-archetype aggregation structures
    # card_key = card_id (or card_name if card_id not in cards table)
    card_archetype_data: dict[str, dict] = defaultdict(
        lambda: {
            "card_name": None,
            "card_id": None,
            "archetypes": [],
            "priority_score": 0.0,
            "core_in_any": False,
            "max_inclusion_rate": 0.0,
            "max_avg_copies": 0.0,
        }
    )

    for arch_row in archetypes:
        archetype = arch_row["archetype"]
        tier = arch_row["tier"]
        tier_weight = TIER_WEIGHTS.get(tier, 0)

        # Step 2: Get all placements for this archetype
        placements = conn.execute(
            "SELECT id FROM open_placements WHERE archetype = ?",
            (archetype,),
        ).fetchall()

        if not placements:
            continue

        placement_ids = [p["id"] for p in placements]

        # Step 3: Query decklist_cards for all placements in this archetype
        placeholders = ",".join("?" * len(placement_ids))

        # Only count placements that actually have decklists
        total_decks = conn.execute(
            f"SELECT COUNT(DISTINCT placement_id) FROM decklist_cards WHERE placement_id IN ({placeholders})",
            placement_ids,
        ).fetchone()[0]

        if total_decks == 0:
            continue
        energy_placeholders = ",".join("?" * len(BASIC_ENERGY_NAMES))
        decklist_rows = conn.execute(
            f"""
            SELECT placement_id, card_id, card_name, count
            FROM decklist_cards
            WHERE placement_id IN ({placeholders})
              AND card_name NOT IN ({energy_placeholders})
            """,
            (*placement_ids, *sorted(BASIC_ENERGY_NAMES)),
        ).fetchall()

        # Step 4: Per-card stats within this archetype
        # card_key -> {decks_with: int, total_copies: int, card_name, card_id}
        archetype_card_stats: dict[str, dict] = defaultdict(
            lambda: {
                "decks_with": 0,
                "total_copies": 0,
                "card_name": None,
                "card_id": None,
                "placement_ids_seen": set(),
            }
        )

        for dc in decklist_rows:
            card_key = dc["card_id"]
            stats = archetype_card_stats[card_key]
            stats["card_name"] = dc["card_name"]
            stats["card_id"] = dc["card_id"]
            # Avoid double-counting same placement (shouldn't happen with PK constraint)
            if dc["placement_id"] not in stats["placement_ids_seen"]:
                stats["placement_ids_seen"].add(dc["placement_id"])
                stats["decks_with"] += 1
                stats["total_copies"] += dc["count"]

        # Step 5: Aggregate into cross-archetype data
        for card_key, stats in archetype_card_stats.items():
            inclusion_rate = stats["decks_with"] / total_decks
            avg_copies = (
                stats["total_copies"] / stats["decks_with"] if stats["decks_with"] > 0 else 0
            )

            entry = card_archetype_data[card_key]
            entry["card_name"] = stats["card_name"]
            entry["card_id"] = stats["card_id"]
            entry["archetypes"].append(archetype)
            entry["priority_score"] += avg_copies * tier_weight
            entry["max_inclusion_rate"] = max(entry["max_inclusion_rate"], inclusion_rate)
            entry["max_avg_copies"] = max(entry["max_avg_copies"], avg_copies)

            # Step 6: Determine core vs flex
            supertype = card_supertype.get(card_key, "").lower()
            if "pok" in supertype:  # Pokemon, Pokémon
                copies_threshold = CORE_AVG_COPIES_POKEMON
            else:
                copies_threshold = CORE_AVG_COPIES_OTHER

            if inclusion_rate >= CORE_INCLUSION_RATE and avg_copies >= copies_threshold:
                entry["core_in_any"] = True

    # Build final result list
    results: list[dict] = []
    for card_key, entry in card_archetype_data.items():
        cid = entry["card_id"]

        # Step 7: Rotation legality filter
        if cid in card_info:
            if not card_info[cid]["rotation_legal"]:
                continue
            set_code = card_info[cid]["set_code"]
            set_number = card_info[cid]["set_number"]
        else:
            # Card not in cards table (unresolved) -- include anyway
            set_code = None
            set_number = None

        core_flex = "core" if entry["core_in_any"] else "flex"

        results.append(
            {
                "card_name": entry["card_name"],
                "card_id": cid if cid in card_info else None,
                "set_code": set_code,
                "set_number": set_number,
                "priority_score": round(entry["priority_score"], 1),
                "core_flex": core_flex,
                "archetypes": entry["archetypes"],
                "avg_copies": round(entry["max_avg_copies"], 1),
                "inclusion_rate": round(entry["max_inclusion_rate"], 2),
            }
        )

    # Step 8: Sort by priority_score descending
    results.sort(key=lambda x: x["priority_score"], reverse=True)

    logger.info("Generated buylist with %d cards", len(results))
    return results
