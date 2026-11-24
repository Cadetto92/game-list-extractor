"""Export the list of games owned on a Steam account to a CSV file and website data."""

import getpass
import json
import os
import sys
import urllib.parse
import urllib.request

from export_utils import load_env, parse_args, write_csv, write_raw_json, write_site_data
from publish_games import offer_publish

OUTPUT = "steam_games.csv"
RAW_OUTPUT = "steam_games.json"
API_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"


def get_owned_games(api_key, steam_id):
    params = urllib.parse.urlencode({
        "key": api_key,
        "steamid": steam_id,
        "include_appinfo": 1,
        "include_played_free_games": 1,
        "format": "json",
    })
    with urllib.request.urlopen(f"{API_URL}?{params}", timeout=30) as response:
        return json.load(response)


def image_url(game):
    return f"https://cdn.akamai.steamstatic.com/steam/apps/{game['appid']}/header.jpg"


def to_row(game):
    return [
        game.get("name", ""),
        game["appid"],
        round(game.get("playtime_forever", 0) / 60, 1),
        f"https://store.steampowered.com/app/{game['appid']}",
        image_url(game),
    ]


def to_site(game):
    # Playtime is deliberately left out: it is personal and the site data is public.
    return {
        "title": game.get("name", ""),
        "id": game["appid"],
        "url": f"https://store.steampowered.com/app/{game['appid']}",
        "image": image_url(game),
    }


def main():
    options = parse_args(__doc__)
    load_env()
    api_key = os.environ.get("STEAM_API_KEY") or getpass.getpass("Steam API key: ").strip()
    steam_id = os.environ.get("STEAM_ID") or input("SteamID64: ").strip()

    try:
        reply = get_owned_games(api_key, steam_id)
    except Exception as error:
        # The error text can contain the request URL, which includes the API key.
        message = str(error)
        for secret in (api_key, steam_id):
            if secret:
                message = message.replace(secret, "[REDACTED]")
        sys.exit(f"Request failed ({message}). Check your Steam API key and SteamID64.")

    if options.json:
        write_raw_json(RAW_OUTPUT, reply, [api_key, steam_id])
    games = reply.get("response", {}).get("games", [])

    if not games:
        sys.exit("No games returned. Check your SteamID64, and set "
                 "'Game details' to Public in your Steam privacy settings.")

    games.sort(key=lambda game: (game.get("name") or "").lower())
    write_csv(OUTPUT, ["Title", "App ID", "Playtime (hours)", "Store URL", "Image URL"], [to_row(g) for g in games])
    write_site_data("steam", "windows", [to_site(g) for g in games])
    offer_publish()


if __name__ == "__main__":
    main()
