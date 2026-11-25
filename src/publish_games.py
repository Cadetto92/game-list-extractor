"""Check the published site data for personal information, then commit and push it."""

import json
import os
import subprocess
import sys

from export_utils import (
    GAME_FIELDS, INDEX_FILE, LIST_FIELDS, SITE_DATA_DIR, is_allowed_image, load_env, parse_args,
)

SECRET_VARIABLES = ("STEAM_API_KEY", "STEAM_ID")
PROFILES_FILE = os.path.join("site", "profiles.json")
# Public friend names are the only account details allowed, and only in this hand-edited file.
PROFILE_FIELDS = {"platform", "label", "value", "note", "url"}
PROFILE_REQUIRED = ("platform", "label", "value")
FRIEND_CODE_LABEL = "friend code"
# A SteamID64 is this base plus the 32-bit account number, which is also the Steam friend code.
STEAM_ID64_BASE = 76561197960265728
# The only files allowed in site/ besides the lists in site/data/*.json.
SITE_FILES = {"site/index.html", "site/style.css", "site/app.js", "site/profiles.json"}
PLATFORM_NAMES = {"epic": "Epic", "gog": "GOG", "steam": "Steam"}
# Maximum number of titles printed (and committed) per category, to keep messages readable.
MAX_LISTED = 40
# A list that loses more than this share of its games needs a second, typed confirmation.
MAX_REMOVED_PERCENT = 10
DATA_PREFIX = "site/data/"
# Every commit must use a GitHub no-reply address: the repository is public.
NOREPLY_SUFFIX = "@users.noreply.github.com"


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
        try:
            data = json.loads(text)
        except ValueError as error:
            sys.exit(f"{path}: not valid JSON ({error}). Run the exporter again.")
        if not isinstance(data, dict) or set(data) != set(LIST_FIELDS):
            sys.exit(f"{path}: unexpected fields. Expected exactly {sorted(LIST_FIELDS)}.")
        if not isinstance(data["games"], list) or data["count"] != len(data["games"]):
            sys.exit(f"{path}: the game count does not match the list. Run the exporter again.")
        if not data["games"]:
            sys.exit(
                f"{path}: the list is empty (0 games). This looks like a failed export, so nothing "
                "was published. Run the exporter again."
            )
        for game in data["games"]:
            if not isinstance(game, dict) or not isinstance(game.get("title"), str) or not game["title"].strip():
                sys.exit(f"{path}: a game has no title. Not publishing.")
            if not all(isinstance(value, str) for value in game.values()):
                sys.exit(f"{path}: '{game['title']}' has a value that is not text. Not publishing.")
            extra = set(game) - set(GAME_FIELDS)
            if extra:
                sys.exit(f"{path}: unexpected game fields {sorted(extra)}")
            check_image(path, game)
        for secret in secrets:
            if secret in text:
                sys.exit(f"{path}: contains a value from your .env. Not publishing.")
    check_site_files(secrets)
    validate_profiles(secrets)
    return names


def check_image(path, game):
    """Exit unless the game's picture URL (if any) is https on a known store picture host."""
    image = game.get("image")
    if image is not None and not is_allowed_image(image):
        sys.exit(f"{path}: image URL for '{game['title']}' is not https on a known store host.")


def check_site_files(secrets):
    """Exit if site/ holds a file that is not part of the website, or any file with a .env value.

    A stray file (a note, a copied .env) must never end up in a commit unnoticed.
    """
    listed = git("ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "site")
    paths = sorted({p for p in listed.split("\0") if p and os.path.isfile(p)})
    unexpected = [
        p for p in paths
        if p not in SITE_FILES and not is_list_file(p)
    ]
    if unexpected:
        sys.exit(
            "Unexpected files in site/, nothing was published. Move or delete them, or add them "
            "to SITE_FILES in publish_games.py if they belong to the website:\n  "
            + "\n  ".join(unexpected)
        )
    for path in paths:
        with open(path, "rb") as file:
            content = file.read()
        for secret in secrets:
            if secret.encode("utf-8") in content:
                sys.exit(f"{path}: contains a value from your .env. Not publishing.")


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
        if old.get(field) == new.get(field):
            continue
        if field == "image":
            # URLs are long, so only say what happened.
            parts.append("image updated" if old.get(field) else "image added")
        else:
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
        "name": name,
        "old_date": old["extract_date"] if old else None,
        "new_date": new["extract_date"],
        "label": list_label(new),
        "is_new_list": old is None,
        "total": new["count"],
        "old_total": len(old_games),
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


def date_text(old_date, new_date):
    return f"date {old_date} -> {new_date}"


def format_changes(changes, refreshed=()):
    """Lines describing the game changes (with any date change) and the lists with only a new date."""
    lines = []
    for change in changes:
        header = f"{change['label']}: "
        header += "new list, " if change["is_new_list"] else ""
        header += f"{change['total']} games"
        if change["old_date"] and change["old_date"] != change["new_date"]:
            header += f" ({date_text(change['old_date'], change['new_date'])})"
        lines += ["", header]
        lines += format_titles("Added", "+", change["added"])
        lines += format_titles("Removed", "-", change["removed"])
        lines += format_titles("Updated", "~", change["updated"])
    for _, label, old_date, new_date in refreshed:
        lines += ["", f"{label}: no game changed, {date_text(old_date, new_date)}"]
    return lines[1:]


def commit_message(changes, refreshed):
    if changes:
        subject = "Update game lists: " + ", ".join(
            f"{c['label']} +{len(c['added'])} -{len(c['removed'])} ~{len(c['updated'])}" for c in changes
        )
        if refreshed:
            subject += "; new date: " + ", ".join(label for _, label, *_ in refreshed)
    else:
        subject = "Refresh list dates: " + ", ".join(label for _, label, *_ in refreshed)
    return subject + "\n\n" + "\n".join(format_changes(changes, refreshed))


def refreshed_lists(changes, names):
    """Return (file name, label, old date, new date) for lists with no game change but a newer date."""
    changed = {change["name"] for change in changes}
    refreshed = []
    for name in names:
        if name in changed:
            continue
        old = read_published(name)
        new = read_current(name)
        if old and old["extract_date"] != new["extract_date"]:
            refreshed.append((name, list_label(new), old["extract_date"], new["extract_date"]))
    return refreshed


def refresh_dates(refreshed):
    """No game changed, but the lists were refreshed: offer to publish only the new dates.

    Returns True when the dates were committed and pushed.
    """
    print("\nNo game changed in any list since the last published version.\n")
    print("\n".join(format_changes([], refreshed)))
    try:
        answer = input('\nUpdate only the "last updated" date on the website? [y/N] ')
    except EOFError:
        answer = "n"
    if answer.strip().lower() not in ("y", "yes"):
        print("Not published. The new dates stay on this computer only.")
        return False
    paths = [f"{DATA_PREFIX}{name}" for name, *_ in refreshed]
    git("add", "--", *paths)
    git("commit", "-m", commit_message([], refreshed), "--only", "--", *paths)
    print("Committed on this computer.")
    push()
    return True


def large_removals(changes):
    """Return the lists that lose more than MAX_REMOVED_PERCENT of their games."""
    return [
        c for c in changes
        if not c["is_new_list"] and len(c["removed"]) * 100 > c["old_total"] * MAX_REMOVED_PERCENT
    ]


def confirm_large_removals(large):
    """Warn about lists that lose many games and require typing the word 'publish'."""
    print(f"\nWARNING: this looks like a failed or partial export. More than {MAX_REMOVED_PERCENT}% "
          "of the games would be removed from:")
    for change in large:
        print(f"  {change['label']}: {len(change['removed'])} of {change['old_total']} games removed")
    print("Publishing replaces the website lists with these shorter ones.")
    try:
        answer = input("Type 'publish' to continue, anything else cancels: ")
    except EOFError:
        answer = ""
    return answer.strip().lower() == "publish"


def is_list_file(path):
    """True for the only files this script may publish: site/data/*.json."""
    return path.startswith(DATA_PREFIX) and path.endswith(".json") and path.count("/") == 2


def unpushed_commits():
    """Return the number of local commits that are not on the remote branch yet (0 if unknown)."""
    count = git("rev-list", "--count", "@{u}..HEAD", check=False).strip()
    return int(count) if count.isdigit() else 0


def check_commits():
    """Exit unless every commit that would go public is safe.

    git push sends all local commits that are not on the remote yet, not only the site/ commit
    made here, and each commit carries its author and committer e-mail. So check both the
    identity used for the new commit and the commits already waiting.
    """
    # Without a remote branch to compare with, there is no way to know what a push would send.
    if not git("rev-parse", "--abbrev-ref", "@{u}", check=False).strip():
        sys.exit(
            "Nothing was published: the current branch does not track a branch on GitHub, so the "
            "commits a push would send cannot be checked.\n"
            "Set it up once yourself with: git push -u origin <branch>"
        )
    emails = {git("config", "user.email", check=False).strip()}
    waiting = git("log", "--format=%ae%n%ce", "@{u}..HEAD", check=False).split()
    emails.update(waiting)
    bad = sorted(email or "(not set)" for email in emails if not email.endswith(NOREPLY_SUFFIX))
    if bad:
        sys.exit(
            "Nothing was published: this repository is public and commits must use your GitHub "
            f"no-reply address (ending in {NOREPLY_SUFFIX}). Found:\n  " + "\n  ".join(bad)
            + "\nSet it with: git config user.email <your no-reply address>\n"
            "(commits already made with another address must be rewritten before pushing)."
        )
    outside = sorted({
        path for path in git("diff", "--name-only", "@{u}..HEAD", check=False).splitlines()
        if path and not is_list_file(path)
    })
    if outside:
        sys.exit(
            "Nothing was published: other commits waiting on this computer would also be pushed, "
            "and they change files other than the game lists:\n  " + "\n  ".join(outside)
            + "\nPush or remove those commits yourself first, then run publish-games again."
        )


def push():
    result = subprocess.run(["git", "push"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        sys.exit(
            "The push failed, so the website is not updated yet.\n"
            "Run 'git push' once the problem is fixed.\n\n" + result.stderr
        )
    print("Pushed. If the Vercel project is connected to this repository, it redeploys the website automatically.")


def last_published(scope):
    return git("log", "-1", "--format=commit %h from %cs", "--", scope, check=False).strip()


def publish(prompt):
    """Validate, show what changed since the last commit, ask, then commit and push.

    Only the game lists (site/data/*.json) are ever committed, and only the files this script
    just checked. Any other change (website files, profiles.json, other staged files or waiting
    commits) stops the publish before anything is committed or pushed.
    """
    load_env()
    names = validate()
    lists = f"{len(names)} {'list contains' if len(names) == 1 else 'lists contain'}"
    print(f"Privacy check passed: {lists} only game data.")
    if os.path.exists(PROFILES_FILE):
        print(f"{PROFILES_FILE} checked: only public names found, no value from your .env.")

    staged = [line for line in git("diff", "--cached", "--name-only").splitlines() if line]
    outside = [path for path in staged if not is_list_file(path)]
    if outside:
        sys.exit("Other files are already staged, nothing was published:\n  " + "\n  ".join(outside))

    files = site_file_changes()
    if files:
        sys.exit(
            "Nothing was published. These website files have changes that were not made by the "
            "scripts:\n  " + "\n  ".join(files)
            + "\nCommit and push your website changes first (or undo them), then run the scripts "
            "or publish-games again to publish the game lists."
        )

    check_commits()

    changes = [change for change in map(compare, names) if change]
    since = last_published(DATA_PREFIX)
    reference = f" ({since})" if since else ""
    waiting = unpushed_commits()
    refreshed = refreshed_lists(changes, names)
    if not changes and refreshed:
        if refresh_dates(refreshed) or not waiting:
            return
    if not changes and waiting:
        print(
            f"\nNo new changes, but {waiting} commit{'s are' if waiting != 1 else ' is'} on this "
            "computer only (an earlier push probably failed), so the website is not updated yet."
        )
        try:
            answer = input("Push now? [y/N] ")
        except EOFError:
            answer = "n"
        if answer.strip().lower() in ("y", "yes"):
            push()
        else:
            print("Not pushed. Run publish-games again or 'git push' later.")
        return
    if not changes:
        print(
            "\nNo changes in any of the game lists compared with the last "
            f"published version{reference}.\nNothing to publish."
        )
        return

    print(f"\nChanges compared with the last published version{reference}:\n")
    print("\n".join(format_changes(changes, refreshed)))

    try:
        answer = input("\n" + prompt)
    except EOFError:
        answer = "n"
    if answer.strip().lower() not in ("y", "yes"):
        print("Not published. The changes stay on this computer only. Run publish-games later to publish.")
        return

    large = large_removals(changes)
    if large and not confirm_large_removals(large):
        print("Not published. The changes stay on this computer only. Run the exporter again.")
        return

    # Commit exactly the checked list files and nothing else, whatever else is in the index.
    paths = [f"{DATA_PREFIX}{name}" for name in [*names, INDEX_FILE]]
    git("add", "--", *paths)
    git("commit", "-m", commit_message(changes, refreshed), "--only", "--", *paths)
    print("Committed on this computer.")
    push()


PROMPT = "Publish to the website now? This will commit and push these changes to GitHub. [y/N] "


def offer_publish():
    """Called at the end of each exporter: show the changes and ask whether to publish them."""
    if "--no-publish" in sys.argv:
        return
    publish(PROMPT)


def main():
    parse_args(__doc__, exporter=False)
    publish(PROMPT)


if __name__ == "__main__":
    main()
