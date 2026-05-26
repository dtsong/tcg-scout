"""Phase 0 spike: probe the structure of snapshotted Labs fixtures (offline)."""

import json
import re
from pathlib import Path

FIX = Path(__file__).parent.parent / "tests" / "fixtures" / "labs" / "0062"
SERVER_DATA_RE = re.compile(r'<script[^>]*>(\{"status":\s*200[^<]+?\})</script>')


def server_blobs(html: str):
    """Yield decoded inner payloads from SvelteKit server-data <script> blobs."""
    for raw in SERVER_DATA_RE.findall(html):
        try:
            outer = json.loads(raw)
            body = outer.get("body")
            inner = json.loads(body) if isinstance(body, str) else None
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(inner, dict):
            yield inner


def summarize(label: str, html: str) -> None:
    print(f"\n===== {label} =====")
    print(f"size={len(html):,}  server_data_blobs={len(SERVER_DATA_RE.findall(html))}")
    print(f"has <table>: {'<table' in html}")
    for i, inner in enumerate(server_blobs(html)):
        msg = inner.get("message")
        print(f"  blob[{i}] top-keys={list(inner.keys())}")
        if isinstance(msg, dict):
            print(f"    message keys={list(msg.keys())}")
            for k, v in msg.items():
                if isinstance(v, list):
                    print(
                        f"      {k}: list[{len(v)}]"
                        + (f" sample={json.dumps(v[0])[:300]}" if v else "")
                    )
                elif isinstance(v, dict):
                    print(f"      {k}: dict keys={list(v.keys())[:12]}")
                else:
                    print(f"      {k}: {json.dumps(v)[:120]}")
        elif isinstance(msg, list):
            print(f"    message: list[{len(msg)}] sample={json.dumps(msg[0])[:400] if msg else ''}")


def main() -> None:
    summarize("pairings round 1", (FIX / "pairings_round_01.html").read_text())
    summarize("pairings round 17 (top cut)", (FIX / "pairings_round_17.html").read_text())
    # First available player page
    player = sorted(FIX.glob("player_*.html"))[0]
    summarize(f"player page {player.name}", player.read_text())


if __name__ == "__main__":
    main()
