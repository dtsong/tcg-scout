"""Tech card weather forecast — tracks adoption trends for meta-defining tech cards."""

import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta


def compute_tech_forecast(conn: sqlite3.Connection, watchlist: set[str]) -> dict:
    """Compute weekly adoption trends for tech/meta cards.

    Returns a dict with generated_at timestamp and per-card trend data
    sorted by volatility (abs trend_delta descending).
    """
    if not watchlist:
        return {"generated_at": datetime.now().isoformat(), "cards": []}

    # All placements that have decklists (at least one card in decklist_cards)
    placement_rows = conn.execute(
        """
        SELECT DISTINCT p.id AS placement_id, t.date, p.archetype
        FROM placements p
        JOIN tournaments t ON t.id = p.tournament_id
        JOIN decklist_cards dc ON dc.placement_id = p.id
        WHERE t.division = 'open'
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

    # Get all decklist_cards rows for watchlist cards
    card_list = sorted(watchlist)
    placeholders = ",".join("?" * len(card_list))
    card_rows = conn.execute(
        f"""
        SELECT dc.placement_id, dc.card_name, dc.count
        FROM decklist_cards dc
        WHERE dc.card_name IN ({placeholders})
        """,
        card_list,
    ).fetchall()

    # Build lookup: placement_id -> {card_name: count}
    placement_cards = defaultdict(dict)
    for r in card_rows:
        placement_cards[r["placement_id"]][r["card_name"]] = r["count"]

    # Compute per-card, per-week stats
    # card -> week -> {deck_count, total_copies}
    card_week_stats = defaultdict(lambda: defaultdict(lambda: {"deck_count": 0, "total_copies": 0}))

    for wk in weeks:
        for pid, _archetype in week_placements[wk]:
            cards_in_deck = placement_cards.get(pid, {})
            for card_name in watchlist:
                if card_name in cards_in_deck:
                    card_week_stats[card_name][wk]["deck_count"] += 1
                    card_week_stats[card_name][wk]["total_copies"] += cards_in_deck[card_name]

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
            elif delta > 2.0:
                direction = "rising"
            elif delta < -2.0:
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
