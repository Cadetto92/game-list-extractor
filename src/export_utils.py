"""Helpers shared by the exporters: CSV writing, website data writing and .env loading."""

import argparse
import csv
import json
import os
import re
import sys
from datetime import date
from urllib.parse import urlparse

RESULTS_DIR = "results"
SITE_DATA_DIR = os.path.join("site", "data")
INDEX_FILE = "index.json"
# The only fields ever written to the published (committed) site data.
# Personal data such as playtime must never be added here. "image" is a public store picture URL.
GAME_FIELDS = ("title", "id", "developer", "category", "url", "image")
# Picture URLs must be https and on one of the stores' own picture hosts.
IMAGE_HOSTS = ("epicgames.com", "unrealengine.com", "steamstatic.com", "gog-statics.com")
LIST_FIELDS =("platform", "device", "extract_date", "count", "games")


def parse_args(description, exporter=True):
    """Read the command-line options of an exporter (or, with exporter=False, of publish-games).

    Unknown options stop the script. publish_games.py looks for --no-publish in sys.argv, so
    it is declared here only to be accepted and described.
    """
    # allow_abbrev=False: a typo such as --js must fail instead of silently meaning --json.
    parser = argparse.ArgumentParser(description=description, allow_abbrev=False)
    if exporter:
        parser.add_argument(
            "--json", action="store_true",
            help="also save the platform's reply, without sensitive data, as JSON in results/",
        )
        parser.add_argument(
            "--no-publish", action="store_true",
            help="do not offer to publish the changes afterwards",
        )
    return parser.parse_args()


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


REDACTED = "[REDACTED]"
# Key names (lower case, without "_" and "-") whose value is always replaced.
SENSITIVE_KEYS = {
    "key", "apikey", "token", "accesstoken", "refreshtoken", "idtoken", "secret", "clientsecret",
    "password", "passwd", "email", "emailaddress", "username", "steamid", "accountid",
    "displayname", "sessionid", "cookie", "cookies", "authorization",
}
SENSITIVE_SUFFIXES = ("token", "secret", "password")
# The domain must start with a letter and end with letters, so "icon@2x.png" is not an e-mail.
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[A-Za-z][\w-]*(?:\.[\w-]+)*\.[A-Za-z]{2,}\b")


def _is_sensitive_key(key):
    name = str(key).lower().replace("_", "").replace("-", "")
    return name in SENSITIVE_KEYS or name.endswith(SENSITIVE_SUFFIXES)


def redact(data, secrets=()):
    """Return a copy of data without sensitive values.

    Values under sensitive key names are replaced, and so are the given secret values and
    e-mail addresses found inside text (links are left alone, so picture URLs stay intact).
    """
    secrets = [str(s) for s in secrets if s]
    if isinstance(data, dict):
        return {
            key: REDACTED if _is_sensitive_key(key) else redact(value, secrets)
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [redact(item, secrets) for item in data]
    if isinstance(data, str):
        for secret in secrets:
            data = data.replace(secret, REDACTED)
        if data.startswith(("http://", "https://")):
            return data
        return EMAIL_PATTERN.sub(REDACTED, data)
    return data


def write_raw_json(filename, data, secrets=()):
    """Save the platform's reply to results/<filename> for your own reference (never published).

    Only called when the exporter is started with --json.

    Sensitive values are removed first: see redact(). Secrets from .env are always removed.
    """
    secrets = [*secrets, os.environ.get("STEAM_API_KEY"), os.environ.get("STEAM_ID")]
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, filename)
    _write_json(path, redact(data, secrets))
    print(f"Raw reply (sensitive data removed) saved to {path}")


def is_allowed_image(url):
    """True if url is https and on one of the stores' own picture hosts."""
    parts = urlparse(url)
    host = parts.hostname or ""
    return parts.scheme == "https" and any(host == h or host.endswith("." + h) for h in IMAGE_HOSTS)


def write_site_data(platform, device, games):
    """Write site/data/<platform>_<device>.json with whitelisted fields, then rebuild the index.

    games is a list of dicts; keys outside GAME_FIELDS are dropped and empty values omitted.
    A picture URL that is not on a known store host is dropped, with a warning.
    """
    os.makedirs(SITE_DATA_DIR, exist_ok=True)
    clean = []
    for game in games:
        entry = {key: str(game[key]) for key in GAME_FIELDS if game.get(key) not in (None, "")}
        if "image" in entry and not is_allowed_image(entry["image"]):
            print(f"WARNING: no picture for '{entry.get('title', '?')}': its link is not https "
                  "on a known store host.", file=sys.stderr)
            del entry["image"]
        clean.append(entry)
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
