"""Optimal 60 — CL-boosted weighted consensus with per-card CL vs meta comparison."""

import sqlite3
from collections import defaultdict
from statistics import variance

from analysis.card_stats import BASIC_ENERGY_NAMES, classify_card
from config import (
    CL_BOOST_FACTOR,
    CL_TOURNAMENT_IDS,
    PLACEMENT_WEIGHT_DEFAULT,
    PLACEMENT_WEIGHTS,
)


def _get_placement_weight(
    standing: int, is_cl: bool = False, boost: float = CL_BOOST_FACTOR
) -> float:
    base = PLACEMENT_WEIGHTS.get(standing, PLACEMENT_WEIGHT_DEFAULT)
    return base * boost if is_cl else base


def _generate_insight(
    card_name: str,
    consensus: str,
    blended_inclusion: float,
    cl_inclusion: float,
    meta_inclusion: float,
    cl_avg: float,
    meta_avg: float,
    cl_count: int,
) -> str | None:
    """Generate a one-line insight string for a card based on computed metrics."""
    delta = cl_inclusion - meta_inclusion

    if cl_count == 0:
        if meta_inclusion >= 90:
            return f"Meta staple: {meta_inclusion:.0f}% inclusion across City Leagues"
        return None

    if delta > 15:
        return (
            f"CL breakout: {cl_inclusion:.0f}% in Fukuoka top cut "
            f"vs {meta_inclusion:.0f}% in City Leagues"
        )

    if delta < -15:
        return (
            f"CL cut: dropped by Fukuoka players "
            f"({cl_inclusion:.0f}% CL vs {meta_inclusion:.0f}% meta)"
        )

    if abs(cl_avg - meta_avg) >= 1.0 and blended_inclusion >= 50:
        return f"Copy divergence: {cl_avg:.1f} copies in CL vs {meta_avg:.1f} in City Leagues"

    if blended_inclusion >= 90:
        return f"Meta staple: {blended_inclusion:.0f}% inclusion across all events"

    if consensus == "cl-signal":
        return (
            f"CL signal: {cl_inclusion:.0f}% inclusion in Fukuoka despite "
            f"only {meta_inclusion:.0f}% in broader meta"
        )

    return None


def compute_optimal_60(
    conn: sqlite3.Connection,
    archetype: str,
    category_lookup: dict[str, str] | None = None,
    cl_tournament_ids: set[str] | None = None,
    cl_boost: float | None = None,
    min_cl_decks: int = 3,
) -> dict | None:
    """Build a CL-boosted weighted consensus 60-card decklist for an archetype.

    Blends Champions League results with broader meta data, applying a boost
    multiplier to CL placement weights. Returns per-card CL vs meta comparison
    metrics alongside the blended consensus.

    Returns None if fewer than 3 total decklists exist.
    """
    cl_ids = cl_tournament_ids or CL_TOURNAMENT_IDS
    boost = cl_boost or CL_BOOST_FACTOR

    rows = conn.execute(
        """
        SELECT p.id AS placement_id, p.standing, t.id AS tournament_id,
               COALESCE(t.tournament_type, 'city-league') AS tournament_type
        FROM open_placements p
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE p.archetype = ?
        """,
        (archetype,),
    ).fetchall()

    if len(rows) < 3:
        return None

    # Classify placements as CL or meta
    cl_pids = set()
    meta_pids = set()
    weight_by_pid: dict[int, float] = {}

    for r in rows:
        pid = r["placement_id"]
        is_cl = r["tournament_type"] == "champions-league" or r["tournament_id"] in cl_ids
        weight_by_pid[pid] = _get_placement_weight(r["standing"], is_cl, boost)
        if is_cl:
            cl_pids.add(pid)
        else:
            meta_pids.add(pid)

    cl_deck_count = len(cl_pids)
    meta_deck_count = len(meta_pids)

    # If below CL threshold, fall back to standard consensus
    has_cl_data = cl_deck_count >= min_cl_decks

    total_weight = sum(weight_by_pid.values())
    placement_ids = list(weight_by_pid.keys())

    # Fetch card rows
    energy_names = sorted(BASIC_ENERGY_NAMES)
    energy_ph = ",".join("?" * len(energy_names))
    pid_ph = ",".join("?" * len(placement_ids))

    card_rows = conn.execute(
        f"""
        SELECT dc.placement_id, dc.card_name, dc.count
        FROM decklist_cards dc
        WHERE dc.placement_id IN ({pid_ph})
          AND dc.card_name NOT IN ({energy_ph})
        """,
        (*placement_ids, *energy_names),
    ).fetchall()

    if not card_rows:
        return None

    # Aggregate per card
    card_data: dict[str, dict] = defaultdict(
        lambda: {
            "weighted_sum": 0.0,
            "weighted_copies": 0.0,
            "raw_count": 0,
            "cl_count": 0,
            "meta_count": 0,
            "cl_copies_total": 0,
            "meta_copies_total": 0,
            "copy_counts": [],
        }
    )

    for cr in card_rows:
        pid = cr["placement_id"]
        w = weight_by_pid[pid]
        cd = card_data[cr["card_name"]]
        cd["weighted_sum"] += w
        cd["weighted_copies"] += cr["count"] * w
        cd["raw_count"] += 1
        cd["copy_counts"].append(cr["count"])

        if pid in cl_pids:
            cd["cl_count"] += 1
            cd["cl_copies_total"] += cr["count"]
        else:
            cd["meta_count"] += 1
            cd["meta_copies_total"] += cr["count"]

    # Build card list with metrics
    cards = []
    for card_name, cd in card_data.items():
        blended_inclusion = round(cd["weighted_sum"] / total_weight * 100, 1)
        blended_avg = (
            round(cd["weighted_copies"] / cd["weighted_sum"], 1) if cd["weighted_sum"] > 0 else 0.0
        )

        cl_inclusion = round(cd["cl_count"] / cl_deck_count * 100, 1) if cl_deck_count > 0 else 0.0
        meta_inclusion = (
            round(cd["meta_count"] / meta_deck_count * 100, 1) if meta_deck_count > 0 else 0.0
        )
        cl_avg = round(cd["cl_copies_total"] / cd["cl_count"], 1) if cd["cl_count"] > 0 else 0.0
        meta_avg = (
            round(cd["meta_copies_total"] / cd["meta_count"], 1) if cd["meta_count"] > 0 else 0.0
        )
        inclusion_delta = round(cl_inclusion - meta_inclusion, 1)

        # Copy variance for flex-core detection
        copy_var = variance(cd["copy_counts"]) if len(cd["copy_counts"]) >= 2 else 0.0

        # 5-tier consensus
        if blended_inclusion >= 75 and copy_var < 0.5:
            consensus = "core"
        elif blended_inclusion >= 75:
            consensus = "flex-core"
        elif blended_inclusion >= 50:
            consensus = "flex"
        elif blended_inclusion >= 25:
            consensus = "tech"
        elif has_cl_data and cl_inclusion >= 50:
            consensus = "cl-signal"
        else:
            consensus = "tech"

        category = classify_card(card_name, category_lookup)

        insight = _generate_insight(
            card_name,
            consensus,
            blended_inclusion,
            cl_inclusion,
            meta_inclusion,
            cl_avg,
            meta_avg,
            cd["cl_count"],
        )

        cards.append(
            {
                "card_name": card_name,
                "count": round(blended_avg),
                "category": category,
                "consensus": consensus,
                "blended_inclusion_pct": blended_inclusion,
                "cl_inclusion_pct": cl_inclusion,
                "meta_inclusion_pct": meta_inclusion,
                "inclusion_delta": inclusion_delta,
                "blended_avg_copies": blended_avg,
                "cl_avg_copies": cl_avg,
                "meta_avg_copies": meta_avg,
                "insight": insight,
            }
        )

    # Sort by blended inclusion DESC, then blended avg copies DESC
    cards.sort(
        key=lambda c: (c["blended_inclusion_pct"], c["blended_avg_copies"]),
        reverse=True,
    )

    # Greedy 60-card selection
    total = 0
    consensus_cards = []
    for card in cards:
        count = card["count"]
        if total + count > 60:
            count = 60 - total
        if count <= 0:
            continue
        consensus_cards.append({**card, "count": count})
        total += count
        if total >= 60:
            break

    # Category totals
    total_pokemon = sum(c["count"] for c in consensus_cards if c["category"] == "Pokemon")
    total_trainer = sum(c["count"] for c in consensus_cards if c["category"] == "Trainer")
    total_energy = sum(c["count"] for c in consensus_cards if c["category"] == "Energy")

    quality_score = round(
        sum(c["blended_inclusion_pct"] * c["count"] for c in consensus_cards) / max(total, 1),
        1,
    )

    # Archetype-level aggregates
    core_count = sum(c["count"] for c in consensus_cards if c["consensus"] == "core")
    core_lock_rate = round(core_count / max(total, 1) * 100, 1)
    divergent_slots = sum(c["count"] for c in consensus_cards if abs(c["inclusion_delta"]) > 15)
    innovation_index = round(divergent_slots / max(total, 1) * 100, 1)

    return {
        "quality_score": quality_score,
        "total_pokemon": total_pokemon,
        "total_trainer": total_trainer,
        "total_energy": total_energy,
        "cl_deck_count": cl_deck_count,
        "city_league_deck_count": meta_deck_count,
        "has_cl_data": has_cl_data,
        "core_lock_rate": core_lock_rate,
        "innovation_index": innovation_index,
        "cards": consensus_cards,
    }
