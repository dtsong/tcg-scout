"""CLI entry point for Rotation Scout."""

import logging
import sqlite3

import click
import httpx
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
        failed_tournaments = 0

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

            # Store tournament and placements in a transaction
            # Parse prefecture from tournament name (e.g. "City League Osaka" -> "Osaka")
            prefecture = None
            if "City League " in tournament.name:
                prefecture = tournament.name.split("City League ", 1)[1].strip() or None

            try:
                conn.execute(
                    "INSERT OR REPLACE INTO tournaments (id, name, date, player_count, country, division, prefecture) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        tournament.source_url,
                        tournament.name,
                        tournament.tournament_date.isoformat(),
                        tournament.player_count,
                        "JP",
                        "open",
                        prefecture,
                    ),
                )

                # Store placements and decklists
                for placement in placements:
                    cursor = conn.execute(
                        "INSERT INTO placements (tournament_id, standing, player_name, archetype, decklist_url) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            tournament.source_url,
                            placement.placement,
                            placement.player_name,
                            placement.archetype,
                            placement.decklist_url,
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
            except sqlite3.Error:
                logger.exception(
                    "Failed to ingest tournament %s, rolling back", tournament.source_url
                )
                conn.rollback()
                failed_tournaments += 1
                continue

        console.print(
            f"\n[green]Done! Stored {total_placements} placements "
            f"and {total_decklists} decklists.[/green]"
        )
        if failed_tournaments:
            console.print(
                f"[red]Warning: {failed_tournaments} tournament(s) failed to ingest. "
                f"Check logs for details.[/red]"
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
            f"\n[green]Meta snapshot #{snapshot_id} created[/green] - "
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
        table.add_column("Type")
        table.add_column("Avg Copies", justify="right")
        table.add_column("Archetypes")

        for card in cards[:30]:
            archetypes_str = ", ".join(card["archetypes"][:3])
            if len(card["archetypes"]) > 3:
                archetypes_str += f" +{len(card['archetypes']) - 3}"
            table.add_row(
                card["card_name"],
                f"{card.get('set_code', '?')}-{card.get('set_number', '?')}",
                f"{card['priority_score']:.1f}",
                card["core_flex"],
                f"{card['avg_copies']:.1f}",
                archetypes_str,
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
                f"  [bold]{event.event_name}[/bold] ({event.division}) - "
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
                    except (OSError, ValueError, RuntimeError) as e:
                        logger.error(
                            "Failed to fetch decklist for %s: %s",
                            placement.player_name,
                            e,
                            exc_info=True,
                        )
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


@cli.command("translate-cards")
@click.option("--dry-run", is_flag=True, help="Show what would change without updating")
@click.pass_context
def translate_cards(ctx: click.Context, dry_run: bool) -> None:
    """Translate JP card names to English and normalise EN variants in decklist_cards.

    Pass 1: JP->EN via JP_CARD_NAMES + cards table + card_mappings table.
    Pass 2: EN->EN via EN_CARD_ALIASES (fan-translation variants to Limitless canonical).
    Idempotent -- safe to run multiple times.
    """
    from analysis.card_stats import EN_CARD_ALIASES, build_jp_en_lookup
    from reports.json_export import JP_CARD_NAMES

    conn = get_format_connection(ctx.obj["format"])
    init_db(conn)

    try:
        lookup = build_jp_en_lookup(conn, fallback=JP_CARD_NAMES)
        rows = conn.execute("SELECT DISTINCT card_name FROM decklist_cards").fetchall()

        # Pass 1: JP → EN
        jp_updates: list[tuple[str, str]] = []
        for row in rows:
            name = row["card_name"]
            en_name = lookup.get(name)
            if en_name and en_name != name:
                jp_updates.append((en_name, name))

        # Pass 2: EN → EN (variant aliases)
        en_updates: list[tuple[str, str]] = []
        for row in rows:
            name = row["card_name"]
            # Also check post-JP-translation name
            resolved = lookup.get(name, name)
            canonical = EN_CARD_ALIASES.get(resolved)
            if canonical and canonical != resolved:
                en_updates.append((canonical, resolved))
            elif name not in lookup:
                canonical = EN_CARD_ALIASES.get(name)
                if canonical and canonical != name:
                    en_updates.append((canonical, name))

        if dry_run:
            if jp_updates:
                console.print(f"[cyan]Would translate {len(jp_updates)} JP card names:[/cyan]")
                for en, jp in sorted(jp_updates, key=lambda x: x[1]):
                    cnt = conn.execute(
                        "SELECT COUNT(*) FROM decklist_cards WHERE card_name = ?", (jp,)
                    ).fetchone()[0]
                    console.print(f"  {jp} → {en} ({cnt} rows)")
            if en_updates:
                console.print(
                    f"[cyan]Would normalise {len(en_updates)} EN card name variants:[/cyan]"
                )
                for canonical, variant in sorted(en_updates, key=lambda x: x[1]):
                    cnt = conn.execute(
                        "SELECT COUNT(*) FROM decklist_cards WHERE card_name = ?", (variant,)
                    ).fetchone()[0]
                    console.print(f"  {variant} → {canonical} ({cnt} rows)")
            if not jp_updates and not en_updates:
                console.print("[green]All card names are already normalised[/green]")
        else:
            for en, jp in jp_updates:
                conn.execute(
                    "UPDATE decklist_cards SET card_name = ? WHERE card_name = ?",
                    (en, jp),
                )
            for canonical, variant in en_updates:
                conn.execute(
                    "UPDATE decklist_cards SET card_name = ? WHERE card_name = ?",
                    (canonical, variant),
                )
            conn.commit()
            console.print(
                f"[green]Translated {len(jp_updates)} JP names, "
                f"normalised {len(en_updates)} EN variants in decklist_cards[/green]"
            )
    finally:
        conn.close()


@cli.command()
@click.option("--dry-run", is_flag=True, help="Show what would change without updating")
@click.pass_context
def reclassify(ctx: click.Context, dry_run: bool) -> None:
    """Re-classify archetypes using decklist-based classification.

    By default, targets placements with archetype='Unknown'. Use --all to
    reclassify every JP placement that has a decklist (fixes misclassified
    decks from backfill-archetypes).
    """
    _run_reclassify(ctx, dry_run=dry_run, target_all=False)


@cli.command("reclassify-all")
@click.option("--dry-run", is_flag=True, help="Show what would change without modifying the DB")
@click.pass_context
def reclassify_all(ctx: click.Context, dry_run: bool) -> None:
    """Re-classify ALL JP placements with decklists, not just Unknown.

    Useful for fixing misclassified decks (e.g., from backfill-archetypes
    assigning wrong archetypes to standing=9 non-top-cut placements).
    """
    _run_reclassify(ctx, dry_run=dry_run, target_all=True)


def _run_reclassify(ctx: click.Context, *, dry_run: bool, target_all: bool) -> None:
    from analysis.archetype_classifier import classify_decklist
    from analysis.card_stats import classify_card

    conn = get_format_connection(ctx.obj["format"])
    init_db(conn)

    try:
        if target_all:
            # Reclassify all JP placements with decklists
            targets = conn.execute(
                """
                SELECT p.id, p.tournament_id, p.player_name, p.archetype
                FROM placements p
                WHERE p.tournament_id LIKE 'jp-%'
                AND EXISTS (SELECT 1 FROM decklist_cards dc WHERE dc.placement_id = p.id)
                """
            ).fetchall()
            console.print(f"Found {len(targets)} JP placements with decklists")
        else:
            targets = conn.execute(
                """
                SELECT p.id, p.tournament_id, p.player_name, p.archetype
                FROM placements p
                WHERE p.archetype = 'Unknown'
                AND EXISTS (SELECT 1 FROM decklist_cards dc WHERE dc.placement_id = p.id)
                """
            ).fetchall()
            console.print(f"Found {len(targets)} Unknown placements with decklists")

        reclassified = 0
        still_unknown = 0
        unchanged = 0
        failed = 0
        changes: dict[str, int] = {}

        for placement in targets:
            try:
                cards = conn.execute(
                    "SELECT card_name, count FROM decklist_cards WHERE placement_id = ?",
                    (placement["id"],),
                ).fetchall()

                # Card names in decklist_cards are already translated to EN.
                # Classify using the EN card names directly.
                translated: list[dict] = []
                for card in cards:
                    name = card["card_name"]
                    category = classify_card(name)
                    translated.append(
                        {"card_name": name, "count": card["count"], "category": category}
                    )

                archetype = classify_decklist(translated)
                old_archetype = placement["archetype"]

                if archetype == "Unknown":
                    still_unknown += 1
                elif archetype == old_archetype:
                    unchanged += 1
                else:
                    reclassified += 1
                    label = f"{old_archetype} -> {archetype}" if target_all else archetype
                    changes[label] = changes.get(label, 0) + 1
                    if not dry_run:
                        conn.execute(
                            "UPDATE placements SET archetype = ? WHERE id = ?",
                            (archetype, placement["id"]),
                        )
            except (sqlite3.OperationalError, KeyError, ValueError, TypeError) as exc:
                logger.error(
                    "Failed to reclassify placement %s: %s", placement["id"], exc, exc_info=True
                )
                failed += 1

        if not dry_run:
            conn.commit()

        if failed > 0 and len(targets) > 0 and failed / len(targets) > 0.5:
            console.print(
                f"\n[red bold]ERROR: {failed}/{len(targets)} placements failed to reclassify. "
                f"This indicates a systematic issue.[/red bold]"
            )
            raise SystemExit(1)

        prefix = "[bold yellow]DRY RUN:[/bold yellow] " if dry_run else ""
        console.print(f"\n{prefix}[green]Reclassified {reclassified} placements[/green]")
        if unchanged:
            console.print(f"  Unchanged: {unchanged}")
        if still_unknown:
            console.print(f"  Still Unknown: {still_unknown}")
        if failed:
            console.print(f"  [red]{failed} placements failed to reclassify - see logs[/red]")
        for arch, count in sorted(changes.items(), key=lambda x: -x[1]):
            console.print(f"  {arch}: {count}")
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
                console.print(f"[yellow]Skipping {division} - no meta file[/yellow]")
                continue

            with open(meta_file) as f:
                meta = json.load(f)

            console.print(f"[cyan]Importing {division}: {meta['event_name']}[/cyan]")

            # Store event
            conn.execute(
                "INSERT OR REPLACE INTO cl_events (id, name, division, date) VALUES (?, ?, ?, ?)",
                (meta["event_id"], meta["event_name"], meta["division"], meta["date"]),
            )

            # Clear existing data for this event (idempotent re-import)
            conn.execute(
                "DELETE FROM cl_decklist_cards WHERE placement_id IN "
                "(SELECT id FROM cl_placements WHERE event_id = ?)",
                (meta["event_id"],),
            )
            conn.execute(
                "DELETE FROM cl_placements WHERE event_id = ?",
                (meta["event_id"],),
            )

            # Store placements
            # Key by (standing, deck_code, player_name) to avoid collisions:
            # player_name is often empty, deck_code is unique per submission
            placement_id_map: dict[tuple[int, str, str], int] = {}
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
                    key = (int(row["standing"]), row["deck_code"], row["player_name"])
                    placement_id_map[key] = cursor.lastrowid
                    total_placements += 1

            # Store decklists
            with open(decklists_file, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = (int(row["standing"]), row["deck_code"], row["player_name"])
                    pid = placement_id_map.get(key)
                    if pid is None:
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
@click.option(
    "--pool-size", default=5, help="Number of concurrent browser instances for decklist fetching"
)
@click.pass_context
def scrape_jp(
    ctx: click.Context,
    start: str | None,
    end: str | None,
    fetch_decklists: bool,
    top: int,
    pool_size: int,
) -> None:
    """Scrape JP City League results from players.pokemon-card.com API.

    Uses plain HTTP for event listings and results (no browser required).
    Pass --fetch-decklists to also fetch decklists via Playwright (requires KERNEL_API_KEY).
    Uses a pool of concurrent browsers (default 5) for faster decklist fetching.
    """
    import asyncio
    import time

    from scraper.pokemon_jp import JPEventResult, JPPlacement, store_cl_city_league_results
    from scraper.pokemon_jp_api import PokemonJPAPIClient

    fmt = get_format_config(ctx.obj["format"])
    start = start or fmt["dataset_start"]
    end = end or fmt["dataset_end"]

    conn = get_format_connection(ctx.obj["format"])
    init_db(conn)

    api_client = PokemonJPAPIClient()

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

        # Phase 1: Fetch all events and placements via HTTP API (fast)
        console.print("\n[bold cyan]Phase 1:[/bold cyan] Fetching event placements via API...")
        deck_url_base = "https://www.pokemon-card.com/deck/confirm.html/deckID/"
        events_data: list[JPEventResult] = []
        all_deck_entries: list[tuple[str, str]] = []

        for i, event in enumerate(new_events, 1):
            event_name = (
                f"{event.prefecture} {event.store_name}".strip() or f"City League {event.date}"
            )
            console.print(f"  [{i}/{len(new_events)}] {event_name} ({event.date})")

            results = api_client.fetch_event_results(event.event_id)

            if not results:
                console.print("    [yellow]No results found, skipping[/yellow]")
                continue

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
                prefecture=event.prefecture,
                store_name=event.store_name,
                capacity=event.capacity,
            )
            events_data.append(jp_event)

            if fetch_decklists:
                for p in placements:
                    if p.deck_url and p.deck_code and p.standing <= top:
                        all_deck_entries.append((p.deck_code, p.deck_url))

        console.print(
            f"[green]Collected {sum(len(e.placements) for e in events_data)} placements "
            f"across {len(events_data)} events[/green]"
        )

        # Phase 2: Batch fetch all decklists concurrently
        all_decklists: dict[str, list] = {}
        if fetch_decklists and all_deck_entries:
            from dotenv import load_dotenv

            load_dotenv()
            from scraper.pokemon_jp import PokemonJPClient

            console.print(
                f"\n[bold cyan]Phase 2:[/bold cyan] Fetching {len(all_deck_entries)} decklists "
                f"with {pool_size} concurrent browsers..."
            )

            completed = [0]
            failed = [0]
            t_start = time.monotonic()

            def on_complete(deck_code: str, card_count: int) -> None:
                completed[0] += 1
                if card_count < 0:
                    failed[0] += 1
                    console.print(
                        f"  [{completed[0]}/{len(all_deck_entries)}] {deck_code}: [red]failed[/red]"
                    )
                elif card_count == 0:
                    console.print(
                        f"  [{completed[0]}/{len(all_deck_entries)}] "
                        f"{deck_code}: [yellow]0 cards[/yellow]"
                    )
                else:
                    console.print(
                        f"  [{completed[0]}/{len(all_deck_entries)}] "
                        f"{deck_code}: {card_count} cards"
                    )

            async def run_batch() -> dict[str, list]:
                jp_client = PokemonJPClient(pool_size=pool_size)
                async with jp_client.browser_pool():
                    return await jp_client.fetch_decklists_batch(
                        all_deck_entries, on_complete=on_complete
                    )

            all_decklists = asyncio.run(run_batch())

            elapsed = time.monotonic() - t_start
            console.print(
                f"[green]Fetched {len(all_decklists)} decklists in {elapsed:.0f}s "
                f"({failed[0]} failed)[/green]"
            )

        # Phase 3: Store everything
        console.print(f"\n[bold cyan]Phase 3:[/bold cyan] Storing {len(events_data)} events...")
        total_placements = 0
        total_decklists = 0

        for jp_event in events_data:
            event_decklists = {
                p.deck_code: all_decklists[p.deck_code]
                for p in jp_event.placements
                if p.deck_code and p.deck_code in all_decklists
            }
            store_cl_city_league_results(conn, jp_event, event_decklists)
            total_placements += len(jp_event.placements)
            total_decklists += len(event_decklists)

        console.print(
            f"\n[green]Done! Stored {total_placements} placements "
            f"and {total_decklists} decklists across {len(events_data)} events.[/green]"
        )
    finally:
        api_client.close()
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
                f"{placement.player_name or 'Unknown'} - {placement.archetype}"
            )

            cursor = conn.execute(
                "INSERT INTO placements (tournament_id, standing, player_name, archetype, decklist_url) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    tournament_url,
                    placement.placement,
                    placement.player_name,
                    placement.archetype,
                    placement.decklist_url,
                ),
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
        # Mark keys that appear more than once as ambiguous (non-unique standing)
        archetype_lookup: dict[tuple[str, int], str] = {}
        ambiguous_keys: set[tuple[str, int]] = set()

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
                if key in archetype_lookup:
                    ambiguous_keys.add(key)
                archetype_lookup[key] = p.archetype

        # Remove ambiguous keys to avoid assigning one tournament's archetype
        # to a different tournament's placements at the same standing
        for key in ambiguous_keys:
            del archetype_lookup[key]

        if ambiguous_keys:
            console.print(
                f"[yellow]Skipped {len(ambiguous_keys)} ambiguous (date, standing) keys[/yellow]"
            )
        console.print(f"Built lookup with [bold]{len(archetype_lookup)}[/bold] unique entries")

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
@click.option(
    "--strict",
    is_flag=True,
    help="Fail on any export error instead of skipping (use in CI)",
)
@click.pass_context
def export_web(ctx: click.Context, narrative: bool, strict: bool) -> None:
    """Export JSON data for the Scout Web dashboard."""
    from labs_db import get_labs_connection, init_labs_db
    from reports.json_export import export_all, export_formats, export_narrative

    fmt = ctx.obj["format"]
    conn = get_format_connection(fmt)
    init_db(conn)
    # Open Labs connection for matchup cascade (auto-upgrades when data exists)
    labs_conn = None
    try:
        labs_conn = get_labs_connection()
        init_labs_db(labs_conn)
    except (FileNotFoundError, sqlite3.OperationalError) as exc:
        console.print(f"[yellow]Labs DB unavailable, using co-occurrence only: {exc}[/yellow]")
        labs_conn = None
    except Exception:
        logger.warning("Failed to connect to Labs database, skipping Labs exports", exc_info=True)
        labs_conn = None
    try:
        out, skipped = export_all(conn, format_slug=fmt, strict=strict, labs_conn=labs_conn)
        console.print(f"[green]Web data exported to {out}[/green]")
        if skipped:
            console.print(
                f"[yellow]Skipped {len(skipped)} optional export(s): {', '.join(skipped)}[/yellow]"
            )
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
        if labs_conn:
            labs_conn.close()


@cli.command("scrape-labs")
@click.argument("tournament_id", type=str)
@click.argument("labs_id", type=str)
@click.option("--fetch-decklists/--no-decklists", default=True, help="Fetch decklists")
@click.option("--max-placements", default=None, type=int, help="Limit to top N standings")
@click.pass_context
def scrape_labs(
    ctx: click.Context,
    tournament_id: str,
    labs_id: str,
    fetch_decklists: bool,
    max_placements: int | None,
) -> None:
    """Scrape international tournament data from Labs Limitless.

    TOURNAMENT_ID is the main Limitless tournament ID (e.g. 551).
    LABS_ID is the Labs tournament ID (e.g. 0058).

    Example: scout scrape-labs 551 0058
    """
    from labs_db import get_labs_connection, init_labs_db
    from scraper.labs_limitless import LabsLimitlessClient

    conn = get_labs_connection()
    init_labs_db(conn)

    try:
        with LabsLimitlessClient() as client:
            console.print(
                f"[cyan]Scraping Labs tournament {tournament_id} (Labs ID: {labs_id})...[/cyan]"
            )

            result = client.ingest_tournament(
                conn,
                tournament_id=tournament_id,
                labs_tournament_id=labs_id,
                fetch_decklists=fetch_decklists,
                max_placements=max_placements,
            )

            console.print(
                f"\n[green]Done! Stored {result['players']} players, "
                f"{result['placements']} placements, "
                f"{result['decklists']} decklists.[/green]"
            )
            if result.get("decklist_failures"):
                console.print(
                    f"[yellow]Warning: {result['decklist_failures']} decklist(s) "
                    f"failed to fetch.[/yellow]"
                )
    except ValueError as exc:
        console.print(f"[red]Error ingesting tournament: {exc}[/red]")
        raise click.Abort()
    except httpx.HTTPStatusError as exc:
        console.print(
            f"[red]HTTP {exc.response.status_code} from {exc.request.url} — "
            f"check your internet connection and verify the tournament ID.[/red]"
        )
        raise click.Abort()
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        console.print(f"[red]Network error: {exc}. Check your internet connection.[/red]")
        raise click.Abort()
    except Exception:
        logger.exception("Unexpected error ingesting tournament %s", tournament_id)
        raise
    finally:
        conn.close()


@cli.command("labs-matchups")
@click.option("--top", default=15, help="Number of top archetypes")
@click.pass_context
def labs_matchups(ctx: click.Context, top: int) -> None:
    """Compute H2H matchup data from Labs international tournaments."""
    from analysis.matchup import compute_labs_archetype_winrates, compute_labs_matchup_matrix
    from labs_db import get_labs_connection, init_labs_db

    conn = None
    try:
        conn = get_labs_connection()
        init_labs_db(conn)

        # Archetype win rates
        winrates = compute_labs_archetype_winrates(conn, top_n=top)
        if not winrates["archetypes"]:
            console.print("[yellow]No Labs data found. Run 'scout scrape-labs' first.[/yellow]")
            return

        console.print(
            f"\n[green]Labs matchup data from {winrates['tournament_count']} tournament(s)[/green]"
        )

        # Display win rates table
        table = Table(title="Archetype Win Rates (Labs H2H)")
        table.add_column("Archetype", style="bold")
        table.add_column("Players", justify="right")
        table.add_column("Record", justify="right")
        table.add_column("Win Rate", justify="right")
        table.add_column("95% CI", justify="right")

        for arch in winrates["archetypes"]:
            wr_pct = f"{arch['win_rate'] * 100:.1f}%"
            ci = f"{arch['ci_lower'] * 100:.1f}-{arch['ci_upper'] * 100:.1f}%"
            record = f"{arch['total_wins']}-{arch['total_losses']}-{arch['total_ties']}"
            table.add_row(
                arch["archetype"],
                str(arch["players"]),
                record,
                wr_pct,
                ci,
            )

        console.print(table)

        # Matchup matrix
        matrix_data = compute_labs_matchup_matrix(conn, top_n=top)
        if matrix_data["archetypes"]:
            console.print(
                f"\n[cyan]Matchup matrix: {len(matrix_data['archetypes'])} archetypes "
                f"(source: {matrix_data['source']})[/cyan]"
            )
            if matrix_data["source"] == "labs-records":
                console.print(
                    "[yellow]Note: Using approximate record-based comparison. "
                    "True H2H match data not available.[/yellow]"
                )

    except Exception:
        logger.exception("Failed to compute Labs matchups")
        raise
    finally:
        if conn is not None:
            conn.close()


@cli.command()
@click.option("--strict", is_flag=True, help="Treat warnings as errors")
@click.pass_context
def validate(ctx: click.Context, strict: bool) -> None:
    """Validate exported data and database integrity."""

    from reports.json_export import DEFAULT_OUTPUT_DIR
    from validation import validate_database, validate_export

    fmt = ctx.obj["format"]
    export_dir = DEFAULT_OUTPUT_DIR / fmt

    console.print(f"[cyan]Validating format: {fmt}[/cyan]\n")

    # Tier 1: Export validation
    console.print("[bold]Export validation[/bold]")
    export_result = validate_export(export_dir)

    for err in export_result.errors:
        console.print(f"  [red]X[/red] {err}")
    for warn in export_result.warnings:
        console.print(f"  [yellow]![/yellow] {warn}")
    if export_result.ok and not export_result.warnings:
        console.print("  [green]OK[/green] All export checks passed")

    # Tier 2: Database validation
    console.print("\n[bold]Database validation[/bold]")
    conn = get_format_connection(fmt)
    try:
        db_result = validate_database(conn)
    finally:
        conn.close()

    for err in db_result.errors:
        console.print(f"  [red]X[/red] {err}")
    for warn in db_result.warnings:
        console.print(f"  [yellow]![/yellow] {warn}")
    if db_result.ok and not db_result.warnings:
        console.print("  [green]OK[/green] All database checks passed")

    # Summary
    total_errors = len(export_result.errors) + len(db_result.errors)
    total_warnings = len(export_result.warnings) + len(db_result.warnings)

    console.print()
    if strict and total_warnings > 0:
        console.print(
            f"[red bold]FAILED[/red bold]: {total_errors} error(s), "
            f"{total_warnings} warning(s) promoted to errors under --strict"
        )
        raise SystemExit(1)
    elif total_errors > 0:
        console.print(
            f"[red bold]FAILED[/red bold]: {total_errors} error(s), {total_warnings} warning(s)"
        )
        raise SystemExit(1)
    else:
        console.print(f"[green bold]PASSED[/green bold]: 0 errors, {total_warnings} warning(s)")


@cli.group()
@click.pass_context
def players(ctx: click.Context) -> None:
    """Player intelligence — track top performers."""
    pass


@players.command("list")
@click.option("--min-appearances", default=2, help="Minimum tournament appearances")
@click.option("--limit", default=50, help="Max players to show")
@click.pass_context
def players_list(ctx: click.Context, min_appearances: int, limit: int) -> None:
    """List top performers by weighted placement score."""
    from analysis.players import list_top_performers

    conn = get_format_connection(ctx.obj["format"])
    init_db(conn)
    try:
        performers = list_top_performers(conn, min_appearances=min_appearances, limit=limit)
        if not performers:
            console.print("[yellow]No players found with enough appearances.[/yellow]")
            return

        table = Table(title=f"Top Performers (min {min_appearances} appearances)")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Player", style="bold")
        table.add_column("Events", justify="right")
        table.add_column("Best", justify="right")
        table.add_column("Score", justify="right")
        table.add_column("Archetypes")

        for i, p in enumerate(performers, 1):
            archetypes_str = ", ".join(p.archetypes[:3])
            if len(p.archetypes) > 3:
                archetypes_str += f" +{len(p.archetypes) - 3}"
            table.add_row(
                str(i),
                p.player_name,
                str(p.tournament_count),
                str(p.best_placement),
                f"{p.weighted_score:.1f}",
                archetypes_str,
            )

        console.print(table)
    finally:
        conn.close()


@players.command("create")
@click.argument("name")
@click.option("--country", default="JP", help="Country code")
@click.option("--notes", default=None, help="Notes about this player")
@click.pass_context
def players_create(ctx: click.Context, name: str, country: str, notes: str | None) -> None:
    """Create a new player identity."""
    from analysis.players import create_player

    conn = get_format_connection(ctx.obj["format"])
    init_db(conn)
    try:
        player_id = create_player(conn, name, country=country, notes=notes)
        console.print(f"[green]Created player #{player_id}: {name} ({country})[/green]")
    finally:
        conn.close()


@players.command("link")
@click.argument("alias")
@click.argument("player_id", type=int)
@click.option("--source", default="limitless", help="Data source for this alias")
@click.pass_context
def players_link(ctx: click.Context, alias: str, player_id: int, source: str) -> None:
    """Link a tournament name (alias) to a player identity and backfill placements."""
    from analysis.players import link_alias, link_placements_by_alias

    conn = get_format_connection(ctx.obj["format"])
    init_db(conn)
    try:
        link_alias(conn, alias, player_id, source=source)
        linked = link_placements_by_alias(conn, player_id, alias)
        console.print(
            f"[green]Linked alias '{alias}' to player #{player_id} "
            f"({linked} placement(s) connected)[/green]"
        )
    finally:
        conn.close()


@players.command("profile")
@click.argument("player_id", type=int)
@click.pass_context
def players_profile(ctx: click.Context, player_id: int) -> None:
    """Show a player's full profile and tournament history."""
    from analysis.players import get_player_profile

    conn = get_format_connection(ctx.obj["format"])
    init_db(conn)
    try:
        profile = get_player_profile(conn, player_id)
        if not profile:
            console.print(f"[red]Player #{player_id} not found.[/red]")
            return

        console.print(f"\n[bold]{profile.display_name}[/bold] (#{profile.player_id})")
        console.print(f"  Country: {profile.country}")
        if profile.notes:
            console.print(f"  Notes: {profile.notes}")
        if profile.twitter_handle:
            console.print(f"  Twitter: @{profile.twitter_handle}")
        if profile.youtube_url:
            console.print(f"  YouTube: {profile.youtube_url}")
        if profile.blog_url:
            console.print(f"  Blog: {profile.blog_url}")
        if profile.aliases:
            console.print(f"  Aliases: {', '.join(profile.aliases)}")

        console.print(
            f"\n  [cyan]{profile.tournament_count} tournaments, "
            f"weighted score: {profile.weighted_score}[/cyan]"
        )

        if profile.deck_timeline:
            console.print("\n  [bold]Deck Timeline:[/bold]")
            table = Table()
            table.add_column("Date")
            table.add_column("Archetype")
            table.add_column("Standing", justify="right")

            for entry in profile.deck_timeline:
                table.add_row(
                    entry.date,
                    entry.archetype,
                    str(entry.standing),
                )
            console.print(table)
    finally:
        conn.close()


@cli.command("scrape-pokecazilla")
@click.argument("url")
@click.option("--list-articles", is_flag=True, help="List recent Pokemon TCG articles instead of scraping a URL")
@click.option("--max-pages", default=3, help="Max listing pages to scan (with --list-articles)")
@click.pass_context
def scrape_pokecazilla(
    ctx: click.Context,
    url: str,
    list_articles: bool,
    max_pages: int,
) -> None:
    """Scrape tournament results from pokecazilla.com.

    Requires KERNEL_API_KEY in .env for cloud browser rendering.

    \b
    Examples:
        scout scrape-pokecazilla https://pokecazilla.com/column/cl2026osaka-decks/
        scout scrape-pokecazilla --list-articles https://pokecazilla.com/category/pokemon/
    """
    import asyncio

    from dotenv import load_dotenv

    load_dotenv()

    from scraper.pokecazilla import PokecazillaClient

    try:
        client = PokecazillaClient()
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)

    if list_articles:
        console.print(f"[cyan]Listing Pokemon TCG articles (max {max_pages} pages)...[/cyan]")
        entries = asyncio.run(client.list_pokemon_articles(max_pages=max_pages))

        table = Table(title="Pokecazilla Pokemon TCG Articles")
        table.add_column("Date", style="dim")
        table.add_column("Title")
        table.add_column("URL", style="cyan")

        for entry in entries:
            table.add_row(entry.date or "-", entry.title, entry.url)

        console.print(table)
        console.print(f"\n[green]Found {len(entries)} articles.[/green]")
    else:
        console.print(f"[cyan]Scraping article: {url}[/cyan]")
        article = asyncio.run(client.fetch_article(url))

        console.print(f"\n[bold]{article.title}[/bold]")
        console.print(f"URL: {article.url}\n")

        if not article.placements:
            console.print("[yellow]No placements found in article.[/yellow]")
            return

        table = Table(title="Top 8 Placements")
        table.add_column("#", justify="right", style="bold")
        table.add_column("Archetype (JP)")
        table.add_column("Deck Code", style="cyan")
        table.add_column("Deck URL", style="dim")

        for p in sorted(article.placements, key=lambda x: x.standing):
            table.add_row(
                str(p.standing),
                p.archetype_jp,
                p.deck_code or "-",
                p.deck_url or "-",
            )

        console.print(table)
        console.print(f"\n[green]{len(article.placements)} placements extracted.[/green]")


@cli.command("scrape-pokecabook")
@click.argument("url")
@click.option(
    "--mode",
    type=click.Choice(["recipe", "analysis", "list"]),
    default="recipe",
    help="Extraction mode: recipe (deck), analysis (avg counts), list (search articles)",
)
@click.option("--search", default=None, help="Search query for list mode")
@click.option("--max-pages", default=1, help="Max listing pages for list mode")
@click.pass_context
def scrape_pokecabook(
    ctx: click.Context,
    url: str,
    mode: str,
    search: str | None,
    max_pages: int,
) -> None:
    """Scrape deck recipes and analytics from pokecabook.com.

    URL is required for recipe/analysis modes. For list mode, pass the base URL
    or use --search to filter.

    \b
    Examples:
        scout scrape-pokecabook https://pokecabook.com/archives/307010
        scout scrape-pokecabook https://pokecabook.com/archives/307010 --mode analysis
        scout scrape-pokecabook https://pokecabook.com --mode list --search "CL大阪"
    """
    import asyncio

    from dotenv import load_dotenv

    load_dotenv()

    from scraper.pokecabook import PokecaBookClient

    try:
        client = PokecaBookClient()
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)

    if mode == "list":
        articles = asyncio.run(client.list_articles(search_query=search, max_pages=max_pages))
        if not articles:
            console.print("[yellow]No articles found.[/yellow]")
            return

        table = Table(title=f"PokecaBook Articles ({len(articles)} found)")
        table.add_column("Date", style="dim")
        table.add_column("Category")
        table.add_column("Title", style="bold")
        table.add_column("URL", style="dim")

        for a in articles:
            table.add_row(a.date, a.category, a.title, a.url)
        console.print(table)

    elif mode == "analysis":
        analysis = asyncio.run(client.fetch_archetype_analysis(url))
        console.print(f"\n[bold]{analysis.archetype_jp}[/bold]")
        if analysis.sample_size:
            console.print(f"  Sample size: {analysis.sample_size} decklists")

        if not analysis.avg_cards:
            console.print("[yellow]No average card data found.[/yellow]")
            return

        table = Table(title="Average Card Counts")
        table.add_column("Category", style="dim")
        table.add_column("Card Name (JP)", style="bold")
        table.add_column("Avg Count", justify="right")
        table.add_column("Adoption %", justify="right")

        for card in analysis.avg_cards:
            table.add_row(
                card.category,
                card.name_jp,
                f"{card.avg_count:.1f}" if card.avg_count else "-",
                f"{card.adoption_rate:.0f}%" if card.adoption_rate else "-",
            )
        console.print(table)

    else:  # recipe
        recipe = asyncio.run(client.fetch_deck_recipe(url))
        console.print(f"\n[bold]{recipe.title}[/bold]")
        if recipe.event_name:
            console.print(f"  Event: {recipe.event_name}")
        if recipe.placement:
            console.print(f"  Placement: {recipe.placement}")
        if recipe.player_name:
            console.print(f"  Player: {recipe.player_name}")

        if not recipe.cards:
            console.print("[yellow]No cards extracted from article.[/yellow]")
            return

        total = sum(c.count for c in recipe.cards)
        table = Table(title=f"Deck Recipe ({total} cards)")
        table.add_column("Category", style="dim")
        table.add_column("Card Name (JP)", style="bold")
        table.add_column("Count", justify="right")

        current_cat = ""
        for card in recipe.cards:
            cat_display = card.category if card.category != current_cat else ""
            current_cat = card.category
            table.add_row(cat_display, card.name_jp, str(card.count))
        console.print(table)


if __name__ == "__main__":
    cli()
