"""Meta share computation and tier assignment."""

import logging
import sqlite3
from datetime import UTC, datetime

from analysis.shared import placement_weight
from config import TIER_THRESHOLDS

logger = logging.getLogger(__name__)


def _assign_tier(meta_share: float, thresholds: dict[str, float] | None = None) -> str:
    """Assign tier based on meta share percentage."""
    t = thresholds or TIER_THRESHOLDS
    if meta_share >= t["S"]:
        return "S"
    if meta_share >= t["A"]:
        return "A"
    if meta_share >= t["B"]:
        return "B"
    if meta_share >= t["C"]:
        return "C"
    return "Rogue"


def compute_meta_snapshot(
    conn: sqlite3.Connection, thresholds: dict[str, float] | None = None
) -> int:
    """Compute meta snapshot from all placements. Returns snapshot_id."""
    conn.row_factory = sqlite3.Row

    # Query all placements grouped by archetype (open division only)
    rows = conn.execute(
        """
        SELECT p.archetype,
               COUNT(*) AS deck_count,
               MIN(p.standing) AS best_placement
        FROM open_placements p
        GROUP BY p.archetype
        """
    ).fetchall()

    if not rows:
        logger.warning("No placements found; cannot compute meta snapshot")
        raise ValueError("No placement data available")

    total_decks = sum(r["deck_count"] for r in rows)
    tournament_count_row = conn.execute(
        "SELECT COUNT(DISTINCT p.tournament_id) AS cnt FROM open_placements p"
    ).fetchone()
    tournament_count = tournament_count_row["cnt"]

    logger.info(
        "Computing meta snapshot: %d archetypes, %d decks, %d tournaments",
        len(rows),
        total_decks,
        tournament_count,
    )

    # Insert meta snapshot
    cur = conn.execute(
        """
        INSERT INTO meta_snapshots (generated_at, tournament_count, deck_count)
        VALUES (?, ?, ?)
        """,
        (datetime.now(UTC).isoformat(), tournament_count, total_decks),
    )
    snapshot_id = cur.lastrowid

    # Compute performance-weighted shares
    weight_rows = conn.execute("SELECT archetype, standing FROM open_placements").fetchall()
    weighted_sums: dict[str, float] = {}
    total_weight = 0.0
    for wr in weight_rows:
        w = placement_weight(wr["standing"])
        weighted_sums[wr["archetype"]] = weighted_sums.get(wr["archetype"], 0.0) + w
        total_weight += w
    weighted_shares = (
        {arch: round(w / total_weight * 100, 2) for arch, w in weighted_sums.items()}
        if total_weight > 0
        else {}
    )

    # Insert archetype stats
    for row in rows:
        meta_share = row["deck_count"] / total_decks * 100
        tier = _assign_tier(meta_share, thresholds)
        conn.execute(
            """
            INSERT INTO archetype_stats
                (snapshot_id, archetype, meta_share, deck_count, best_placement, tier, weighted_share)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                row["archetype"],
                round(meta_share, 2),
                row["deck_count"],
                row["best_placement"],
                tier,
                weighted_shares.get(row["archetype"]),
            ),
        )

    conn.commit()
    logger.info("Meta snapshot %d created", snapshot_id)
    return snapshot_id


def get_latest_snapshot(conn: sqlite3.Connection) -> dict | None:
    """Get the latest meta snapshot with archetype stats.

    Returns dict with snapshot info and a list of archetype_stats rows
    sorted by meta_share descending, or None if no snapshots exist.
    """
    conn.row_factory = sqlite3.Row

    snapshot = conn.execute(
        """
        SELECT id, generated_at, tournament_count, deck_count
        FROM meta_snapshots
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    if snapshot is None:
        return None

    stats = conn.execute(
        """
        SELECT archetype, meta_share, deck_count, best_placement, tier, weighted_share
        FROM archetype_stats
        WHERE snapshot_id = ?
        ORDER BY meta_share DESC
        """,
        (snapshot["id"],),
    ).fetchall()

    all_archetypes = [dict(row) for row in stats]
    unknown_archetype = next(
        (row for row in all_archetypes if row["archetype"] == "Unknown"),
        None,
    )

    return {
        "id": snapshot["id"],
        "generated_at": snapshot["generated_at"],
        "tournament_count": snapshot["tournament_count"],
        "deck_count": snapshot["deck_count"],
        "archetypes": [row for row in all_archetypes if row["archetype"] != "Unknown"],
        "unknown_archetype": unknown_archetype,
    }
