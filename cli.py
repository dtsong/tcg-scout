"""CLI entry point for Rotation Scout."""

import logging
import os
import sqlite3

import click
import httpx
from rich.console import Console
from rich.table import Table

from config import DEFAULT_FORMAT, FORMATS, TPC_REGION_COUNTRIES, get_format_config
from db import get_format_connection, init_db, reset_db

console = Console()
logger = logging.getLogger("scout")


def _fetch_decklists_batch(
    deck_entries: list[tuple[str, str]],
    pool_size: int,
) -> dict[str, list]:
    """Fetch decklists via Playwright browser pool with progress logging.

    Args:
        deck_entries: List of (deck_code, deck_url) tuples.
        pool_size: Number of concurrent browser instances.

    Returns:
        Dict mapping deck_code to list of JPDeckCard.
    """
    import asyncio
    import time

    from dotenv import load_dotenv

    load_dotenv()
    from scraper.pokemon_jp import PokemonJPClient

    console.print(
        f"\nFetching {len(deck_entries)} decklists with {pool_size} concurrent browsers..."
    )

    completed = [0]
    failed = [0]
    t_start = time.monotonic()

    def on_complete(deck_code: str, card_count: int) -> None:
        completed[0] += 1
        if card_count < 0:
            failed[0] += 1
            console.print(f"  [{completed[0]}/{len(deck_entries)}] {deck_code}: [red]failed[/red]")
        elif card_count == 0:
            console.print(
                f"  [{completed[0]}/{len(deck_entries)}] {deck_code}: [yellow]0 cards[/yellow]"
            )
        else:
            console.print(f"  [{completed[0]}/{len(deck_entries)}] {deck_code}: {card_count} cards")

    async def run_batch() -> dict[str, list]:
        jp_client = PokemonJPClient(pool_size=pool_size)
        async with jp_client.browser_pool():
            return await jp_client.fetch_decklists_batch(deck_entries, on_complete=on_complete)

    all_decklists = asyncio.run(run_batch())

    elapsed = time.monotonic() - t_start
    console.print(
        f"[green]Fetched {len(all_decklists)} decklists in {elapsed:.0f}s "
        f"({failed[0]} failed)[/green]"
    )
    return all_decklists


def _store_events_with_decklists(
    conn: sqlite3.Connection,
    events_data: list,
    all_decklists: dict[str, list],
) -> None:
    """Store events and their decklists, printing a summary."""
    from scraper.pokemon_jp import store_cl_city_league_results

    console.print(f"\nStoring {len(events_data)} events...")
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


@cli.command("repair-decklists")
@click.option("--dry-run", is_flag=True, help="Show what would be repaired without fetching")
@click.option("--pool-size", default=5, help="Number of concurrent browser instances")
@click.pass_context
def repair_decklists(ctx: click.Context, dry_run: bool, pool_size: int) -> None:
    """Re-fetch decklists that have fewer than 60 cards due to card_id collisions.

    Recovers deck codes from the API when decklist_url is missing.
    """
    fmt = ctx.obj["format"]
    conn = get_format_connection(fmt)
    init_db(conn)

    try:
        _run_repair_decklists(conn, dry_run, pool_size)
    finally:
        conn.close()


def _run_repair_decklists(conn: sqlite3.Connection, dry_run: bool, pool_size: int) -> None:
    from scraper.pokemon_jp_api import PokemonJPAPIClient

    # Find all sub-60 placements
    bad_placements = conn.execute("""
        SELECT p.id, p.tournament_id, p.standing, p.player_name, p.decklist_url,
               SUM(dc.count) as total_cards
        FROM placements p
        JOIN tournaments t ON p.tournament_id = t.id
        JOIN decklist_cards dc ON dc.placement_id = p.id
        WHERE t.id LIKE 'jp-%'
        GROUP BY p.id
        HAVING total_cards < 60
        ORDER BY t.date, p.standing
    """).fetchall()

    console.print(f"Found [bold]{len(bad_placements)}[/bold] decklists with <60 cards")

    if not bad_placements:
        return

    # Group by tournament to batch API lookups
    by_tournament: dict[str, list] = {}
    for row in bad_placements:
        by_tournament.setdefault(row["tournament_id"], []).append(row)

    console.print(f"Across [bold]{len(by_tournament)}[/bold] tournaments\n")

    # Phase 1: Recover deck codes for placements missing URLs
    deck_url_base = "https://www.pokemon-card.com/deck/confirm.html/deckID/"
    deck_entries: list[tuple[int, str, str]] = []  # (placement_id, deck_code, deck_url)
    api_client = PokemonJPAPIClient()

    try:
        for tid, placements in by_tournament.items():
            try:
                event_id = int(tid.replace("jp-", ""))
            except ValueError:
                console.print(f"  [yellow]Skipping {tid}: non-numeric event ID[/yellow]")
                continue

            # Check if any placements need URL recovery
            needs_api = [p for p in placements if not p["decklist_url"]]
            has_url = [p for p in placements if p["decklist_url"]]

            # Add known URLs
            for p in has_url:
                url = p["decklist_url"]
                code = url.split("deckID/")[-1] if "deckID/" in url else None
                if code:
                    deck_entries.append((p["id"], code, url))

            if needs_api:
                try:
                    results = api_client.fetch_event_results(event_id)
                except httpx.HTTPError as e:
                    console.print(f"  [red]API error for {tid}: {e}[/red]")
                    continue
                api_by_standing: dict[int, str] = {}
                for r in results:
                    if r.deck_id:
                        api_by_standing[r.rank] = r.deck_id

                for p in needs_api:
                    deck_id = api_by_standing.get(p["standing"])
                    if deck_id:
                        deck_entries.append((p["id"], deck_id, deck_url_base + deck_id))
                    else:
                        console.print(
                            f"  [yellow]No deck code for {p['player_name']} "
                            f"(#{p['standing']}) in {tid}[/yellow]"
                        )
    finally:
        api_client.close()

    console.print(
        f"\n[cyan]Recovered {len(deck_entries)} deck URLs "
        f"({len(bad_placements) - len(deck_entries)} unrecoverable)[/cyan]"
    )

    if dry_run:
        console.print("\n[yellow]Dry run -- no changes made[/yellow]")
        return

    if not deck_entries:
        console.print("[yellow]No decklists to repair[/yellow]")
        return

    # Phase 2: Re-fetch all decklists
    fetch_list = [(code, url) for _, code, url in deck_entries]
    all_decklists = _fetch_decklists_batch(fetch_list, pool_size)

    # Phase 3: Delete old cards and re-store
    console.print("\nReplacing card data...")
    from analysis.card_stats import build_jp_en_lookup
    from reports.json_export import JP_CARD_NAMES
    from scraper.pokemon_jp import store_decklist_cards

    jp_en_lookup = build_jp_en_lookup(conn, fallback=JP_CARD_NAMES)
    repaired = 0
    still_bad = 0

    for placement_id, deck_code, _ in deck_entries:
        if deck_code not in all_decklists:
            continue

        cards = all_decklists[deck_code]
        total = sum(c.count for c in cards)

        if total < 60:
            still_bad += 1
            continue

        conn.execute("DELETE FROM decklist_cards WHERE placement_id = ?", (placement_id,))
        store_decklist_cards(conn, placement_id, cards, jp_en_lookup)

        # Update decklist_url if it was missing
        conn.execute(
            "UPDATE placements SET decklist_url = ? WHERE id = ? AND (decklist_url IS NULL OR decklist_url = '')",
            (f"https://www.pokemon-card.com/deck/confirm.html/deckID/{deck_code}", placement_id),
        )

        repaired += 1

    conn.commit()
    console.print(
        f"\n[green]Repaired {repaired} decklists[/green]"
        f"\n[yellow]{still_bad} still <60 after re-fetch (parser issue)[/yellow]"
        f"\n[yellow]{len(bad_placements) - len(deck_entries)} had no deck code[/yellow]"
    )


@cli.command("backfill-decklists")
@click.option("--limit", default=None, type=int, help="Max placements to backfill")
@click.option(
    "--since", default=None, help="Only backfill tournaments on/after this date (YYYY-MM-DD)"
)
@click.option(
    "--source",
    type=click.Choice(["jp", "limitless", "labs", "all"]),
    default="all",
    help="Which scraper source to backfill (labs = labs.limitlesstcg.com, i.e. TPCI)",
)
@click.option("--pool-size", default=5, help="Concurrent browsers for JP decklist fetching")
@click.option(
    "--max-standing",
    default=None,
    type=int,
    help="Only backfill placements finishing at/above this standing (e.g. 32 = top cut)",
)
@click.pass_context
def backfill_decklists(
    ctx: click.Context,
    limit: int | None,
    since: str | None,
    source: str,
    pool_size: int,
    max_standing: int | None,
) -> None:
    """Fetch missing decklists for placements that have a deck URL but no card data.

    Targets placements in open_placements (post-dedup) where decklist_url is set
    but no rows exist in decklist_cards. Use --source to limit to one scraper,
    --since to bound by tournament date, --limit to cap total volume per run, and
    --max-standing to bound depth per tournament (top-cut only).
    """
    fmt = ctx.obj["format"]
    conn = get_format_connection(fmt)
    init_db(conn)

    try:
        remaining = limit
        if source in ("jp", "all"):
            n = _backfill_jp_decklists(conn, remaining, since, pool_size, max_standing)
            if remaining is not None:
                remaining = max(0, remaining - n)
        if source in ("limitless", "all") and (remaining is None or remaining > 0):
            n = _backfill_limitless_decklists(conn, remaining, since, max_standing)
            if remaining is not None:
                remaining = max(0, remaining - n)
        if source in ("labs", "all") and (remaining is None or remaining > 0):
            _backfill_labs_decklists(conn, remaining, since, max_standing)
    finally:
        conn.close()


# Columns the backfill selector may match a source pattern against. Allowlisted
# because the value is interpolated into SQL; never accept caller-supplied columns.
_MATCH_COLUMNS = {"t.id", "p.decklist_url"}


def _select_missing_decklist_placements(
    conn: sqlite3.Connection,
    pattern: str,
    limit: int | None,
    since: str | None,
    max_standing: int | None = None,
    match_column: str = "t.id",
) -> list[sqlite3.Row]:
    """Return open placements with decklist_url but no decklist_cards rows.

    ``pattern`` is a SQL LIKE pattern matched against ``match_column``. Sources
    keyed by tournament id (JP, main-site Limitless) match ``t.id``; sources
    where the tournament id is opaque (TPCI/Labs integer ids) match
    ``p.decklist_url`` by host instead.

    ``max_standing`` bounds the depth per tournament (e.g. 32 = top cut only),
    enabling a fast top-cut backfill instead of fetching every standings row.
    """
    if match_column not in _MATCH_COLUMNS:
        raise ValueError(f"Unsupported match_column: {match_column!r}")
    sql = f"""
        SELECT p.id, p.tournament_id, p.standing, p.decklist_url, t.date
        FROM open_placements p
        JOIN tournaments t ON t.id = p.tournament_id
        LEFT JOIN decklist_cards dc ON dc.placement_id = p.id
        WHERE p.decklist_url IS NOT NULL
          AND p.decklist_url != ''
          AND dc.placement_id IS NULL
          AND {match_column} LIKE ?
    """
    params: list = [pattern]
    if since:
        sql += " AND t.date >= ?"
        params.append(since)
    if max_standing is not None:
        sql += " AND p.standing <= ?"
        params.append(max_standing)
    sql += " GROUP BY p.id ORDER BY t.date DESC, p.standing ASC"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return conn.execute(sql, params).fetchall()


def _backfill_jp_decklists(
    conn: sqlite3.Connection,
    limit: int | None,
    since: str | None,
    pool_size: int,
    max_standing: int | None = None,
) -> int:
    """Fetch missing JP (jp-*) decklists via Playwright batch and store cards."""
    placements = _select_missing_decklist_placements(conn, "jp-%", limit, since, max_standing)
    console.print(f"\n[cyan]JP backfill:[/cyan] {len(placements)} placements missing decklists")
    if not placements:
        return 0

    deck_url_base = "https://www.pokemon-card.com/deck/confirm.html/deckID/"
    deck_entries: list[tuple[str, str]] = []
    by_code: dict[str, list[int]] = {}
    for p in placements:
        url = p["decklist_url"]
        code = url.split("deckID/")[-1] if "deckID/" in url else None
        if not code:
            continue
        by_code.setdefault(code, []).append(p["id"])
        deck_entries.append((code, deck_url_base + code))

    # Deduplicate codes (same deck shared across placements)
    unique_entries = list({code: (code, url) for code, url in deck_entries}.values())
    if not unique_entries:
        console.print("[yellow]No recoverable JP deck codes[/yellow]")
        return 0

    all_decklists = _fetch_decklists_batch(unique_entries, pool_size)

    from analysis.card_stats import build_jp_en_lookup
    from reports.json_export import JP_CARD_NAMES
    from scraper.pokemon_jp import store_decklist_cards

    jp_en_lookup = build_jp_en_lookup(conn, fallback=JP_CARD_NAMES)
    stored = 0
    empty = 0
    for code, placement_ids in by_code.items():
        cards = all_decklists.get(code)
        if not cards:
            empty += 1
            continue
        for placement_id in placement_ids:
            conn.execute("DELETE FROM decklist_cards WHERE placement_id = ?", (placement_id,))
            store_decklist_cards(conn, placement_id, cards, jp_en_lookup)
            stored += 1
    conn.commit()

    console.print(
        f"[green]JP backfill: stored {stored} decklists "
        f"({empty} deck codes returned no cards)[/green]"
    )
    return stored


def _backfill_limitless_decklists(
    conn: sqlite3.Connection,
    limit: int | None,
    since: str | None,
    max_standing: int | None = None,
) -> int:
    """Fetch missing Limitless decklists via plain HTTP and store cards.

    Covers two id shapes on limitlesstcg.com: JP City League tournaments
    (``t.id`` is the full tournament URL) and the main-site international majors
    scrape-tpci ingests for pre-Labs events (opaque integer ``t.id``, decklists
    at ``limitlesstcg.com/decks/list/<id>``). The two patterns match different
    columns, so query each and merge unique by placement id.
    """
    by_tid = _select_missing_decklist_placements(
        conn, "https://limitlesstcg.com/%", limit, since, max_standing
    )
    by_url = _select_missing_decklist_placements(
        conn,
        "https://limitlesstcg.com/decks/list/%",
        limit,
        since,
        max_standing,
        match_column="p.decklist_url",
    )
    seen: set = set()
    placements = []
    for row in (*by_tid, *by_url):
        if row["id"] not in seen:
            seen.add(row["id"])
            placements.append(row)
    if limit:
        placements = placements[:limit]
    console.print(
        f"\n[cyan]Limitless backfill:[/cyan] {len(placements)} placements missing decklists"
    )
    if not placements:
        return 0

    from scraper.limitless import LimitlessClient

    client = LimitlessClient()
    stored = 0
    empty = 0
    try:
        for i, p in enumerate(placements, 1):
            url = p["decklist_url"]
            console.print(f"  [{i}/{len(placements)}] placement #{p['id']} {url}")
            try:
                decklist = client.fetch_decklist(url)
            except (httpx.HTTPError, OSError) as exc:
                console.print(f"    [red]Error: {exc}[/red]")
                continue
            if not decklist or not decklist.cards:
                empty += 1
                continue
            conn.execute("DELETE FROM decklist_cards WHERE placement_id = ?", (p["id"],))
            for card in decklist.cards:
                conn.execute(
                    "INSERT OR REPLACE INTO decklist_cards "
                    "(placement_id, card_id, card_name, count) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        p["id"],
                        card.get("card_id", card.get("name", "unknown")),
                        card.get("name"),
                        card.get("count", 1),
                    ),
                )
            stored += 1
        conn.commit()
    finally:
        client.close()

    console.print(
        f"[green]Limitless backfill: stored {stored} decklists ({empty} returned no cards)[/green]"
    )
    return stored


def _backfill_labs_decklists(
    conn: sqlite3.Connection,
    limit: int | None,
    since: str | None,
    max_standing: int | None = None,
) -> int:
    """Fetch missing Labs (labs.limitlesstcg.com) decklists and store cards.

    TPCI tournament ids are opaque integers, so placements are matched by their
    per-player decklist_url host rather than by tournament id.
    """
    placements = _select_missing_decklist_placements(
        conn,
        "https://labs.limitlesstcg.com/%",
        limit,
        since,
        max_standing,
        match_column="p.decklist_url",
    )
    console.print(f"\n[cyan]Labs backfill:[/cyan] {len(placements)} placements missing decklists")
    if not placements:
        return 0

    from scraper.labs_limitless import LabsLimitlessClient

    client = LabsLimitlessClient()
    stored = 0
    empty = 0
    try:
        for i, p in enumerate(placements, 1):
            url = p["decklist_url"]
            console.print(f"  [{i}/{len(placements)}] placement #{p['id']} {url}")
            try:
                decklist = client.fetch_decklist(url)
            except (httpx.HTTPError, OSError) as exc:
                console.print(f"    [red]Error: {exc}[/red]")
                continue
            if not decklist or not decklist.cards:
                empty += 1
                continue
            conn.execute("DELETE FROM decklist_cards WHERE placement_id = ?", (p["id"],))
            for card in decklist.cards:
                conn.execute(
                    "INSERT OR REPLACE INTO decklist_cards "
                    "(placement_id, card_id, card_name, count) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        p["id"],
                        card.get("card_id", card.get("name", "unknown")),
                        card.get("name"),
                        card.get("count", 1),
                    ),
                )
            stored += 1
        conn.commit()
    finally:
        client.close()

    console.print(
        f"[green]Labs backfill: stored {stored} decklists ({empty} returned no cards)[/green]"
    )
    return stored


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
    from scraper.pokemon_jp import JPEventResult, JPPlacement
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

            try:
                results = api_client.fetch_event_results(event.event_id)
            except Exception as exc:
                console.print(f"    [red]Error fetching event {event.event_id}: {exc}[/red]")
                continue

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
            all_decklists = _fetch_decklists_batch(all_deck_entries, pool_size)

        # Phase 3: Store everything
        _store_events_with_decklists(conn, events_data, all_decklists)
    finally:
        api_client.close()
        conn.close()


@cli.command("scrape-cl-api")
@click.argument("cl_name", required=False, default=None)
@click.option("--event-ids", default=None, help="Comma-separated event_holding_ids to scrape")
@click.option(
    "--fetch-decklists/--no-decklists", default=True, help="Fetch decklists via Playwright"
)
@click.option("--top", default=16, help="Max placements to fetch decklists for")
@click.option(
    "--pool-size", default=5, help="Number of concurrent browser instances for decklist fetching"
)
@click.option("--list", "list_cls", is_flag=True, help="List available CL events")
@click.pass_context
def scrape_cl_api(
    ctx: click.Context,
    cl_name: str | None,
    event_ids: str | None,
    fetch_decklists: bool,
    top: int,
    pool_size: int,
    list_cls: bool,
) -> None:
    """Scrape Champions League results from players.pokemon-card.com API.

    Uses plain HTTP for event results (no browser required for listings).
    Pass --fetch-decklists to also fetch decklists via Playwright.

    Examples:
        scout scrape-cl-api --list
        scout scrape-cl-api osaka-2026
        scout scrape-cl-api --event-ids 981570,953305,953306
    """
    from config import POKEMON_JP_CL_EVENTS
    from scraper.pokemon_jp import JPEventResult, JPPlacement
    from scraper.pokemon_jp_api import CL_DIVISION_MAP, PokemonJPAPIClient

    if list_cls:
        console.print("[bold]Available CL events:[/bold]")
        for key, info in POKEMON_JP_CL_EVENTS.items():
            event_ids_str = ", ".join(str(eid) for eid in info["events"])
            console.print(
                f"  [cyan]{key}[/cyan]: {info['name']} ({info['date']}) -- {event_ids_str}"
            )
        return

    # Build list of (event_id, division) to scrape
    events_to_scrape: list[tuple[int, str | None]] = []

    if event_ids:
        for eid_str in event_ids.split(","):
            events_to_scrape.append((int(eid_str.strip()), None))
    elif cl_name:
        if cl_name not in POKEMON_JP_CL_EVENTS:
            console.print(f"[red]Unknown CL event: {cl_name}[/red]")
            console.print(f"Available: {', '.join(POKEMON_JP_CL_EVENTS.keys())}")
            return
        cl_info = POKEMON_JP_CL_EVENTS[cl_name]
        for eid, division in cl_info["events"].items():
            events_to_scrape.append((eid, division))
    else:
        console.print("[red]Specify a CL name or --event-ids. Use --list to see options.[/red]")
        return

    fmt = ctx.obj["format"]
    conn = get_format_connection(fmt)
    init_db(conn)

    api_client = PokemonJPAPIClient()
    deck_url_base = "https://www.pokemon-card.com/deck/confirm.html/deckID/"

    try:
        # Phase 1: Fetch event metadata and results via API
        console.print(
            f"[bold cyan]Phase 1:[/bold cyan] Fetching {len(events_to_scrape)} CL events via API..."
        )
        events_data: list[JPEventResult] = []
        all_deck_entries: list[tuple[str, str]] = []

        for eid, known_division in events_to_scrape:
            try:
                meta, results = api_client.fetch_event_with_metadata(eid)
            except httpx.HTTPError as e:
                console.print(f"  [red]Failed to fetch event {eid}: {e}[/red]")
                continue

            if not meta:
                console.print(f"  [red]Event {eid}: API error (check logs)[/red]")
                continue
            if not results:
                console.print(f"  [yellow]Event {eid}: no results[/yellow]")
                continue

            # Determine division from metadata or known config
            title = meta.get("event_title", "")
            division = known_division or "masters"
            if not known_division:
                detected = False
                for jp_div, en_div in CL_DIVISION_MAP.items():
                    if jp_div in title:
                        division = en_div
                        detected = True
                        break
                if not detected:
                    console.print(
                        "    [yellow]Could not detect division from title, defaulting to masters[/yellow]"
                    )

            # Map CL division to tournament division
            tournament_division = {"masters": "open", "seniors": "senior", "juniors": "junior"}.get(
                division, "open"
            )

            # Parse date -- event_result_detail_search uses different fields than event_search
            date_iso = ""
            event_date = meta.get("eventDate")
            if isinstance(event_date, dict) and event_date.get("date"):
                date_iso = event_date["date"][:10]  # "2026-03-29 00:00:00.000000" -> "2026-03-29"
            elif meta.get("eventDaySupply"):
                date_iso = meta["eventDaySupply"].replace("/", "-")
            elif meta.get("event_date_params"):
                date_raw = meta["event_date_params"]
                if len(date_raw) == 8 and date_raw.isdigit():
                    date_iso = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}"

            if not date_iso:
                console.print(f"    [yellow]Warning: could not parse date for event {eid}[/yellow]")

            console.print(
                f"  [green]{eid}[/green]: {title[:60]} | {len(results)} placements | {division}"
            )

            # Check if already in DB
            existing = conn.execute(
                "SELECT id FROM tournaments WHERE id = ?", (f"jp-{eid}",)
            ).fetchone()
            if existing:
                console.print("    [yellow]Already in database, skipping[/yellow]")
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
                event_id=eid,
                event_name=title,
                division=tournament_division,
                date=date_iso,
                placements=placements,
            )
            events_data.append(jp_event)

            if fetch_decklists:
                for p in placements:
                    if p.deck_url and p.deck_code and p.standing <= top:
                        all_deck_entries.append((p.deck_code, p.deck_url))

        if not events_data:
            console.print("[yellow]No new events to process.[/yellow]")
            return

        console.print(
            f"\n[green]Collected {sum(len(e.placements) for e in events_data)} placements "
            f"across {len(events_data)} events[/green]"
        )

        # Phase 2: Batch fetch decklists
        all_decklists: dict[str, list] = {}
        if fetch_decklists and all_deck_entries:
            all_decklists = _fetch_decklists_batch(all_deck_entries, pool_size)

        # Phase 3: Store everything
        _store_events_with_decklists(conn, events_data, all_decklists)
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

        # Build lookup: (date_str, player_name) -> archetype
        # Player names are nearly unique per date; keying on (date, standing)
        # collapses when multiple tournaments share the same prefecture/day.
        # Mark keys where the same (date, name) maps to different archetypes.
        archetype_lookup: dict[tuple[str, str], str] = {}
        ambiguous_keys: set[tuple[str, str]] = set()

        for i, tournament in enumerate(tournaments, 1):
            console.print(
                f"  [{i}/{len(tournaments)}] {tournament.name} ({tournament.tournament_date})"
            )
            placements = client.fetch_jp_city_league_placements(
                tournament.source_url, max_placements
            )
            date_str = tournament.tournament_date.isoformat()
            for p in placements:
                if not p.player_name or not p.archetype or p.archetype == "Unknown":
                    continue
                key = (date_str, p.player_name)
                existing = archetype_lookup.get(key)
                if existing is not None and existing != p.archetype:
                    ambiguous_keys.add(key)
                else:
                    archetype_lookup[key] = p.archetype

        for key in ambiguous_keys:
            archetype_lookup.pop(key, None)

        if ambiguous_keys:
            console.print(
                f"[yellow]Skipped {len(ambiguous_keys)} ambiguous (date, player_name) keys[/yellow]"
            )
        console.print(f"Built lookup with [bold]{len(archetype_lookup)}[/bold] unique entries")

        # Update placements in DB
        updated = 0
        for row in rows:
            if not row["player_name"]:
                continue
            key = (row["date"], row["player_name"])
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

    # Open the Postgres labs store when configured — it's the canonical
    # international source and takes precedence over the SQLite labs DB.
    labs_pg_cm = None
    labs_pg_conn = None
    if any(os.environ.get(k) for k in ("SCOUT_DATABASE_URL", "DATABASE_URL", "SUPABASE_DB_URL")):
        try:
            from db_postgres import get_pg_connection

            labs_pg_cm = get_pg_connection()
            labs_pg_conn = labs_pg_cm.__enter__()
        except Exception as exc:  # noqa: BLE001 - fall back to SQLite/co-occurrence
            console.print(
                f"[yellow]Labs Postgres unavailable, using SQLite/co-occurrence: {exc}[/yellow]"
            )
            labs_pg_cm = None
            labs_pg_conn = None

    try:
        out, skipped = export_all(
            conn, format_slug=fmt, strict=strict, labs_conn=labs_conn, labs_pg_conn=labs_pg_conn
        )
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
        if labs_pg_cm is not None:
            labs_pg_cm.__exit__(None, None, None)


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


@cli.command("scrape-labs-pg")
@click.argument("tournament_id", type=str)
@click.argument("labs_id", type=str)
@click.option("--fetch-decklists/--no-decklists", default=True, help="Fetch decklists")
@click.option("--max-placements", default=None, type=int, help="Limit standings to top N")
@click.option("--dry-run", is_flag=True, help="Fetch + validate, write nothing")
@click.pass_context
def scrape_labs_pg(
    ctx: click.Context,
    tournament_id: str,
    labs_id: str,
    fetch_decklists: bool,
    max_placements: int | None,
    dry_run: bool,
) -> None:
    """Full-depth Labs ingestion into Postgres (labs schema): standings,
    decklists, and per-round H2H matches.

    TOURNAMENT_ID is the main Limitless id (e.g. 551); LABS_ID is the labs id
    (e.g. 0062). Resumable (skips rounds already in labs.matches) and idempotent
    (re-runs are free). Requires SCOUT_DATABASE_URL (Supabase Session Pooler).

    Example: scout scrape-labs-pg 551 0062
    """
    from db_postgres import (
        backfill_match_archetypes,
        get_ingested_rounds,
        insert_matches,
        refresh_matchup_matrix,
        upsert_decklist,
        upsert_placement,
        upsert_player,
        upsert_tournament,
    )
    from scraper.labs_limitless import (
        LabsLimitlessClient,
        labs_player_id,
        pairing_to_match_row,
    )

    pg_cm = None
    conn = None
    if not dry_run:
        from dotenv import load_dotenv

        from db_postgres import PostgresConfigError, get_pg_connection

        # Pick up the connection string from .env / .env.local without forcing
        # the operator to export it manually (consistent with sibling commands).
        load_dotenv()
        load_dotenv(".env.local", override=False)

        try:
            pg_cm = get_pg_connection()
            conn = pg_cm.__enter__()
        except PostgresConfigError as exc:
            console.print(f"[red]{exc}[/red]")
            console.print(
                "[yellow]Set SCOUT_DATABASE_URL to the Supabase Session Pooler URI "
                "(port 5432) or pass --dry-run.[/yellow]"
            )
            raise click.Abort()

    try:
        with LabsLimitlessClient() as client:
            console.print(
                f"[cyan]Labs->Postgres: tournament {tournament_id} (labs {labs_id})"
                f"{' [DRY RUN]' if dry_run else ''}[/cyan]"
            )

            # --- Metadata + standings -------------------------------------
            meta = client.fetch_tournament_metadata(tournament_id)
            standings = client.fetch_standings(labs_id)
            if max_placements:
                standings = standings[:max_placements]
            if not standings:
                raise ValueError(f"No standings for labs tournament {labs_id}")

            tournament_type = _classify_tpci_type(meta.name)

            if conn is not None:
                upsert_tournament(
                    conn,
                    tournament_id=tournament_id,
                    name=meta.name,
                    date=meta.date,
                    labs_id=labs_id,
                    country=meta.country or None,
                    region=meta.region or None,
                    fmt=meta.format or None,
                    tournament_type=tournament_type,
                    player_count=meta.player_count or None,
                    division="open",
                )

                for placement in standings:
                    pid = labs_player_id(labs_id, placement.player.player_id)
                    upsert_player(
                        conn,
                        player_id=pid,
                        name=placement.player.name,
                        country=placement.player.country or None,
                    )
                    placement_db_id = upsert_placement(
                        conn,
                        tournament_id=tournament_id,
                        player_id=pid,
                        player_name=placement.player.name,
                        standing=placement.standing,
                        archetype=placement.archetype,
                        record_w=placement.record_w,
                        record_l=placement.record_l,
                        record_t=placement.record_t,
                        decklist_url=placement.decklist_url,
                        has_decklist=bool(placement.decklist_url) and fetch_decklists,
                    )
                    if fetch_decklists and placement.decklist_url:
                        deck = client.fetch_decklist(placement.decklist_url)
                        if deck and deck.cards:
                            upsert_decklist(
                                conn,
                                placement_id=placement_db_id,
                                source_url=deck.source_url,
                                cards=deck.cards,
                            )
                conn.commit()
                console.print(f"  [green]standings: {len(standings)} placements[/green]")

            # --- Per-round matches (resumable) ----------------------------
            first = client.fetch_pairings(labs_id, 1)
            total_rounds = first.total_rounds or 1
            done_rounds = get_ingested_rounds(conn, tournament_id) if conn else set()

            total_matches = 0
            for rnd in range(1, total_rounds + 1):
                if rnd in done_rounds:
                    console.print(f"  round {rnd}: already ingested, skipping")
                    continue
                page = first if rnd == 1 else client.fetch_pairings(labs_id, rnd)
                rows = [
                    r
                    for p in page.pairings
                    if (r := pairing_to_match_row(labs_id, tournament_id, p)) is not None
                ]
                total_matches += len(rows)
                if conn is not None:
                    # Safety net: ensure every match participant exists in players.
                    for p in page.pairings:
                        if p.is_bye:
                            continue
                        for local, name, ctry in (
                            (p.p1_local, p.p1_name, p.p1_country),
                            (p.p2_local, p.p2_name, p.p2_country),
                        ):
                            upsert_player(
                                conn,
                                player_id=labs_player_id(labs_id, local),
                                name=name or f"player-{local}",
                                country=ctry or None,
                            )
                    insert_matches(conn, rows)
                    conn.commit()
                console.print(f"  round {rnd}: {len(rows)} matches")

            if conn is not None:
                backfill_match_archetypes(conn, tournament_id)
                conn.commit()
                refresh_matchup_matrix(conn)
                conn.commit()
                console.print(
                    f"[green]Done. {total_matches} matches across {total_rounds} rounds; "
                    f"archetypes backfilled; matview refreshed.[/green]"
                )
            else:
                console.print(
                    f"[green][DRY RUN] would write {total_matches} matches across "
                    f"{total_rounds} rounds (no DB changes).[/green]"
                )
    except ValueError as exc:
        if conn is not None:
            conn.rollback()
        console.print(f"[red]Error: {exc}[/red]")
        raise click.Abort()
    except httpx.HTTPStatusError as exc:
        if conn is not None:
            conn.rollback()
        console.print(f"[red]HTTP {exc.response.status_code} from {exc.request.url}[/red]")
        raise click.Abort()
    except Exception:
        if conn is not None:
            conn.rollback()
        logger.exception("Unexpected error ingesting labs tournament %s to Postgres", tournament_id)
        raise
    finally:
        if pg_cm is not None:
            pg_cm.__exit__(None, None, None)


_TPCI_TYPE_BY_PREFIX = {
    "regional": "regional",
    "special": "special-event",
    "world": "worlds",
    "champions": "champions-league",
}


def _classify_tpci_type(name: str) -> str:
    """Derive Scout tournament_type from Limitless tournament name.

    Best-effort classification based on the first word of the name. Falls
    back to 'other' for things we haven't tagged (e.g. "Korean League").
    """
    if not name:
        return "other"
    first = name.split()[0].lower()
    if first in _TPCI_TYPE_BY_PREFIX:
        return _TPCI_TYPE_BY_PREFIX[first]
    upper = name.upper()
    if "INTERNATIONAL" in upper or upper.endswith("IC") or " IC " in f" {upper} ":
        return "international"
    return "other"


@cli.command("scrape-tpci")
@click.option(
    "--since",
    default=None,
    help="ISO date lower bound (defaults to active format's dataset_start)",
)
@click.option(
    "--until",
    default=None,
    help="ISO date upper bound (defaults to active format's dataset_end). "
    "Bounds a historical rotation window so it does not bleed into later formats.",
)
@click.option(
    "--type-filter",
    default="major",
    help="Limitless type filter: major (all checkpoints), regional, international, worlds, special",
)
@click.option(
    "--format-filter",
    default="STANDARD",
    help="Limitless format filter (STANDARD, EXPANDED)",
)
@click.option(
    "--max-placements", default=None, type=int, help="Limit to top N standings per tournament"
)
@click.option("--fetch-decklists/--no-decklists", default=True, help="Fetch decklists")
@click.option(
    "--max-tournaments",
    default=None,
    type=int,
    help="Limit number of new tournaments to process (useful for smoke testing)",
)
@click.option(
    "--max-pages",
    default=1,
    type=int,
    help="Listing pages to walk newest-to-oldest (raise for deep historical backfills)",
)
@click.option(
    "--exclude-country",
    "exclude_country",
    multiple=True,
    help="ISO 2-letter country code to drop (repeatable). Defaults to the TPC "
    "region (JP, KR) so their separate circuits stay out of the TPCi format.",
)
@click.pass_context
def scrape_tpci(
    ctx: click.Context,
    since: str | None,
    until: str | None,
    type_filter: str,
    format_filter: str,
    max_placements: int | None,
    fetch_decklists: bool,
    max_tournaments: int | None,
    max_pages: int,
    exclude_country: tuple[str, ...],
) -> None:
    """Discover and ingest international TPCi tournaments into the active format's DB.

    Writes to the standard format DB (configured by --format), not data/labs.db.
    Use --format tpci-standard to target the dedicated international DB.

    Example:
        scout --format tpci-standard scrape-tpci --since 2026-04-01
    """
    from scraper.labs_limitless import LabsLimitlessClient

    fmt_slug = ctx.obj["format"]
    fmt = get_format_config(fmt_slug)
    since = since or fmt["dataset_start"]
    until = until or fmt["dataset_end"]
    # Default to dropping TPC-region events; an explicit --exclude-country overrides.
    exclude_countries = (
        frozenset(c.strip().upper() for c in exclude_country)
        if exclude_country
        else TPC_REGION_COUNTRIES
    )

    conn = get_format_connection(fmt_slug)
    init_db(conn)

    with LabsLimitlessClient() as client:
        pages_note = f", {max_pages} listing pages" if max_pages > 1 else ""
        excl_note = (
            f", excluding {', '.join(sorted(exclude_countries))}" if exclude_countries else ""
        )
        console.print(
            f"[cyan]Discovering {format_filter}/{type_filter} tournaments "
            f"from {since} to {until}{pages_note}{excl_note}...[/cyan]"
        )
        listings = client.list_tournaments(
            format_filter=format_filter,
            type_filter=type_filter,
            since=since,
            until=until,
            max_pages=max_pages,
            exclude_countries=exclude_countries,
        )
        console.print(f"Found [bold]{len(listings)}[/bold] tournaments in listing")

        if not listings:
            console.print("[yellow]No tournaments matched filters.[/yellow]")
            conn.close()
            return

        # Skip tournaments already in this DB
        existing = {row["id"] for row in conn.execute("SELECT id FROM tournaments")}
        new_listings = [t for t in listings if t.tournament_id not in existing]
        if max_tournaments:
            new_listings = new_listings[:max_tournaments]
        console.print(
            f"[cyan]{len(new_listings)} new tournament(s) to ingest "
            f"({len(existing)} already in DB)[/cyan]"
        )

        total_placements = 0
        total_decklists = 0
        failed = 0

        try:
            for i, listing in enumerate(new_listings, 1):
                console.print(
                    f"  [{i}/{len(new_listings)}] {listing.name} ({listing.date}, {listing.country})"
                )

                try:
                    metadata = client.fetch_tournament_metadata(listing.tournament_id)
                except ValueError as exc:
                    console.print(f"    [yellow]Metadata parse failed: {exc}[/yellow]")
                    failed += 1
                    continue

                try:
                    if metadata.labs_tournament_id:
                        standings = client.fetch_standings(metadata.labs_tournament_id)
                    else:
                        # Pre-Labs international major: standings live on the
                        # main-site Results page (no Labs index before ~Sept 2024).
                        console.print(
                            "    [cyan]No Labs standings; falling back to main-site page[/cyan]"
                        )
                        standings = client.fetch_main_site_standings(listing.tournament_id)
                except ValueError as exc:
                    console.print(f"    [yellow]Standings parse failed: {exc}[/yellow]")
                    failed += 1
                    continue

                if not standings:
                    console.print("    [yellow]Empty standings; skipping[/yellow]")
                    continue

                if max_placements:
                    standings = standings[:max_placements]

                tournament_type = _classify_tpci_type(listing.name)

                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO tournaments "
                        "(id, name, date, player_count, country, division, tournament_type) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            listing.tournament_id,
                            listing.name,
                            listing.date,
                            listing.player_count,
                            listing.country,
                            "open",
                            tournament_type,
                        ),
                    )

                    for placement in standings:
                        cursor = conn.execute(
                            "INSERT INTO placements "
                            "(tournament_id, standing, player_name, archetype, decklist_url) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (
                                listing.tournament_id,
                                placement.standing,
                                placement.player.name,
                                placement.archetype,
                                placement.decklist_url,
                            ),
                        )
                        placement_id = cursor.lastrowid
                        total_placements += 1

                        if fetch_decklists and placement.decklist_url:
                            try:
                                decklist = client.fetch_decklist(placement.decklist_url)
                            except httpx.HTTPStatusError as exc:
                                if exc.response.status_code in (401, 403):
                                    raise  # Circuit-break out of this tournament
                                decklist = None
                            if decklist and decklist.cards:
                                for card in decklist.cards:
                                    conn.execute(
                                        "INSERT OR REPLACE INTO decklist_cards "
                                        "(placement_id, card_id, card_name, count) "
                                        "VALUES (?, ?, ?, ?)",
                                        (
                                            placement_id,
                                            card.get("card_id") or card.get("name") or "unknown",
                                            card.get("name"),
                                            card.get("count", 1),
                                        ),
                                    )
                                total_decklists += 1

                    conn.commit()
                except sqlite3.Error:
                    logger.exception(
                        "Failed to ingest tournament %s, rolling back",
                        listing.tournament_id,
                    )
                    conn.rollback()
                    failed += 1
                    continue
                except httpx.HTTPStatusError as exc:
                    console.print(
                        f"    [red]Aborting tournament — HTTP {exc.response.status_code} "
                        f"on {exc.request.url}[/red]"
                    )
                    conn.rollback()
                    failed += 1
                    continue

            console.print(
                f"\n[green]Done! Ingested {total_placements} placements "
                f"and {total_decklists} decklists from {len(new_listings) - failed} "
                f"tournament(s).[/green]"
            )
            if failed:
                console.print(f"[red]{failed} tournament(s) failed to ingest. Check logs.[/red]")
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
@click.option(
    "--list-articles",
    is_flag=True,
    help="List recent Pokemon TCG articles instead of scraping a URL",
)
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
