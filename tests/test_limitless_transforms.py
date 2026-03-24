"""Tests for scraper/limitless.py — HTML transform and parsing functions.

All tests use inline HTML string literals passed to BeautifulSoup.
No HTTP mocking or fixture files are needed.
"""

import sys
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup, Tag

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.limitless import (
    _DECKLIST_LINE_RE,
    LimitlessClient,
    match_archetype_labels,
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_tag(html: str, selector: str = "a") -> Tag:
    """Parse an HTML fragment and return the first matching tag."""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find(selector)
    assert tag is not None, f"No <{selector}> found in fragment"
    return tag


# ---------------------------------------------------------------------------
# Sprite / archetype extraction
# ---------------------------------------------------------------------------


class TestExtractArchetypeAndSprites:
    """Tests for LimitlessClient._extract_archetype_and_sprites (static method)."""

    def test_img_with_alt_text(self):
        """img tag with alt text produces the correct archetype name and sprite URL."""
        html = """
        <a href="/decks/list/12345">
            <img src="https://r2.limitlesstcg.net/pokemon/gen9/charizard.png"
                 alt="Charizard" />
        </a>
        """
        tag = _make_tag(html)
        archetype, sprite_urls = LimitlessClient._extract_archetype_and_sprites(tag)

        assert archetype == "Charizard"
        assert sprite_urls == ["https://r2.limitlesstcg.net/pokemon/gen9/charizard.png"]

    def test_img_without_alt_parses_filename(self):
        """img tag without alt text falls back to parsing the filename from src."""
        html = """
        <a href="/decks/list/12345">
            <img src="https://r2.limitlesstcg.net/pokemon/gen9/dragapult.png" />
        </a>
        """
        tag = _make_tag(html)
        archetype, sprite_urls = LimitlessClient._extract_archetype_and_sprites(tag)

        assert archetype == "Dragapult"
        assert len(sprite_urls) == 1

    def test_empty_link_no_sprites(self):
        """A link with no img children returns empty archetype and empty sprite list."""
        html = '<a href="/decks/list/99999">Some Text</a>'
        tag = _make_tag(html)
        archetype, sprite_urls = LimitlessClient._extract_archetype_and_sprites(tag)

        assert archetype == ""
        assert sprite_urls == []

    def test_multiple_sprites_joined(self):
        """Multiple img tags produce a slash-separated archetype and ordered sprite list."""
        html = """
        <a href="/decks/list/12345">
            <img src="https://r2.limitlesstcg.net/pokemon/gen9/charizard.png"
                 alt="Charizard" />
            <img src="https://r2.limitlesstcg.net/pokemon/gen9/pidgeot.png"
                 alt="Pidgeot" />
        </a>
        """
        tag = _make_tag(html)
        archetype, sprite_urls = LimitlessClient._extract_archetype_and_sprites(tag)

        assert archetype == "Charizard / Pidgeot"
        assert len(sprite_urls) == 2
        assert "charizard.png" in sprite_urls[0]
        assert "pidgeot.png" in sprite_urls[1]

    def test_filename_with_underscores(self):
        """Underscores and hyphens in filenames are converted to spaces and title-cased."""
        html = """
        <a href="/decks/list/1">
            <img src="https://r2.limitlesstcg.net/pokemon/gen9/iron_hands.png" />
        </a>
        """
        tag = _make_tag(html)
        archetype, _ = LimitlessClient._extract_archetype_and_sprites(tag)

        assert archetype == "Iron Hands"


# ---------------------------------------------------------------------------
# Decklist line regex
# ---------------------------------------------------------------------------


class TestDecklistLineRegex:
    """Tests for the _DECKLIST_LINE_RE pattern used in text-format decklist parsing."""

    def test_standard_card_line(self):
        match = _DECKLIST_LINE_RE.match("4 Dragapult ex SV6 86")
        assert match is not None
        assert match.group(1) == "4"
        assert match.group(2) == "Dragapult ex"
        assert match.group(3) == "SV6"
        assert match.group(4) == "86"

    def test_energy_line(self):
        match = _DECKLIST_LINE_RE.match("8 Psychic Energy Energy PSY1")
        assert match is not None
        assert match.group(1) == "8"
        assert match.group(3) == "Energy"

    def test_non_card_line_no_match(self):
        assert _DECKLIST_LINE_RE.match("Pokemon: 12") is None
        assert _DECKLIST_LINE_RE.match("") is None


# ---------------------------------------------------------------------------
# Decklist parsing (card-link strategy)
# ---------------------------------------------------------------------------


class TestDecklistParsingCardLinks:
    """Tests for the card-link HTML parsing strategy inside fetch_decklist.

    Since fetch_decklist wraps HTTP + parsing, we test the parsing logic by
    patching _soup to return a pre-built BeautifulSoup tree.
    """

    def _make_client_with_soup(self, html: str) -> LimitlessClient:
        """Create a client whose _soup returns a fixed BeautifulSoup tree."""
        soup = BeautifulSoup(html, "html.parser")
        client = LimitlessClient.__new__(LimitlessClient)
        client._base_url = "https://limitlesstcg.com"
        client._soup = lambda url: soup
        return client

    def test_card_link_format(self):
        """Card-link HTML elements are parsed into structured card dicts."""
        html = """
        <div>
            <a class="card-link" href="/cards/SV6/86?translate=en">
                <span class="card-count">4</span>
                <span class="card-name">Dragapult ex</span>
            </a>
            <a class="card-link" href="/cards/SV5/23">
                <span class="card-count">2</span>
                <span class="card-name">Pidgeot ex</span>
            </a>
        </div>
        """
        client = self._make_client_with_soup(html)
        result = client.fetch_decklist("https://limitlesstcg.com/decks/list/1")

        assert result is not None
        assert len(result.cards) == 2
        assert result.cards[0]["count"] == 4
        assert result.cards[0]["name"] == "Dragapult ex"
        assert result.cards[0]["set_code"] == "SV6"
        assert result.cards[0]["card_number"] == "86"
        assert result.cards[0]["card_id"] == "SV6-86"

    def test_text_format_fallback(self):
        """When no card-link elements exist, the text-format regex is used."""
        html = """
        <div>
            <pre>
4 Dragapult ex SV6 86
2 Pidgeot ex SV5 23
            </pre>
        </div>
        """
        client = self._make_client_with_soup(html)
        result = client.fetch_decklist("https://limitlesstcg.com/decks/list/2")

        assert result is not None
        assert len(result.cards) == 2
        assert result.cards[0]["name"] == "Dragapult ex"
        assert result.cards[1]["name"] == "Pidgeot ex"

    def test_basic_energy_text_format(self):
        """Basic energy lines without set codes are parsed via the energy regex."""
        html = """
        <div>
            <pre>
8 Basic Psychic Energy
4 Basic Fire Energy
            </pre>
        </div>
        """
        client = self._make_client_with_soup(html)
        result = client.fetch_decklist("https://limitlesstcg.com/decks/list/3")

        assert result is not None
        assert len(result.cards) == 2
        assert result.cards[0]["name"] == "Basic Psychic Energy"
        assert result.cards[0]["set_code"] == "Energy"
        assert result.cards[0]["count"] == 8
        assert result.cards[1]["count"] == 4

    def test_empty_decklist_returns_none(self):
        """A page with no parseable cards returns None."""
        html = "<div><p>No decklist available.</p></div>"
        client = self._make_client_with_soup(html)
        result = client.fetch_decklist("https://limitlesstcg.com/decks/list/999")

        assert result is None


# ---------------------------------------------------------------------------
# Standings row parsing
# ---------------------------------------------------------------------------


class TestStandingsRowParsing:
    """Tests for placement parsing inside fetch_jp_city_league_placements.

    We patch _soup to return a pre-built standings table, and mock
    normalize_archetype to isolate the HTML parsing from archetype logic.
    """

    def _make_client_with_soup(self, html: str) -> LimitlessClient:
        soup = BeautifulSoup(html, "html.parser")
        client = LimitlessClient.__new__(LimitlessClient)
        client._base_url = "https://limitlesstcg.com"
        client._soup = lambda url: soup
        return client

    @patch(
        "scraper.limitless.normalize_archetype",
        side_effect=lambda urls, html_archetype="": html_archetype or "Unknown",
    )
    def test_standard_placement_row(self, mock_norm):
        """A standard 4-column row extracts rank, player, archetype, and decklist URL."""
        html = """
        <table class="striped">
            <tr><th>#</th><th>Player</th><th>Deck</th><th>List</th></tr>
            <tr>
                <td>1.</td>
                <td>Satoshi</td>
                <td>
                    <a href="/decks/list/100">
                        <img src="https://r2.limitlesstcg.net/pokemon/gen9/charizard.png"
                             alt="Charizard" />
                    </a>
                </td>
                <td><a href="/decks/list/100">View</a></td>
            </tr>
        </table>
        """
        client = self._make_client_with_soup(html)
        placements = client.fetch_jp_city_league_placements(
            "https://limitlesstcg.com/tournaments/jp/1234"
        )

        assert len(placements) == 1
        p = placements[0]
        assert p.placement == 1
        assert p.player_name == "Satoshi"
        assert p.decklist_url == "https://limitlesstcg.com/decks/list/100"
        assert len(p.sprite_urls) == 1

    @patch(
        "scraper.limitless.normalize_archetype",
        side_effect=lambda urls, html_archetype="": html_archetype or "Unknown",
    )
    def test_missing_decklist_url(self, mock_norm):
        """A row without a decklist link sets decklist_url to None."""
        html = """
        <table class="striped">
            <tr><th>#</th><th>Player</th><th>Deck</th></tr>
            <tr>
                <td>2.</td>
                <td>Kasumi</td>
                <td>Lugia VSTAR</td>
            </tr>
        </table>
        """
        client = self._make_client_with_soup(html)
        placements = client.fetch_jp_city_league_placements(
            "https://limitlesstcg.com/tournaments/jp/1234"
        )

        assert len(placements) == 1
        p = placements[0]
        assert p.placement == 2
        assert p.player_name == "Kasumi"
        assert p.decklist_url is None

    @patch(
        "scraper.limitless.normalize_archetype",
        side_effect=lambda urls, html_archetype="": html_archetype or "Unknown",
    )
    def test_archetype_fallback_plain_text(self, mock_norm):
        """When no sprites are present, cells[2] text is used as the archetype fallback."""
        html = """
        <table class="striped">
            <tr><th>#</th><th>Player</th><th>Deck</th></tr>
            <tr>
                <td>3.</td>
                <td>Takeshi</td>
                <td>Gardevoir ex</td>
            </tr>
        </table>
        """
        client = self._make_client_with_soup(html)
        placements = client.fetch_jp_city_league_placements(
            "https://limitlesstcg.com/tournaments/jp/1234"
        )

        assert len(placements) == 1
        # normalize_archetype is called with empty sprite_urls and html_archetype="Gardevoir ex"
        mock_norm.assert_called_once_with([], html_archetype="Gardevoir ex")


# ---------------------------------------------------------------------------
# match_archetype_labels (pure function, no HTTP)
# ---------------------------------------------------------------------------


class TestMatchArchetypeLabels:
    def test_matching_by_date_and_standing(self):
        jp = [
            {"date": "2026-01-15", "standing": 1, "player_name": "A"},
            {"date": "2026-01-15", "standing": 2, "player_name": "B"},
        ]
        limitless = [
            {"date": "2026-01-15", "standing": 1, "archetype": "Charizard ex"},
        ]
        result = match_archetype_labels(jp, limitless)

        assert result[0]["archetype"] == "Charizard ex"
        assert result[1]["archetype"] == "Unknown"

    def test_preserves_existing_archetype_when_no_match(self):
        jp = [{"date": "2026-01-15", "standing": 1, "archetype": "Lugia VSTAR"}]
        limitless = []
        result = match_archetype_labels(jp, limitless)

        assert result[0]["archetype"] == "Lugia VSTAR"
