"""Tests for cross-archetype card analysis export."""

import sqlite3

from db import init_db
from reports.json_export import export_card_analysis


def _seed(conn: sqlite3.Connection) -> None:
    """Seed DB with two archetypes, each having top-4 and non-top-4 placements."""
    conn.execute(
        "INSERT INTO tournaments (id, name, date, player_count) VALUES ('t1', 'T1', '2026-03-01', 16)"
    )
    for i, standing in enumerate([1, 3, 9, 12], start=1):
        conn.execute(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, 't1', ?, ?, 'Charizard Pidgeot')",
            (i, standing, f"Player{i}"),
        )
    for i, standing in enumerate([2, 4, 10, 15], start=5):
        conn.execute(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, 't1', ?, ?, 'Lugia Archeops')",
            (i, standing, f"Player{i}"),
        )
    # Charizard: pids 1(1st),2(3rd),3(9th),4(12th) — top-4 = pids 1,2
    # Lugia:     pids 5(2nd),6(4th),7(10th),8(15th) — top-4 = pids 5,6
    # Boss's Orders only in top-4 placements → delta = +50 for both archetypes
    for pid in [1, 2, 5, 6]:
        conn.execute(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) "
            "VALUES (?, 'boss-orders', 'Boss''s Orders', 2)",
            (pid,),
        )
    # Rare Candy only in Charizard top-4 (pids 1,2) → delta = +50 for Charizard only
    for pid in [1, 2]:
        conn.execute(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) "
            "VALUES (?, 'rare-candy', 'Rare Candy', 3)",
            (pid,),
        )
    conn.execute(
        "INSERT INTO meta_snapshots (id, generated_at, tournament_count, deck_count) "
        "VALUES (1, '2026-03-01', 1, 8)"
    )
    conn.execute(
        "INSERT INTO archetype_stats (snapshot_id, archetype, deck_count, meta_share, tier) "
        "VALUES (1, 'Charizard Pidgeot', 4, 50.0, 'S')"
    )
    conn.execute(
        "INSERT INTO archetype_stats (snapshot_id, archetype, deck_count, meta_share, tier) "
        "VALUES (1, 'Lugia Archeops', 4, 50.0, 'A')"
    )
    conn.commit()


def test_export_card_analysis_returns_cards(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    _seed(conn)
    export_card_analysis(conn, tmp_path)
    import json

    data = json.loads((tmp_path / "card-analysis.json").read_text())
    assert "cards" in data
    assert len(data["cards"]) > 0
    boss = next(c for c in data["cards"] if c["card_name"] == "Boss's Orders")
    assert len(boss["archetypes"]) == 2
    assert boss["archetype_count"] == 2
    candy = next(c for c in data["cards"] if c["card_name"] == "Rare Candy")
    assert len(candy["archetypes"]) == 1
    assert candy["archetypes"][0]["archetype"] == "Charizard Pidgeot"


def test_export_card_analysis_computes_delta(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    _seed(conn)
    export_card_analysis(conn, tmp_path)
    import json

    data = json.loads((tmp_path / "card-analysis.json").read_text())
    candy = next(c for c in data["cards"] if c["card_name"] == "Rare Candy")
    arch = candy["archetypes"][0]
    assert arch["delta_vs_field"] == 50.0


def test_export_card_analysis_sorts_by_avg_delta(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    _seed(conn)
    export_card_analysis(conn, tmp_path)
    import json

    data = json.loads((tmp_path / "card-analysis.json").read_text())
    deltas = [c["avg_delta"] for c in data["cards"]]
    assert deltas == sorted(deltas, reverse=True)
