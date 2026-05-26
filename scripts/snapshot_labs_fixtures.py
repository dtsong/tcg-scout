"""Phase 0 spike: snapshot raw Labs Limitless pages into tests/fixtures/labs/.

Saves standings, per-round pairings, and a sample of per-player "Matches" pages
for one tournament (default Prague, labs_id 0062) so the pairings parser and the
record-delta winner reconstruction can be developed and tested OFFLINE.

Usage:
    python scripts/snapshot_labs_fixtures.py [LABS_ID]

Reuses LabsLimitlessClient (20 RPM, retries). One-off developer tool; not part of
the production pipeline.
"""

import re
import sys
from pathlib import Path

from scraper.labs_limitless import LABS_STANDINGS_URL, LabsLimitlessClient

FIXTURE_ROOT = Path(__file__).parent.parent / "tests" / "fixtures" / "labs"
MAX_ROUNDS = 20
SAMPLE_PLAYER_PAGES = 8  # per-player Matches pages to snapshot for delta validation


def _save(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"  wrote {path.relative_to(FIXTURE_ROOT.parent.parent)} ({len(text):,} bytes)")


def main(labs_id: str) -> None:
    out = FIXTURE_ROOT / labs_id
    client = LabsLimitlessClient()
    try:
        # 1. Standings (truth for final records + player roster)
        standings_url = f"{LABS_STANDINGS_URL}/{labs_id}/standings"
        print(f"standings: {standings_url}")
        standings_html = client._get(standings_url).text
        _save(out / "standings.html", standings_html)

        # Player IDs in standing order (top finishers first) for sample Matches pages.
        player_ids: list[str] = []
        for m in re.finditer(rf"/{labs_id}/player/(\d+)\b", standings_html):
            pid = m.group(1)
            if pid not in player_ids:
                player_ids.append(pid)

        # 2. Per-round pairings until a round has no standings/pairings table.
        for rnd in range(1, MAX_ROUNDS + 1):
            url = f"{LABS_STANDINGS_URL}/{labs_id}/pairings?round={rnd}"
            try:
                html = client._get(url).text
            except Exception as exc:  # noqa: BLE001 - spike tool, log and stop
                print(f"  round {rnd}: stop ({exc})")
                break
            # Heuristic: a real round page has player links; an out-of-range round won't.
            if f"/{labs_id}/player/" not in html:
                print(f"  round {rnd}: no player links, assuming past final round")
                break
            _save(out / f"pairings_round_{rnd:02d}.html", html)

        # 3. Sample per-player Matches pages (truth for winner reconstruction check).
        for pid in player_ids[:SAMPLE_PLAYER_PAGES]:
            url = f"{LABS_STANDINGS_URL}/{labs_id}/player/{pid}"
            try:
                html = client._get(url).text
            except Exception as exc:  # noqa: BLE001
                print(f"  player {pid}: skip ({exc})")
                continue
            _save(out / f"player_{pid}.html", html)

        print(f"\nDone. Fixtures in {out}")
        print(f"Found {len(player_ids)} unique player ids in standings.")
    finally:
        client.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "0062")
