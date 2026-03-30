#!/usr/bin/env python3
"""Check data freshness and alert via Discord webhook if stale.

Usage:
    DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/... python scripts/check_freshness.py

Uses only stdlib — no pip install required.
"""

import json
import os
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

STALE_HOURS = 72
MANIFEST_PATH = Path(__file__).parent.parent / "web" / "data-manifest.json"


def get_latest_snapshot_date() -> datetime | None:
    """Read the latest snapshot date from data-manifest.json's created_at field."""
    if not MANIFEST_PATH.exists():
        return None

    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        archives = manifest.get("archives", [])
        if not archives:
            return None
        created_at = archives[0].get("created_at")
        if created_at:
            return datetime.strptime(created_at, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except (json.JSONDecodeError, OSError, ValueError, KeyError) as exc:
        print(f"WARNING: Could not parse created_at from data-manifest.json: {exc}")

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
            "Cannot read data-manifest.json. "
            "Data pipeline may not have run."
        )
        return 1

    # Ensure timezone-aware comparison
    if snapshot_date.tzinfo is None:
        snapshot_date = snapshot_date.replace(tzinfo=UTC)

    age_hours = (now - snapshot_date).total_seconds() / 3600

    if age_hours > STALE_HOURS:
        send_discord_alert(
            f"**Scout Freshness Alert**\n"
            f"Data is {age_hours:.0f}h old (threshold: {STALE_HOURS}h).\n"
            f"Last export: {snapshot_date.strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Check Cloud Build for pipeline failures."
        )
        return 1

    print(f"Data is fresh: {age_hours:.0f}h old (threshold: {STALE_HOURS}h)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
