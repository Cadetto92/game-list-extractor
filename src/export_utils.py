"""Helpers shared by the game library exporters."""

import csv
import json
import os
from datetime import date

RESULTS_DIR = "results"
SITE_DATA_DIR = os.path.join("site", "data")
INDEX_FILE = "index.json"
# The only fields ever written to the published (committed) site data.
# Personal data such as playtime must never be added here.
GAME_FIELDS = ("title", "id", "developer", "category", "url")
LIST_FIELDS = ("platform", "device", "extract_date", "count", "games")


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


def write_site_data(platform, device, games):
    """Write site/data/<platform>_<device>.json with whitelisted fields, then rebuild the index.

    games is a list of dicts; keys outside GAME_FIELDS are dropped and empty values omitted.
    """
    os.makedirs(SITE_DATA_DIR, exist_ok=True)
    clean = [
        {key: str(game[key]) for key in GAME_FIELDS if game.get(key) not in (None, "")}
        for game in games
    ]
    name = f"{platform}_{device}".lower()
    data = {
        "platform": platform,
        "device": device,
        "extract_date": date.today().isoformat(),
        "count": len(clean),
        "games": clean,
    }
    _write_json(os.path.join(SITE_DATA_DIR, f"{name}.json"), data)

    files = sorted(
        f for f in os.listdir(SITE_DATA_DIR) if f.endswith(".json") and f != INDEX_FILE
    )
    _write_json(os.path.join(SITE_DATA_DIR, INDEX_FILE), {"lists": files})
    print(f"Website data prepared in {os.path.join(SITE_DATA_DIR, name)}.json (local file, not published yet)")


def _write_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        json.dump(data, file, ensure_ascii=False, indent=1)
        file.write("\n")
