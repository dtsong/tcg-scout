"""Card synergy analysis — co-occurrence patterns across decklists."""

import sqlite3
from collections import defaultdict

from analysis.shared import BASIC_ENERGY_NAMES, placement_weight, slugify


def compute_synergy_pairs(
    conn: sqlite3.Connection,
    min_cooccurrences: int = 5,
    top_partners_per_card: int = 15,
) -> dict:
    """Compute card pair synergy metrics from decklist co-occurrence.

    Returns:
        {
            "pairs": [...],  # Top 200 pairs by lift
            "per_card": {card_name: [partner, ...]}  # Top N partners per card
        }
    """
    energy_names = sorted(BASIC_ENERGY_NAMES)
    energy_placeholders = ",".join("?" * len(energy_names))

    total_decks = conn.execute(
        """
        SELECT COUNT(DISTINCT p.id)
        FROM open_placements p
        JOIN decklist_cards dc ON dc.placement_id = p.id
        """
    ).fetchone()[0]
    if total_decks < 2:
        return {"pairs": [], "per_card": {}}

    # Get per-card appearance sets: {card_name: set(placement_ids)}
    rows = conn.execute(
        f"""
        SELECT dc.card_name, dc.placement_id
        FROM decklist_cards dc
        JOIN open_placements p ON p.id = dc.placement_id
        WHERE dc.card_name NOT IN ({energy_placeholders})
        """,
        energy_names,
    ).fetchall()

    card_placements: dict[str, set[int]] = defaultdict(set)
    for r in rows:
        card_placements[r["card_name"]].add(r["placement_id"])

    # Get placement weights for weighted scoring
    placement_standings = {}
    standing_rows = conn.execute("SELECT id, standing FROM open_placements").fetchall()
    for r in standing_rows:
        placement_standings[r["id"]] = r["standing"]

    # Filter to cards with enough appearances to be meaningful
    min_card_appearances = 3
    eligible_cards = {
        name: pids for name, pids in card_placements.items() if len(pids) >= min_card_appearances
    }

    card_names = sorted(eligible_cards.keys())
    n = len(card_names)

    # Compute pair metrics using set intersection
    pairs: list[dict] = []

    for i in range(n):
        card_a = card_names[i]
        set_a = eligible_cards[card_a]
        p_a = len(set_a) / total_decks

        for j in range(i + 1, n):
            card_b = card_names[j]
            set_b = eligible_cards[card_b]

            intersection = set_a & set_b
            support = len(intersection)

            if support < min_cooccurrences:
                continue

            p_b = len(set_b) / total_decks
            p_ab = support / total_decks

            # Lift: how much more likely they co-occur vs independent
            expected = p_a * p_b
            lift = p_ab / expected if expected > 0 else 0

            # Jaccard: overlap strength
            union = len(set_a | set_b)
            jaccard = support / union if union > 0 else 0

            # Weighted score: sum of placement weights for co-occurrences
            weighted_score = sum(
                placement_weight(placement_standings.get(pid, 99)) for pid in intersection
            )

            pair = {
                "card_a": card_a,
                "card_b": card_b,
                "support": support,
                "lift": round(lift, 3),
                "jaccard": round(jaccard, 3),
                "weighted_score": round(weighted_score, 2),
            }
            pairs.append(pair)

    # Sort by lift for top pairs
    pairs.sort(key=lambda p: p["lift"], reverse=True)

    # Build per-card top partners
    # Use a dict to accumulate all partner data per card
    card_partner_data: dict[str, list[dict]] = defaultdict(list)
    for pair in pairs:
        card_partner_data[pair["card_a"]].append(
            {
                "card_name": pair["card_b"],
                "support": pair["support"],
                "lift": pair["lift"],
                "jaccard": pair["jaccard"],
                "weighted_score": pair["weighted_score"],
            }
        )
        card_partner_data[pair["card_b"]].append(
            {
                "card_name": pair["card_a"],
                "support": pair["support"],
                "lift": pair["lift"],
                "jaccard": pair["jaccard"],
                "weighted_score": pair["weighted_score"],
            }
        )

    # Keep top N partners per card, sorted by lift
    per_card = {}
    for card_name, partners in card_partner_data.items():
        partners.sort(key=lambda p: p["lift"], reverse=True)
        per_card[card_name] = partners[:top_partners_per_card]

    # Get archetype context for top pairs
    top_pairs = pairs[:200]
    for pair in top_pairs:
        pair["archetypes"] = _get_pair_archetypes(
            conn, pair["card_a"], pair["card_b"], card_placements
        )

    return {
        "pairs": top_pairs,
        "per_card": per_card,
    }


def compute_archetype_overlap_matrix(
    conn: sqlite3.Connection,
    top_n: int = 15,
) -> dict:
    """Compute card overlap (Jaccard similarity) between top archetypes.

    Returns:
        {
            "archetypes": [{name, slug, weighted_share, sprite_filenames}, ...],
            "matrix": [[float, ...], ...]  # n x n Jaccard similarity
        }
    """

    # Get top archetypes by deck count from latest snapshot
    snapshot_rows = conn.execute(
        """
        SELECT archetype, deck_count, tier
        FROM archetype_stats
        WHERE snapshot_id = (SELECT MAX(id) FROM meta_snapshots)
        ORDER BY deck_count DESC
        LIMIT ?
        """,
        (top_n,),
    ).fetchall()

    if not snapshot_rows:
        return {"archetypes": [], "matrix": []}

    arch_names = [r["archetype"] for r in snapshot_rows]

    # Get card sets per archetype (non-energy cards used in >30% of decks)
    energy_names = sorted(BASIC_ENERGY_NAMES)
    energy_placeholders = ",".join("?" * len(energy_names))

    arch_card_sets: dict[str, set[str]] = {}
    for arch_name in arch_names:
        total = conn.execute(
            "SELECT COUNT(*) FROM open_placements WHERE archetype = ?",
            (arch_name,),
        ).fetchone()[0]

        if total == 0:
            arch_card_sets[arch_name] = set()
            continue

        threshold = max(1, total * 0.3)  # 30% inclusion
        rows = conn.execute(
            f"""
            SELECT dc.card_name, COUNT(DISTINCT dc.placement_id) AS cnt
            FROM decklist_cards dc
            JOIN open_placements p ON p.id = dc.placement_id
            WHERE p.archetype = ?
              AND dc.card_name NOT IN ({energy_placeholders})
            GROUP BY dc.card_name
            HAVING cnt >= ?
            """,
            (arch_name, *energy_names, threshold),
        ).fetchall()

        arch_card_sets[arch_name] = {r["card_name"] for r in rows}

    # Get sprite filenames and weighted shares
    from reports.json_export import _compute_weighted_shares, _get_sprite_filenames

    snapshot = {"archetypes": snapshot_rows}
    weighted_shares = _compute_weighted_shares(conn, snapshot)

    archetypes = []
    for r in snapshot_rows:
        archetypes.append(
            {
                "archetype": r["archetype"],
                "slug": slugify(r["archetype"]),
                "sprite_filenames": _get_sprite_filenames(r["archetype"]),
                "weighted_share": round(weighted_shares.get(r["archetype"], 0.0), 1),
            }
        )

    # Compute Jaccard matrix
    n = len(arch_names)
    matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        set_i = arch_card_sets[arch_names[i]]
        for j in range(n):
            if i == j:
                matrix[i][j] = 1.0
                continue
            set_j = arch_card_sets[arch_names[j]]
            union = len(set_i | set_j)
            if union == 0:
                matrix[i][j] = 0.0
            else:
                matrix[i][j] = round(len(set_i & set_j) / union, 3)

    return {
        "archetypes": archetypes,
        "matrix": matrix,
    }


def _get_pair_archetypes(
    conn: sqlite3.Connection,
    card_a: str,
    card_b: str,
    card_placements: dict[str, set[int]],
) -> list[str]:
    """Get archetypes where both cards co-occur."""
    intersection = card_placements.get(card_a, set()) & card_placements.get(card_b, set())
    if not intersection:
        return []

    placeholders = ",".join("?" * len(intersection))
    rows = conn.execute(
        f"""
        SELECT DISTINCT archetype FROM open_placements
        WHERE id IN ({placeholders})
        ORDER BY archetype
        """,
        list(intersection),
    ).fetchall()

    return [r["archetype"] for r in rows]
