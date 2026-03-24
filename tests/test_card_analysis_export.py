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


def test_export_card_analysis_sorts_by_weighted_impact(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    _seed(conn)
    export_card_analysis(conn, tmp_path)
    import json

    data = json.loads((tmp_path / "card-analysis.json").read_text())
    impacts = [c["weighted_impact"] for c in data["cards"]]
    assert impacts == sorted(impacts, reverse=True)


def test_export_card_analysis_weighted_impact_favors_higher_tier(tmp_path):
    """Weighted impact should skew toward S-tier deltas over Rogue deltas."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)

    # Create S-tier and Rogue-tier archetypes with different deltas for the same card
    conn.execute(
        "INSERT INTO tournaments (id, name, date, player_count) VALUES ('t1', 'T1', '2026-03-01', 32)"
    )
    # S-tier archetype: 10 placements, 5 top-4
    for i in range(1, 11):
        standing = i  # 1-4 are top-4, 5-10 are field
        conn.execute(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, 't1', ?, ?, 'TopDeck')",
            (i, standing, f"Player{i}"),
        )
    # Rogue archetype: 4 placements, 2 top-4 (standings 1,2,5,6)
    for i, standing in [(11, 1), (12, 2), (13, 5), (14, 6)]:
        conn.execute(
            "INSERT INTO placements (id, tournament_id, standing, player_name, archetype) "
            "VALUES (?, 't1', ?, ?, 'RogueDeck')",
            (i, standing, f"Player{i}"),
        )

    # "Tech Card" appears only in top-4 of TopDeck (delta = big)
    # and only in top-4 of RogueDeck but with lower inclusion (delta = small via different card set)
    # TopDeck top-4 (pids 1-4): Tech Card in all 4 → top4_incl = 100%
    # TopDeck field (pids 1-10): Tech Card in 4 of 10 → field_incl = 40%, delta = +60
    for pid in [1, 2, 3, 4]:
        conn.execute(
            "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) "
            "VALUES (?, 'tech', 'Tech Card', 1)",
            (pid,),
        )
    # RogueDeck top-4 (pids 11,12): Tech Card in 1 of 2 → top4_incl = 50%
    # RogueDeck field (pids 11-14): Tech Card in 2 of 4 → field_incl = 50%, delta = 0 → skipped
    # Actually we want a non-zero delta, so put card in top-4 only:
    # top4_incl = 50% (1 of 2), field_incl = 25% (1 of 4), delta = +25
    conn.execute(
        "INSERT INTO decklist_cards (placement_id, card_id, card_name, count) "
        "VALUES (11, 'tech', 'Tech Card', 1)"
    )

    conn.execute(
        "INSERT INTO meta_snapshots (id, generated_at, tournament_count, deck_count) "
        "VALUES (1, '2026-03-01', 1, 14)"
    )
    conn.execute(
        "INSERT INTO archetype_stats (snapshot_id, archetype, deck_count, meta_share, tier) "
        "VALUES (1, 'TopDeck', 10, 71.4, 'S')"
    )
    conn.execute(
        "INSERT INTO archetype_stats (snapshot_id, archetype, deck_count, meta_share, tier) "
        "VALUES (1, 'RogueDeck', 4, 28.6, 'Rogue')"
    )
    conn.commit()

    export_card_analysis(conn, tmp_path)
    import json

    data = json.loads((tmp_path / "card-analysis.json").read_text())
    tech = next(c for c in data["cards"] if c["card_name"] == "Tech Card")

    # avg_delta = (60 + 25) / 2 = 42.5
    # weighted_impact = (60*0.4*5 + 25*0.2*0.5) / (0.4*5 + 0.2*0.5) = 122.5 / 2.1 = 58.3
    assert tech["avg_delta"] == 42.5
    assert tech["weighted_impact"] == 58.3
    # Weighted impact skews toward the S-tier delta (60), away from simple average (42.5)
    assert tech["weighted_impact"] > tech["avg_delta"]


def test_export_card_analysis_includes_confidence(tmp_path):
    """Each archetype entry should have a confidence field."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    _seed(conn)
    export_card_analysis(conn, tmp_path)
    import json

    data = json.loads((tmp_path / "card-analysis.json").read_text())
    boss = next(c for c in data["cards"] if c["card_name"] == "Boss's Orders")
    for arch in boss["archetypes"]:
        assert "confidence" in arch
        assert 0 <= arch["confidence"] <= 1.0
    # top4_sample_size=2 for both archetypes -> confidence = min(1.0, 2/10) = 0.2
    assert boss["archetypes"][0]["confidence"] == 0.2
