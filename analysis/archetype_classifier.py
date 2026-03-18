"""Content-based archetype classification from decklist cards."""

from config import ARCHETYPE_ANCHOR_CARDS


def classify_decklist(cards: list[dict]) -> str:
    """Classify a decklist into an archetype based on card contents.

    Args:
        cards: List of dicts with 'card_name', 'count', 'category' keys.

    Returns:
        Archetype name string, or "Unknown" if no match.
    """
    pokemon_names = {
        c["card_name"] for c in cards
        if c.get("category") == "Pokemon"
    }

    for anchor, mapping in ARCHETYPE_ANCHOR_CARDS.items():
        if anchor not in pokemon_names:
            continue

        if isinstance(mapping, str):
            return mapping

        for secondary, archetype_name in mapping.items():
            if secondary == "_default":
                continue
            if secondary in pokemon_names:
                return archetype_name

        return mapping.get("_default", anchor)

    return "Unknown"
