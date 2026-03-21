"""CLI entry point for Rotation Scout."""

import logging

import click
from rich.console import Console
from rich.table import Table

from config import DEFAULT_FORMAT, FORMATS, get_format_config
from db import get_format_connection, init_db, reset_db

console = Console()
logger = logging.getLogger("scout")


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option(
    "--format",
    "format_slug",
    default=DEFAULT_FORMAT,
    type=click.Choice(list(FORMATS.keys())),
    help="Format to operate on",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, format_slug: str) -> None:
    """Rotation Scout — JP meta intelligence for Pokemon TCG."""
    ctx.ensure_object(dict)
    ctx.obj["format"] = format_slug
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


@cli.command()
@click.option("--reset", is_flag=True, help="Drop and recreate the database")
@click.pass_context
def init(ctx: click.Context, reset: bool) -> None:
    """Initialize the database."""
    fmt = ctx.obj["format"]
    if reset:
        reset_db(fmt)
        console.print(f"[green]Database reset and recreated for {fmt}.[/green]")
    else:
        conn = get_format_connection(fmt)
        init_db(conn)
        conn.close()
        console.print(f"[green]Database initialized for {fmt}.[/green]")


@cli.command()
@click.pass_context
def cards(ctx: click.Context) -> None:
    """Fetch card data from TCGdex and flag rotation-legal cards."""
    from scraper.tcgdex import TCGdexClient

    conn = get_format_connection(ctx.obj["format"])
    init_db(conn)

    client = TCGdexClient()
    try:
        count = client.populate_cards_table(conn)
        console.print(f"[green]Loaded {count} rotation-legal cards into database.[/green]")
    finally:
        conn.close()


@cli.command()
@click.option("--start", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--end", default=None, help="End date (YYYY-MM-DD)")
@click.option("--max-placements", default=32, help="Max placements per tournament")
@click.option("--fetch-decklists/--no-decklists", default=True, help="Fetch decklists")
@click.pass_context
def scrape(
    ctx: click.Context,
    start: str | None,
    end: str | None,
    max_placements: int,
    fetch_decklists: bool,
) -> None:
    """Scrape JP City League results from LimitlessTCG."""
    from scraper.limitless import LimitlessClient

    fmt = get_format_config(ctx.obj["format"])
    start = start or fmt["dataset_start"]
    end = end or fmt["dataset_end"]

    conn = get_format_connection(ctx.obj["format"])
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
                f"  [{i}/{len(new_tournaments)}] {tournament.name} ({tournament.tournament_date})"
            )

            # Fetch placements
            placements = client.fetch_jp_city_league_placements(
                tournament.source_url, max_placements
            )

            if not placements:
                console.print("    [yellow]No placements found, skipping[/yellow]")
                continue

            # Store tournament (Limitless only tracks open division)
            conn.execute(
                "INSERT OR REPLACE INTO tournaments (id, name, date, player_count, country, division) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    tournament.source_url,
                    tournament.name,
                    tournament.tournament_date.isoformat(),
                    tournament.player_count,
                    "JP",
                    "open",
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
@click.pass_context
def meta(ctx: click.Context) -> None:
    """Compute meta snapshot from scraped data."""
    from analysis.meta import compute_meta_snapshot, get_latest_snapshot

    conn = get_format_connection(ctx.obj["format"])
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
@click.pass_context
def buylist(ctx: click.Context) -> None:
    """Generate prioritized buy list from meta data."""
    from analysis.buylist import generate_buylist
    from analysis.meta import get_latest_snapshot

    conn = get_format_connection(ctx.obj["format"])
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
        table = Table(title="Top Buy List Cards (showing top 30)")
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
@click.pass_context
def report(ctx: click.Context) -> None:
    """Generate Markdown meta report and CSV buy list."""
    from analysis.buylist import generate_buylist
    from analysis.meta import get_latest_snapshot
    from reports.csv_export import export_buylist_csv
    from reports.markdown import render_meta_report

    conn = get_format_connection(ctx.obj["format"])
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


@cli.command()
@click.argument("event_ids", nargs=-1, type=int, required=True)
@click.option("--fetch-decklists/--no-decklists", default=True, help="Fetch decklists")
@click.option("--top", default=16, help="Max placements to fetch decklists for")
@click.pass_context
def champions(
    ctx: click.Context, event_ids: tuple[int, ...], fetch_decklists: bool, top: int
) -> None:
    """Scrape Champions League results from players.pokemon-card.com.

    Requires KERNEL_API_KEY in .env for cloud browser rendering.
    Pass event IDs as arguments (e.g., scout champions 903701 903702 903703).
    """
    import asyncio

    from dotenv import load_dotenv

    load_dotenv()

    from scraper.pokemon_jp import PokemonJPClient, store_event_results

    conn = get_format_connection(ctx.obj["format"])
    init_db(conn)

    try:
        client = PokemonJPClient()

        for event_id in event_ids:
            console.print(f"\n[cyan]Scraping event {event_id}...[/cyan]")

            # Fetch event results
            event = asyncio.run(client.fetch_event_results(event_id))
            console.print(
                f"  [bold]{event.event_name}[/bold] ({event.division}) — "
                f"{len(event.placements)} placements"
            )

            # Fetch decklists for top placements
            decklists: dict[str, list] = {}
            if fetch_decklists:
                decks_to_fetch = [p for p in event.placements if p.deck_url and p.standing <= top]
                console.print(f"  Fetching {len(decks_to_fetch)} decklists...")

                for i, placement in enumerate(decks_to_fetch, 1):
                    console.print(
                        f"    [{i}/{len(decks_to_fetch)}] "
                        f"#{placement.standing} {placement.player_name}"
                    )
                    try:
                        cards = asyncio.run(client.fetch_decklist(placement.deck_url))
                        if cards and placement.deck_code:
                            decklists[placement.deck_code] = cards
                            console.print(f"      {len(cards)} cards")
                    except Exception as e:
                        console.print(f"      [red]Error: {e}[/red]")

            # Store in database
            store_event_results(conn, event, decklists)
            console.print(
                f"  [green]Stored {len(event.placements)} placements, "
                f"{len(decklists)} decklists[/green]"
            )

    finally:
        conn.close()


@cli.command()
@click.option("--sets", help="Comma-separated JP set codes to sync (e.g., SV7,SV8a)")
@click.pass_context
def mappings(ctx: click.Context, sets: str | None) -> None:
    """Sync JP-to-EN card ID mappings from Limitless."""
    from scraper.card_mappings import sync_card_mappings

    conn = get_format_connection(ctx.obj["format"])
    init_db(conn)

    set_codes = [s.strip() for s in sets.split(",")] if sets else None

    try:
        count = sync_card_mappings(conn, set_codes=set_codes)
        console.print(f"[green]Synced {count} new card mappings[/green]")
    finally:
        conn.close()


@cli.command()
@click.pass_context
def translate(ctx: click.Context) -> None:
    """Translate JP card names in CL decklists using card mappings."""
    from scraper.pokemon_jp import translate_cl_decklists

    conn = get_format_connection(ctx.obj["format"])
    init_db(conn)

    try:
        count = translate_cl_decklists(conn)
        console.print(f"[green]Translated {count} cards[/green]")
    finally:
        conn.close()


@cli.command("import-cl")
@click.option("--dir", "data_dir", default="data/fukuoka-cl", help="Directory with CL CSV files")
@click.pass_context
def import_cl(ctx: click.Context, data_dir: str) -> None:
    """Import Champions League data from CSV files into SQLite."""
    import csv
    import json
    from pathlib import Path

    data_path = Path(data_dir)
    if not data_path.exists():
        console.print(f"[red]Directory {data_dir} not found[/red]")
        return

    conn = get_format_connection(ctx.obj["format"])
    init_db(conn)

    try:
        divisions = ["juniors", "seniors", "masters"]
        total_placements = 0
        total_cards = 0

        for division in divisions:
            meta_file = data_path / f"{division}-meta.json"
            placements_file = data_path / f"{division}-placements.csv"
            decklists_file = data_path / f"{division}-decklists.csv"

            if not meta_file.exists():
                console.print(f"[yellow]Skipping {division} — no meta file[/yellow]")
                continue

            with open(meta_file) as f:
                meta = json.load(f)

            console.print(f"[cyan]Importing {division}: {meta['event_name']}[/cyan]")

            # Store event
            conn.execute(
                "INSERT OR REPLACE INTO cl_events (id, name, division, date) VALUES (?, ?, ?, ?)",
                (meta["event_id"], meta["event_name"], meta["division"], meta["date"]),
            )

            # Store placements
            placement_id_map: dict[tuple[int, str], int] = {}
            with open(placements_file, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cursor = conn.execute(
                        "INSERT INTO cl_placements (event_id, standing, player_name, region, deck_code, deck_url) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            meta["event_id"],
                            int(row["standing"]),
                            row["player_name"],
                            row["region"],
                            row["deck_code"],
                            row["deck_url"],
                        ),
                    )
                    key = (int(row["standing"]), row["player_name"])
                    placement_id_map[key] = cursor.lastrowid
                    total_placements += 1

            # Store decklists
            with open(decklists_file, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = (int(row["standing"]), row["player_name"])
                    pid = placement_id_map.get(key)
                    if not pid:
                        continue
                    conn.execute(
                        "INSERT OR REPLACE INTO cl_decklist_cards "
                        "(placement_id, card_name_jp, set_code, count, category) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            pid,
                            row["card_name_jp"],
                            row["set_code"],
                            int(row["count"]),
                            row["category"],
                        ),
                    )
                    total_cards += 1

            conn.commit()

        console.print(
            f"\n[green]Imported {total_placements} placements, {total_cards} decklist cards[/green]"
        )
    finally:
        conn.close()


@cli.command("scrape-jp")
@click.option("--start", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--end", default=None, help="End date (YYYY-MM-DD)")
@click.option(
    "--fetch-decklists/--no-decklists", default=True, help="Fetch decklists via Playwright"
)
@click.option("--top", default=64, help="Max placements to fetch decklists for")
@click.pass_context
def scrape_jp(
    ctx: click.Context, start: str | None, end: str | None, fetch_decklists: bool, top: int
) -> None:
    """Scrape JP City League results from players.pokemon-card.com API.

    Uses plain HTTP for event listings and results (no browser required).
    Pass --fetch-decklists to also fetch decklists via Playwright (requires KERNEL_API_KEY).
    """
    import asyncio

    from scraper.pokemon_jp import JPEventResult, JPPlacement, store_cl_city_league_results
    from scraper.pokemon_jp_api import PokemonJPAPIClient

    fmt = get_format_config(ctx.obj["format"])
    start = start or fmt["dataset_start"]
    end = end or fmt["dataset_end"]

    conn = get_format_connection(ctx.obj["format"])
    init_db(conn)

    api_client = PokemonJPAPIClient()
    jp_client = None

    try:
        # Fetch event listings via plain HTTP
        console.print(f"[cyan]Fetching JP City League events ({start} to {end})...[/cyan]")
        events = api_client.fetch_cl_events(start, end)
        console.print(f"Found [bold]{len(events)}[/bold] events")

        if not events:
            console.print("[yellow]No events found in date range.[/yellow]")
            return

        # Check which tournaments are already in DB
        existing = {row["id"] for row in conn.execute("SELECT id FROM tournaments")}
        new_events = [e for e in events if f"jp-{e.event_id}" not in existing]
        console.print(
            f"[cyan]{len(new_events)} new events to process ({len(existing)} already in DB)[/cyan]"
        )

        if fetch_decklists:
            from dotenv import load_dotenv

            load_dotenv()
            from scraper.pokemon_jp import PokemonJPClient

            jp_client = PokemonJPClient()

        total_placements = 0
        total_decklists = 0

        for i, event in enumerate(new_events, 1):
            event_name = (
                f"{event.prefecture} {event.store_name}".strip() or f"City League {event.date}"
            )
            console.print(f"  [{i}/{len(new_events)}] {event_name} ({event.date})")

            # Fetch placements via plain HTTP API
            results = api_client.fetch_event_results(event.event_id)

            if not results:
                console.print("    [yellow]No results found, skipping[/yellow]")
                continue

            # Build JPPlacement list from API results
            deck_url_base = "https://players.pokemon-card.com/deck/confirm.html/deckID/"
            placements = [
                JPPlacement(
                    standing=r.rank,
                    player_name=r.player_name,
                    region=r.area,
                    deck_url=(deck_url_base + r.deck_id) if r.deck_id else None,
                    deck_code=r.deck_id,
                )
                for r in results
            ]

            jp_event = JPEventResult(
                event_id=event.event_id,
                event_name=event_name,
                division=event.division,
                date=event.date,
                placements=placements,
            )

            # Fetch decklists for top placements if requested
            decklists: dict[str, list] = {}
            if fetch_decklists and jp_client:
                decks_to_fetch = [p for p in placements if p.deck_url and p.standing <= top]
                console.print(f"    Fetching {len(decks_to_fetch)} decklists...")
                for j, placement in enumerate(decks_to_fetch, 1):
                    console.print(
                        f"      [{j}/{len(decks_to_fetch)}] "
                        f"#{placement.standing} {placement.player_name}"
                    )
                    try:
                        cards = asyncio.run(jp_client.fetch_decklist(placement.deck_url))
                        if cards and placement.deck_code:
                            decklists[placement.deck_code] = cards
                            total_decklists += 1
                            console.print(f"        {len(cards)} cards")
                    except Exception as e:
                        console.print(f"        [red]Error: {e}[/red]")

            store_cl_city_league_results(conn, jp_event, decklists)
            total_placements += len(placements)
            console.print(
                f"    [green]Stored {len(placements)} placements"
                + (f", {len(decklists)} decklists" if decklists else "")
                + "[/green]"
            )

        console.print(
            f"\n[green]Done! Stored {total_placements} placements "
            f"and {total_decklists} decklists.[/green]"
        )
    finally:
        api_client.close()
        if jp_client is not None:
            pass  # PokemonJPClient has no explicit close
        conn.close()


@cli.command("scrape-tournament")
@click.argument("tournament_id", type=int)
@click.option("--name", default=None, help="Tournament name (default: auto-detected)")
@click.option("--date", default=None, help="Tournament date YYYY-MM-DD (required)")
@click.option("--max-placements", default=64, help="Max placements to scrape")
@click.option("--fetch-decklists/--no-decklists", default=True, help="Fetch decklists")
@click.option(
    "--tournament-type",
    default="champions-league",
    type=click.Choice(["city-league", "champions-league"]),
    help="Tournament type tag",
)
@click.option("--player-count", default=0, help="Player count (for metadata)")
@click.pass_context
def scrape_tournament(
    ctx: click.Context,
    tournament_id: int,
    name: str | None,
    date: str | None,
    max_placements: int,
    fetch_decklists: bool,
    tournament_type: str,
    player_count: int,
) -> None:
    """Scrape a single Limitless tournament by ID.

    Example: scout scrape-tournament 547 --name "Fukuoka CL 2026" --date 2026-03-20 --player-count 7000
    """
    if not date:
        console.print("[red]--date is required (e.g. --date 2026-03-20)[/red]")
        return
    from scraper.limitless import LimitlessClient

    fmt = ctx.obj["format"]
    conn = get_format_connection(fmt)
    init_db(conn)

    tournament_url = f"https://limitlesstcg.com/tournaments/{tournament_id}"
    tournament_name = name or f"Limitless Tournament {tournament_id}"

    client = LimitlessClient()
    try:
        # Check if already scraped
        existing = conn.execute(
            "SELECT id FROM tournaments WHERE id = ?", (tournament_url,)
        ).fetchone()
        if existing:
            console.print(f"[yellow]Tournament {tournament_id} already in database.[/yellow]")
            return

        console.print(f"[cyan]Scraping {tournament_url}...[/cyan]")
        placements = client.fetch_jp_city_league_placements(tournament_url, max_placements)

        if not placements:
            console.print("[yellow]No placements found.[/yellow]")
            return

        console.print(f"Found [bold]{len(placements)}[/bold] placements")

        # Store tournament
        conn.execute(
            "INSERT OR REPLACE INTO tournaments "
            "(id, name, date, player_count, country, division, tournament_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                tournament_url,
                tournament_name,
                date,
                player_count,
                "JP",
                "open",
                tournament_type,
            ),
        )

        total_decklists = 0
        for i, placement in enumerate(placements, 1):
            console.print(
                f"  [{i}/{len(placements)}] #{placement.placement} "
                f"{placement.player_name or 'Unknown'} — {placement.archetype}"
            )

            cursor = conn.execute(
                "INSERT INTO placements (tournament_id, standing, player_name, archetype) "
                "VALUES (?, ?, ?, ?)",
                (tournament_url, placement.placement, placement.player_name, placement.archetype),
            )
            placement_id = cursor.lastrowid

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
                    console.print(f"    {len(decklist.cards)} cards")

        conn.commit()
        console.print(
            f"\n[green]Done! Stored {len(placements)} placements "
            f"and {total_decklists} decklists for {tournament_name}.[/green]"
        )
    finally:
        client.close()
        conn.close()


@cli.command("backfill-archetypes")
@click.option("--start", default=None, help="Override start date (YYYY-MM-DD)")
@click.option("--end", default=None, help="Override end date (YYYY-MM-DD)")
@click.option("--max-placements", default=32, help="Max placements per Limitless tournament")
@click.pass_context
def backfill_archetypes(
    ctx: click.Context, start: str | None, end: str | None, max_placements: int
) -> None:
    """Backfill Unknown archetypes using Limitless tournament data.

    Queries placements with archetype='Unknown', fetches matching Limitless
    tournament data for those date ranges, and updates archetypes by
    matching on (date, standing).
    """
    from scraper.limitless import LimitlessClient

    conn = get_format_connection(ctx.obj["format"])
    init_db(conn)

    try:
        # Find date range of Unknown placements
        rows = conn.execute(
            "SELECT p.id, p.standing, p.player_name, t.date "
            "FROM open_placements p "
            "JOIN tournaments t ON p.tournament_id = t.id "
            "WHERE p.archetype = 'Unknown' "
            "ORDER BY t.date"
        ).fetchall()

        if not rows:
            console.print("[yellow]No Unknown placements found.[/yellow]")
            return

        console.print(f"Found [bold]{len(rows)}[/bold] placements with archetype='Unknown'")

        # Determine date range
        dates = [r["date"] for r in rows]
        range_start = start or min(dates)
        range_end = end or max(dates)

        console.print(f"[cyan]Fetching Limitless listings ({range_start} to {range_end})...[/cyan]")

        client = LimitlessClient()
        tournaments = client.fetch_jp_city_league_listings(range_start, range_end)
        console.print(f"Found [bold]{len(tournaments)}[/bold] Limitless tournaments")

        if not tournaments:
            console.print("[yellow]No Limitless tournaments found for that range.[/yellow]")
            return

        # Build lookup: (date_str, standing) -> archetype
        archetype_lookup: dict[tuple[str, int], str] = {}

        for i, tournament in enumerate(tournaments, 1):
            console.print(
                f"  [{i}/{len(tournaments)}] {tournament.name} ({tournament.tournament_date})"
            )
            placements = client.fetch_jp_city_league_placements(
                tournament.source_url, max_placements
            )
            date_str = tournament.tournament_date.isoformat()
            for p in placements:
                key = (date_str, p.placement)
                archetype_lookup[key] = p.archetype

        console.print(f"Built lookup with [bold]{len(archetype_lookup)}[/bold] entries")

        # Update placements in DB
        updated = 0
        for row in rows:
            key = (row["date"], row["standing"])
            archetype = archetype_lookup.get(key)
            if archetype and archetype != "Unknown":
                conn.execute(
                    "UPDATE placements SET archetype = ? WHERE id = ?",
                    (archetype, row["id"]),
                )
                updated += 1

        conn.commit()
        console.print(f"\n[green]Updated {updated}/{len(rows)} placements with archetypes.[/green]")
    finally:
        conn.close()


@cli.command("export-web")
@click.option(
    "--narrative",
    is_flag=True,
    help="Also generate LLM narrative report (requires ANTHROPIC_API_KEY)",
)
@click.pass_context
def export_web(ctx: click.Context, narrative: bool) -> None:
    """Export JSON data for the Scout Web dashboard."""
    from reports.json_export import export_all, export_formats, export_narrative

    fmt = ctx.obj["format"]
    conn = get_format_connection(fmt)
    try:
        out = export_all(conn, format_slug=fmt)
        console.print(f"[green]Web data exported to {out}[/green]")
        export_formats()
        console.print("[green]formats.json updated[/green]")
        if narrative:
            result = export_narrative(fmt, out)
            if result:
                console.print(f"[green]Narrative report written to {result}[/green]")
            else:
                console.print("[yellow]Narrative report generation skipped.[/yellow]")
    finally:
        conn.close()


if __name__ == "__main__":
    cli()
