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
TOKEN_SECRET = 'account.harnessoauthaccesstoken_github_1784959546428'


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
            ("RestoreCache", "restore_dbs"),
            ("RestoreCache", "restore_export"),
            ("Run", "bootstrap"),
            ("Run", "scrape"),
            ("Run", "validate"),
            ("SaveCache", "save_dbs"),
            ("SaveCache", "save_export"),
            ("Run", "publish"),
        ]

    def test_cache_keys_match_between_restore_and_save(self):
        by_id = {s["identifier"]: s["spec"] for s in self.steps}
        assert by_id["restore_dbs"]["key"] == by_id["save_dbs"]["key"] == "scout-dbs"
        assert by_id["restore_export"]["key"] == by_id["save_export"]["key"] == "scout-export"
        assert by_id["save_dbs"]["sourcePaths"] == ["data"]
        assert by_id["save_export"]["sourcePaths"] == ["web/public/data"]
        for name in ("save_dbs", "save_export"):
            assert by_id[name]["override"] is True, f"{name} must replace the previous cache"
        for name in ("restore_dbs", "restore_export"):
            assert by_id[name]["failIfKeyDoesntExist"] is False, "first run has no cache"

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
