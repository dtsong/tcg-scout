"""Phase 0 spike validation (offline): prove pairings JSON yields correct matches.

Builds the full match list from all snapshotted pairings rounds, inspects winner/
bye/tie semantics, then cross-checks each player's reconstructed W-L-T against the
truth from their per-player Matches page. Confirms we can populate labs.matches
WITHOUT record-delta reconstruction (winner is explicit in the pairings payload).
"""

import json
import re
from collections import defaultdict
from pathlib import Path

FIX = Path(__file__).parent.parent / "tests" / "fixtures" / "labs" / "0062"
SERVER_DATA_RE = re.compile(r'<script[^>]*>(\{"status":\s*200[^<]+?\})</script>')


def server_blobs(html: str):
    for raw in SERVER_DATA_RE.findall(html):
        try:
            outer = json.loads(raw)
            body = outer.get("body")
            inner = json.loads(body) if isinstance(body, str) else None
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(inner, dict):
            yield inner


def pairings_list(html: str) -> list[dict]:
    """The match-list blob is the one whose message is a list."""
    for inner in server_blobs(html):
        msg = inner.get("message")
        if isinstance(msg, list):
            return msg
    return []


def main() -> None:
    rounds = sorted(FIX.glob("pairings_round_*.html"))
    all_matches: list[tuple[int, dict]] = []
    winner_vals = defaultdict(int)
    p2_missing = 0
    for rf in rounds:
        rnd = int(re.search(r"round_(\d+)", rf.name).group(1))
        matches = pairings_list(rf.read_text())
        for m in matches:
            all_matches.append((rnd, m))
            w = m.get("winner")
            winner_vals["tie/zero" if w in (0, None) else "decisive"] += 1
            p2 = m.get("player2")
            if p2 in (None, 0):
                p2_missing += 1

    print(f"rounds snapshotted: {len(rounds)}  total match rows: {len(all_matches)}")
    print(f"winner field: {dict(winner_vals)}")
    print(f"rows with no player2 (bye candidates): {p2_missing}")

    # Inspect a couple of raw rows to lock field semantics.
    print("\nsample rows (round, keys, winner, completed):")
    for rnd, m in all_matches[:3]:
        print(
            f"  r{rnd} winner={m.get('winner')} completed={m.get('completed')} "
            f"p1={m.get('player1')}({m.get('player1_record')}) "
            f"p2={m.get('player2')}({m.get('player2_record')}) "
            f"decks={m.get('p1_deck')}/{m.get('p2_deck')}"
        )

    # Reconstruct W-L-T per player from pairings winner field.
    rec = defaultdict(lambda: [0, 0, 0])  # pid -> [w,l,t]
    for _rnd, m in all_matches:
        p1, p2, w = m.get("player1"), m.get("player2"), m.get("winner")
        if p2 in (None, 0):  # bye -> win for p1, no opponent
            if p1:
                rec[p1][0] += 1
            continue
        if w in (0, None):  # tie
            rec[p1][2] += 1
            rec[p2][2] += 1
        elif w == p1:
            rec[p1][0] += 1
            rec[p2][1] += 1
        elif w == p2:
            rec[p2][0] += 1
            rec[p1][1] += 1

    # Truth from per-player Matches pages. NOTE: pairings player1/player2 are
    # tournament-LOCAL ids; blob[0].player_id is the GLOBAL limitless id. The
    # local id is recoverable from blob[2] (the player's own match list uses
    # local p1_id/p2_id), which is the id space the file URL also uses.
    print("\ncross-check vs per-player page truth (local_id: reconstructed vs truth):")
    mismatches = 0
    for pf in sorted(FIX.glob("player_*.html")):
        local_id = int(re.search(r"player_(\d+)", pf.name).group(1))
        blobs = list(server_blobs(pf.read_text()))
        meta = next(
            (
                b["message"]
                for b in blobs
                if isinstance(b.get("message"), dict) and "wins" in b["message"]
            ),
            None,
        )
        if not meta:
            continue
        truth = (meta["wins"], meta["losses"], meta["ties"])
        got = tuple(rec.get(local_id, [0, 0, 0]))
        ok = got == truth
        mismatches += 0 if ok else 1
        print(
            f"  local={local_id:<5} global={meta['player_id']:<6} "
            f"({meta['name']:<22}) recon={got} truth={truth} "
            f"{'OK' if ok else 'MISMATCH'}"
        )

    print(
        f"\nGATE: {'PASS - winner is explicit, records reconcile' if mismatches == 0 else f'{mismatches} MISMATCHES - investigate'}"
    )


if __name__ == "__main__":
    main()
