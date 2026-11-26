"""The JP release schedule drives the JP format windows.

A JP set is tournament-legal two weeks after release, and a JP format runs
until the next format-starting set is legal. If nobody adds the next format,
the current one freezes and the daily scrape quietly finds nothing to do, so
``check_jp_release_coverage`` turns that gap into a pipeline failure.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from cli import cli
from config import (
    FORMATS,
    JP_SET_RELEASES,
    check_jp_release_coverage,
    jp_legal_date,
)


def _format_starting_releases() -> list[dict]:
    return [r for r in JP_SET_RELEASES if r["starts_format"]]


class TestSchedule:
    def test_legal_date_is_two_weeks_after_release(self):
        assert jp_legal_date("2026-07-31") == "2026-08-14"
        assert jp_legal_date("2026-11-27") == "2026-12-11"

    def test_releases_are_in_date_order(self):
        dated = [r["release_date"] for r in JP_SET_RELEASES if r["release_date"]]
        assert dated == sorted(dated)

    def test_every_release_names_a_kind_and_a_source(self):
        for release in JP_SET_RELEASES:
            assert release["kind"] in {"expansion", "high-class", "special", "deck"}
            assert release["source"].startswith("https://"), release["name"]

    def test_format_starting_releases_have_a_known_date(self):
        """A boundary on an unconfirmed date would cut a format window in the wrong place."""
        for release in _format_starting_releases():
            assert release["release_date"], release["name"]

    def test_linked_formats_exist_and_are_jp(self):
        for release in JP_SET_RELEASES:
            if release["format"]:
                assert FORMATS[release["format"]]["region"] == "jp"


class TestFormatWindowsFollowSchedule:
    @pytest.mark.parametrize(
        "release",
        [r for r in JP_SET_RELEASES if r["format"]],
        ids=lambda r: r["format"],
    )
    def test_window_starts_on_legal_date_and_ends_before_the_next(self, release):
        fmt = FORMATS[release["format"]]
        assert fmt["dataset_start"] == jp_legal_date(release["release_date"])

        boundaries = _format_starting_releases()
        following = boundaries[boundaries.index(release) + 1 :]
        if following:
            next_legal = jp_legal_date(following[0]["release_date"])
            assert fmt["rotation_date"] == next_legal
            assert fmt["dataset_end"] < next_legal

    def test_storm_emeralda_hands_over_to_hadou_seeker_without_a_gap(self):
        assert FORMATS["storm-emeralda"]["dataset_end"] == "2026-12-10"
        assert FORMATS["hadou-seeker"]["dataset_start"] == "2026-12-11"


class TestCoverageCheck:
    def test_no_active_jp_format_is_an_error(self):
        errors, _ = check_jp_release_coverage("2030-01-01")
        assert any("no active JP format" in e for e in errors)

    def test_mid_window_is_clean(self):
        errors, warnings = check_jp_release_coverage("2026-09-15")
        assert errors == [] and warnings == []

    def test_unformatted_boundary_within_three_weeks_warns(self):
        """The ex-star triple sets start a format on 2027-06-04 that config does not have yet."""
        _, warnings = check_jp_release_coverage("2027-05-20")
        assert any("Magma Heartbeat" in w for w in warnings)

    def test_unformatted_boundary_already_legal_is_an_error(self):
        errors, _ = check_jp_release_coverage("2027-06-05")
        assert errors

    def test_cli_exits_non_zero_on_error(self):
        result = CliRunner().invoke(cli, ["release-check", "--today", "2030-01-01"])
        assert result.exit_code == 1
        assert "no active JP format" in result.output

    def test_cli_warnings_do_not_fail(self):
        result = CliRunner().invoke(cli, ["release-check", "--today", "2027-05-20"])
        assert result.exit_code == 0, result.output
        assert "Magma Heartbeat" in result.output
