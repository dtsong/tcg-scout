"""Archetype normalizer using Limitless TCG naming conventions.

Produces names directly from sprite URLs: single sprite -> "Dragapult",
multiple sprites -> "Dragapult / Dusknoir" (alphabetical, slash-separated).
"""

import re

LIMITLESS_SPRITE_CDN = "https://r2.limitlesstcg.net/pokemon/gen9"

_FILENAME_RE = re.compile(r"/([a-zA-Z0-9_-]+)\.png")


def build_sprite_key(sprite_urls: list[str]) -> str:
    """Build a canonical sprite key from image URLs.

    Extracts filename stems, lowercases, sorts alphabetically, joins with hyphens.
    """
    names: list[str] = []
    for url in sprite_urls:
        match = _FILENAME_RE.search(url)
        if match:
            name = match.group(1).lower().replace("_", "-")
            names.append(name)
    names.sort()
    return "-".join(names)


def normalize_archetype(sprite_urls: list[str], html_archetype: str = "") -> str:
    """Resolve archetype name from sprite URLs with optional HTML text fallback.

    Produces Limitless-style names directly from sprite filenames:
    - Single sprite: "Dragapult"
    - Multiple sprites: "Dragapult / Dusknoir" (alphabetical)
    - Fallback: html_archetype stripped, then "Unknown"
    """
    if sprite_urls:
        names: list[str] = []
        for url in sprite_urls:
            match = _FILENAME_RE.search(url)
            if match:
                fn = match.group(1).lower().replace("_", "-")
                titled = "-".join(p.capitalize() for p in fn.split("-"))
                names.append(titled)
        if names:
            names.sort()
            if len(names) == 1:
                return names[0]
            return " / ".join(names)

    # Fallback to HTML text
    if html_archetype and html_archetype.strip():
        return html_archetype.strip()

    return "Unknown"


def classify_from_decklist(cards: list[dict]) -> str:
    """Classify archetype from decklist card contents.

    Uses content-based anchor card detection.
    Falls back to "Unknown" if no anchor cards match.
    """
    from analysis.archetype_classifier import classify_decklist

    return classify_decklist(cards)
