"""Validate the content-based archetype classifier against Limitless labels.

Runs the classifier on every decklist in the DB and compares
against the Limitless-assigned archetype. Outputs accuracy stats.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.archetype import classify_from_decklist
from db import get_format_connection


def validate(format_slug: str = "nihil-zero") -> None:
    conn = get_format_connection(format_slug)

    placements = conn.execute(
        "SELECT id, archetype FROM open_placements WHERE archetype != 'Unknown'"
    ).fetchall()

    correct = 0
    wrong = 0
    no_decklist = 0
    mismatches: Counter = Counter()

    for p in placements:
        cards = conn.execute(
            "SELECT card_name, count FROM decklist_cards WHERE placement_id = ?",
            (p["id"],),
        ).fetchall()

        if not cards:
            no_decklist += 1
            continue

        # decklist_cards has no category column, so mark all as Pokemon
        # (the classifier filters on category=="Pokemon", so this means
        # all cards are candidates -- Trainer/Energy names won't match anchors)
        card_dicts = [
            {"card_name": c["card_name"], "count": c["count"], "category": "Pokemon"} for c in cards
        ]
        predicted = classify_from_decklist(card_dicts)
        actual = p["archetype"]

        if predicted == actual:
            correct += 1
        else:
            wrong += 1
            mismatches[(actual, predicted)] += 1

    total = correct + wrong
    accuracy = correct / total * 100 if total > 0 else 0

    print(f"\nClassifier Validation: {format_slug}")
    print(f"{'=' * 50}")
    print(f"Total placements: {len(placements)}")
    print(f"With decklists:   {total}")
    print(f"No decklist:      {no_decklist}")
    print(f"Correct:          {correct} ({accuracy:.1f}%)")
    print(f"Wrong:            {wrong}")

    if mismatches:
        print("\nTop mismatches:")
        for (actual, predicted), count in mismatches.most_common(20):
            print(f"  {count:4d}x  actual={actual}  predicted={predicted}")

    conn.close()


if __name__ == "__main__":
    validate(sys.argv[1] if len(sys.argv) > 1 else "nihil-zero")
