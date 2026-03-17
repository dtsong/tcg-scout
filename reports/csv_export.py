"""CSV buy list export."""

import csv
import sqlite3
from datetime import date
from pathlib import Path

DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "reports" / "output"

COLUMNS = [
    "card_name",
    "set_code",
    "set_number",
    "priority_score",
    "urgency",
    "core_flex",
    "archetypes",
    "avg_copies",
]


def export_buylist_csv(
    buylist: list[dict],
    output_dir: Path | None = None,
) -> Path:
    """Export buy list to CSV. Returns path to the CSV file."""
    out = output_dir or DEFAULT_OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    filepath = out / f"buylist-{date.today().isoformat()}.csv"

    with filepath.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for item in buylist:
            row = dict(item)
            # Join archetypes list with semicolons
            archetypes = row.get("archetypes", [])
            if isinstance(archetypes, list):
                row["archetypes"] = ";".join(archetypes)
            writer.writerow(row)

    return filepath
