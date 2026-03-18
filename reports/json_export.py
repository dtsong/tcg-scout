"""JSON export for Scout Web — generates static data files for the Next.js dashboard."""

import json
import logging
import sqlite3
from pathlib import Path

from analysis.buylist import generate_buylist
from analysis.meta import get_latest_snapshot
from config import (
    DATASET_END,
    DATASET_START,
    ROTATION_DATE,
    TIER_THRESHOLDS,
)

logger = logging.getLogger(__name__)

# Default output directory (web/public/data/)
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "web" / "public" / "data"

# Known ACE SPEC card names
ACE_SPEC_CARDS = {
    "Prime Catcher",
    "Hero's Cape",
    "Master Ball",
    "Maximum Belt",
    "Reboot Pod",
    "Survival Brace",
    "Unfair Stamp",
    "Sparkling Crystal",
    "Deluxe Bomb",
    "Neo Upper Energy",
    "Legacy Energy",
    "Awakening Drum",
    "Grand Tree",
    "Dangerous Laser",
    "Secret Box",
    "Poké Vital A",
    "Miracle Headset",
    "Amulet of Hope",
    "Hyper Aroma",
}

# Minimum deck count for an archetype to get its own detail page
MIN_ARCHETYPE_DECKS = 10


def _write_json(data: dict | list, path: Path) -> None:
    """Write data to a JSON file, creating directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote %s", path)


def _slugify(name: str) -> str:
    """Convert archetype name to URL slug."""
    import re

    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def export_meta(conn: sqlite3.Connection, output_dir: Path) -> dict | None:
    """Export meta.json — snapshot stats + tier list."""
    snapshot = get_latest_snapshot(conn)
    if not snapshot:
        logger.warning("No meta snapshot found")
        return None

    # Get date range from tournaments
    date_range = conn.execute(
        "SELECT MIN(date) as earliest, MAX(date) as latest FROM tournaments"
    ).fetchone()

    archetypes = []
    for arch in snapshot["archetypes"]:
        archetypes.append({
            "archetype": arch["archetype"],
            "slug": _slugify(arch["archetype"]),
            "meta_share": round(arch["meta_share"], 1),
            "deck_count": arch["deck_count"],
            "best_placement": arch["best_placement"],
            "tier": arch["tier"],
        })

    data = {
        "generated_at": snapshot["generated_at"],
        "tournament_count": snapshot["tournament_count"],
        "deck_count": snapshot["deck_count"],
        "date_range": {
            "start": date_range["earliest"] if date_range else DATASET_START,
            "end": date_range["latest"] if date_range else DATASET_END,
        },
        "rotation_date": ROTATION_DATE,
        "tier_thresholds": TIER_THRESHOLDS,
        "archetypes": archetypes,
    }

    _write_json(data, output_dir / "meta.json")
    return data


def export_buylist(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export buylist.json — full prioritized card list."""
    snapshot = get_latest_snapshot(conn)
    if not snapshot:
        return

    cards = generate_buylist(conn, snapshot["id"])
    if not cards:
        return

    _write_json(cards, output_dir / "buylist.json")


def export_staples(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export staples.json — format staples with 40%+ usage across all decks."""
    total_decks = conn.execute("SELECT COUNT(*) FROM placements").fetchone()[0]

    rows = conn.execute(
        """
        SELECT card_name,
               COUNT(DISTINCT placement_id) AS deck_count,
               ROUND(AVG(count), 1) AS avg_copies
        FROM decklist_cards
        GROUP BY card_name
        HAVING COUNT(DISTINCT placement_id) * 100.0 / ? >= 40
        ORDER BY deck_count DESC
        """,
        (total_decks,),
    ).fetchall()

    staples = []
    for row in rows:
        pct = round(row["deck_count"] * 100.0 / total_decks, 1)
        staples.append({
            "card_name": row["card_name"],
            "deck_count": row["deck_count"],
            "usage_pct": pct,
            "avg_copies": row["avg_copies"],
        })

    _write_json(staples, output_dir / "staples.json")


def export_flex(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export flex.json — broad flex cards with 20-40% usage."""
    total_decks = conn.execute("SELECT COUNT(*) FROM placements").fetchone()[0]

    rows = conn.execute(
        """
        SELECT card_name,
               COUNT(DISTINCT placement_id) AS deck_count,
               ROUND(AVG(count), 1) AS avg_copies
        FROM decklist_cards
        GROUP BY card_name
        HAVING COUNT(DISTINCT placement_id) * 100.0 / ? >= 20
           AND COUNT(DISTINCT placement_id) * 100.0 / ? < 40
        ORDER BY deck_count DESC
        """,
        (total_decks, total_decks),
    ).fetchall()

    flex = []
    for row in rows:
        pct = round(row["deck_count"] * 100.0 / total_decks, 1)
        flex.append({
            "card_name": row["card_name"],
            "deck_count": row["deck_count"],
            "usage_pct": pct,
            "avg_copies": row["avg_copies"],
        })

    _write_json(flex, output_dir / "flex.json")


def export_trends(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export trends.json — card usage growth (early vs late period)."""
    # Split at midpoint of dataset
    midpoint = "2026-02-15"

    # Early period stats
    early_total = conn.execute(
        "SELECT COUNT(*) FROM placements p JOIN tournaments t ON t.id = p.tournament_id WHERE t.date < ?",
        (midpoint,),
    ).fetchone()[0]

    late_total = conn.execute(
        "SELECT COUNT(*) FROM placements p JOIN tournaments t ON t.id = p.tournament_id WHERE t.date >= ?",
        (midpoint,),
    ).fetchone()[0]

    if early_total == 0 or late_total == 0:
        logger.warning("Insufficient data for trend analysis")
        _write_json({"midpoint": midpoint, "early_decks": 0, "late_decks": 0, "cards": []}, output_dir / "trends.json")
        return

    # Get per-card early/late counts
    rows = conn.execute(
        """
        SELECT dc.card_name,
               SUM(CASE WHEN t.date < ? THEN 1 ELSE 0 END) AS early_count,
               SUM(CASE WHEN t.date >= ? THEN 1 ELSE 0 END) AS late_count
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        JOIN tournaments t ON t.id = p.tournament_id
        GROUP BY dc.card_name
        HAVING early_count >= 5 AND late_count >= 5
        """,
        (midpoint, midpoint),
    ).fetchall()

    cards = []
    for row in rows:
        early_pct = round(row["early_count"] * 100.0 / early_total, 1)
        late_pct = round(row["late_count"] * 100.0 / late_total, 1)
        delta = round(late_pct - early_pct, 1)
        cards.append({
            "card_name": row["card_name"],
            "early_count": row["early_count"],
            "late_count": row["late_count"],
            "early_pct": early_pct,
            "late_pct": late_pct,
            "delta": delta,
        })

    # Sort by absolute delta descending, take top 20 surging
    cards.sort(key=lambda x: x["delta"], reverse=True)
    surging = cards[:20]

    _write_json({
        "midpoint": midpoint,
        "early_decks": early_total,
        "late_decks": late_total,
        "cards": surging,
    }, output_dir / "trends.json")


def export_winning_edge(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export winning-edge.json — 1st place overrepresentation vs field for S/A/B decks."""
    snapshot = get_latest_snapshot(conn)
    if not snapshot:
        return

    # Get S/A/B archetype names
    sa_archetypes = [
        a["archetype"] for a in snapshot["archetypes"]
        if a["tier"] in ("S", "A", "B")
    ]

    if not sa_archetypes:
        _write_json([], output_dir / "winning-edge.json")
        return

    placeholders = ",".join("?" * len(sa_archetypes))

    # Total decks in S/A/B
    total_field = conn.execute(
        f"SELECT COUNT(*) FROM placements WHERE archetype IN ({placeholders})",
        sa_archetypes,
    ).fetchone()[0]

    # Total 1st place decks in S/A/B
    total_winners = conn.execute(
        f"SELECT COUNT(*) FROM placements WHERE standing = 1 AND archetype IN ({placeholders})",
        sa_archetypes,
    ).fetchone()[0]

    if total_field == 0 or total_winners == 0:
        _write_json([], output_dir / "winning-edge.json")
        return

    # Per-card: field usage vs winner usage
    field_rows = conn.execute(
        f"""
        SELECT dc.card_name,
               COUNT(DISTINCT dc.placement_id) AS field_decks
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        WHERE p.archetype IN ({placeholders})
        GROUP BY dc.card_name
        HAVING field_decks >= 10
        """,
        sa_archetypes,
    ).fetchall()

    field_usage = {row["card_name"]: row["field_decks"] for row in field_rows}

    winner_rows = conn.execute(
        f"""
        SELECT dc.card_name,
               COUNT(DISTINCT dc.placement_id) AS winner_decks
        FROM decklist_cards dc
        JOIN placements p ON p.id = dc.placement_id
        WHERE p.standing = 1 AND p.archetype IN ({placeholders})
        GROUP BY dc.card_name
        """,
        sa_archetypes,
    ).fetchall()

    cards = []
    for row in winner_rows:
        name = row["card_name"]
        if name not in field_usage:
            continue
        field_pct = round(field_usage[name] * 100.0 / total_field, 1)
        win_pct = round(row["winner_decks"] * 100.0 / total_winners, 1)
        edge = round(win_pct - field_pct, 1)
        cards.append({
            "card_name": name,
            "field_pct": field_pct,
            "win_pct": win_pct,
            "edge": edge,
            "winner_decks": row["winner_decks"],
            "field_decks": field_usage[name],
        })

    cards.sort(key=lambda x: x["edge"], reverse=True)
    _write_json(cards[:20], output_dir / "winning-edge.json")


def export_ace_specs(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export ace-specs.json — ACE SPEC card distribution across decks."""
    total_decks = conn.execute("SELECT COUNT(*) FROM placements").fetchone()[0]
    placeholders = ",".join("?" * len(ACE_SPEC_CARDS))

    rows = conn.execute(
        f"""
        SELECT card_name,
               COUNT(DISTINCT placement_id) AS deck_count
        FROM decklist_cards
        WHERE card_name IN ({placeholders})
        GROUP BY card_name
        ORDER BY deck_count DESC
        """,
        list(ACE_SPEC_CARDS),
    ).fetchall()

    specs = []
    for row in rows:
        pct = round(row["deck_count"] * 100.0 / total_decks, 1)
        specs.append({
            "card_name": row["card_name"],
            "deck_count": row["deck_count"],
            "usage_pct": pct,
        })

    _write_json(specs, output_dir / "ace-specs.json")


def export_archetypes(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export per-archetype detail JSON files with core cards."""
    snapshot = get_latest_snapshot(conn)
    if not snapshot:
        return

    arch_dir = output_dir / "archetypes"
    arch_dir.mkdir(parents=True, exist_ok=True)

    for arch in snapshot["archetypes"]:
        if arch["deck_count"] < MIN_ARCHETYPE_DECKS:
            continue

        archetype_name = arch["archetype"]
        slug = _slugify(archetype_name)

        # Get all placements for this archetype
        placements = conn.execute(
            "SELECT id FROM placements WHERE archetype = ?",
            (archetype_name,),
        ).fetchall()

        if not placements:
            continue

        placement_ids = [p["id"] for p in placements]
        total_decks = len(placement_ids)
        placeholders = ",".join("?" * len(placement_ids))

        # Get per-card stats
        rows = conn.execute(
            f"""
            SELECT card_name,
                   COUNT(DISTINCT placement_id) AS decks_with,
                   SUM(count) AS total_copies
            FROM decklist_cards
            WHERE placement_id IN ({placeholders})
            GROUP BY card_name
            ORDER BY decks_with DESC
            """,
            placement_ids,
        ).fetchall()

        core_cards = []
        all_cards = []
        for row in rows:
            inclusion = round(row["decks_with"] / total_decks * 100, 1)
            avg_copies = round(row["total_copies"] / row["decks_with"], 1)
            card_data = {
                "card_name": row["card_name"],
                "inclusion_pct": inclusion,
                "avg_copies": avg_copies,
                "decks_with": row["decks_with"],
            }
            all_cards.append(card_data)
            if inclusion >= 80:
                core_cards.append(card_data)

        arch_data = {
            "archetype": archetype_name,
            "slug": slug,
            "tier": arch["tier"],
            "meta_share": round(arch["meta_share"], 1),
            "deck_count": arch["deck_count"],
            "best_placement": arch["best_placement"],
            "core_cards": core_cards,
            "all_cards": all_cards,
        }

        _write_json(arch_data, arch_dir / f"{slug}.json")


def export_champions_league(conn: sqlite3.Connection, output_dir: Path) -> None:
    """Export Champions League data by division."""
    cl_dir = output_dir / "champions-league"
    cl_dir.mkdir(parents=True, exist_ok=True)

    events = conn.execute(
        "SELECT DISTINCT id, name, division, date FROM cl_events ORDER BY division"
    ).fetchall()

    if not events:
        logger.warning("No Champions League events found")
        return

    for event in events:
        division = event["division"]

        # Get placements (deduplicated)
        placements = conn.execute(
            """
            SELECT DISTINCT standing, player_name, region, deck_code
            FROM cl_placements
            WHERE event_id = ?
            ORDER BY standing
            """,
            (event["id"],),
        ).fetchall()

        placement_list = []
        for p in placements:
            # Get decklist for this placement
            decklist_rows = conn.execute(
                """
                SELECT DISTINCT c.card_name_jp, c.card_name_en, c.count, c.category
                FROM cl_placements cp
                JOIN cl_decklist_cards c ON c.placement_id = cp.id
                WHERE cp.event_id = ? AND cp.standing = ? AND cp.player_name = ?
                ORDER BY c.category, c.card_name_jp
                """,
                (event["id"], p["standing"], p["player_name"]),
            ).fetchall()

            decklist = []
            for card in decklist_rows:
                decklist.append({
                    "card_name_jp": card["card_name_jp"],
                    "card_name_en": card["card_name_en"],
                    "count": card["count"],
                    "category": card["category"],
                })

            placement_list.append({
                "standing": p["standing"],
                "player_name": p["player_name"],
                "region": p["region"],
                "deck_code": p["deck_code"],
                "decklist": decklist,
            })

        division_data = {
            "event_id": event["id"],
            "event_name": event["name"],
            "division": division,
            "date": event["date"],
            "placements": placement_list,
        }

        _write_json(division_data, cl_dir / f"{division}.json")


def export_all(conn: sqlite3.Connection, output_dir: Path | None = None) -> Path:
    """Run all exports. Returns the output directory."""
    out = output_dir or DEFAULT_OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    logger.info("Exporting web data to %s", out)

    export_meta(conn, out)
    export_buylist(conn, out)
    export_staples(conn, out)
    export_flex(conn, out)
    export_trends(conn, out)
    export_winning_edge(conn, out)
    export_ace_specs(conn, out)
    export_archetypes(conn, out)
    export_champions_league(conn, out)

    logger.info("Export complete")
    return out
