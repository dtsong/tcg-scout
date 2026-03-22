"""Cloud Function: poll JP City League API and trigger scrape on new tournaments.

Designed to run every 2 hours during JST 10:00-22:00 via Cloud Scheduler.
Checks the JP API for new tournament results, and only triggers the full
Cloud Build scrape pipeline when new data is detected.

State is persisted in GCS as a small JSON file to track known event IDs.
"""

import json
import logging
import os
from datetime import UTC, datetime

import functions_framework
import httpx
from google.cloud import storage
from google.cloud.devtools import cloudbuild_v1 as build_v1

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Configuration via environment variables
PROJECT_ID = os.environ.get("GCP_PROJECT", "trainerlab-prod")
CACHE_BUCKET = os.environ.get("CACHE_BUCKET", "tcg-scout-cache")
STATE_FILE = os.environ.get("STATE_FILE", "poll-state.json")
TRIGGER_ID = os.environ.get("CLOUD_BUILD_TRIGGER_ID", "")
CLOUDBUILD_CONFIG = os.environ.get("CLOUDBUILD_CONFIG", "cloudbuild-scrape.yaml")
REPO_NAME = os.environ.get("REPO_NAME", "tcg-scout")
REPO_OWNER = os.environ.get("REPO_OWNER", "dtsong")
BRANCH = os.environ.get("BRANCH", "main")

# JP API constants
JP_API_BASE = "https://players.pokemon-card.com"
CITY_LEAGUE_EVENT_TYPES = ["3:1", "3:2", "3:3", "3:4", "3:5", "3:6", "3:7", "3:8"]


def fetch_recent_event_ids() -> set[int]:
    """Fetch the most recent City League event IDs from the JP API.

    Only fetches the first page (20 events, newest first) since we only
    need to detect new additions at the top of the list.
    """
    with httpx.Client(base_url=JP_API_BASE, timeout=15.0) as client:
        resp = client.get(
            "/event_search",
            params={
                "offset": 0,
                "order": 4,  # newest first
                "result_resist": 1,  # only events with results
                "event_type[]": CITY_LEAGUE_EVENT_TYPES,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if data.get("code") != 200:
        logger.warning("JP API returned code %s", data.get("code"))
        return set()

    events = data.get("event", [])
    return {e["event_holding_id"] for e in events if "event_holding_id" in e}


def load_state(storage_client: storage.Client) -> dict:
    """Load poll state from GCS."""
    bucket = storage_client.bucket(CACHE_BUCKET)
    blob = bucket.blob(STATE_FILE)

    if not blob.exists():
        logger.info("No existing state file, starting fresh")
        return {"known_event_ids": [], "last_poll": None, "last_trigger": None}

    return json.loads(blob.download_as_text())


def save_state(storage_client: storage.Client, state: dict) -> None:
    """Save poll state to GCS."""
    bucket = storage_client.bucket(CACHE_BUCKET)
    blob = bucket.blob(STATE_FILE)
    blob.upload_from_string(
        json.dumps(state, indent=2),
        content_type="application/json",
    )


def trigger_cloud_build(project_id: str) -> str:
    """Trigger the scrape Cloud Build pipeline.

    Returns the build ID if successful.
    """
    client = build_v1.CloudBuildClient()

    if TRIGGER_ID:
        # Use existing trigger
        request = build_v1.RunBuildTriggerRequest(
            project_id=project_id,
            trigger_id=TRIGGER_ID,
        )
        operation = client.run_build_trigger(request=request)
        build = operation.result()
        return build.id

    # Direct build submission from config
    build_config = build_v1.Build(
        source=build_v1.Source(
            repo_source=build_v1.RepoSource(
                project_id=project_id,
                repo_name=f"github_{REPO_OWNER}_{REPO_NAME}",
                branch_name=BRANCH,
            ),
        ),
        filename=CLOUDBUILD_CONFIG,
    )

    operation = client.create_build(project_id=project_id, build=build_config)
    build = operation.result(timeout=30)
    return build.id


@functions_framework.http
def poll_tournaments(request):
    """HTTP Cloud Function entry point.

    Called by Cloud Scheduler every 2 hours during JP peak hours.
    Returns JSON with poll results.
    """
    now = datetime.now(UTC).isoformat()

    try:
        current_ids = fetch_recent_event_ids()
    except Exception:
        logger.exception("Failed to fetch events from JP API")
        return ({"error": "JP API fetch failed"}, 502)

    if not current_ids:
        logger.warning("No events returned from JP API")
        return ({"status": "no_events", "polled_at": now}, 200)

    storage_client = storage.Client(project=PROJECT_ID)
    state = load_state(storage_client)
    known_ids = set(state.get("known_event_ids", []))

    new_ids = current_ids - known_ids
    state["last_poll"] = now

    if not new_ids:
        logger.info("No new events detected (%d known)", len(known_ids))
        save_state(storage_client, state)
        return (
            {
                "status": "no_new_events",
                "known_count": len(known_ids),
                "polled_at": now,
            },
            200,
        )

    logger.info("Detected %d new events: %s", len(new_ids), sorted(new_ids))

    # Update known IDs (keep union of old + current page)
    state["known_event_ids"] = sorted(known_ids | current_ids)
    state["last_trigger"] = now
    state["new_event_count"] = len(new_ids)
    save_state(storage_client, state)

    # Trigger the full scrape pipeline
    try:
        build_id = trigger_cloud_build(PROJECT_ID)
        logger.info("Triggered Cloud Build: %s", build_id)
    except Exception:
        logger.exception("Failed to trigger Cloud Build")
        return (
            {
                "status": "trigger_failed",
                "new_events": len(new_ids),
                "polled_at": now,
            },
            500,
        )

    return (
        {
            "status": "triggered",
            "new_events": len(new_ids),
            "new_event_ids": sorted(new_ids),
            "build_id": build_id,
            "polled_at": now,
        },
        200,
    )
