"""Check the published site data for personal information, then commit and push it."""

import json
import os
import subprocess
import sys

from export_utils import GAME_FIELDS, INDEX_FILE, LIST_FIELDS, SITE_DATA_DIR, load_env

SECRET_VARIABLES = ("STEAM_API_KEY", "STEAM_ID")
PLATFORM_NAMES = {"epic": "Epic", "gog": "GOG", "steam": "Steam"}
# Longest list of titles printed (and committed) per category, to keep messages readable.
MAX_LISTED = 40


def git(*args, check=True):
    # Explicit UTF-8: the Windows default (cp1252) garbles titles such as "Rocket League®".
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if check and result.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{result.stderr}")
    return result.stdout


def validate():
    """Return the list files after checking they hold only whitelisted fields and no secrets."""
    if not os.path.isdir(SITE_DATA_DIR):
        sys.exit(f"{SITE_DATA_DIR} not found. Run the exporters first.")
    names = sorted(f for f in os.listdir(SITE_DATA_DIR) if f.endswith(".json") and f != INDEX_FILE)
    if not names:
        sys.exit(f"No list files in {SITE_DATA_DIR}. Run the exporters first.")

    secrets = [os.environ[name] for name in SECRET_VARIABLES if os.environ.get(name)]
    for name in names:
        path = os.path.join(SITE_DATA_DIR, name)
        with open(path, encoding="utf-8") as file:
            text = file.read()
        data = json.loads(text)
        if set(data) != set(LIST_FIELDS):
            sys.exit(f"{path}: unexpected fields {sorted(set(data) ^ set(LIST_FIELDS))}")
        for game in data["games"]:
            extra = set(game) - set(GAME_FIELDS)
            if extra:
                sys.exit(f"{path}: unexpected game fields {sorted(extra)}")
        for secret in secrets:
            if secret in text:
                sys.exit(f"{path}: contains a value from your .env. Not publishing.")
    return names


def list_label(data):
    return f"{PLATFORM_NAMES.get(data['platform'], data['platform'])} ({data['device'].capitalize()})"


def read_current(name):
    with open(os.path.join(SITE_DATA_DIR, name), encoding="utf-8") as file:
        return json.load(file)


def read_published(name):
    """Return the version of a list file in the last commit, or None if it was never committed."""
    text = git("show", f"HEAD:site/data/{name}", check=False)
    try:
        return json.loads(text)
    except ValueError:
        return None


def game_key(game):
    return game.get("id") or game["title"]


def describe_update(old, new):
    parts = []
    if old["title"] != new["title"]:
        parts.append(f"renamed from '{old['title']}'")
    for field in GAME_FIELDS:
        if field in ("id", "title"):
            continue
        if old.get(field) != new.get(field):
            parts.append(f"{field}: '{old.get(field, '')}' -> '{new.get(field, '')}'")
    return f"{new['title']} ({', '.join(parts)})"


def compare(name):
    """Return the changes of one list since the last commit, or None when there are none."""
    new = read_current(name)
    old = read_published(name)
    old_games = {game_key(g): g for g in old["games"]} if old else {}
    new_games = {game_key(g): g for g in new["games"]}

    added = sorted((g["title"] for k, g in new_games.items() if k not in old_games), key=str.lower)
    removed = sorted((g["title"] for k, g in old_games.items() if k not in new_games), key=str.lower)
    updated = sorted(
        (describe_update(old_games[k], g) for k, g in new_games.items()
         if k in old_games and any(old_games[k].get(f) != g.get(f) for f in GAME_FIELDS)),
        key=str.lower,
    )
    if not (added or removed or updated):
        return None
    return {
        "label": list_label(new),
        "is_new_list": old is None,
        "total": new["count"],
        "added": added,
        "removed": removed,
        "updated": updated,
    }


def format_titles(heading, symbol, items):
    if not items:
        return []
    lines = [f"  {heading} ({len(items)}):"]
    lines += [f"    {symbol} {item}" for item in items[:MAX_LISTED]]
    if len(items) > MAX_LISTED:
        lines.append(f"    ... and {len(items) - MAX_LISTED} more")
    return lines


def format_changes(changes):
    lines = []
    for change in changes:
        header = f"{change['label']}: "
        header += "new list, " if change["is_new_list"] else ""
        header += f"{change['total']} games"
        lines += ["", header]
        lines += format_titles("Added", "+", change["added"])
        lines += format_titles("Removed", "-", change["removed"])
        lines += format_titles("Updated", "~", change["updated"])
    return lines[1:]


def commit_message(changes):
    summary = ", ".join(
        f"{c['label']} +{len(c['added'])} -{len(c['removed'])} ~{len(c['updated'])}" for c in changes
    )
    return "Update game lists: " + summary + "\n\n" + "\n".join(format_changes(changes))


def last_published():
    return git("log", "-1", "--format=commit %h from %cs", "--", "site/data", check=False).strip()


def publish(prompt):
    """Validate, show what changed since the last commit, ask, then commit and push site/."""
    load_env()
    names = validate()
    print(f"Privacy check passed: {len(names)} lists contain only game data (no personal information).")

    staged = [line for line in git("diff", "--cached", "--name-only").splitlines() if line]
    outside = [path for path in staged if not path.startswith("site/")]
    if outside:
        sys.exit("Other files are already staged, nothing was published:\n  " + "\n  ".join(outside))

    changes = [change for change in map(compare, names) if change]
    if not changes:
        since = last_published()
        print(
            "\nNo change in any game list compared with the last published version"
            + (f" ({since})" if since else "")
            + ".\nNothing to publish."
        )
        return

    print("\nChanges compared with the last published version" + (f" ({last_published()})" if last_published() else "") + ":\n")
    print("\n".join(format_changes(changes)))

    try:
        answer = input("\n" + prompt)
    except EOFError:
        answer = "n"
    if answer.strip().lower() in ("n", "no"):
        print("Not published. The lists are updated locally only. Run publish-games later to publish.")
        return

    git("add", "--", "site")
    git("commit", "-m", commit_message(changes))
    result = subprocess.run(["git", "push"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        sys.exit(
            "The commit was made but the push failed, so the website is not updated yet.\n"
            "Run 'git push' once the problem is fixed.\n\n" + result.stderr
        )
    print("Pushed. Vercel redeploys the website automatically.")


def offer_publish():
    """Called at the end of each exporter: show the changes and ask whether to publish them."""
    if "--no-publish" in sys.argv:
        return
    publish("Publish to the website now? This will commit and push these changes to GitHub. [Y/n] ")


def main():
    publish("Publish to the website now? This will commit and push these changes to GitHub. [Y/n] ")


if __name__ == "__main__":
    main()
