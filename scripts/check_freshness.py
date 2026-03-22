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
ACTIVE_FORMAT = "ninja-spinner"
DATA_DIR = Path(__file__).parent.parent / "web" / "public" / "data"


def get_latest_snapshot_date(format_slug: str) -> datetime | None:
    """Read the latest snapshot date from meta.json's generated_at field, falling back to file mtime."""
    meta_path = DATA_DIR / format_slug / "meta.json"
    if not meta_path.exists():
        return None

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        generated_at = meta.get("generated_at")
        if generated_at:
            return datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(
            f"WARNING: Could not parse generated_at from meta.json: {exc}, falling back to file mtime"
        )

    # Fallback: use file modification time
    try:
        mtime = meta_path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=UTC)
    except OSError as exc:
        print(f"WARNING: Could not stat meta.json: {exc}")
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
    snapshot_date = get_latest_snapshot_date(ACTIVE_FORMAT)

    if snapshot_date is None:
        send_discord_alert(
            f"**Scout Freshness Alert**\n"
            f"Cannot read meta.json for `{ACTIVE_FORMAT}`. "
            f"Data directory may be missing."
        )
        return 1

    # Ensure timezone-aware comparison
    if snapshot_date.tzinfo is None:
        snapshot_date = snapshot_date.replace(tzinfo=UTC)

    age_hours = (now - snapshot_date).total_seconds() / 3600

    if age_hours > STALE_HOURS:
        send_discord_alert(
            f"**Scout Freshness Alert**\n"
            f"Data for `{ACTIVE_FORMAT}` is {age_hours:.0f}h old "
            f"(threshold: {STALE_HOURS}h).\n"
            f"Last snapshot: {snapshot_date.strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Check Cloud Build for pipeline failures."
        )
        return 1

    print(f"Data is fresh: {age_hours:.0f}h old (threshold: {STALE_HOURS}h)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
