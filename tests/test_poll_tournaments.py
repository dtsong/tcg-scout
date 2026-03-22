"""Tests for the poll_tournaments Cloud Function."""

import json
from unittest.mock import MagicMock, patch

import pytest

MODULE = "functions.poll_tournaments.main"


@pytest.fixture(autouse=True)
def _env_vars(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT", "test-project")
    monkeypatch.setenv("CACHE_BUCKET", "test-bucket")
    monkeypatch.setenv("STATE_FILE", "poll-state.json")
    monkeypatch.setenv("CLOUDBUILD_CONFIG", "cloudbuild-scrape.yaml")
    monkeypatch.setenv("REPO_OWNER", "dtsong")
    monkeypatch.setenv("REPO_NAME", "tcg-scout")
    monkeypatch.setenv("BRANCH", "main")


def _jp_api_response(event_ids: list[int]) -> dict:
    return {
        "code": 200,
        "event": [{"event_holding_id": eid} for eid in event_ids],
        "eventCount": len(event_ids),
    }


class TestFetchRecentEventIds:
    def test_returns_event_ids(self):
        from functions.poll_tournaments.main import fetch_recent_event_ids

        mock_resp = MagicMock()
        mock_resp.json.return_value = _jp_api_response([100, 200, 300])
        mock_resp.raise_for_status = MagicMock()

        with patch(f"{MODULE}.httpx.Client") as mock_httpx:
            mock_client = MagicMock()
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_resp

            result = fetch_recent_event_ids()
            assert result == {100, 200, 300}

    def test_returns_empty_on_api_error_code(self):
        from functions.poll_tournaments.main import fetch_recent_event_ids

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 500}
        mock_resp.raise_for_status = MagicMock()

        with patch(f"{MODULE}.httpx.Client") as mock_httpx:
            mock_client = MagicMock()
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_resp

            assert fetch_recent_event_ids() == set()

    def test_returns_empty_on_no_events(self):
        from functions.poll_tournaments.main import fetch_recent_event_ids

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 200, "event": [], "eventCount": 0}
        mock_resp.raise_for_status = MagicMock()

        with patch(f"{MODULE}.httpx.Client") as mock_httpx:
            mock_client = MagicMock()
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_resp

            assert fetch_recent_event_ids() == set()


class TestLoadState:
    def test_returns_default_when_no_state(self):
        from functions.poll_tournaments.main import load_state

        mock_blob = MagicMock()
        mock_blob.exists.return_value = False
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        state = load_state(mock_client)
        assert state["known_event_ids"] == []
        assert state["last_poll"] is None

    def test_loads_existing_state(self):
        from functions.poll_tournaments.main import load_state

        existing = {
            "known_event_ids": [100, 200],
            "last_poll": "2026-03-22T00:00:00",
            "last_trigger": None,
        }
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_blob.download_as_text.return_value = json.dumps(existing)
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        state = load_state(mock_client)
        assert state["known_event_ids"] == [100, 200]


class TestPollTournaments:
    @patch(f"{MODULE}.trigger_cloud_build")
    @patch(f"{MODULE}.save_state")
    @patch(f"{MODULE}.load_state")
    @patch(f"{MODULE}.fetch_recent_event_ids")
    @patch(f"{MODULE}.storage")
    def test_no_new_events_skips_trigger(
        self, mock_storage, mock_fetch, mock_load, mock_save, mock_trigger
    ):
        from functions.poll_tournaments.main import poll_tournaments

        mock_fetch.return_value = {100, 200}
        mock_load.return_value = {
            "known_event_ids": [100, 200],
            "last_poll": None,
            "last_trigger": None,
        }

        response, status = poll_tournaments(MagicMock())

        assert status == 200
        assert response["status"] == "no_new_events"
        mock_trigger.assert_not_called()

    @patch(f"{MODULE}.trigger_cloud_build")
    @patch(f"{MODULE}.save_state")
    @patch(f"{MODULE}.load_state")
    @patch(f"{MODULE}.fetch_recent_event_ids")
    @patch(f"{MODULE}.storage")
    def test_new_events_triggers_build(
        self, mock_storage, mock_fetch, mock_load, mock_save, mock_trigger
    ):
        from functions.poll_tournaments.main import poll_tournaments

        mock_fetch.return_value = {100, 200, 300}
        mock_load.return_value = {
            "known_event_ids": [100, 200],
            "last_poll": None,
            "last_trigger": None,
        }
        mock_trigger.return_value = "build-abc"

        response, status = poll_tournaments(MagicMock())

        assert status == 200
        assert response["status"] == "triggered"
        assert response["new_events"] == 1
        assert 300 in response["new_event_ids"]
        mock_trigger.assert_called_once_with("test-project")

    @patch(f"{MODULE}.trigger_cloud_build")
    @patch(f"{MODULE}.save_state")
    @patch(f"{MODULE}.load_state")
    @patch(f"{MODULE}.fetch_recent_event_ids")
    @patch(f"{MODULE}.storage")
    def test_fresh_state_triggers_on_first_run(
        self, mock_storage, mock_fetch, mock_load, mock_save, mock_trigger
    ):
        from functions.poll_tournaments.main import poll_tournaments

        mock_fetch.return_value = {100, 200}
        mock_load.return_value = {"known_event_ids": [], "last_poll": None, "last_trigger": None}
        mock_trigger.return_value = "build-first"

        response, status = poll_tournaments(MagicMock())

        assert status == 200
        assert response["status"] == "triggered"
        assert response["new_events"] == 2
        mock_trigger.assert_called_once()

    @patch(f"{MODULE}.fetch_recent_event_ids")
    def test_api_failure_returns_502(self, mock_fetch):
        from functions.poll_tournaments.main import poll_tournaments

        mock_fetch.side_effect = Exception("Connection timeout")

        response, status = poll_tournaments(MagicMock())

        assert status == 502
        assert "error" in response

    @patch(f"{MODULE}.trigger_cloud_build")
    @patch(f"{MODULE}.save_state")
    @patch(f"{MODULE}.load_state")
    @patch(f"{MODULE}.fetch_recent_event_ids")
    @patch(f"{MODULE}.storage")
    def test_build_trigger_failure_returns_500(
        self, mock_storage, mock_fetch, mock_load, mock_save, mock_trigger
    ):
        from functions.poll_tournaments.main import poll_tournaments

        mock_fetch.return_value = {100, 200, 300}
        mock_load.return_value = {
            "known_event_ids": [100, 200],
            "last_poll": None,
            "last_trigger": None,
        }
        mock_trigger.side_effect = Exception("Cloud Build unavailable")

        response, status = poll_tournaments(MagicMock())

        assert status == 500
        assert response["status"] == "trigger_failed"

    @patch(f"{MODULE}.save_state")
    @patch(f"{MODULE}.load_state")
    @patch(f"{MODULE}.fetch_recent_event_ids")
    @patch(f"{MODULE}.storage")
    def test_empty_api_response(self, mock_storage, mock_fetch, mock_load, mock_save):
        from functions.poll_tournaments.main import poll_tournaments

        mock_fetch.return_value = set()

        response, status = poll_tournaments(MagicMock())

        assert status == 200
        assert response["status"] == "no_events"
        mock_load.assert_not_called()
