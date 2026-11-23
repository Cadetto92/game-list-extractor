"""Export the list of games you own on GOG to a CSV file."""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from export_utils import write_csv, write_site_data
from publish_games import offer_publish

OUTPUT = "gog_games.csv"
# Public client credentials of the GOG Galaxy app, as used by Heroic's gogdl
# (https://github.com/Heroic-Games-Launcher/heroic-gogdl). GOG rejects any other value.
CLIENT_ID = "46899977096215655"
CLIENT_SECRET = "9d85c43b1482497dbbce61f6e4aa173a433796eeae2ca8c5f6129f2dc4de46d9"
REDIRECT_URI = "https://embed.gog.com/on_login_success?origin=client"

LOGIN_URL = (
    "https://auth.gog.com/auth?"
    + urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "layout": "client2",
    })
)


def http_get_json(url, token=None):
    request = urllib.request.Request(url, headers={"User-Agent": "gog-library-export"})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def describe_error(error):
    """Return an error message, including GOG's explanation when it sent one."""
    if isinstance(error, urllib.error.HTTPError):
        try:
            body = json.loads(error.read().decode("utf-8"))
            return f"{error} - {body.get('error_description') or body.get('error')}"
        except ValueError:
            pass
    return str(error)


def extract_code(pasted):
    pasted = pasted.strip()
    if "code=" in pasted:
        query = urllib.parse.urlparse(pasted).query
        return urllib.parse.parse_qs(query)["code"][0]
    return pasted


def get_token(code):
    url = "https://auth.gog.com/token?" + urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    })
    return http_get_json(url)["access_token"]


def get_games(token):
    games, page, total_pages = [], 1, 1
    while page <= total_pages:
        url = ("https://embed.gog.com/account/getFilteredProducts?"
               f"mediaType=1&sortBy=title&page={page}")
        data = http_get_json(url, token)
        total_pages = data.get("totalPages", 1)
        games.extend(data.get("products", []))
        print(f"  page {page}/{total_pages}: {len(games)} games so far")
        page += 1
    return games


def to_row(product):
    url = product.get("url")
    return [
        product.get("title", ""),
        product.get("id", ""),
        product.get("category", ""),
        "https://www.gog.com" + url if url else "",
    ]


def to_site(product):
    row = to_row(product)
    return {"title": row[0], "id": row[1], "category": row[2], "url": row[3]}


def main():
    print("1) Open this link and log in to GOG:\n")
    print(LOGIN_URL + "\n")
    pasted = input("2) Paste the URL of the page you land on (contains 'code='): ")
    try:
        token = get_token(extract_code(pasted))
    except Exception as error:
        sys.exit(f"Login failed ({describe_error(error)}). The code expires quickly: try again.")

    print("Fetching your library...")
    try:
        games = get_games(token)
    except Exception as error:
        sys.exit(f"Could not read your library ({describe_error(error)}).")

    games.sort(key=lambda product: (product.get("title") or "").lower())
    write_csv(OUTPUT, ["Title", "Product ID", "Category", "Store URL"], [to_row(p) for p in games])
    write_site_data("gog", "windows", [to_site(p) for p in games])
    offer_publish()


if __name__ == "__main__":
    main()
