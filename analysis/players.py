"""Player intelligence: performance tracking, consistency scoring, deck timelines."""

import logging
import sqlite3
from dataclasses import dataclass

from config import PLACEMENT_WEIGHT_DEFAULT, PLACEMENT_WEIGHTS

logger = logging.getLogger(__name__)


@dataclass
class TopPerformer:
    """A player name appearing frequently in top placements."""

    player_name: str
    tournament_count: int
    best_placement: int
    weighted_score: float
    archetypes: list[str]


@dataclass
class PlacementRecord:
    """A single placement linked to a player via the bridge table."""

    standing: int
    archetype: str
    player_name: str
    tournament_name: str
    date: str
    confidence: float


@dataclass
class DeckTimelineEntry:
    """A single entry in a player's deck timeline."""

    date: str
    archetype: str
    standing: int


@dataclass
class PlayerProfile:
    """Full profile for a curated player identity."""

    player_id: int
    display_name: str
    country: str
    notes: str | None
    twitter_handle: str | None
    youtube_url: str | None
    blog_url: str | None
    aliases: list[str]
    placements: list[PlacementRecord]
    tournament_count: int
    weighted_score: float
    deck_timeline: list[DeckTimelineEntry]


def _placement_weight(standing: int) -> float:
    """Get the weight for a given standing."""
    return PLACEMENT_WEIGHTS.get(standing, PLACEMENT_WEIGHT_DEFAULT)


def list_top_performers(
    conn: sqlite3.Connection,
    *,
    min_appearances: int = 2,
    limit: int = 50,
) -> list[TopPerformer]:
    """Find players who appear most frequently in open-division top placements.

    Uses raw player_name from placements (no identity resolution).
    Returns players sorted by weighted score descending.
    """
    rows = conn.execute(
        """
        SELECT
            p.player_name,
            p.standing,
            p.archetype,
            t.date
        FROM open_placements p
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE p.player_name IS NOT NULL
          AND p.player_name != ''
        ORDER BY p.player_name, t.date
        """
    ).fetchall()

    if not rows:
        return []

    # Aggregate by player_name, dedup tournaments by date
    aggregated: dict[str, dict] = {}
    for row in rows:
        name = row["player_name"]
        if name not in aggregated:
            aggregated[name] = {
                "dates": set(),
                "best": row["standing"],
                "score": 0.0,
                "archetypes": [],
            }
        entry = aggregated[name]
        entry["dates"].add(str(row["date"]))
        entry["best"] = min(entry["best"], row["standing"])
        entry["score"] += _placement_weight(row["standing"])
        if row["archetype"] not in entry["archetypes"]:
            entry["archetypes"].append(row["archetype"])

    results = []
    for name, data in aggregated.items():
        count = len(data["dates"])
        if count < min_appearances:
            continue
        results.append(
            TopPerformer(
                player_name=name,
                tournament_count=count,
                best_placement=data["best"],
                weighted_score=round(data["score"], 2),
                archetypes=data["archetypes"],
            )
        )

    results.sort(key=lambda p: p.weighted_score, reverse=True)
    return results[:limit]


def get_player_profile(conn: sqlite3.Connection, player_id: int) -> PlayerProfile | None:
    """Build a full profile for a curated player identity."""
    player = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
    if not player:
        return None

    aliases = [
        row["alias"]
        for row in conn.execute(
            "SELECT alias FROM player_aliases WHERE player_id = ?", (player_id,)
        ).fetchall()
    ]

    # Get linked placements via bridge table
    placements = conn.execute(
        """
        SELECT
            p.standing,
            p.archetype,
            p.player_name,
            t.name AS tournament_name,
            t.date,
            pp.confidence
        FROM placement_players pp
        JOIN placements p ON p.id = pp.placement_id
        JOIN tournaments t ON t.id = p.tournament_id
        WHERE pp.player_id = ?
        ORDER BY t.date DESC
        """,
        (player_id,),
    ).fetchall()

    placement_list = [
        PlacementRecord(
            standing=row["standing"],
            archetype=row["archetype"],
            player_name=row["player_name"],
            tournament_name=row["tournament_name"],
            date=row["date"],
            confidence=row["confidence"],
        )
        for row in placements
    ]
    tournament_dates = {p.date for p in placement_list}
    weighted_score = sum(_placement_weight(p.standing) for p in placement_list)

    deck_timeline = [
        DeckTimelineEntry(date=p.date, archetype=p.archetype, standing=p.standing)
        for p in placement_list
    ]

    return PlayerProfile(
        player_id=player["id"],
        display_name=player["display_name"],
        country=player["country"] or "JP",
        notes=player["notes"],
        twitter_handle=player["twitter_handle"],
        youtube_url=player["youtube_url"],
        blog_url=player["blog_url"],
        aliases=aliases,
        placements=placement_list,
        tournament_count=len(tournament_dates),
        weighted_score=round(weighted_score, 2),
        deck_timeline=deck_timeline,
    )


def create_player(
    conn: sqlite3.Connection,
    display_name: str,
    *,
    country: str = "JP",
    notes: str | None = None,
) -> int:
    """Create a new player identity. Returns the player ID."""
    cursor = conn.execute(
        "INSERT INTO players (display_name, country, notes) VALUES (?, ?, ?)",
        (display_name, country, notes),
    )
    conn.commit()
    return cursor.lastrowid


def link_alias(
    conn: sqlite3.Connection,
    alias: str,
    player_id: int,
    *,
    source: str = "limitless",
) -> None:
    """Link a raw player name (alias) to a player identity."""
    conn.execute(
        "INSERT OR REPLACE INTO player_aliases (alias, player_id, source) VALUES (?, ?, ?)",
        (alias, player_id, source),
    )
    conn.commit()


def link_placements_by_alias(
    conn: sqlite3.Connection,
    player_id: int,
    alias: str,
    *,
    confidence: float = 1.0,
) -> int:
    """Link all placements matching a player_name alias to a player identity.

    Returns the number of placements linked.
    """
    placement_ids = conn.execute(
        "SELECT id FROM placements WHERE player_name = ?", (alias,)
    ).fetchall()

    linked = 0
    for row in placement_ids:
        conn.execute(
            "INSERT OR REPLACE INTO placement_players (placement_id, player_id, confidence) "
            "VALUES (?, ?, ?)",
            (row["id"], player_id, confidence),
        )
        linked += 1

    conn.commit()
    return linked
