#!/usr/bin/env python3
"""Probe players.pokemon-card.com API to find Osaka CL 2026 event IDs.

Based on the pattern:
  Yokohama (Sep 2025): ~795978-795984
  Aichi (Dec 2025):    ~849961-849967
  Fukuoka (Feb 2026):  ~903701-903703
  Osaka (Mar 2026):    ~950000-960000 (estimated)

Uses the event_result_detail_search endpoint which returns event metadata
including the event title when results exist.
"""

import sys
import time

import httpx

BASE_URL = "https://players.pokemon-card.com"


def probe_event(client: httpx.Client, event_id: int) -> dict | None:
    """Check if an event ID has published results."""
    try:
        resp = client.get(
            f"{BASE_URL}/event_result_detail_search",
            params={
                "event_holding_id": event_id,
                "offset": 0,
                "per_page": 1,
            },
        )
        data = resp.json()
        if data.get("code") == 200 and data.get("count", 0) > 0:
            event_info = data.get("event", {})
            return {
                "event_id": event_id,
                "title": event_info.get("event_title", ""),
                "date": event_info.get("event_date_params", ""),
                "count": data.get("count", 0),
            }
    except Exception as e:
        print(f"  Error probing {event_id}: {e}", file=sys.stderr)
    return None


def main():
    # Scan ranges based on the ~54K gap pattern
    # Fukuoka was 903701-903703, so Osaka is likely ~957,000-958,000
    # But let's cast a wider net
    # Search specifically for CL events containing "チャンピオンズ" or "大阪"
    # Try a focused scan around known CL event ranges
    ranges = [
        (903700, 904000, 1),  # Near Fukuoka
        (904000, 910000, 50),  # Slightly above
        (910000, 930000, 100),  # Medium range
    ]

    found = []

    with httpx.Client(timeout=10) as client:
        for start, end, step in ranges:
            print(f"\nScanning {start}-{end} (step {step})...")
            for event_id in range(start, end, step):
                result = probe_event(client, event_id)
                if result:
                    title = result["title"]
                    print(
                        f"  FOUND: {event_id} -> {title} ({result['count']} results, date={result['date']})"
                    )
                    found.append(result)
                    # If we found a CL event, do a fine-grained scan around it
                    if "チャンピオンズ" in title or "大阪" in title:
                        print(f"  -> Fine scanning {event_id - 50} to {event_id + 50}...")
                        for fine_id in range(event_id - 50, event_id + 50):
                            if fine_id == event_id:
                                continue
                            fine_result = probe_event(client, fine_id)
                            if fine_result:
                                print(
                                    f"  FOUND: {fine_id} -> {fine_result['title']} ({fine_result['count']} results)"
                                )
                                found.append(fine_result)
                time.sleep(0.05)  # Be respectful

    if found:
        print("\n=== FOUND EVENTS ===")
        for f in found:
            print(f"  ID={f['event_id']}  title={f['title']}  date={f['date']}  count={f['count']}")
    else:
        print("\nNo events found in scanned ranges.")
        print("Results may not be published yet. Try again later.")
        print("\nAlternative: try broader ranges or check mt.matrix.jp/decklist/")


if __name__ == "__main__":
    main()
