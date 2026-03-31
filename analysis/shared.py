"""Shared utilities — placement weighting, slugification, energy constants."""

import re

from config import PLACEMENT_WEIGHT_DEFAULT, PLACEMENT_WEIGHTS

BASIC_ENERGY_NAMES: frozenset[str] = frozenset(
    {
        "Basic Fire Energy",
        "Basic Water Energy",
        "Basic Lightning Energy",
        "Basic Psychic Energy",
        "Basic Fighting Energy",
        "Basic Darkness Energy",
        "Basic Metal Energy",
        "Basic Grass Energy",
        "Basic Colorless Energy",
        "Basic Fairy Energy",
        "Fire Energy",
        "Water Energy",
        "Lightning Energy",
        "Psychic Energy",
        "Fighting Energy",
        "Darkness Energy",
        "Metal Energy",
        "Grass Energy",
    }
)


def placement_weight(standing: int, boost: float = 1.0) -> float:
    return PLACEMENT_WEIGHTS.get(standing, PLACEMENT_WEIGHT_DEFAULT) * boost


def slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")
