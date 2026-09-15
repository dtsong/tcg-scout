#!/usr/bin/env python3
"""Check data freshness and alert via Discord webhook if stale.

Usage:
    DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/... python scripts/check_freshness.py

Reads freshness from ``web/data-manifest.json`` on main, which the Harness
``scout_scrape`` pipeline rewrites and commits only after the release tarball
is uploaded, so the manifest's ``created_at`` stamp is the last successful run.

Uses only stdlib, so no pip install is required.
"""

import json
import os
import sys
import urllib.request
from datetime import UTC, datetime

STALE_HOURS = 72
MANIFEST_URL = "https://raw.githubusercontent.com/dtsong/tcg-scout/main/web/data-manifest.json"
STAMP_FORMAT = "%Y%m%dT%H%M%SZ"


def get_latest_snapshot_date() -> datetime | None:
    """Fetch the manifest on main and parse the newest archive's created_at stamp."""
    req = urllib.request.Request(MANIFEST_URL, headers={"Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            manifest = json.load(resp)
        stamps = [a["created_at"] for a in manifest.get("archives", []) if a.get("created_at")]
        if not stamps:
            return None
        return datetime.strptime(max(stamps), STAMP_FORMAT).replace(tzinfo=UTC)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"WARNING: Could not read {MANIFEST_URL}: {exc}")
        return None


def send_discord_alert(message: str) -> None:
    """Send an alert to Discord via webhook."""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("DISCORD_WEBHOOK_URL not set, printing to stdout instead")
        print(message)
        return

    payload = json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req)
    except Exception as exc:
        print(f"WARNING: Failed to send Discord alert: {exc}")
        print(f"Alert message was: {message}")


def main() -> int:
    now = datetime.now(UTC)
    snapshot_date = get_latest_snapshot_date()

    if snapshot_date is None:
        send_discord_alert(
            "**Scout Freshness Alert**\n"
            f"Cannot read {MANIFEST_URL}. "
            "Data pipeline may not have run."
        )
        return 1

    age_hours = (now - snapshot_date).total_seconds() / 3600

    if age_hours > STALE_HOURS:
        send_discord_alert(
            f"**Scout Freshness Alert**\n"
            f"Data is {age_hours:.0f}h old (threshold: {STALE_HOURS}h).\n"
            f"Last export: {snapshot_date.strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Check the Harness scout_scrape pipeline for failures."
        )
        return 1

    print(f"Data is fresh: {age_hours:.0f}h old (threshold: {STALE_HOURS}h)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
