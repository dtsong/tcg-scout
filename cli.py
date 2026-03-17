"""CLI entry point for Rotation Scout."""

import logging
import sys

import click
from rich.console import Console
from rich.table import Table

from config import DATASET_START, DATASET_END
from db import get_connection, init_db, reset_db

console = Console()
logger = logging.getLogger("scout")


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool) -> None:
    """Rotation Scout — JP meta intelligence for Pokemon TCG."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


@cli.command()
@click.option("--reset", is_flag=True, help="Drop and recreate the database")
def init(reset: bool) -> None:
    """Initialize the database."""
    if reset:
        reset_db()
        console.print("[green]Database reset and recreated.[/green]")
    else:
        conn = get_connection()
        init_db(conn)
        conn.close()
        console.print("[green]Database initialized.[/green]")


@cli.command()
def cards() -> None:
    """Fetch card data from TCGdex and flag rotation-legal cards."""
    from scraper.tcgdex import TCGdexClient

    conn = get_connection()
    init_db(conn)

    client = TCGdexClient()
    try:
        count = client.populate_cards_table(conn)
        console.print(f"[green]Loaded {count} rotation-legal cards into database.[/green]")
    finally:
        conn.close()


@cli.command()
@click.option("--start", default=DATASET_START, help="Start date (YYYY-MM-DD)")
@click.option("--end", default=DATASET_END, help="End date (YYYY-MM-DD)")
@click.option("--max-placements", default=32, help="Max placements per tournament")
@click.option("--fetch-decklists/--no-decklists", default=True, help="Fetch decklists")
def scrape(start: str, end: str, max_placements: int, fetch_decklists: bool) -> None:
    """Scrape JP City League results from LimitlessTCG."""
    from scraper.limitless import LimitlessClient

    conn = get_connection()
    init_db(conn)

    client = LimitlessClient()
    try:
        # Fetch tournament listings
        console.print(f"[cyan]Fetching JP City League listings ({start} to {end})...[/cyan]")
        tournaments = client.fetch_jp_city_league_listings(start, end)
        console.print(f"Found [bold]{len(tournaments)}[/bold] tournaments")

        if not tournaments:
            console.print("[yellow]No tournaments found in date range.[/yellow]")
            return

        # Check which tournaments are already in DB
        existing = set()
        for row in conn.execute("SELECT id FROM tournaments"):
            existing.add(row["id"])

        new_tournaments = [t for t in tournaments if t.source_url not in existing]
        console.print(
            f"[cyan]{len(new_tournaments)} new tournaments to process "
            f"({len(existing)} already in DB)[/cyan]"
        )

        total_placements = 0
        total_decklists = 0

        for i, tournament in enumerate(new_tournaments, 1):
            console.print(
                f"  [{i}/{len(new_tournaments)}] {tournament.name} "
                f"({tournament.tournament_date})"
            )

            # Fetch placements
            placements = client.fetch_jp_city_league_placements(
                tournament.source_url, max_placements
            )

            if not placements:
                console.print("    [yellow]No placements found, skipping[/yellow]")
                continue

            # Store tournament
            conn.execute(
                "INSERT OR REPLACE INTO tournaments (id, name, date, player_count, country) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    tournament.source_url,
                    tournament.name,
                    tournament.tournament_date.isoformat(),
                    tournament.player_count,
                    "JP",
                ),
            )

            # Store placements and decklists
            for placement in placements:
                cursor = conn.execute(
                    "INSERT INTO placements (tournament_id, standing, player_name, archetype) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        tournament.source_url,
                        placement.placement,
                        placement.player_name,
                        placement.archetype,
                    ),
                )
                placement_id = cursor.lastrowid

                # Fetch and store decklist if available
                if fetch_decklists and placement.decklist_url:
                    decklist = client.fetch_decklist(placement.decklist_url)
                    if decklist and decklist.cards:
                        for card in decklist.cards:
                            conn.execute(
                                "INSERT OR REPLACE INTO decklist_cards "
                                "(placement_id, card_id, card_name, count) "
                                "VALUES (?, ?, ?, ?)",
                                (
                                    placement_id,
                                    card.get("card_id", card.get("name", "unknown")),
                                    card.get("name"),
                                    card.get("count", 1),
                                ),
                            )
                        total_decklists += 1

                total_placements += 1

            conn.commit()

        console.print(
            f"\n[green]Done! Stored {total_placements} placements "
            f"and {total_decklists} decklists.[/green]"
        )
    finally:
        client.close()
        conn.close()


@cli.command()
def meta() -> None:
    """Compute meta snapshot from scraped data."""
    from analysis.meta import compute_meta_snapshot, get_latest_snapshot

    conn = get_connection()
    try:
        snapshot_id = compute_meta_snapshot(conn)
        snapshot = get_latest_snapshot(conn)

        if not snapshot:
            console.print("[yellow]No data to compute meta from.[/yellow]")
            return

        console.print(
            f"\n[green]Meta snapshot #{snapshot_id} created[/green] — "
            f"{snapshot['tournament_count']} tournaments, "
            f"{snapshot['deck_count']} decks"
        )

        # Display tier table
        table = Table(title="Archetype Tiers")
        table.add_column("Tier", style="bold")
        table.add_column("Archetype")
        table.add_column("Meta Share", justify="right")
        table.add_column("Decks", justify="right")
        table.add_column("Best", justify="right")

        tier_styles = {"S": "red", "A": "yellow", "B": "cyan", "C": "white", "Rogue": "dim"}

        for arch in snapshot["archetypes"]:
            style = tier_styles.get(arch["tier"], "white")
            table.add_row(
                arch["tier"],
                arch["archetype"],
                f"{arch['meta_share']:.1f}%",
                str(arch["deck_count"]),
                str(arch["best_placement"]) if arch["best_placement"] else "-",
                style=style,
            )

        console.print(table)
    finally:
        conn.close()


@cli.command()
def buylist() -> None:
    """Generate prioritized buy list from meta data."""
    from analysis.buylist import generate_buylist
    from analysis.meta import get_latest_snapshot

    conn = get_connection()
    try:
        snapshot = get_latest_snapshot(conn)
        if not snapshot:
            console.print("[yellow]No meta snapshot found. Run 'scout meta' first.[/yellow]")
            return

        cards = generate_buylist(conn, snapshot["id"])
        if not cards:
            console.print("[yellow]No buy list items generated.[/yellow]")
            return

        console.print(f"\n[green]Buy list: {len(cards)} cards[/green]")

        # Display top cards
        table = Table(title=f"Top Buy List Cards (showing top 30)")
        table.add_column("Card", style="bold")
        table.add_column("Set")
        table.add_column("Priority", justify="right")
        table.add_column("Urgency")
        table.add_column("Type")
        table.add_column("Avg Copies", justify="right")
        table.add_column("Archetypes")

        urgency_styles = {"URGENT": "red bold", "HIGH": "yellow", "MODERATE": "cyan"}

        for card in cards[:30]:
            style = urgency_styles.get(card["urgency"], "white")
            archetypes_str = ", ".join(card["archetypes"][:3])
            if len(card["archetypes"]) > 3:
                archetypes_str += f" +{len(card['archetypes']) - 3}"
            table.add_row(
                card["card_name"],
                f"{card.get('set_code', '?')}-{card.get('set_number', '?')}",
                f"{card['priority_score']:.1f}",
                card["urgency"],
                card["core_flex"],
                f"{card['avg_copies']:.1f}",
                archetypes_str,
                style=style,
            )

        console.print(table)
    finally:
        conn.close()


@cli.command()
def report() -> None:
    """Generate Markdown meta report and CSV buy list."""
    from analysis.buylist import generate_buylist
    from analysis.meta import get_latest_snapshot
    from reports.csv_export import export_buylist_csv
    from reports.markdown import render_meta_report

    conn = get_connection()
    try:
        snapshot = get_latest_snapshot(conn)
        if not snapshot:
            console.print("[yellow]No meta snapshot found. Run 'scout meta' first.[/yellow]")
            return

        # Generate meta report
        md_path = render_meta_report(conn, snapshot["id"])
        console.print(f"[green]Meta report written to {md_path}[/green]")

        # Generate buy list CSV
        cards = generate_buylist(conn, snapshot["id"])
        if cards:
            csv_path = export_buylist_csv(cards)
            console.print(f"[green]Buy list CSV written to {csv_path}[/green]")
        else:
            console.print("[yellow]No buy list items to export.[/yellow]")
    finally:
        conn.close()


if __name__ == "__main__":
    cli()
