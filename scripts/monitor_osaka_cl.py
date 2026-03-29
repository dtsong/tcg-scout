#!/usr/bin/env python3
"""Monitor for Osaka CL 2026 official results on players.pokemon-card.com.

Checks the API periodically for new Champions League event IDs.
Also re-scrapes pokekameshi for updated community results.

Usage:
    python scripts/monitor_osaka_cl.py                # One-shot check
    python scripts/monitor_osaka_cl.py --watch 300    # Poll every 5 minutes
"""

import argparse
import json
import logging
import time
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://players.pokemon-card.com"

# Known latest City League ID as of 2026-03-29
LAST_KNOWN_CL_ID = 952988
# Scan range above the last known City League event
SCAN_START = LAST_KNOWN_CL_ID + 1
SCAN_END = SCAN_START + 2000
SCAN_STEP = 1

# pokekameshi page counts from last scrape
LAST_COUNTS = {"masters": 19, "seniors": 17, "juniors": 4}

STATE_FILE = Path("data/osaka-cl/monitor-state.json")


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_scan_end": SCAN_START, "found_cl_ids": [], "pokekameshi_counts": LAST_COUNTS}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def probe_api(start: int, end: int, step: int = 1) -> list[dict]:
    """Probe the API for Champions League events."""
    found = []
    with httpx.Client(timeout=10) as client:
        for eid in range(start, end, step):
            try:
                resp = client.get(
                    f"{BASE_URL}/event_result_detail_search",
                    params={"event_holding_id": eid, "offset": 0, "per_page": 1},
                )
                data = resp.json()
                if data.get("code") == 200 and data.get("count", 0) > 0:
                    event = data.get("event", {})
                    title = event.get("event_title", "")
                    # Check if this is a Champions League event (not City League)
                    if "チャンピオンズ" in title or "大阪" in title:
                        found.append(
                            {
                                "event_id": eid,
                                "title": title,
                                "count": data.get("count", 0),
                            }
                        )
                        logger.info(
                            "CHAMPIONS LEAGUE FOUND: %d -> %s (%d results)",
                            eid,
                            title,
                            data["count"],
                        )
            except Exception:
                pass
            time.sleep(0.02)
    return found


def check_pokekameshi() -> dict[str, int]:
    """Check pokekameshi for updated entry counts (requires Playwright)."""
    try:
        import asyncio

        from playwright.async_api import async_playwright

        async def _count():
            counts = {}
            urls = {
                "masters": "https://pokekameshi.com/cl2026osaka/",
                "seniors": "https://pokekameshi.com/cl2026osaka-senior/",
                "juniors": "https://pokekameshi.com/cl2026osaka-junior/",
            }
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                page = await browser.new_page()
                for div, url in urls.items():
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(3)
                        count = await page.evaluate("""() => {
                            return document.querySelectorAll('a[href*="pokemon-card.com/deck/confirm"]').length;
                        }""")
                        counts[div] = count
                    except Exception as e:
                        logger.warning("Failed to check %s: %s", div, e)
                        counts[div] = -1
                await browser.close()
            return counts

        return asyncio.run(_count())
    except ImportError:
        logger.warning("Playwright not available, skipping pokekameshi check")
        return {}


def run_check(state: dict) -> bool:
    """Run one check cycle. Returns True if new data was found."""
    changes = False

    # 1. Probe official API for Champions League events
    scan_start = state.get("last_scan_end", SCAN_START)
    scan_end = scan_start + 2000
    logger.info("Probing official API: %d-%d", scan_start, scan_end)
    cl_events = probe_api(scan_start, scan_end)
    state["last_scan_end"] = scan_end

    if cl_events:
        logger.info("*** NEW CHAMPIONS LEAGUE EVENTS FOUND! ***")
        for ev in cl_events:
            logger.info("  ID=%d  title=%s  count=%d", ev["event_id"], ev["title"], ev["count"])
        state.setdefault("found_cl_ids", []).extend(cl_events)
        changes = True

        # Print the scrape command
        ids = " ".join(str(ev["event_id"]) for ev in cl_events)
        logger.info("\nRun this to scrape:")
        logger.info("  scout --format ninja-spinner champions %s --fetch-decklists --top 64", ids)
    else:
        logger.info("No Champions League events found in API (IDs %d-%d)", scan_start, scan_end)

    # 2. Check pokekameshi for updated counts
    logger.info("Checking pokekameshi for updates...")
    new_counts = check_pokekameshi()
    old_counts = state.get("pokekameshi_counts", LAST_COUNTS)

    for div, count in new_counts.items():
        if count < 0:
            continue
        old = old_counts.get(div, 0)
        if count > old:
            logger.info("*** pokekameshi %s: %d -> %d entries (NEW DATA!) ***", div, old, count)
            changes = True
        else:
            logger.info("pokekameshi %s: %d entries (unchanged)", div, count)

    if new_counts:
        state["pokekameshi_counts"] = {k: v for k, v in new_counts.items() if v >= 0}

    save_state(state)
    return changes


def main():
    parser = argparse.ArgumentParser(description="Monitor for Osaka CL 2026 results")
    parser.add_argument("--watch", type=int, metavar="SECONDS", help="Poll interval in seconds")
    parser.add_argument("--reset", action="store_true", help="Reset monitoring state")
    args = parser.parse_args()

    if args.reset:
        STATE_FILE.unlink(missing_ok=True)
        logger.info("State reset.")

    state = load_state()

    if args.watch:
        logger.info("Monitoring every %d seconds. Press Ctrl+C to stop.", args.watch)
        try:
            while True:
                found = run_check(state)
                if found:
                    logger.info("=== NEW DATA DETECTED! Check above for details. ===")
                logger.info("Next check in %d seconds...\n", args.watch)
                time.sleep(args.watch)
        except KeyboardInterrupt:
            logger.info("\nStopping monitor.")
    else:
        run_check(state)


if __name__ == "__main__":
    main()
