"""Check the published site data for personal information, then commit and push it."""

import json
import os
import subprocess
import sys

from export_utils import GAME_FIELDS, INDEX_FILE, LIST_FIELDS, SITE_DATA_DIR, load_env

SECRET_VARIABLES = ("STEAM_API_KEY", "STEAM_ID")
PROFILES_FILE = os.path.join("site", "profiles.json")
# Public friend names are the only account details allowed, and only in this hand-edited file.
PROFILE_FIELDS = {"platform", "label", "value", "note", "url"}
PROFILE_REQUIRED = ("platform", "label", "value")
FRIEND_CODE_LABEL = "friend code"
# A SteamID64 is this base plus the 32-bit account number, which is also the Steam friend code.
STEAM_ID64_BASE = 76561197960265728
PLATFORM_NAMES = {"epic": "Epic", "gog": "GOG", "steam": "Steam"}
# Maximum number of titles printed (and committed) per category, to keep messages readable.
MAX_LISTED = 40


def git(*args, check=True):
    # Explicit UTF-8: the Windows default (cp1252) garbles titles such as "Rocket League®".
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if check and result.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{result.stderr}")
    return result.stdout


def derived_friend_code():
    """Return the Steam friend code worked out from STEAM_ID in .env, or None."""
    try:
        code = int(os.environ.get("STEAM_ID", "")) - STEAM_ID64_BASE
    except ValueError:
        return None
    return str(code) if code > 0 else None


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
    validate_profiles(secrets)
    return names


def validate_profiles(secrets):
    """Check the hand-edited friends file, if there is one.

    Each entry needs platform, label and value (text), may only use known fields, and must not
    contain a value from .env. The Steam friend code worked out from STEAM_ID is allowed only as
    the value of an entry labelled "Friend code", because it is published on purpose.
    """
    if not os.path.exists(PROFILES_FILE):
        return
    try:
        with open(PROFILES_FILE, encoding="utf-8") as file:
            text = file.read()
        profiles = json.loads(text)["profiles"]
    except (ValueError, KeyError, TypeError) as error:
        sys.exit(f'{PROFILES_FILE}: cannot read it ({error}). Expected {{"profiles": [ ... ]}}.')
    if not isinstance(profiles, list):
        sys.exit(f'{PROFILES_FILE}: "profiles" must be a list.')

    for number, profile in enumerate(profiles, start=1):
        where = f"{PROFILES_FILE}: entry {number}"
        if not isinstance(profile, dict):
            sys.exit(f"{where} must be an object.")
        extra = set(profile) - PROFILE_FIELDS
        if extra:
            sys.exit(f"{where}: unexpected fields {sorted(extra)}")
        for field in PROFILE_REQUIRED:
            if not isinstance(profile.get(field), str) or not profile[field].strip():
                sys.exit(f"{where}: '{field}' is required and must be text.")
        for field in ("note", "url"):
            if field in profile and not isinstance(profile[field], str):
                sys.exit(f"{where}: '{field}' must be text.")
        if "url" in profile and not profile["url"].startswith("https://"):
            sys.exit(f"{where}: 'url' must start with https://")

    for secret in secrets:
        if secret in text:
            sys.exit(f"{PROFILES_FILE}: contains a value from your .env. Not publishing.")
    code = derived_friend_code()
    if code:
        scanned = json.dumps([
            {**p, "value": "" if p["label"].strip().lower() == FRIEND_CODE_LABEL else p["value"]}
            for p in profiles
        ])
        if code in scanned:
            sys.exit(
                f"{PROFILES_FILE}: your Steam friend code ({code}) appears outside an entry "
                'labelled "Friend code". Not publishing.'
            )


def site_file_changes():
    """Return website files (outside site/data) that are modified or new since the last commit."""
    # -z: unquoted paths separated by NUL, so accents and spaces are safe. A rename or copy
    # entry is followed by one extra entry holding the original path.
    entries = git("status", "--porcelain", "-z", "--untracked-files=all", "--", "site").split("\0")
    paths = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        if entry[0] in "RC":
            index += 1
        paths.append(entry[3:])
    return sorted(path for path in paths if not path.startswith("site/data/"))


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


def commit_message(changes, files):
    subjects = []
    body = []
    if changes:
        subjects.append("Update game lists: " + ", ".join(
            f"{c['label']} +{len(c['added'])} -{len(c['removed'])} ~{len(c['updated'])}" for c in changes
        ))
        body += format_changes(changes)
    if files:
        subjects.append("Update website files")
        body += ([""] if body else []) + ["Website files:"] + [f"  ~ {path}" for path in files]
    return "; ".join(subjects) + "\n\n" + "\n".join(body)


def last_published(scope):
    return git("log", "-1", "--format=commit %h from %cs", "--", scope, check=False).strip()


def publish(prompt):
    """Validate, show what changed since the last commit, ask, then commit and push.

    By default only site/data (the game lists) is published. Website files such as the page
    code and profiles.json are published only with the --site option, so half-finished page
    edits are never pushed together with a game list update.
    """
    include_site = "--site" in sys.argv
    scope = "site" if include_site else "site/data"
    load_env()
    names = validate()
    lists = f"{len(names)} {'list contains' if len(names) == 1 else 'lists contain'}"
    print(f"Privacy check passed: {lists} only game data.")
    if os.path.exists(PROFILES_FILE):
        print(f"{PROFILES_FILE} checked: only the public names you entered, no value from your .env.")

    staged = [line for line in git("diff", "--cached", "--name-only").splitlines() if line]
    outside = [path for path in staged if not path.startswith("site/")]
    if outside:
        sys.exit("Other files are already staged, nothing was published:\n  " + "\n  ".join(outside))

    changes = [change for change in map(compare, names) if change]
    site_files = site_file_changes()
    files = site_files if include_site else []
    skipped = "" if include_site or not site_files else (
        "\nWebsite files changed but NOT included (add --site to publish them):\n"
        + "\n".join(f"  ~ {path}" for path in site_files) + "\n"
    )
    since = last_published(scope)
    reference = f" ({since})" if since else ""
    if not changes and not files:
        what = "game lists or website files" if include_site else "game lists"
        print(
            f"\nNo changes in any of the {what} compared with the last published version"
            + reference + ".\nNothing to publish." + ("\n" + skipped if skipped else "")
        )
        return

    print(f"\nChanges compared with the last published version{reference}:\n")
    if changes:
        print("\n".join(format_changes(changes)))
    if files:
        print(("\n" if changes else "") + "Website files changed:\n" + "\n".join(f"  ~ {path}" for path in files))
    if skipped:
        print(skipped)

    try:
        answer = input("\n" + prompt)
    except EOFError:
        answer = "n"
    if answer.strip().lower() not in ("y", "yes"):
        print("Not published. The changes stay on this computer only. Run publish-games later to publish.")
        return

    git("add", "--", scope)
    git("commit", "-m", commit_message(changes, files))
    result = subprocess.run(["git", "push"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        sys.exit(
            "The commit was made but the push failed, so the website is not updated yet.\n"
            "Run 'git push' once the problem is fixed.\n\n" + result.stderr
        )
    print("Pushed. If the Vercel project is connected to this repository, it redeploys the website automatically.")


def offer_publish():
    """Called at the end of each exporter: show the changes and ask whether to publish them."""
    if "--no-publish" in sys.argv:
        return
    publish("Publish to the website now? This will commit and push these changes to GitHub. [y/N] ")


def main():
    publish("Publish to the website now? This will commit and push these changes to GitHub. [y/N] ")


if __name__ == "__main__":
    main()
