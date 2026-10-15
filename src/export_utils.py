"""Helpers shared by the game library exporters."""

import csv
import os
from datetime import date

RESULTS_DIR = "results"


def load_env(path=".env"):
    """Load KEY=value lines from a .env file without overriding variables already set."""
    try:
        with open(path, encoding="utf-8-sig") as file:
            lines = file.read().splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("\"'")
        if value:
            os.environ.setdefault(key.strip(), value)


def write_csv(filename, header, rows):
    """Write rows to results/<filename>, after the extract date, the game count and the header."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, filename)
    # utf-8-sig adds a byte order mark so Excel shows accented characters correctly.
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file, quoting=csv.QUOTE_ALL)
        writer.writerow(["Extract date", date.today().isoformat()])
        writer.writerow(["Number of games", len(rows)])
        writer.writerow([])
        writer.writerow(header)
        writer.writerows(rows)

    print(f"{len(rows)} games saved to {path}")
