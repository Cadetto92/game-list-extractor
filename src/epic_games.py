"""Export the list of games you own on Epic to CSV files and website data."""

import importlib.util
import json
import shutil
import subprocess
import sys
import time
import urllib.parse

from export_utils import parse_args, write_csv, write_raw_json, write_site_data
from publish_games import offer_publish

RAW_OUTPUT = "epic_games.json"
WINDOWS_OUTPUT = "epic_games_windows.csv"
ANDROID_OUTPUT = "epic_games_android.csv"
HEADER = ["Title", "App ID", "Developer", "Image URL"]
EXCLUDE = "epic_exclude.txt"
ATTEMPTS = 3
RETRY_DELAY = 5


def read_excluded():
    """Return the App IDs listed in the exclusion file, if there is one."""
    try:
        with open(EXCLUDE, encoding="utf-8-sig") as file:
            lines = [line.split("#", 1)[0].strip() for line in file]
    except FileNotFoundError:
        return set()
    return {line for line in lines if line}


def platforms(game):
    """Return the platforms a game is released on."""
    metadata = game.get("metadata") or {}
    return {
        platform
        for release in metadata.get("releaseInfo") or []
        for platform in release.get("platform") or []
    }


def image_url(game):
    """Return a small wide picture of the game, or "" when Epic has none."""
    images = {i.get("type"): i.get("url") for i in (game.get("metadata") or {}).get("keyImages") or []}
    url = images.get("DieselGameBox") or images.get("DieselGameBoxWide")
    if not url:
        return ""
    # Epic's originals are 2560 px wide PNGs (over 1 MB); its CDN resizes them on request.
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query)
    query = [(k, v) for k, v in query if k not in ("h", "w", "resize")] + [("h", "270"), ("resize", "1"), ("w", "480")]
    # Titles can put spaces in the path; "%" stays so that encoded characters are not encoded twice.
    return urllib.parse.urlunsplit((
        parts.scheme, parts.netloc, urllib.parse.quote(parts.path, safe="/%"),
        urllib.parse.urlencode(query), "",
    ))


def to_row(game):
    metadata = game.get("metadata") or {}
    return [
        game.get("app_title", ""), game.get("app_name", ""), metadata.get("developer", ""), image_url(game),
    ]


def to_site(game):
    metadata = game.get("metadata") or {}
    return {
        "title": game.get("app_title", ""),
        "id": game.get("app_name", ""),
        "developer": metadata.get("developer", ""),
        "image": image_url(game),
    }


def find_legendary():
    """Return the command that starts Legendary, as a list, or None if it is not installed."""
    # Running it as a module avoids legendary.exe, which a Windows Application Control
    # policy can block. It also needs no PATH entry or activated venv.
    if importlib.util.find_spec("legendary") is not None:
        return [sys.executable, "-m", "legendary.cli"]
    exe = shutil.which("legendary")
    return [exe] if exe else None


def main():
    options = parse_args(__doc__)
    legendary = find_legendary()
    if not legendary:
        sys.exit("Legendary not found. Install the Epic extra and authenticate with: legendary auth")

    # No --force-refresh: Legendary still lists new purchases, and reusing its cached
    # metadata avoids one request per game, each of which can time out.
    cmd = [*legendary, "list", "--json", "-T"]
    for attempt in range(1, ATTEMPTS + 1):
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            break
        if attempt < ATTEMPTS:
            print(
                f"Reading your library failed (attempt {attempt}/{ATTEMPTS}), "
                f"retrying in {RETRY_DELAY} seconds...",
                file=sys.stderr,
            )
            time.sleep(RETRY_DELAY)
    else:
        if "timed out" in result.stderr.lower():
            sys.exit(
                f"Epic's servers did not respond in time after {ATTEMPTS} attempts. "
                "Try again in a few minutes.\n\n" + result.stderr
            )
        sys.exit(
            "Could not read your library. If you are not logged in, run: legendary auth\n\n"
            + result.stderr
        )

    games = json.loads(result.stdout)
    if options.json:
        write_raw_json(RAW_OUTPUT, games)

    excluded = read_excluded()
    unknown = excluded - {game.get("app_name", "") for game in games}
    if unknown:
        print(
            f"WARNING: these App IDs in {EXCLUDE} are not in your library and were ignored:\n"
            + "\n".join(f"  {app_id}" for app_id in sorted(unknown))
            + f"\nCheck these values in {EXCLUDE}: there is probably a typo.\n",
            file=sys.stderr,
        )
    games = [game for game in games if game.get("app_name", "") not in excluded]
    games.sort(key=lambda game: (game.get("app_title") or "").lower())

    # Anything that is not Android-only goes in the Windows file, so no game is dropped.
    android = [game for game in games if "Android" in platforms(game)]
    windows = [game for game in games if platforms(game) != {"Android"}]

    write_csv(WINDOWS_OUTPUT, HEADER, [to_row(game) for game in windows])
    write_csv(ANDROID_OUTPUT, HEADER, [to_row(game) for game in android])
    write_site_data("epic", "windows", [to_site(game) for game in windows])
    write_site_data("epic", "android", [to_site(game) for game in android])
    offer_publish()


if __name__ == "__main__":
    main()
