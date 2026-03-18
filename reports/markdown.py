"""Markdown meta report renderer."""

import sqlite3
from datetime import date
from pathlib import Path

TIER_ORDER = ["S", "A", "B", "C", "Rogue"]

DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "reports" / "output"


def render_meta_report(
    conn: sqlite3.Connection,
    snapshot_id: int,
    output_dir: Path | None = None,
) -> Path:
    """Render a Markdown meta report. Writes to file and returns the file path."""
    # Fetch snapshot metadata
    row = conn.execute(
        "SELECT generated_at, tournament_count, deck_count FROM meta_snapshots WHERE id = ?",
        (snapshot_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Snapshot {snapshot_id} not found")

    snapshot_date = row["generated_at"][:10] if row["generated_at"] else str(date.today())
    tournament_count = row["tournament_count"] or 0
    deck_count = row["deck_count"] or 0

    # Fetch archetype stats
    rows = conn.execute(
        "SELECT archetype, meta_share, deck_count, best_placement, tier "
        "FROM archetype_stats WHERE snapshot_id = ? "
        "ORDER BY meta_share DESC",
        (snapshot_id,),
    ).fetchall()

    # Group by tier
    tiers: dict[str, list] = {t: [] for t in TIER_ORDER}
    for r in rows:
        tier = r["tier"] or "Rogue"
        if tier not in tiers:
            tier = "Rogue"
        tiers[tier].append(r)

    # Sort within each tier by meta_share desc (already sorted overall, but ensure per-tier)
    for tier in tiers:
        tiers[tier].sort(key=lambda x: x["meta_share"], reverse=True)

    # Build markdown
    lines: list[str] = []
    lines.append(f"# JP Rotation Meta Report — {snapshot_date}")
    lines.append(
        f"> Data: {tournament_count} tournaments, {deck_count} decks "
        f"| Format: JP Standard (BO1) | Rotation-legal only"
    )
    lines.append("> Note: JP plays BO1 — aggressive/linear decks may be overrepresented vs BO3")
    lines.append("")
    lines.append("## Tier List")
    lines.append("| Tier | Archetype | Meta Share | Decks | Best Finish |")
    lines.append("|------|-----------|-----------|-------|-------------|")

    for tier in TIER_ORDER:
        for r in tiers[tier]:
            best = _format_placement(r["best_placement"])
            share = f"{r['meta_share']:.1f}%"
            lines.append(f"| {tier} | {r['archetype']} | {share} | {r['deck_count']} | {best} |")

    md = "\n".join(lines) + "\n"

    # Write to file
    out = output_dir or DEFAULT_OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    filepath = out / f"meta-{snapshot_date}.md"
    filepath.write_text(md, encoding="utf-8")

    return filepath


def _format_placement(placement: int | None) -> str:
    """Format a placement number as a finish string (e.g. 1 -> '1st')."""
    if placement is None:
        return "—"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(placement if placement < 20 else placement % 10, "th")
    return f"{placement}{suffix}"
