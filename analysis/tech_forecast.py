"""Tech card weather forecast — tracks adoption trends for meta-defining tech cards."""

import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta

from config import TECH_TREND_THRESHOLD


def _build_jp_to_en(conn: sqlite3.Connection) -> dict[str, str]:
    """Build JP→EN card name lookup from cards table and card_mappings."""
    lookup: dict[str, str] = {}
    try:
        for row in conn.execute(
            "SELECT name_jp, name_en FROM cards WHERE name_jp IS NOT NULL AND name_jp != ''"
        ):
            lookup[row["name_jp"]] = row["name_en"]
    except sqlite3.OperationalError:
        pass
    try:
        for row in conn.execute(
            "SELECT card_name_jp, card_name_en FROM card_mappings "
            "WHERE card_name_jp IS NOT NULL AND card_name_en IS NOT NULL"
        ):
            lookup[row["card_name_jp"]] = row["card_name_en"]
    except sqlite3.OperationalError:
        pass
    return lookup


def compute_tech_forecast(conn: sqlite3.Connection, watchlist: set[str]) -> dict:
    """Compute weekly adoption trends for tech/meta cards.

    Returns a dict with generated_at timestamp and per-card trend data
    sorted by volatility (abs trend_delta descending).
    """
    conn.row_factory = sqlite3.Row
    if not watchlist:
        return {"generated_at": datetime.now().isoformat(), "cards": []}

    # Build JP→EN mapping so we can match JP card names to EN watchlist
    jp_to_en = _build_jp_to_en(conn)
    en_to_jp: dict[str, str] = {v: k for k, v in jp_to_en.items()}

    # Build the full set of names to query (EN + JP equivalents)
    query_names = set(watchlist)
    for en_name in watchlist:
        jp_name = en_to_jp.get(en_name)
        if jp_name:
            query_names.add(jp_name)

    # All open-division placements that have decklists
    placement_rows = conn.execute(
        """
        SELECT DISTINCT p.id AS placement_id, t.date, p.archetype
        FROM open_placements p
        JOIN tournaments t ON t.id = p.tournament_id
        JOIN decklist_cards dc ON dc.placement_id = p.id
        ORDER BY t.date
        """
    ).fetchall()

    if not placement_rows:
        return {"generated_at": datetime.now().isoformat(), "cards": []}

    # Group placements by ISO week (Monday-based)
    week_placements = defaultdict(list)  # week -> [(placement_id, archetype)]
    for r in placement_rows:
        d = date.fromisoformat(r["date"])
        monday = d - timedelta(days=d.weekday())
        week_placements[monday.isoformat()].append((r["placement_id"], r["archetype"]))

    weeks = sorted(week_placements.keys())

    # Get all decklist_cards rows for watchlist cards (both EN and JP names)
    card_list = sorted(query_names)
    placeholders = ",".join("?" * len(card_list))
    card_rows = conn.execute(
        f"""
        SELECT dc.placement_id, dc.card_name, dc.count
        FROM decklist_cards dc
        WHERE dc.card_name IN ({placeholders})
        """,
        card_list,
    ).fetchall()

    # Build lookup: placement_id -> {en_card_name: count}
    # Normalize JP names to their EN equivalents
    placement_cards = defaultdict(dict)
    for r in card_rows:
        name = r["card_name"]
        en_name = jp_to_en.get(name, name)
        placement_cards[r["placement_id"]][en_name] = r["count"]

    # Compute per-card, per-week stats
    # card -> week -> {deck_count, total_copies}
    card_week_stats = defaultdict(lambda: defaultdict(lambda: {"deck_count": 0, "total_copies": 0}))

    for wk in weeks:
        for pid, _archetype in week_placements[wk]:
            for card_name, count in placement_cards.get(pid, {}).items():
                card_week_stats[card_name][wk]["deck_count"] += 1
                card_week_stats[card_name][wk]["total_copies"] += count

    # Build per-card results
    results = []

    for card_name in watchlist:
        weekly_data = []
        for wk in weeks:
            total_decks = len(week_placements[wk])
            stats = card_week_stats[card_name][wk]
            deck_count = stats["deck_count"]
            adoption_pct = round(deck_count / total_decks * 100, 1) if total_decks > 0 else 0.0
            avg_copies = round(stats["total_copies"] / deck_count, 1) if deck_count > 0 else 0.0

            weekly_data.append(
                {
                    "week": wk,
                    "adoption_pct": adoption_pct,
                    "avg_copies": avg_copies,
                    "deck_count": deck_count,
                    "total_decks": total_decks,
                }
            )

        # Current = last week, prior = second-to-last week
        current = weekly_data[-1]
        current_adoption = current["adoption_pct"]
        current_avg = current["avg_copies"]

        if len(weekly_data) >= 2:
            prior = weekly_data[-2]
            prior_adoption = prior["adoption_pct"]
            delta = round(current_adoption - prior_adoption, 1)

            if prior_adoption == 0.0 and current_adoption > 0.0:
                direction = "new"
            elif delta > TECH_TREND_THRESHOLD:
                direction = "rising"
            elif delta < -TECH_TREND_THRESHOLD:
                direction = "falling"
            else:
                direction = "stable"
        else:
            delta = 0.0
            direction = "new" if current_adoption > 0.0 else "stable"

        # Top archetypes: compute inclusion within each archetype for latest week
        latest_week = weeks[-1]
        archetype_stats = defaultdict(lambda: {"included": 0, "total": 0, "total_copies": 0})

        for pid, archetype in week_placements[latest_week]:
            archetype_stats[archetype]["total"] += 1
            cards_in_deck = placement_cards.get(pid, {})
            if card_name in cards_in_deck:
                archetype_stats[archetype]["included"] += 1
                archetype_stats[archetype]["total_copies"] += cards_in_deck[card_name]

        top_archetypes = []
        for arch, st in archetype_stats.items():
            if st["included"] > 0:
                top_archetypes.append(
                    {
                        "archetype": arch,
                        "inclusion_pct": round(st["included"] / st["total"] * 100, 1),
                        "avg_copies": round(st["total_copies"] / st["included"], 1),
                    }
                )

        top_archetypes.sort(key=lambda x: x["inclusion_pct"], reverse=True)
        top_archetypes = top_archetypes[:5]

        results.append(
            {
                "card_name": card_name,
                "current_adoption_pct": current_adoption,
                "current_avg_copies": current_avg,
                "trend_direction": direction,
                "trend_delta": delta,
                "weekly_data": weekly_data,
                "top_archetypes": top_archetypes,
            }
        )

    # Sort by volatility (abs trend_delta descending)
    results.sort(key=lambda x: abs(x["trend_delta"]), reverse=True)

    return {
        "generated_at": datetime.now().isoformat(),
        "cards": results,
    }
