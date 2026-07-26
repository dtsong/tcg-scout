"""JP event naming/classification and pipeline format-partition invariants.

Covers the PJCS 2026 regression: national championships carry no shop_name, so
they were stored as "<prefecture> None" city-league rows.
"""

import re
from pathlib import Path

import pytest

from config import FORMATS, get_formats_by_status, is_format_frozen
from scraper.pokemon_jp_api import JPCityLeagueEvent, classify_jp_tournament_type

PJCS_TITLE = "ポケモンジャパンチャンピオンシップス2026 カードゲーム部門 マスターリーグ Day2"
CL_TITLE = "チャンピオンズリーグ2026 京都"

REPO_ROOT = Path(__file__).resolve().parent.parent


def _event(**overrides) -> JPCityLeagueEvent:
    base = {
        "event_id": 1,
        "date": "2026-06-07",
        "prefecture": "神奈川県",
        "store_name": "",
        "capacity": 0,
        "division": "open",
        "event_title": "",
    }
    return JPCityLeagueEvent(**{**base, **overrides})


class TestTournamentTypeClassification:
    @pytest.mark.parametrize("title", [PJCS_TITLE, CL_TITLE])
    def test_championship_titles(self, title):
        assert classify_jp_tournament_type(title) == "championship"

    @pytest.mark.parametrize("title", ["", "シティリーグ", "ジムバトル"])
    def test_non_championship_titles(self, title):
        assert classify_jp_tournament_type(title) == "city-league"


class TestDisplayName:
    def test_shop_event_uses_prefecture_and_shop(self):
        event = _event(store_name="トーナメントセンターバトロコ 高田馬場")
        assert event.display_name == "神奈川県 トーナメントセンターバトロコ 高田馬場"
        assert event.tournament_type == "city-league"

    def test_national_event_uses_official_title(self):
        """The regression: no shop -> must not render as '<prefecture> None'."""
        event = _event(event_title=PJCS_TITLE)
        assert event.display_name == PJCS_TITLE
        assert event.tournament_type == "championship"

    def test_no_shop_and_no_title_falls_back_to_prefecture(self):
        assert _event().display_name == "神奈川県"

    def test_no_identity_at_all_falls_back_to_date(self):
        assert _event(prefecture="").display_name == "City League 2026-06-07"


class TestFromApiNullHandling:
    def test_explicit_nulls_do_not_become_the_string_none(self):
        """`.get(k, "")` returns None when the key exists with a null value."""
        event = JPCityLeagueEvent.from_api(
            {
                "event_holding_id": 1032135,
                "event_date_params": "20260607",
                "prefecture_name": "神奈川県",
                "shop_name": None,
                "capacity": None,
                "leagueName": "マスター",
                "event_title": PJCS_TITLE,
            }
        )
        assert event.store_name == ""
        assert event.capacity == 0
        assert "None" not in event.display_name
        assert event.display_name == PJCS_TITLE
        assert event.tournament_type == "championship"
        assert event.division == "open"


class TestFormatPartition:
    def test_frozen_is_decided_by_dataset_end(self):
        assert is_format_frozen("nihil-zero", today="2026-07-26")
        assert not is_format_frozen("abyss-eye", today="2026-07-26")

    def test_partition_is_total_and_disjoint(self):
        frozen = set(get_formats_by_status(frozen=True, today="2026-07-26"))
        active = set(get_formats_by_status(frozen=False, today="2026-07-26"))
        assert frozen | active == set(FORMATS)
        assert not frozen & active

    def test_default_format_is_active(self):
        """A frozen DEFAULT_FORMAT silently points the pipeline at dead data."""
        from config import DEFAULT_FORMAT

        assert not is_format_frozen(DEFAULT_FORMAT)


class TestCloudBuildSubstitutionsMatchConfig:
    """cloudbuild-scrape.yaml duplicates the format partition as substitutions
    (gsutil steps cannot call Python). Guard against drift on rotation."""

    @staticmethod
    def _substitution(name: str) -> list[str]:
        text = (REPO_ROOT / "cloudbuild-scrape.yaml").read_text(encoding="utf-8")
        match = re.search(rf"^  {name}: (.+)$", text, re.MULTILINE)
        assert match, f"{name} missing from cloudbuild-scrape.yaml"
        return match.group(1).split()

    def test_frozen_formats_match_config(self):
        assert set(self._substitution("_FROZEN_FORMATS")) == set(get_formats_by_status(frozen=True))

    def test_scrape_formats_are_active(self):
        """Scraping a frozen format burns the budget for zero new rows."""
        active = set(get_formats_by_status(frozen=False))
        assert set(self._substitution("_SCRAPE_FORMATS")) <= active
