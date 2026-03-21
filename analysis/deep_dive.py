"""Deep dive archetype report — weighted consensus 60, weekly card timeline, placement distribution."""

import sqlite3
from collections import defaultdict
from datetime import date, timedelta

from analysis.card_stats import BASIC_ENERGY_NAMES, classify_card
from config import PLACEMENT_WEIGHT_DEFAULT, PLACEMENT_WEIGHTS


def _get_placement_weight(standing: int) -> float:
    return PLACEMENT_WEIGHTS.get(standing, PLACEMENT_WEIGHT_DEFAULT)


def compute_weighted_consensus_60(
    conn: sqlite3.Connection,
    archetype: str,
    category_lookup: dict[str, str] | None = None,
    card_set_lookup: dict[str, tuple[str, str]] | None = None,
) -> dict | None:
    """Build a weighted consensus 60-card decklist for an archetype.

    Higher-placing decks contribute more weight to card inclusion and copy counts.
    Returns None if fewer than 3 decklists exist.
    """
    rows = conn.execute(
        """
        SELECT p.id AS placement_id, p.standing
        FROM open_placements p
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE p.archetype = ?
        """,
        (archetype,),
    ).fetchall()

    if len(rows) < 3:
        return None

    placement_ids = [r["placement_id"] for r in rows]

    energy_names = sorted(BASIC_ENERGY_NAMES)
    energy_placeholders = ",".join("?" * len(energy_names))
    pid_placeholders = ",".join("?" * len(placement_ids))

    # Only consider placements that actually have decklists
    pids_with_decklists = {
        r[0]
        for r in conn.execute(
            f"SELECT DISTINCT placement_id FROM decklist_cards WHERE placement_id IN ({pid_placeholders})",
            placement_ids,
        ).fetchall()
    }

    if len(pids_with_decklists) < 3:
        return None

    weight_by_pid = {
        r["placement_id"]: _get_placement_weight(r["standing"])
        for r in rows
        if r["placement_id"] in pids_with_decklists
    }
    total_weight = sum(weight_by_pid.values())

    card_rows = conn.execute(
        f"""
        SELECT dc.placement_id, dc.card_name, dc.count
        FROM decklist_cards dc
        WHERE dc.placement_id IN ({pid_placeholders})
          AND dc.card_name NOT IN ({energy_placeholders})
        """,
        (*placement_ids, *energy_names),
    ).fetchall()

    if not card_rows:
        return None

    # Aggregate per card: weighted inclusion, weighted avg copies, raw inclusion
    card_data: dict[str, dict] = defaultdict(
        lambda: {"weighted_sum": 0.0, "weighted_copies": 0.0, "raw_count": 0, "total_copies": 0}
    )
    for cr in card_rows:
        w = weight_by_pid.get(cr["placement_id"])
        if w is None:
            continue
        cd = card_data[cr["card_name"]]
        cd["weighted_sum"] += w
        cd["weighted_copies"] += cr["count"] * w
        cd["raw_count"] += 1
        cd["total_copies"] += cr["count"]

    total_decks = len(pids_with_decklists)
    cards = []
    for card_name, cd in card_data.items():
        weighted_inclusion = round(cd["weighted_sum"] / total_weight * 100, 1)
        weighted_avg = (
            round(cd["weighted_copies"] / cd["weighted_sum"], 1) if cd["weighted_sum"] > 0 else 0.0
        )
        confidence = round(cd["raw_count"] / total_decks, 2)

        if weighted_inclusion >= 75:
            consensus = "core"
        elif weighted_inclusion >= 50:
            consensus = "common"
        else:
            consensus = "tech"

        category = classify_card(card_name, category_lookup)
        set_info = card_set_lookup.get(card_name) if card_set_lookup else None
        cards.append(
            {
                "card_name": card_name,
                "count": round(weighted_avg),
                "category": category,
                "weighted_inclusion_pct": weighted_inclusion,
                "weighted_avg_copies": weighted_avg,
                "confidence": confidence,
                "consensus": consensus,
                "set_code": set_info[0] if set_info else None,
                "set_number": set_info[1] if set_info else None,
            }
        )

    # Sort by weighted inclusion DESC, then weighted avg copies DESC
    cards.sort(key=lambda c: (c["weighted_inclusion_pct"], c["weighted_avg_copies"]), reverse=True)

    # Build 60-card list greedily
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
        sum(c["weighted_inclusion_pct"] * c["count"] for c in consensus_cards) / max(total, 1),
        1,
    )

    return {
        "quality_score": quality_score,
        "total_pokemon": total_pokemon,
        "total_trainer": total_trainer,
        "total_energy": total_energy,
        "cards": consensus_cards,
    }


def compute_weekly_card_timeline(
    conn: sqlite3.Connection,
    archetype: str,
    min_inclusion_any_week: float = 20.0,
) -> dict | None:
    """Compute per-card inclusion rates across ISO weeks for an archetype.

    Returns None if fewer than 2 weeks of data exist.
    """
    energy_names = sorted(BASIC_ENERGY_NAMES)
    energy_placeholders = ",".join("?" * len(energy_names))

    rows = conn.execute(
        """
        SELECT p.id AS placement_id, t.date
        FROM open_placements p
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE p.archetype = ?
        ORDER BY t.date
        """,
        (archetype,),
    ).fetchall()

    if not rows:
        return None

    # Group by ISO week
    week_pids: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        d = date.fromisoformat(r["date"])
        monday = d - timedelta(days=d.weekday())
        week_pids[monday.isoformat()].append(r["placement_id"])

    weeks = sorted(week_pids.keys())
    if len(weeks) < 2:
        return None

    # Per-week, per-card stats
    week_card_data: dict[str, dict[str, dict]] = {}
    for wk in weeks:
        pids = week_pids[wk]
        placeholders = ",".join("?" * len(pids))

        # Only count placements that actually have decklists
        total = conn.execute(
            f"SELECT COUNT(DISTINCT placement_id) FROM decklist_cards WHERE placement_id IN ({placeholders})",
            pids,
        ).fetchone()[0]

        if total == 0:
            continue

        card_rows = conn.execute(
            f"""
            SELECT dc.card_name,
                   COUNT(DISTINCT dc.placement_id) AS cnt,
                   CAST(SUM(dc.count) AS REAL) / COUNT(DISTINCT dc.placement_id) AS avg_copies
            FROM decklist_cards dc
            WHERE dc.placement_id IN ({placeholders})
              AND dc.card_name NOT IN ({energy_placeholders})
            GROUP BY dc.card_name
            """,
            (*pids, *energy_names),
        ).fetchall()

        rates = {}
        for cr in card_rows:
            rates[cr["card_name"]] = {
                "pct": round(cr["cnt"] / total * 100, 1),
                "copies": round(cr["avg_copies"], 1),
            }
        week_card_data[wk] = rates

    # Find all cards that reach min_inclusion_any_week in at least one week
    all_cards: set[str] = set()
    for wk_rates in week_card_data.values():
        for card_name, stats in wk_rates.items():
            if stats["pct"] >= min_inclusion_any_week:
                all_cards.add(card_name)

    # Build timeline per card
    card_timelines = []
    for card_name in sorted(all_cards):
        timeline = []
        copies_timeline = []
        for wk in weeks:
            stats = week_card_data[wk].get(card_name, {"pct": 0.0, "copies": 0.0})
            timeline.append(stats["pct"])
            copies_timeline.append(stats["copies"])

        # Classify trend
        first_pct = timeline[0]
        last_pct = timeline[-1]
        total_delta = round(last_pct - first_pct, 1)

        if first_pct < 10 and last_pct >= 30:
            trend = "adopted"
        elif first_pct >= 30 and last_pct < 10:
            trend = "dropped"
        elif abs(total_delta) > 20:
            trend = "shifted"
        else:
            trend = "stable"

        category = classify_card(card_name)
        card_timelines.append(
            {
                "card_name": card_name,
                "category": category,
                "timeline": timeline,
                "copies_timeline": copies_timeline,
                "trend": trend,
                "total_delta": total_delta,
            }
        )

    # Sort by absolute delta descending
    card_timelines.sort(key=lambda c: abs(c["total_delta"]), reverse=True)

    return {
        "weeks": weeks,
        "cards": card_timelines,
    }


_BRACKET_RANGES = [
    ("1st", 1, 1),
    ("2nd", 2, 2),
    ("3rd-4th", 3, 4),
    ("5th-8th", 5, 8),
    ("9th-16th", 9, 16),
    ("17th+", 17, 9999),
]


def compute_placement_distribution(placements: list[dict]) -> list[dict]:
    """Bin standings into brackets and return counts + percentages."""
    total = len(placements)
    if total == 0:
        return []

    result = []
    for label, lo, hi in _BRACKET_RANGES:
        count = sum(1 for p in placements if lo <= p["standing"] <= hi)
        if count > 0:
            result.append(
                {
                    "bracket": label,
                    "count": count,
                    "pct": round(count / total * 100, 1),
                }
            )

    return result


def compute_notable_techs(timeline_data: dict | None) -> list[dict]:
    """Extract notable tech adoption/drop events from timeline data."""
    if not timeline_data or not timeline_data.get("cards"):
        return []

    weeks = timeline_data["weeks"]
    notable = []

    for card in timeline_data["cards"]:
        tl = card["timeline"]
        if len(tl) < 2:
            continue

        # Find the largest week-over-week transition exceeding +/-20 points
        max_delta = 0
        best_event = None
        for i in range(1, len(tl)):
            delta = tl[i] - tl[i - 1]
            if abs(delta) <= abs(max_delta):
                continue
            from_pct = tl[i - 1]
            to_pct = tl[i]
            if delta > 20:
                event = "appeared" if from_pct < 10 else "surged"
            elif delta < -20:
                event = "disappeared" if to_pct < 10 else "declined"
            else:
                continue
            max_delta = delta
            best_event = {
                "card_name": card["card_name"],
                "event": event,
                "week": weeks[i],
                "from_pct": round(from_pct, 1),
                "to_pct": round(to_pct, 1),
            }

        if best_event:
            notable.append(best_event)

    notable.sort(key=lambda e: abs(e["to_pct"] - e["from_pct"]), reverse=True)
    return notable
