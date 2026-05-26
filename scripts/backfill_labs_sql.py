"""One-off: fetch a Labs tournament and emit batched SQL for MCP execution.

The normal ingestion path is `scout scrape-labs-pg` (writes via psycopg). In
environments where the Postgres connection string is unavailable (psycopg can't
connect) but a Supabase MCP `execute_sql` channel is, this script reproduces the
exact same write order/columns as cli.py:scrape-labs-pg, emitting `.sql` files
that can be pushed through MCP. Idempotent on the server (ON CONFLICT).

Usage:
    python scripts/backfill_labs_sql.py <labs_id> <tournament_pk> [--outdir DIR]

Example:
    python scripts/backfill_labs_sql.py 0062 labs-0062 --outdir /tmp/prague
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from scraper.labs_limitless import (
    LabsLimitlessClient,
    _iter_labs_server_blobs,
    labs_player_id,
    pairing_to_match_row,
)

_MONTHS = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
}


def sql_str(v) -> str:
    """SQL literal: NULL, TRUE/FALSE, numbers verbatim, strings single-quoted."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def parse_meta_date(raw: str | None) -> str | None:
    """'April 25-26, 2026' / 'April 25, 2026' -> ISO start date '2026-04-25'."""
    if not raw:
        return None
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2})", raw)
    y = re.search(r"(\d{4})", raw)
    if not (m and y):
        return None
    mon = _MONTHS.get(m.group(1).lower())
    if not mon:
        return None
    return f"{y.group(1)}-{mon}-{int(m.group(2)):02d}"


def batched_insert(header: str, rows: list[str], conflict: str, batch: int = 400) -> str:
    """Build multi-row INSERT statements (batched) sharing one ON CONFLICT tail."""
    out = []
    for i in range(0, len(rows), batch):
        chunk = ",\n".join(rows[i : i + batch])
        out.append(f"{header}\nVALUES\n{chunk}\n{conflict};")
    return "\n\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("labs_id")
    ap.add_argument("tournament_pk")
    ap.add_argument("--outdir", default="/tmp/labs_backfill")
    args = ap.parse_args()

    labs_id, tpk = args.labs_id, args.tournament_pk
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    with LabsLimitlessClient() as client:
        # --- meta + FULL standings from the standings-page server blobs ---
        # The rendered HTML <table> truncates to ~512 rows, but blob[1] carries
        # every player. tp_id is the tournament-local id (1..N) that pairings use
        # (verified: 100/100 name match vs pairing locals); player_id is global.
        # deck_name is Labs's curated archetype display label.
        labs_url = client._labs_url
        s_html = client._get(f"{labs_url}/{labs_id}/standings").text
        s_blobs = list(_iter_labs_server_blobs(s_html))
        meta = next((b for b in s_blobs if isinstance(b, dict)), {})
        standings_blob = next((b for b in s_blobs if isinstance(b, list) and len(b) > 0), [])
        city = meta.get("city")
        country = meta.get("country")
        ttype = meta.get("type")
        date = parse_meta_date(meta.get("date"))
        total_rounds = int(meta.get("round") or 0)
        player_count = int(meta.get("players") or 0)
        rk9_id = meta.get("rk9_id")
        name = meta.get("name") or (
            f"{city} {str(ttype).title()}".strip() if city else f"Labs {labs_id}"
        )

        # Normalize blob rows into the placement shape the SQL emitter expects.
        standings = []
        for r in standings_blob:
            tp = r.get("tp_id")
            if not tp:
                continue
            standings.append(
                {
                    "local_id": int(tp),
                    "name": (r.get("name") or f"player-{tp}").strip(),
                    "country": (r.get("country") or "").strip() or None,
                    "standing": int(r.get("placement") or 0) or len(standings) + 1,
                    "archetype": (r.get("deck_name") or "Unknown").strip() or "Unknown",
                    "record_w": int(r.get("wins") or 0),
                    "record_l": int(r.get("losses") or 0),
                    "record_t": int(r.get("ties") or 0),
                    "decklist_url": (
                        f"{labs_url}/{labs_id}/player/{tp}/decklist" if r.get("decklist") else None
                    ),
                }
            )
        print(
            f"meta: name={name!r} date={date} rounds={total_rounds} "
            f"players={player_count} standings={len(standings)}"
        )

        # --- tournament + players + placements ---
        tour_sql = (
            "INSERT INTO labs.tournaments\n"
            "  (id, labs_id, rk9_id, name, date, country, city, region, format,\n"
            "   tournament_type, player_count, total_rounds, division, source,\n"
            "   updated_at_src, refreshed_at)\n"
            "VALUES ("
            + ", ".join(
                [
                    sql_str(tpk),
                    sql_str(labs_id),
                    sql_str(rk9_id),
                    sql_str(name),
                    sql_str(date),
                    sql_str(country),
                    sql_str(city),
                    "NULL",
                    "NULL",
                    sql_str(ttype),
                    sql_str(player_count),
                    sql_str(total_rounds),
                    "'open'",
                    "'limitless-labs'",
                    "NULL",
                    "now()",
                ]
            )
            + ")\n"
            "ON CONFLICT (id) DO UPDATE SET\n"
            "  labs_id=excluded.labs_id, rk9_id=excluded.rk9_id, name=excluded.name,\n"
            "  date=excluded.date, country=excluded.country, city=excluded.city,\n"
            "  tournament_type=excluded.tournament_type,\n"
            "  player_count=excluded.player_count, total_rounds=excluded.total_rounds,\n"
            "  division=excluded.division, refreshed_at=now();"
        )

        player_rows, placement_rows = [], []
        for pl in standings:
            pid = labs_player_id(labs_id, pl["local_id"])
            player_rows.append(f"({sql_str(pid)}, {sql_str(pl['name'])}, {sql_str(pl['country'])})")
            placement_rows.append(
                "("
                + ", ".join(
                    [
                        sql_str(tpk),
                        sql_str(pid),
                        sql_str(pl["name"]),
                        sql_str(pl["standing"]),
                        sql_str(pl["archetype"]),
                        "NULL",
                        "NULL",
                        sql_str(pl["record_w"]),
                        sql_str(pl["record_l"]),
                        sql_str(pl["record_t"]),
                        sql_str(pl["decklist_url"]),
                        "FALSE",
                    ]
                )
                + ")"
            )

        players_sql = batched_insert(
            "INSERT INTO labs.players (id, name, country)",
            player_rows,
            "ON CONFLICT (id) DO UPDATE SET name=excluded.name, country=excluded.country",
        )
        placements_sql = batched_insert(
            "INSERT INTO labs.placements\n"
            "  (tournament_id, player_id, player_name, standing, archetype,\n"
            "   archetype_slug, sprite_key, record_w, record_l, record_t,\n"
            "   decklist_url, has_decklist)",
            placement_rows,
            "ON CONFLICT (tournament_id, player_id) DO UPDATE SET\n"
            "  player_name=excluded.player_name, standing=excluded.standing,\n"
            "  archetype=excluded.archetype, record_w=excluded.record_w,\n"
            "  record_l=excluded.record_l, record_t=excluded.record_t,\n"
            "  decklist_url=excluded.decklist_url, has_decklist=excluded.has_decklist",
        )

        (outdir / "01_tournament_players_placements.sql").write_text(
            tour_sql + "\n\n" + players_sql + "\n\n" + placements_sql + "\n"
        )

        # --- matches: every round, plus a safety-net player upsert ---
        match_rows, extra_players, total_matches = [], {}, 0
        for rnd in range(1, total_rounds + 1):
            page = client.fetch_pairings(labs_id, rnd)
            for p in page.pairings:
                if not p.is_bye:
                    for local, nm, ctry in (
                        (p.p1_local, p.p1_name, p.p1_country),
                        (p.p2_local, p.p2_name, p.p2_country),
                    ):
                        extra_players[labs_player_id(labs_id, local)] = (
                            nm or f"player-{local}",
                            ctry or None,
                        )
                r = pairing_to_match_row(labs_id, tpk, p)
                if r is None:
                    continue
                total_matches += 1
                match_rows.append(
                    "("
                    + ", ".join(
                        [
                            sql_str(r["id"]),
                            sql_str(r["tournament_id"]),
                            sql_str(r["round"]),
                            sql_str(r["player_low_id"]),
                            sql_str(r["player_high_id"]),
                            sql_str(r["player_low_archetype"]),
                            sql_str(r["player_high_archetype"]),
                            sql_str(r["winner_id"]),
                            sql_str(r["result"]),
                            sql_str(r["is_bye"]),
                        ]
                    )
                    + ")"
                )
            print(f"  round {rnd}: cumulative matches={total_matches}")

        extra_rows = [
            f"({sql_str(pid)}, {sql_str(nm)}, {sql_str(ctry)})"
            for pid, (nm, ctry) in extra_players.items()
        ]
        safety_players_sql = batched_insert(
            "INSERT INTO labs.players (id, name, country)",
            extra_rows,
            "ON CONFLICT (id) DO UPDATE SET name=excluded.name, country=excluded.country",
        )
        matches_sql = batched_insert(
            "INSERT INTO labs.matches\n"
            "  (id, tournament_id, round, player_low_id, player_high_id,\n"
            "   player_low_archetype, player_high_archetype, winner_id, result, is_bye)",
            match_rows,
            "ON CONFLICT (id) DO NOTHING",
        )
        (outdir / "02_matches.sql").write_text(safety_players_sql + "\n\n" + matches_sql + "\n")

        # --- archetype backfill + matview refresh ---
        (outdir / "03_finalize.sql").write_text(
            "UPDATE labs.matches m SET player_low_archetype = p.archetype\n"
            "FROM labs.placements p\n"
            "WHERE p.tournament_id = m.tournament_id AND p.player_id = m.player_low_id\n"
            f"  AND m.tournament_id = {sql_str(tpk)}\n"
            "  AND p.archetype IS NOT NULL AND p.archetype <> 'Unknown';\n\n"
            "UPDATE labs.matches m SET player_high_archetype = p.archetype\n"
            "FROM labs.placements p\n"
            "WHERE p.tournament_id = m.tournament_id AND p.player_id = m.player_high_id\n"
            f"  AND m.tournament_id = {sql_str(tpk)}\n"
            "  AND p.archetype IS NOT NULL AND p.archetype <> 'Unknown';\n\n"
            "REFRESH MATERIALIZED VIEW labs.matchup_matrix_agg;\n"
        )

        print(
            f"\nWrote SQL to {outdir}/  (standings={len(standings)}, "
            f"matches={total_matches}, rounds={total_rounds})"
        )


if __name__ == "__main__":
    main()
