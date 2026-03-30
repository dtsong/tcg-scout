"""Tests for scraper/pokecabook.py -- HTML parsing logic."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.pokecabook import (
    PBAvgCard,
    PBCard,
    _is_category_header,
    _parse_placement_text,
    parse_avg_cards_from_html,
    parse_deck_cards_from_html,
    parse_deck_entries_from_html,
)


class TestParseDeckEntries:
    """Test deck entry extraction from figure-based PokecaBook articles."""

    def test_cl_results_article(self):
        """Realistic CL results article with headings and figures."""
        html = """
        <h2 class="wp-block-heading">マスターリーグ</h2>
        <h4 class="wp-block-heading"><span id="toc2">優勝</span></h4>
        <figure class="wp-block-image size-full o_001">
            <a href="https://pokecabook.com/wp-content/uploads/kfF5VV-EpPYgW-fVkFkb.jpg">
                <img src="https://pokecabook.com/wp-content/uploads/kfF5VV-EpPYgW-fVkFkb.jpg"
                     data-src="https://pokecabook.com/wp-content/uploads/kfF5VV-EpPYgW-fVkFkb.jpg"
                     alt="" class="wp-image-307069" />
            </a>
            <figcaption class="wp-element-caption">
                チャンピオンズリーグ2026大阪
                <a rel="noopener" target="_blank"
                   href="https://www.pokemon-card.com/deck/result.html/deckID/kfF5VV-EpPYgW-fVkFkb/">優勝</a>
            </figcaption>
        </figure>
        <h4 class="wp-block-heading"><span id="toc3">準優勝</span></h4>
        <figure class="wp-block-image size-full o_002">
            <a href="https://pokecabook.com/wp-content/uploads/x8848G-x86vd6-DcKcxD.jpg">
                <img data-src="https://pokecabook.com/wp-content/uploads/x8848G-x86vd6-DcKcxD.jpg"
                     src="data:image/png;base64,placeholder" alt="" />
            </a>
            <figcaption class="wp-element-caption">
                チャンピオンズリーグ2026大阪
                <a href="https://www.pokemon-card.com/deck/result.html/deckID/x8848G-x86vd6-DcKcxD/">準優勝</a>
            </figcaption>
        </figure>
        <h4 class="wp-block-heading">TOP4</h4>
        <figure class="wp-block-image size-full o_004">
            <a href="https://pokecabook.com/wp-content/uploads/cY8888-EQzq2O-ccDKcG.jpg">
                <img data-src="https://pokecabook.com/wp-content/uploads/cY8888-EQzq2O-ccDKcG.jpg"
                     src="data:image/png;base64,placeholder" alt="" />
            </a>
            <figcaption class="wp-element-caption">
                チャンピオンズリーグ2026大阪
                <a href="https://www.pokemon-card.com/deck/result.html/deckID/cY8888-EQzq2O-ccDKcG/">TOP4</a>
            </figcaption>
        </figure>
        """
        entries = parse_deck_entries_from_html(html)
        assert len(entries) == 3

        # 1st place
        assert entries[0].deck_id == "kfF5VV-EpPYgW-fVkFkb"
        assert entries[0].placement == 1
        assert entries[0].placement_label == "優勝"
        assert "kfF5VV-EpPYgW-fVkFkb.jpg" in entries[0].image_url
        assert "pokemon-card.com" in entries[0].deck_url

        # 2nd place
        assert entries[1].deck_id == "x8848G-x86vd6-DcKcxD"
        assert entries[1].placement == 2
        assert entries[1].placement_label == "準優勝"
        # Should use data-src, not base64 placeholder
        assert entries[1].image_url.startswith("https://")

        # TOP4
        assert entries[2].deck_id == "cY8888-EQzq2O-ccDKcG"
        assert entries[2].placement == 4

    def test_gym_battle_article(self):
        """Deck recipe article with placement in figcaption only."""
        html = """
        <h2 class="wp-block-heading">ニンジャスピナー環境</h2>
        <figure class="wp-block-image">
            <img src="https://pokecabook.com/wp-content/uploads/kbfkFF-9PvH0K-wF51kV.jpg" alt="" />
            <figcaption class="wp-element-caption">
                <a href="https://www.pokemon-card.com/deck/result.html/deckID/kbfkFF-9PvH0K-wF51kV/">
                    3/27【金】ジムバトル優勝
                </a>
            </figcaption>
        </figure>
        <figure class="wp-block-image">
            <img src="https://pokecabook.com/wp-content/uploads/HgHN9g-7XhwWZ-ng9NnN.jpg" alt="" />
            <figcaption class="wp-element-caption">
                <a href="https://www.pokemon-card.com/deck/result.html/deckID/HgHN9g-7XhwWZ-ng9NnN/">
                    3/25【水】ジムバトル優勝
                </a>
            </figcaption>
        </figure>
        """
        entries = parse_deck_entries_from_html(html)
        assert len(entries) == 2
        assert entries[0].deck_id == "kbfkFF-9PvH0K-wF51kV"
        assert entries[0].placement == 1  # "優勝" in figcaption
        assert "3/27" in entries[0].event_label
        assert entries[1].deck_id == "HgHN9g-7XhwWZ-ng9NnN"

    def test_no_figures(self):
        html = "<p>No deck data here</p>"
        assert parse_deck_entries_from_html(html) == []

    def test_figure_without_deck_link(self):
        """Figure with image but no pokemon-card.com link should be skipped."""
        html = """
        <figure class="wp-block-image">
            <img src="https://pokecabook.com/some-other-image.jpg" alt="" />
            <figcaption>Just a random image</figcaption>
        </figure>
        """
        assert parse_deck_entries_from_html(html) == []

    def test_empty_html(self):
        assert parse_deck_entries_from_html("") == []

    def test_multiple_top4_entries(self):
        """Multiple figures under the same heading share placement."""
        html = """
        <h4>TOP8</h4>
        <figure class="wp-block-image">
            <img src="https://pokecabook.com/img1.jpg" alt="" />
            <figcaption>
                <a href="https://www.pokemon-card.com/deck/result.html/deckID/aaa-bbb-ccc/">TOP8</a>
            </figcaption>
        </figure>
        <figure class="wp-block-image">
            <img src="https://pokecabook.com/img2.jpg" alt="" />
            <figcaption>
                <a href="https://www.pokemon-card.com/deck/result.html/deckID/ddd-eee-fff/">TOP8</a>
            </figcaption>
        </figure>
        """
        entries = parse_deck_entries_from_html(html)
        assert len(entries) == 2
        assert entries[0].placement == 8
        assert entries[1].placement == 8


class TestParsePlacementText:
    """Test placement text parsing helper."""

    def test_yuushou(self):
        assert _parse_placement_text("優勝") == (1, "優勝")

    def test_jun_yuushou(self):
        assert _parse_placement_text("準優勝") == (2, "準優勝")

    def test_top4(self):
        assert _parse_placement_text("TOP4") == (4, "TOP4")

    def test_top8(self):
        assert _parse_placement_text("TOP8") == (8, "TOP8")

    def test_top16(self):
        assert _parse_placement_text("TOP16") == (16, "TOP16")

    def test_best4(self):
        assert _parse_placement_text("ベスト4") == (4, "ベスト4")

    def test_embedded_in_text(self):
        rank, label = _parse_placement_text("チャンピオンズリーグ2026大阪 優勝")
        assert rank == 1
        assert label == "優勝"

    def test_jun_yuushou_not_matched_as_yuushou(self):
        """準優勝 should return 2, not 1."""
        rank, _ = _parse_placement_text("CL大阪 準優勝")
        assert rank == 2

    def test_no_placement(self):
        assert _parse_placement_text("マスターリーグ") == (None, "")

    def test_gym_battle_caption(self):
        rank, label = _parse_placement_text("3/27【金】ジムバトル優勝")
        assert rank == 1
        assert label == "優勝"


class TestParseDeckCardsTable:
    """Test table-based deck recipe extraction."""

    def test_basic_table_extraction(self):
        html = """
        <table>
            <tr><th colspan="2">ポケモン (12)</th></tr>
            <tr><td>リザードンex</td><td>3枚</td></tr>
            <tr><td>ピジョットex</td><td>2枚</td></tr>
            <tr><th colspan="2">グッズ (10)</th></tr>
            <tr><td>ネストボール</td><td>4枚</td></tr>
            <tr><td>ハイパーボール</td><td>3枚</td></tr>
            <tr><th colspan="2">エネルギー (8)</th></tr>
            <tr><td>基本炎エネルギー</td><td>4枚</td></tr>
        </table>
        """
        cards = parse_deck_cards_from_html(html)
        assert len(cards) == 5

        assert cards[0].name_jp == "リザードンex"
        assert cards[0].count == 3
        assert cards[0].category == "Pokemon"

        assert cards[2].name_jp == "ネストボール"
        assert cards[2].count == 4
        assert cards[2].category == "Trainer"

        assert cards[4].name_jp == "基本炎エネルギー"
        assert cards[4].count == 4
        assert cards[4].category == "Energy"

    def test_count_without_枚_suffix(self):
        html = """
        <table>
            <tr><th>ポケモン</th></tr>
            <tr><td>ルギアV</td><td>3</td></tr>
            <tr><td>アーケオス</td><td>2</td></tr>
        </table>
        """
        cards = parse_deck_cards_from_html(html)
        assert len(cards) == 2
        assert cards[0].count == 3
        assert cards[1].count == 2

    def test_empty_table(self):
        html = "<table><tr><td>No cards here</td></tr></table>"
        cards = parse_deck_cards_from_html(html)
        assert cards == []

    def test_no_html(self):
        cards = parse_deck_cards_from_html("")
        assert cards == []

    def test_multiple_categories(self):
        html = """
        <table>
            <tr><th>ポケモン</th></tr>
            <tr><td>ミュウVMAX</td><td>1枚</td></tr>
            <tr><th>サポート</th></tr>
            <tr><td>ボスの指令</td><td>2枚</td></tr>
            <tr><th>スタジアム</th></tr>
            <tr><td>シンオウ神殿</td><td>1枚</td></tr>
            <tr><th>ポケモンのどうぐ</th></tr>
            <tr><td>こだわりベルト</td><td>2枚</td></tr>
        </table>
        """
        cards = parse_deck_cards_from_html(html)
        assert len(cards) == 4
        # All trainer subcategories map to "Trainer"
        assert cards[1].category == "Trainer"
        assert cards[2].category == "Trainer"
        assert cards[3].category == "Trainer"


class TestParseDeckCardsList:
    """Test list-based deck recipe extraction (fallback when no tables)."""

    def test_list_format(self):
        html = """
        <div>
            <h3>ポケモン (6)</h3>
            <p>リザードンex 3枚</p>
            <p>ヒトカゲ 3枚</p>
            <h3>グッズ (4)</h3>
            <p>ネストボール 4枚</p>
            <h3>エネルギー (4)</h3>
            <p>基本炎エネルギー 4枚</p>
        </div>
        """
        cards = parse_deck_cards_from_html(html)
        assert len(cards) == 4
        assert cards[0].name_jp == "リザードンex"
        assert cards[0].count == 3
        assert cards[0].category == "Pokemon"

    def test_x_count_format(self):
        """Cards listed as 'name x3' or 'name X2'."""
        html = """
        <div>
            <h3>ポケモン</h3>
            <p>リザードンex x3</p>
            <p>ヒトカゲ X2</p>
        </div>
        """
        cards = parse_deck_cards_from_html(html)
        assert len(cards) == 2
        assert cards[0].count == 3
        assert cards[1].count == 2


class TestParseAvgCards:
    """Test average card count table extraction."""

    def test_basic_avg_table(self):
        html = """
        <table>
            <tr><th>カード名</th><th>平均枚数</th><th>採用率</th></tr>
            <tr><th colspan="3">ポケモン</th></tr>
            <tr><td>リザードンex</td><td>2.8枚</td><td>100%</td></tr>
            <tr><td>ピジョットex</td><td>1.5枚</td><td>85%</td></tr>
            <tr><th colspan="3">グッズ</th></tr>
            <tr><td>ネストボール</td><td>3.7枚</td><td>95%</td></tr>
        </table>
        """
        avg_cards = parse_avg_cards_from_html(html)
        assert len(avg_cards) == 3

        assert avg_cards[0].name_jp == "リザードンex"
        assert avg_cards[0].avg_count == pytest.approx(2.8)
        assert avg_cards[0].adoption_rate == pytest.approx(100.0)
        assert avg_cards[0].category == "Pokemon"

        assert avg_cards[1].name_jp == "ピジョットex"
        assert avg_cards[1].avg_count == pytest.approx(1.5)
        assert avg_cards[1].adoption_rate == pytest.approx(85.0)

        assert avg_cards[2].name_jp == "ネストボール"
        assert avg_cards[2].category == "Trainer"

    def test_avg_without_枚_suffix(self):
        html = """
        <table>
            <tr><th colspan="2">ポケモン</th></tr>
            <tr><td>ミュウV</td><td>2.5</td><td>90%</td></tr>
        </table>
        """
        avg_cards = parse_avg_cards_from_html(html)
        assert len(avg_cards) == 1
        assert avg_cards[0].avg_count == pytest.approx(2.5)

    def test_adoption_rate_only(self):
        html = """
        <table>
            <tr><th colspan="2">ポケモン</th></tr>
            <tr><td>ルギアV</td><td>-</td><td>75%</td></tr>
        </table>
        """
        avg_cards = parse_avg_cards_from_html(html)
        assert len(avg_cards) == 1
        assert avg_cards[0].adoption_rate == pytest.approx(75.0)

    def test_empty_table(self):
        html = "<table><tr><td>Nothing</td></tr></table>"
        assert parse_avg_cards_from_html(html) == []

    def test_no_html(self):
        assert parse_avg_cards_from_html("") == []


class TestIsCategoryHeader:
    def test_pokemon_header(self):
        assert _is_category_header("ポケモン (12)")

    def test_trainer_header(self):
        assert _is_category_header("グッズ (8)")
        assert _is_category_header("サポート (6)")
        assert _is_category_header("スタジアム (2)")
        assert _is_category_header("ポケモンのどうぐ (4)")

    def test_energy_header(self):
        assert _is_category_header("エネルギー (4)")

    def test_card_name(self):
        assert not _is_category_header("リザードンex")
        assert not _is_category_header("ネストボール")

    def test_empty(self):
        assert not _is_category_header("")


class TestDataclasses:
    """Verify dataclass defaults and fields."""

    def test_pb_card_defaults(self):
        card = PBCard(name_jp="テスト")
        assert card.count == 1
        assert card.category == ""

    def test_pb_avg_card_defaults(self):
        card = PBAvgCard(name_jp="テスト")
        assert card.avg_count == 0.0
        assert card.adoption_rate == 0.0
        assert card.category == ""

    def test_pb_card_with_values(self):
        card = PBCard(name_jp="リザードンex", count=3, category="Pokemon")
        assert card.name_jp == "リザードンex"
        assert card.count == 3
        assert card.category == "Pokemon"
