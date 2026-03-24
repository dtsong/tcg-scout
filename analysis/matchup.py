"""Matchup analysis — co-occurrence proxy and Labs H2H win rates."""

import logging
import math
import sqlite3
from collections import defaultdict
from typing import TypedDict

from config import LABS_MIN_MATCHES_TO_PUBLISH, LABS_WILSON_Z


class ConfidenceInterval(TypedDict):
    lower: float
    upper: float


class ArchetypeWinrateEntry(TypedDict):
    archetype: str
    players: int
    total_wins: int
    total_losses: int
    total_ties: int
    total_matches: int
    win_rate: float
    ci_lower: float
    ci_upper: float


class WinrateResult(TypedDict):
    archetypes: list[ArchetypeWinrateEntry]
    source: str
    tournament_count: int


class MatchupMatrixResult(TypedDict):
    archetypes: list[str]
    matrix: list[list[float]]
    sample_sizes: list[list[int]]
    confidence: list[list[ConfidenceInterval]]
    source: str


logger = logging.getLogger(__name__)


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
        FROM open_placements p
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


# ---------------------------------------------------------------------------
# Labs H2H — archetype win rates from actual W-L-T records
# ---------------------------------------------------------------------------


def _wilson_ci(wins: int, total: int, z: float = LABS_WILSON_Z) -> tuple[float, float]:
    """Compute Wilson score confidence interval for a proportion.

    Returns (lower_bound, upper_bound) as proportions in [0, 1].
    """
    if total == 0:
        return 0.0, 0.0
    p = wins / total
    denominator = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denominator
    spread = z * math.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denominator
    return max(0.0, center - spread), min(1.0, center + spread)


def compute_labs_archetype_winrates(
    conn: sqlite3.Connection,
    top_n: int = 20,
    min_players: int = 5,
) -> WinrateResult:
    """Compute archetype win rates from Labs placement records.

    Uses actual W-L-T records from tournament standings to compute
    per-archetype win rates with Wilson score confidence intervals.

    Args:
        conn: SQLite connection to labs.db.
        top_n: Number of top archetypes to include.
        min_players: Minimum players with an archetype to include.

    Returns:
        {
            "archetypes": [
                {
                    "archetype": str,
                    "players": int,
                    "total_wins": int,
                    "total_losses": int,
                    "total_ties": int,
                    "total_matches": int,
                    "win_rate": float,
                    "ci_lower": float,
                    "ci_upper": float,
                },
                ...
            ],
            "source": "labs-h2h",
            "tournament_count": int,
        }
    """
    # Aggregate W-L-T records by archetype
    rows = conn.execute(
        """
        SELECT
            archetype,
            COUNT(*) AS players,
            SUM(record_w) AS total_w,
            SUM(record_l) AS total_l,
            SUM(record_t) AS total_t
        FROM placements
        WHERE archetype IS NOT NULL AND archetype != 'Unknown'
        GROUP BY archetype
        HAVING COUNT(*) >= ?
        ORDER BY SUM(record_w) + SUM(record_l) + SUM(record_t) DESC
        LIMIT ?
        """,
        (min_players, top_n),
    ).fetchall()

    tournament_count = conn.execute("SELECT COUNT(*) FROM tournaments").fetchone()[0]

    archetypes = []
    for r in rows:
        total_w = r["total_w"] or 0
        total_l = r["total_l"] or 0
        total_t = r["total_t"] or 0
        total_matches = total_w + total_l + total_t

        if total_matches == 0:
            continue

        win_rate = total_w / total_matches
        ci_lower, ci_upper = _wilson_ci(total_w, total_matches)

        archetypes.append(
            {
                "archetype": r["archetype"],
                "players": r["players"],
                "total_wins": total_w,
                "total_losses": total_l,
                "total_ties": total_t,
                "total_matches": total_matches,
                "win_rate": round(win_rate, 4),
                "ci_lower": round(ci_lower, 4),
                "ci_upper": round(ci_upper, 4),
            }
        )

    return {
        "archetypes": archetypes,
        "source": "labs-h2h",
        "tournament_count": tournament_count,
    }


def _top_archetypes(conn: sqlite3.Connection, top_n: int) -> list[sqlite3.Row]:
    """Get the top archetypes by player count from the placements table."""
    return conn.execute(
        """
        SELECT archetype, COUNT(*) AS cnt
        FROM placements
        WHERE archetype IS NOT NULL AND archetype != 'Unknown'
        GROUP BY archetype
        ORDER BY cnt DESC
        LIMIT ?
        """,
        (top_n,),
    ).fetchall()


# NOTE: Callers must add "source" key when returning this sentinel.
_EMPTY_MATRIX: MatchupMatrixResult = {
    "archetypes": [],
    "matrix": [],
    "sample_sizes": [],
    "confidence": [],
    "source": "",
}


def compute_labs_matchup_matrix(
    conn: sqlite3.Connection,
    top_n: int = 15,
    min_matches: int = LABS_MIN_MATCHES_TO_PUBLISH,
) -> MatchupMatrixResult:
    """Compute archetype-vs-archetype matchup data from Labs H2H matches.

    When actual match-level H2H data is available (matches table), computes
    true win rates between archetype pairs. Falls back to record-based
    performance comparison when H2H pairings aren't available.

    Args:
        conn: SQLite connection to labs.db.
        top_n: Number of top archetypes by player count.
        min_matches: Minimum matches between a pair to publish.

    Returns:
        {
            "archetypes": [name, ...],
            "matrix": [[win_rate, ...], ...],  # matrix[i][j] = i's win rate vs j
            "sample_sizes": [[count, ...], ...],
            "confidence": [[{"lower": f, "upper": f}, ...], ...],
            "source": "labs-h2h" | "labs-records",
        }
    """
    # Check if we have match-level data
    has_matches = False
    table_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='matches'"
    ).fetchone()
    if table_exists:
        match_count = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        has_matches = match_count > 0

    if has_matches:
        return _compute_h2h_from_matches(conn, top_n, min_matches)

    logger.info("No match-level H2H data; falling back to record-based comparison")
    return _compute_h2h_from_records(conn, top_n, min_matches)


def _compute_h2h_from_matches(
    conn: sqlite3.Connection,
    top_n: int,
    min_matches: int,
) -> MatchupMatrixResult:
    """Compute true H2H win rates from the matches table."""
    arch_rows = _top_archetypes(conn, top_n)
    if not arch_rows:
        return {**_EMPTY_MATRIX, "source": "labs-h2h"}

    arch_names = [r["archetype"] for r in arch_rows]
    arch_idx = {name: i for i, name in enumerate(arch_names)}
    n = len(arch_names)

    wins = [[0] * n for _ in range(n)]
    totals = [[0] * n for _ in range(n)]

    # Aggregate matches (filtered to top archetypes)
    placeholders = ",".join("?" for _ in arch_names)
    rows = conn.execute(
        f"""
        SELECT player1_archetype, player2_archetype, winner_id, player1_id, player2_id
        FROM matches
        WHERE player1_archetype IN ({placeholders})
          AND player2_archetype IN ({placeholders})
          AND winner_id IS NOT NULL
        """,
        (*arch_names, *arch_names),
    ).fetchall()

    for r in rows:
        a1, a2 = r["player1_archetype"], r["player2_archetype"]
        if a1 not in arch_idx or a2 not in arch_idx:
            continue
        i, j = arch_idx[a1], arch_idx[a2]
        if i == j:
            continue  # Mirror match

        if r["winner_id"] == r["player1_id"]:
            totals[i][j] += 1
            totals[j][i] += 1
            wins[i][j] += 1
        elif r["winner_id"] == r["player2_id"]:
            totals[i][j] += 1
            totals[j][i] += 1
            wins[j][i] += 1
        else:
            logger.warning(
                "Match winner_id %r does not match player1_id %r or player2_id %r — skipping",
                r["winner_id"],
                r["player1_id"],
                r["player2_id"],
            )

    # Build output matrices
    matrix = [[0.0] * n for _ in range(n)]
    confidence = [[{"lower": 0.0, "upper": 0.0} for _ in range(n)] for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i == j:
                matrix[i][j] = 0.5
                confidence[i][j] = {"lower": 0.5, "upper": 0.5}
            elif totals[i][j] >= min_matches:
                wr = wins[i][j] / totals[i][j]
                ci_lo, ci_hi = _wilson_ci(wins[i][j], totals[i][j])
                matrix[i][j] = round(wr, 4)
                confidence[i][j] = {"lower": round(ci_lo, 4), "upper": round(ci_hi, 4)}

    return {
        "archetypes": arch_names,
        "matrix": matrix,
        "sample_sizes": totals,
        "confidence": confidence,
        "source": "labs-h2h",
    }


def _compute_h2h_from_records(
    conn: sqlite3.Connection,
    top_n: int,
    min_matches: int,
) -> MatchupMatrixResult:
    """Approximate matchup comparison from archetype W-L-T records.

    When true H2H pairings aren't available, compare archetype
    win rates within the same tournaments as a performance proxy.
    """
    arch_rows = _top_archetypes(conn, top_n)
    if not arch_rows:
        return {**_EMPTY_MATRIX, "source": "labs-records"}

    arch_names = [r["archetype"] for r in arch_rows]
    arch_set = set(arch_names)
    n = len(arch_names)

    # Per-tournament archetype win rates
    rows = conn.execute(
        """
        SELECT
            tournament_id,
            archetype,
            AVG(CAST(record_w AS REAL) / NULLIF(record_w + record_l + record_t, 0)) AS avg_wr,
            COUNT(*) AS players
        FROM placements
        WHERE archetype IS NOT NULL AND archetype != 'Unknown'
        GROUP BY tournament_id, archetype
        """
    ).fetchall()

    # {tournament_id: {archetype: (avg_win_rate, player_count)}}
    tourney_data: dict[str, dict[str, tuple[float, int]]] = defaultdict(dict)
    for r in rows:
        if r["archetype"] in arch_set and r["avg_wr"] is not None:
            tourney_data[r["tournament_id"]][r["archetype"]] = (r["avg_wr"], r["players"])

    # Compute pairwise win rate comparisons
    matrix = [[0.0] * n for _ in range(n)]
    counts = [[0] * n for _ in range(n)]
    confidence = [[{"lower": 0.0, "upper": 0.0} for _ in range(n)] for _ in range(n)]

    for _tid, arch_wrs in tourney_data.items():
        for i in range(n):
            if arch_names[i] not in arch_wrs:
                continue
            wr_i, players_i = arch_wrs[arch_names[i]]
            for j in range(i + 1, n):
                if arch_names[j] not in arch_wrs:
                    continue
                wr_j, players_j = arch_wrs[arch_names[j]]
                # Weight by min player count as proxy for actual matchup encounters
                weight = min(players_i, players_j)
                matrix[i][j] += wr_i * weight
                matrix[j][i] += wr_j * weight
                counts[i][j] += weight
                counts[j][i] += weight

    # Average and apply minimum threshold
    for i in range(n):
        for j in range(n):
            if i == j:
                matrix[i][j] = 0.5
                confidence[i][j] = {"lower": 0.5, "upper": 0.5}
            elif counts[i][j] >= min_matches:
                avg_wr = matrix[i][j] / counts[i][j]
                matrix[i][j] = round(avg_wr, 4)
                # Approximate CI using Wald interval (normal approximation)
                se = math.sqrt(avg_wr * (1 - avg_wr) / counts[i][j]) if 0 < avg_wr < 1 else 0.0
                ci_lo = max(0.0, avg_wr - LABS_WILSON_Z * se)
                ci_hi = min(1.0, avg_wr + LABS_WILSON_Z * se)
                confidence[i][j] = {"lower": round(ci_lo, 4), "upper": round(ci_hi, 4)}
            else:
                matrix[i][j] = 0.0
                confidence[i][j] = {"lower": 0.0, "upper": 0.0}

    return {
        "archetypes": arch_names,
        "matrix": matrix,
        "sample_sizes": counts,
        "confidence": confidence,
        "source": "labs-records",
    }
