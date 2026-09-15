"""Guards for the Harness pipeline and trigger YAML under .harness/.

The YAML is the source of truth (applied through the Harness MCP tools), so
these tests pin the shape the runbook depends on: literal identifiers, step
order, cache keys, the branch guard on the publish step, no hard-coded format
slugs, and no plain-text secrets.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from cli import cli
from config import FORMATS, format_region

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS = REPO_ROOT / ".harness"
CODEBASE_CONNECTOR = "account.Github_OAuth_1784959546725"
TOKEN_SECRET = "account.harnessoauthaccesstoken_github_1784959546428"


def _load(relative: str) -> dict:
    return yaml.safe_load((HARNESS / relative).read_text(encoding="utf-8"))


def _steps(pipeline: dict) -> list[dict]:
    stages = pipeline["pipeline"]["stages"]
    assert len(stages) == 1, "one CI stage keeps the credit math simple"
    return [s["step"] for s in stages[0]["stage"]["spec"]["execution"]["steps"]]


def _run_commands(steps: list[dict]) -> str:
    return "\n".join(s["spec"]["command"] for s in steps if s["type"] == "Run")


class TestScrapePipeline:
    @classmethod
    def setup_class(cls):
        cls.doc = _load("pipelines/scrape.yaml")
        cls.pipeline = cls.doc["pipeline"]
        cls.steps = _steps(cls.doc)

    def test_identity_and_codebase(self):
        assert self.pipeline["identifier"] == "scout_scrape"
        assert self.pipeline["projectIdentifier"] == "default_project"
        assert self.pipeline["orgIdentifier"] == "default"
        codebase = self.pipeline["properties"]["ci"]["codebase"]
        assert codebase["connectorRef"] == CODEBASE_CONNECTOR
        assert codebase["repoName"] == "dtsong/tcg-scout"

    def test_runs_on_harness_cloud_linux(self):
        stage = self.pipeline["stages"][0]["stage"]["spec"]
        assert stage["runtime"]["type"] == "Cloud"
        assert stage["platform"] == {"os": "Linux", "arch": "Amd64"}

    def test_step_order(self):
        assert [(s["type"], s["identifier"]) for s in self.steps] == [
            ("Run", "bootstrap"),
            ("Run", "scrape"),
            ("Run", "validate"),
            ("Run", "publish"),
            ("Run", "discard_state"),
        ]

    def test_state_rides_cache_intelligence(self):
        """Harness Cloud has no bucket connector, so stage-level caching holds the state."""
        caching = self.pipeline["stages"][0]["stage"]["spec"]["caching"]
        assert caching["enabled"] is True
        assert caching["key"] == "scout-state", "a fixed key so every run restores the last one"
        assert caching["override"] is True, "each run must replace the previous state"
        assert "/harness/data" in caching["paths"]
        assert "/harness/web/public/data" in caching["paths"]

    def test_failed_run_discards_cached_state(self):
        discard = self.steps[-1]
        assert discard["when"] == {"stageStatus": "Failure"}
        assert "rm -rf data web/public/data" in discard["spec"]["command"]
        publish = next(s for s in self.steps if s["identifier"] == "publish")
        assert "when" not in publish, "publish runs only on the default (success) path"

    def test_scrape_step_derives_formats_from_config_not_literals(self):
        scrape = next(s for s in self.steps if s["identifier"] == "scrape")
        command = scrape["spec"]["command"]
        assert "formats-list --status active --region jp" in command
        assert "formats-list --status active" in command
        assert "formats-list --status frozen" in command
        for slug in FORMATS:
            assert slug not in command, f"{slug} is hard-coded; use formats-list"
        assert scrape["timeout"] == "45m"

    def test_publish_step_guards_on_main_and_uses_the_account_secret(self):
        publish = next(s for s in self.steps if s["identifier"] == "publish")
        env = publish["spec"]["envVariables"]
        assert env["GITHUB_TOKEN"] == f'<+secrets.getValue("{TOKEN_SECRET}")>'
        assert env["BRANCH"] == "<+codebase.branch>"
        command = publish["spec"]["command"]
        assert 'if [ "$BRANCH" != "main" ]' in command
        assert "publish_data_release.py publish" in command
        assert "git add web/data-manifest.json" in command
        assert "HEAD:main" in command

    def test_bootstrap_restores_before_scraping(self):
        bootstrap = next(s for s in self.steps if s["identifier"] == "bootstrap")
        assert "publish_data_release.py restore" in bootstrap["spec"]["command"]
        assert "GITHUB_TOKEN" in bootstrap["spec"]["envVariables"]

    def test_restore_from_release_flag_drops_cached_state_first(self):
        variables = {v["name"]: v for v in self.pipeline["variables"]}
        assert variables["restore_from_release"]["value"] == "<+input>.default(false)"
        bootstrap = next(s for s in self.steps if s["identifier"] == "bootstrap")
        env = bootstrap["spec"]["envVariables"]
        assert env["RESTORE_FROM_RELEASE"] == "<+pipeline.variables.restore_from_release>"
        command = bootstrap["spec"]["command"]
        assert 'if [ "$RESTORE_FROM_RELEASE" = "true" ]' in command
        assert command.index("rm -rf data web/public/data") < command.index(
            "publish_data_release.py restore"
        )

    def test_no_plain_text_secrets(self):
        text = (HARNESS / "pipelines" / "scrape.yaml").read_text(encoding="utf-8")
        for marker in ("ghp_", "gho_", "ghs_", "github_pat_", "pat."):
            assert marker not in text


class TestScrapeTrigger:
    def test_daily_cron_on_main(self):
        trigger = _load("triggers/scrape-cron.yaml")["trigger"]
        assert trigger["identifier"] == "scout_scrape_daily"
        assert trigger["pipelineIdentifier"] == "scout_scrape"
        assert trigger["enabled"] is True
        assert trigger["source"]["type"] == "Scheduled"
        assert trigger["source"]["spec"]["spec"]["expression"] == "0 6 * * *"
        inputs = yaml.safe_load(trigger["inputYaml"])
        assert inputs["pipeline"]["properties"]["ci"]["codebase"]["build"] == {
            "type": "branch",
            "spec": {"branch": "main"},
        }
        assert inputs["pipeline"]["variables"] == [
            {"name": "restore_from_release", "type": "String", "value": "false"}
        ]


class TestFormatsListRegion:
    def test_region_filter_returns_only_jp_active_formats(self):
        result = CliRunner().invoke(cli, ["formats-list", "--status", "active", "--region", "jp"])
        assert result.exit_code == 0, result.output
        slugs = result.output.split()
        assert slugs, "at least one active JP format is expected during a season"
        assert all(format_region(s) == "jp" for s in slugs)
        assert "tpci-standard-2027" not in slugs

    def test_region_defaults_to_all(self):
        result = CliRunner().invoke(cli, ["formats-list"])
        assert result.output.split() == list(FORMATS)


class TestVerifyPipeline:
    @classmethod
    def setup_class(cls):
        cls.doc = _load("pipelines/verify.yaml")
        cls.pipeline = cls.doc["pipeline"]
        cls.steps = _steps(cls.doc)

    def test_identity_and_codebase(self):
        assert self.pipeline["identifier"] == "scout_verify"
        codebase = self.pipeline["properties"]["ci"]["codebase"]
        assert codebase["connectorRef"] == CODEBASE_CONNECTOR
        assert codebase["repoName"] == "dtsong/tcg-scout"

    def test_python_and_web_gates(self):
        assert [s["identifier"] for s in self.steps] == ["python", "web"]
        python = self.steps[0]["spec"]["command"]
        for gate in ("uv sync --locked", "ruff check .", "ruff format --check .", "pytest tests/"):
            assert gate in python, gate
        web = self.steps[1]["spec"]["command"]
        for gate in ("npm ci", "tsc --noEmit", "eslint . --quiet", "vitest run"):
            assert gate in web, gate

    def test_playwright_is_not_run_on_harness(self):
        """e2e would blow the free-tier credit budget; see the spec's budget table."""
        assert "playwright" not in _run_commands(self.steps).lower()

    def test_no_secrets_needed(self):
        assert "secrets.getValue" not in (HARNESS / "pipelines" / "verify.yaml").read_text()

    def test_dependency_cache_keyed_on_lockfiles(self):
        caching = self.pipeline["stages"][0]["stage"]["spec"]["caching"]
        assert caching["enabled"] is True
        assert 'checksum "uv.lock"' in caching["key"]
        assert 'checksum "web/package-lock.json"' in caching["key"]


def test_step_names_are_harness_safe():
    """Harness rejects step names containing commas or other punctuation."""
    import re

    for name in ("scrape.yaml", "verify.yaml"):
        for step in _steps(_load(f"pipelines/{name}")):
            assert re.fullmatch(r"[a-zA-Z_][-0-9a-zA-Z_\s]{0,127}", step["name"]), step["name"]


class TestVerifyTrigger:
    def test_push_to_main_aborts_previous(self):
        trigger = _load("triggers/verify-on-push.yaml")["trigger"]
        assert trigger["identifier"] == "scout_verify_on_push"
        assert trigger["pipelineIdentifier"] == "scout_verify"
        assert trigger["enabled"] is True
        webhook = trigger["source"]["spec"]
        assert webhook["type"] == "Github"
        assert webhook["spec"]["type"] == "Push"
        assert webhook["spec"]["spec"]["connectorRef"] == CODEBASE_CONNECTOR
        assert webhook["spec"]["spec"]["autoAbortPreviousExecutions"] is True
        conditions = webhook["spec"]["spec"]["payloadConditions"]
        assert {"key": "targetBranch", "operator": "Equals", "value": "main"} in conditions
