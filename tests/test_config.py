"""Tests for config.py — validation of configuration invariants."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    CORE_AVG_COPIES_OTHER,
    CORE_AVG_COPIES_POKEMON,
    CORE_INCLUSION_RATE,
    FORMATS,
    PLACEMENT_WEIGHT_DEFAULT,
    PLACEMENT_WEIGHTS,
    TIER_THRESHOLDS,
    TIER_WEIGHTS,
)


class TestTierThresholds:
    def test_descending_order(self):
        """S > A > B > C thresholds."""
        ordered = ["S", "A", "B", "C"]
        values = [TIER_THRESHOLDS[k] for k in ordered]
        for i in range(len(values) - 1):
            assert values[i] > values[i + 1], (
                f"TIER_THRESHOLDS[{ordered[i]!r}]={values[i]} should be > "
                f"TIER_THRESHOLDS[{ordered[i + 1]!r}]={values[i + 1]}"
            )

    def test_all_positive(self):
        for tier, value in TIER_THRESHOLDS.items():
            assert value > 0, f"TIER_THRESHOLDS[{tier!r}] should be positive, got {value}"


class TestPlacementWeights:
    def test_all_positive(self):
        for placement, weight in PLACEMENT_WEIGHTS.items():
            assert weight > 0, f"PLACEMENT_WEIGHTS[{placement}] should be > 0, got {weight}"
        assert PLACEMENT_WEIGHT_DEFAULT > 0

    def test_descending_by_placement(self):
        """Higher placements (lower number) should have >= weight than lower placements."""
        placements = sorted(PLACEMENT_WEIGHTS.keys())
        for i in range(len(placements) - 1):
            w_higher = PLACEMENT_WEIGHTS[placements[i]]
            w_lower = PLACEMENT_WEIGHTS[placements[i + 1]]
            assert w_higher >= w_lower, (
                f"Placement {placements[i]} weight ({w_higher}) should be >= "
                f"placement {placements[i + 1]} weight ({w_lower})"
            )

    def test_default_lte_minimum_explicit(self):
        """Default weight should be <= the smallest explicit weight."""
        min_explicit = min(PLACEMENT_WEIGHTS.values())
        assert PLACEMENT_WEIGHT_DEFAULT <= min_explicit


class TestTierWeights:
    def test_superset_of_thresholds_plus_rogue(self):
        expected_keys = set(TIER_THRESHOLDS.keys()) | {"Rogue"}
        assert expected_keys <= set(TIER_WEIGHTS.keys()), (
            f"TIER_WEIGHTS keys {set(TIER_WEIGHTS.keys())} should be a superset of "
            f"TIER_THRESHOLDS keys + Rogue: {expected_keys}"
        )


class TestFormatDates:
    def test_dates_parseable(self):
        """All format date fields should be valid ISO dates."""
        date_fields = ["dataset_start", "dataset_end", "rotation_date"]
        for slug, fmt in FORMATS.items():
            for field in date_fields:
                raw = fmt[field]
                parsed = date.fromisoformat(raw)
                assert isinstance(parsed, date), (
                    f"FORMATS[{slug!r}][{field!r}] = {raw!r} is not a valid ISO date"
                )

    def test_date_ordering(self):
        """dataset_start < dataset_end < rotation_date for each format."""
        for slug, fmt in FORMATS.items():
            start = date.fromisoformat(fmt["dataset_start"])
            end = date.fromisoformat(fmt["dataset_end"])
            rotation = date.fromisoformat(fmt["rotation_date"])
            assert start < end, (
                f"FORMATS[{slug!r}]: dataset_start ({start}) should be < dataset_end ({end})"
            )
            assert end < rotation, (
                f"FORMATS[{slug!r}]: dataset_end ({end}) should be < rotation_date ({rotation})"
            )


class TestCoreThresholds:
    def test_inclusion_rate_between_zero_and_one(self):
        assert 0 < CORE_INCLUSION_RATE <= 1, (
            f"CORE_INCLUSION_RATE should be in (0, 1], got {CORE_INCLUSION_RATE}"
        )

    def test_avg_copies_positive_integers(self):
        for name, value in [
            ("CORE_AVG_COPIES_POKEMON", CORE_AVG_COPIES_POKEMON),
            ("CORE_AVG_COPIES_OTHER", CORE_AVG_COPIES_OTHER),
        ]:
            assert isinstance(value, int), f"{name} should be an int, got {type(value).__name__}"
            assert value > 0, f"{name} should be positive, got {value}"
