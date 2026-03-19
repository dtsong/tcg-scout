"""Matchup analysis — tournament co-occurrence performance proxy."""

import sqlite3
from collections import defaultdict


def compute_matchup_matrix(
    conn: sqlite3.Connection,
    top_n: int = 15,
    min_cooccurrences: int = 10,
) -> dict:
    """Compute archetype performance advantage matrix.

    For each pair of archetypes that co-occur in the same tournaments,
    compare their average standings. A positive value means archetype_i
    outperforms archetype_j (lower average standing = better).

    Returns:
        {
            "archetypes": [name, ...],
            "matrix": [[advantage, ...], ...],  # matrix[i][j] = i's advantage over j
            "sample_sizes": [[count, ...], ...],  # co-occurrence count
        }
    """
    # Get top archetypes by deck count
    arch_rows = conn.execute(
        """
        SELECT archetype, deck_count FROM archetype_stats
        WHERE snapshot_id = (SELECT MAX(id) FROM meta_snapshots)
        ORDER BY deck_count DESC
        LIMIT ?
        """,
        (top_n,),
    ).fetchall()

    if not arch_rows:
        return {"archetypes": [], "matrix": [], "sample_sizes": []}

    arch_names = [r["archetype"] for r in arch_rows]
    arch_set = set(arch_names)

    # Get per-tournament, per-archetype average standings
    rows = conn.execute(
        """
        SELECT t.id AS tid, p.archetype, AVG(p.standing) AS avg_standing
        FROM placements p
        JOIN tournaments t ON t.id = p.tournament_id
        GROUP BY t.id, p.archetype
        """
    ).fetchall()

    # Build: {tournament_id: {archetype: avg_standing}}
    tournament_data: dict[str, dict[str, float]] = defaultdict(dict)
    for r in rows:
        if r["archetype"] in arch_set:
            tournament_data[r["tid"]][r["archetype"]] = r["avg_standing"]

    # Compute pairwise advantages
    n = len(arch_names)
    advantages = [[0.0] * n for _ in range(n)]
    counts = [[0] * n for _ in range(n)]

    for _tid, arch_standings in tournament_data.items():
        for i in range(n):
            if arch_names[i] not in arch_standings:
                continue
            for j in range(i + 1, n):
                if arch_names[j] not in arch_standings:
                    continue
                # Both archetypes present in this tournament
                diff = arch_standings[arch_names[j]] - arch_standings[arch_names[i]]
                # Positive diff = archetype_i has lower (better) standing
                advantages[i][j] += diff
                advantages[j][i] -= diff
                counts[i][j] += 1
                counts[j][i] += 1

    # Average the accumulated differences
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                matrix[i][j] = 0.0
            elif counts[i][j] >= min_cooccurrences:
                matrix[i][j] = round(advantages[i][j] / counts[i][j], 1)
            else:
                matrix[i][j] = 0.0  # Insufficient data

    return {
        "archetypes": arch_names,
        "matrix": matrix,
        "sample_sizes": counts,
    }
