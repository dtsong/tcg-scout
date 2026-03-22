"""Archetype evolution tracking — week-over-week decklist changes."""

import sqlite3
from collections import defaultdict
from datetime import date, timedelta

from analysis.card_stats import BASIC_ENERGY_NAMES, EN_CARD_ALIASES, _slugify, build_jp_en_lookup

# Minimum decks with decklists required per week to compute shifts.
# Prevents small-sample noise (e.g., 4 decks in week 1 → 100% rates).
MIN_DECKS_PER_WEEK = 15


def _week_start(d: date, epoch: date | None = None) -> date:
    """Return the start of the week containing date d.

    If epoch is provided, weeks are aligned to that date (7-day intervals).
    Otherwise, uses ISO Monday-based weeks.
    """
    if epoch is not None:
        days_since = (d - epoch).days
        return epoch + timedelta(days=(days_since // 7) * 7)
    return d - timedelta(days=d.weekday())


def compute_archetype_evolution(
    conn: sqlite3.Connection,
    archetype: str,
    adoption_threshold_low: float = 20.0,
    adoption_threshold_high: float = 50.0,
    jp_en_lookup: dict[str, str] | None = None,
    format_start: str | None = None,
) -> list[dict]:
    """Compute weekly card inclusion rate changes for an archetype.

    Tracks card adoption/drop events: cards moving across thresholds.

    Args:
        format_start: If provided (YYYY-MM-DD), align week boundaries to this
            date instead of ISO Monday. Prevents partial first weeks.

    Returns a list of weekly evolution events:
    [
        {
            "week": "2026-02-17",
            "adopted": [{"card": "Card Name", "from_pct": 15.0, "to_pct": 55.0}],
            "dropped": [{"card": "Card Name", "from_pct": 60.0, "to_pct": 10.0}],
        },
        ...
    ]
    """
    energy_names = sorted(BASIC_ENERGY_NAMES)
    energy_placeholders = ",".join("?" * len(energy_names))
    epoch = date.fromisoformat(format_start) if format_start else None

    # Get all placements for this archetype with tournament dates
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
        return []

    # Group placements by week (aligned to format start if provided)
    week_placements: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        d = date.fromisoformat(r["date"])
        wk = _week_start(d, epoch)
        week_placements[wk.isoformat()].append(r["placement_id"])

    weeks = sorted(week_placements.keys())
    if len(weeks) < 2:
        return []

    # For each week, compute per-card inclusion rates
    week_card_rates: dict[str, dict[str, float]] = {}

    for wk in weeks:
        pids = week_placements[wk]
        placeholders = ",".join("?" * len(pids))

        # Only count placements that actually have decklists
        total = conn.execute(
            f"SELECT COUNT(DISTINCT placement_id) FROM decklist_cards WHERE placement_id IN ({placeholders})",
            pids,
        ).fetchone()[0]

        if total < MIN_DECKS_PER_WEEK:
            continue

        card_rows = conn.execute(
            f"""
            SELECT dc.card_name, COUNT(DISTINCT dc.placement_id) AS cnt
            FROM decklist_cards dc
            WHERE dc.placement_id IN ({placeholders})
              AND dc.card_name NOT IN ({energy_placeholders})
            GROUP BY dc.card_name
            """,
            (*pids, *energy_names),
        ).fetchall()

        rates: dict[str, float] = {}
        for cr in card_rows:
            name = cr["card_name"]
            if jp_en_lookup:
                name = jp_en_lookup.get(name, name)
            name = EN_CARD_ALIASES.get(name, name)
            if name in BASIC_ENERGY_NAMES:
                continue
            pct = round(cr["cnt"] / total * 100, 1)
            rates[name] = min(round(rates.get(name, 0) + pct, 1), 100.0)
        week_card_rates[wk] = rates

    # Detect adoption/drop events between consecutive weeks with data
    weeks_with_data = [wk for wk in weeks if wk in week_card_rates]
    if len(weeks_with_data) < 2:
        return []

    evolution = []
    for i in range(1, len(weeks_with_data)):
        prev_week = weeks_with_data[i - 1]
        curr_week = weeks_with_data[i]
        prev_rates = week_card_rates[prev_week]
        curr_rates = week_card_rates[curr_week]

        all_cards = set(prev_rates.keys()) | set(curr_rates.keys())

        adopted = []
        dropped = []

        for card in all_cards:
            from_pct = prev_rates.get(card, 0.0)
            to_pct = curr_rates.get(card, 0.0)

            # Adoption: crossed from below high threshold to at/above high threshold
            if from_pct < adoption_threshold_high and to_pct >= adoption_threshold_high:
                adopted.append(
                    {
                        "card": card,
                        "from_pct": from_pct,
                        "to_pct": to_pct,
                    }
                )

            # Drop: crossed from above high threshold to below low threshold
            if from_pct >= adoption_threshold_high and to_pct < adoption_threshold_low:
                dropped.append(
                    {
                        "card": card,
                        "from_pct": from_pct,
                        "to_pct": to_pct,
                    }
                )

        # Sort by magnitude of change
        adopted.sort(key=lambda e: e["to_pct"] - e["from_pct"], reverse=True)
        dropped.sort(key=lambda e: e["from_pct"] - e["to_pct"], reverse=True)

        if adopted or dropped:
            evolution.append(
                {
                    "week": curr_week,
                    "adopted": adopted,
                    "dropped": dropped,
                }
            )

    return evolution


def compute_meta_evolution(
    conn: sqlite3.Connection, top_n: int | None = None, format_start: str | None = None
) -> dict:
    """Compute format-wide "what changed this week" — card movements across all archetypes.

    Returns a dict with highlights (top 5) and all movements:
    {
        "highlights": [...top 5 movements...],
        "movements": [...all movements...],
    }

    Each movement has: card, archetype, archetype_slug, direction, from_pct,
    to_pct, delta, deck_count, week.
    """
    # Get all archetypes from latest snapshot
    arch_rows = conn.execute(
        """
        SELECT archetype, deck_count FROM archetype_stats
        WHERE snapshot_id = (SELECT MAX(id) FROM meta_snapshots)
          AND tier IN ('S', 'A', 'B')
        ORDER BY deck_count DESC
        """
    ).fetchall()

    if not arch_rows:
        return {"highlights": [], "movements": []}

    # Lazy import to avoid circular dependency (json_export imports from this module)
    from reports.json_export import JP_CARD_NAMES

    jp_en_lookup = build_jp_en_lookup(conn, fallback=JP_CARD_NAMES)

    all_movements = []
    for ar in arch_rows:
        evolution = compute_archetype_evolution(
            conn, ar["archetype"], jp_en_lookup=jp_en_lookup, format_start=format_start
        )
        for event in evolution:
            base = {
                "archetype": ar["archetype"],
                "archetype_slug": _slugify(ar["archetype"]),
                "deck_count": ar["deck_count"],
                "week": event["week"],
            }
            for card in event["adopted"]:
                all_movements.append(
                    {
                        **base,
                        "card": card["card"],
                        "direction": "adopted",
                        "from_pct": card["from_pct"],
                        "to_pct": card["to_pct"],
                        "delta": round(card["to_pct"] - card["from_pct"], 1),
                    }
                )
            for card in event["dropped"]:
                all_movements.append(
                    {
                        **base,
                        "card": card["card"],
                        "direction": "dropped",
                        "from_pct": card["from_pct"],
                        "to_pct": card["to_pct"],
                        "delta": round(card["from_pct"] - card["to_pct"], 1),
                    }
                )

    # Sort by recency then magnitude
    all_movements.sort(key=lambda m: (m["week"], m["delta"]), reverse=True)

    limit = top_n if top_n is not None else 5
    return {
        "highlights": all_movements[:limit],
        "movements": all_movements,
    }
