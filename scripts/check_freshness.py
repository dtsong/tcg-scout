#!/usr/bin/env python3
"""Check data freshness and alert via Discord webhook if stale.

Usage:
    DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/... python scripts/check_freshness.py

Reads freshness from the public GCS archive's Last-Modified header so we
measure the real pipeline (Cloud Build -> GCS) rather than the in-repo
manifest, which can lag if the post-scrape git push fails.

Uses only stdlib — no pip install required.
"""

import json
import os
import sys
import urllib.request
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

STALE_HOURS = 72
DATA_ARCHIVE_URL = "https://storage.googleapis.com/tcg-scout-data/data-latest.tar.gz"


def get_latest_snapshot_date() -> datetime | None:
    """HEAD the public GCS archive and parse its Last-Modified header."""
    req = urllib.request.Request(DATA_ARCHIVE_URL, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            last_modified = resp.headers.get("Last-Modified")
            if not last_modified:
                return None
            return parsedate_to_datetime(last_modified).astimezone(UTC)
    except (OSError, ValueError) as exc:
        print(f"WARNING: Could not fetch Last-Modified from {DATA_ARCHIVE_URL}: {exc}")
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
            f"Cannot HEAD {DATA_ARCHIVE_URL}. "
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
