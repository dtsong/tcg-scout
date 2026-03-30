"""Tests for scraper/pokecazilla.py — parsing logic (no browser required)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.pokecazilla import (
    DECK_CODE_RE,
    PokecazillaPlacement,
    parse_placements_from_html,
    parse_standing,
)


class TestParseStanding:
    def test_winner(self):
        assert parse_standing("優勝") == 1

    def test_runner_up(self):
        assert parse_standing("準優勝") == 2

    def test_numbered_position(self):
        assert parse_standing("3位") == 3
        assert parse_standing("8位") == 8

    def test_top4(self):
        assert parse_standing("ベスト4") == 3

    def test_top8(self):
        assert parse_standing("ベスト8") == 5

    def test_with_surrounding_text(self):
        assert parse_standing("優勝 フーディン") == 1
        assert parse_standing("準優勝 オーロンゲ") == 2

    def test_no_match(self):
        assert parse_standing("some random text") is None
        assert parse_standing("") is None


class TestDeckCodeRegex:
    def test_matches_valid_code(self):
        assert DECK_CODE_RE.search("kfF5VV-EpPYgW-fVkFkb").group(0) == "kfF5VV-EpPYgW-fVkFkb"

    def test_matches_in_url(self):
        url = "https://www.pokemon-card.com/deck/confirm.html/deckID/kfF5VV-EpPYgW-fVkFkb"
        assert DECK_CODE_RE.search(url).group(0) == "kfF5VV-EpPYgW-fVkFkb"

    def test_no_match_for_invalid(self):
        assert DECK_CODE_RE.search("abc-def-ghi") is None


class TestParsePlacementsFromHTML:
    """Test the core HTML parsing logic with synthetic article content."""

    SAMPLE_HTML = """
    <div class="entry-content">
        <h2>優勝 フーディン</h2>
        <p>デッキコード: kfF5VV-EpPYgW-fVkFkb</p>

        <h2>準優勝 オーロンゲ</h2>
        <p><a href="https://www.pokemon-card.com/deck/confirm.html/deckID/x8848G-x86vd6-DcKcxD">デッキリスト</a></p>

        <h2>ベスト4 イワパレス</h2>
        <p>デッキコード: cY8888-EQzq2O-ccDKcG</p>

        <h2>ベスト4 ロケット団</h2>
        <p>デッキコード: g9PLHn-Vqy7Lt-g9HNgN</p>

        <h2>ベスト8 ドラパルト</h2>
        <p>デッキコード: fkv5Vk-vQQ1oP-VbwbFk</p>

        <h2>ベスト8 ミライドン</h2>
        <p>デッキコード: aB1234-cD5678-eF9012</p>

        <h2>ベスト8 ルギア</h2>
        <p>デッキコード: xY3456-zW7890-aB1234</p>

        <h2>ベスト8 パルキア</h2>
        <p>デッキコード: mN5678-oP9012-qR3456</p>
    </div>
    """

    def test_extracts_all_placements(self):
        placements = parse_placements_from_html(self.SAMPLE_HTML)
        assert len(placements) == 8

    def test_winner_parsed_correctly(self):
        placements = parse_placements_from_html(self.SAMPLE_HTML)
        winner = placements[0]
        assert winner.standing == 1
        assert "フーディン" in winner.archetype_jp
        assert winner.deck_code == "kfF5VV-EpPYgW-fVkFkb"

    def test_runner_up_parsed_correctly(self):
        placements = parse_placements_from_html(self.SAMPLE_HTML)
        runner_up = placements[1]
        assert runner_up.standing == 2
        assert "オーロンゲ" in runner_up.archetype_jp
        assert runner_up.deck_code == "x8848G-x86vd6-DcKcxD"
        assert "pokemon-card.com" in runner_up.deck_url

    def test_top4_standing_increments(self):
        placements = parse_placements_from_html(self.SAMPLE_HTML)
        top4 = [p for p in placements if p.standing in (3, 4)]
        assert len(top4) == 2
        standings = sorted(p.standing for p in top4)
        assert standings == [3, 4]

    def test_top8_standing_increments(self):
        placements = parse_placements_from_html(self.SAMPLE_HTML)
        top8 = [p for p in placements if p.standing in (5, 6, 7, 8)]
        assert len(top8) == 4
        standings = sorted(p.standing for p in top8)
        assert standings == [5, 6, 7, 8]

    def test_deck_codes_extracted(self):
        placements = parse_placements_from_html(self.SAMPLE_HTML)
        codes = [p.deck_code for p in placements if p.deck_code]
        assert len(codes) == 8
        assert "kfF5VV-EpPYgW-fVkFkb" in codes
        assert "cY8888-EQzq2O-ccDKcG" in codes

    def test_deck_url_generated_from_code(self):
        placements = parse_placements_from_html(self.SAMPLE_HTML)
        winner = placements[0]
        assert winner.deck_url == (
            "https://www.pokemon-card.com/deck/confirm.html/deckID/kfF5VV-EpPYgW-fVkFkb"
        )

    def test_link_based_deck_url_preserved(self):
        placements = parse_placements_from_html(self.SAMPLE_HTML)
        runner_up = placements[1]
        assert runner_up.deck_url == (
            "https://www.pokemon-card.com/deck/confirm.html/deckID/x8848G-x86vd6-DcKcxD"
        )


class TestParsePlacementsTable:
    """Test table-based fallback parsing."""

    TABLE_HTML = """
    <table>
        <tr><th>順位</th><th>デッキ</th><th>デッキコード</th></tr>
        <tr><td>優勝</td><td>フーディン</td><td>kfF5VV-EpPYgW-fVkFkb</td></tr>
        <tr><td>準優勝</td><td>オーロンゲ</td><td>x8848G-x86vd6-DcKcxD</td></tr>
    </table>
    """

    def test_table_extraction(self):
        placements = parse_placements_from_html(self.TABLE_HTML)
        assert len(placements) == 2
        assert placements[0].standing == 1
        assert placements[0].archetype_jp == "フーディン"
        assert placements[0].deck_code == "kfF5VV-EpPYgW-fVkFkb"
        assert placements[1].standing == 2
        assert placements[1].archetype_jp == "オーロンゲ"


class TestParsePlacementsEdgeCases:
    def test_empty_html(self):
        placements = parse_placements_from_html("")
        assert placements == []

    def test_no_placements_in_html(self):
        html = "<div><h2>Some random article</h2><p>No tournament data here.</p></div>"
        placements = parse_placements_from_html(html)
        assert placements == []

    def test_deck_suffix_stripped(self):
        html = """
        <div>
            <h2>優勝 フーディンデッキ</h2>
            <p>kfF5VV-EpPYgW-fVkFkb</p>
        </div>
        """
        placements = parse_placements_from_html(html)
        assert len(placements) == 1
        assert placements[0].archetype_jp == "フーディン"

    def test_heading_with_brackets(self):
        html = """
        <div>
            <h2>【優勝】フーディン</h2>
            <p>kfF5VV-EpPYgW-fVkFkb</p>
        </div>
        """
        placements = parse_placements_from_html(html)
        assert len(placements) == 1
        assert "フーディン" in placements[0].archetype_jp
