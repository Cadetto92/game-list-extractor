# Game List Extractor

Python command-line tools that export owned games from Epic, GOG, and Steam to CSV files, and a small website that shows the lists.

## Website

My game list is published at: **<https://my-game-list-cadetto.vercel.app>** (hosted free on Vercel). It is a simple list of games with a picture (the store banner) before each title and a coloured platform tag on each (`Steam`, `GOG`, `Epic`, and `Epic (Android)` for the Android version: Windows is the default, so it is not named). It has the tabs All / Epic / GOG / Steam, a Windows / Android switch on the Epic tab, a title search, and an **Add me as a friend** box with my Steam, Epic and GOG names. It works on phones too.

## Project layout

```
src/
  epic_games.py     Epic exporter
  gog_games.py      GOG exporter
  steam_games.py    Steam exporter
  export_utils.py   Shared helpers (CSV writing, site data writing, .env loading)
  publish_games.py  Checks the game lists, then commits and pushes only those lists
site/               Static website (index.html, style.css, app.js)
site/data/          Published game lists as JSON, written by the exporters (committed)
site/profiles.json  Hand-edited friend names shown on the site (Steam, Epic, GOG)
vercel.json         Tells Vercel to serve the site/ folder
results/            CSV files written by the exporters, plus raw JSON replies with --json (created on first run, ignored by git)
epic_exclude.txt    App IDs to leave out of the Epic export
.env.example        Template for the Steam settings in .env
CLAUDE.md           Notes for future Claude Code sessions (privacy rules, conventions)
```

Run the commands from the project directory: they read `epic_exclude.txt` and `.env` from the current directory and write to `results/` and `site/data/` inside it.

## CSV format

The CSV files follow RFC 4180: every value is wrapped in double quotes, a double quote inside a value is written as two (`""`), and an empty value is written as `""`. They are saved as UTF-8 with a byte order mark, so Excel shows accented characters correctly.

Each file starts with the extract date and the number of games, then a blank line, then the column header and one row per game, sorted by title:

```
"Extract date","2026-10-15"
"Number of games","2"

"Title","App ID","Developer","Image URL"
"Borderlands 2","Dodo","2K Games, Inc.","https://cdn1.epicgames.com/..."
```

To open a file in Google Sheets, use **File > Import > Upload**. It handles the quotes and the commas inside values.

## How the data is retrieved

No browser plugin and no scraping. All three platforms return JSON.

| Platform | Mechanism | Official? | Auth |
|---|---|---|---|
| Steam | Direct HTTPS GET, JSON | Yes, documented | API key + SteamID64 |
| GOG | Direct HTTPS GET, JSON | No, reverse-engineered | OAuth2 code flow, Bearer token |
| Epic | Subprocess call to Legendary CLI | No, Legendary wraps a private API | Legendary's own login |

- **Steam** (`src/steam_games.py`): one GET to `https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/`, with your Web API key in the `key` parameter. Your profile's "Game details" must be public.
- **GOG** (`src/gog_games.py`): GOG's internal API, as used by the GOG Galaxy app and website. You log in on `auth.gog.com` in your browser and paste the redirect URL (it contains `code=`). The script exchanges the code for an access token, then calls `embed.gog.com/account/getFilteredProducts` page by page with `Authorization: Bearer <token>`. The client ID and secret are the public ones of the GOG Galaxy app (as used by Heroic's gogdl); they are not personal. GOG may change this API without notice.
- **Epic** (`src/epic_games.py`): the script does not call Epic itself. It runs [Legendary](https://github.com/derrod/legendary) (`python -m legendary.cli list --json -T`) and reads its JSON output. Legendary handles the login (`legendary auth`) and talks to Epic's private launcher API.

## Pictures

Each game has an `Image URL` column in the CSV and an `image` field in `site/data/`: the store's own banner (Steam `header.jpg`, GOG product card, Epic wide box art resized to 480 px). The website shows these links directly (hotlinking). Nothing is downloaded or stored in this repository, and a game whose picture fails to load just shows an empty box. Only `https` links on the stores' picture hosts are kept: an exporter drops any other link with a warning (that game just has no picture), and `publish-games` refuses to publish one. A changed picture link is reported as an update, like a changed title.

## Raw replies (optional)

Add `--json` to any exporter (for example `python src\steam_games.py --json`) to also save the full reply from the platform as `results/epic_games.json`, `results/gog_games.json` or `results/steam_games.json`, so you can see what is available. Without the option nothing is written. These files are for you only: `results/` is ignored by git and never published. Sensitive values are removed first: values under keys such as `key`, `token`, `secret`, `password`, `email`, `username` or `steamid`, your API key and SteamID64 from `.env`, the GOG token and any e-mail address found in text become `[REDACTED]`. Playtime is kept in the Steam file, as it is private.

## Publishing the website

Each exporter also writes its list to `site/data/` (for example `site/data/epic_windows.json`). The website reads those files. To update it:

1. Run the exporters you want to refresh.
2. When an exporter finishes, it compares the new lists with the last published version and prints, per platform and device, the games added, removed and updated. It then asks `Publish to the website now? This will commit and push these changes to GitHub. [y/N]`. Answer `y` to check the data, commit and push `site/data/`; the commit message contains the same summary. Press Enter or answer `n` to keep the change local. If no game changed and no list has a newer date, it says so and does not ask anything.
3. If the Vercel project is connected to this repository (see the setup below), it redeploys automatically after the push.

Add `--no-publish` to an exporter (for example `export-steam-games --no-publish`) to skip the question. `publish-games` does the same check, commit and push on its own, for example to publish several refreshed lists in one commit.

**Only the game lists are published.** `publish-games` commits and pushes the files in `site/data/` that it has just checked, and nothing else. It stops, with nothing committed or pushed, when:

- a website file (`site/index.html`, `style.css`, `app.js`, `profiles.json`) has changed. Commit and push website changes yourself with git, after previewing the page (command below), then publish the lists;
- another file is already staged, or `site/` holds a file that is not part of the website;
- a commit waiting to be pushed changes anything other than the game lists (`git push` would send it too);
- an author or committer e-mail, or the e-mail you are about to commit with, does not end in `@users.noreply.github.com`;
- the current branch does not track a branch on GitHub (set it once with `git push -u origin <branch>`);
- a list is empty (0 games), has a game without a title, or its count does not match its games;
- a file contains a value from your `.env`.

**Big removals.** If a list would lose more than 10% of its games compared with the last published version, a warning names the list and asks you to type `publish` to continue; anything else cancels.

**Dates.** The log always shows date changes: next to a list with game changes (`(date 2026-11-24 -> 2026-11-25)`) and as `no game changed, date ...` for a refreshed list without game changes. The same lines go in the commit message. If no game changed anywhere but a list was refreshed (its date is newer), it asks `Update only the "last updated" date on the website? [y/N]`; on `y` it commits and pushes just those list files.

**Failed push.** If a push failed earlier, `publish-games` says that commits are only on your computer and offers to push them.

### What is published

Only game information: title, store ID, developer or category, store link, picture link, the extract date and counts, per platform and device. The site shows only the picture, the title and the platform tag; developer and category stay in the data files. The exporters never write anything else. Never published by the exporters: `.env`, the Steam API key and SteamID64, any account name or credentials, playtime, and the CSV files in `results/`.

The one exception is the optional **Add me as a friend** section, filled by hand in `site/profiles.json`: a Steam friend code, an Epic display name and a GOG username, so that people can add you. Edit or delete that file to change or remove the section. Only put names there that you are happy for strangers to see: never a login name, email, password or API key. Note that a Steam friend code is your Steam account number, from which your SteamID64 can be worked out.

The publishing step also refuses to publish if a list file contains any other field or a picture link that is not https on a store host; if `profiles.json` is not valid, lacks a `platform`, `label` or `value`, or has fields other than `platform`, `label`, `value`, `note` and `url`; or if the friend code worked out from your `STEAM_ID` appears anywhere in `profiles.json` except as the value of the entry labelled "Friend code". The page also asks search engines not to index it.

To avoid exposing a personal email address in commits, set your GitHub no-reply address: `git config user.email "<id>+<username>@users.noreply.github.com"`.

### One-time Vercel setup

1. Sign in at <https://vercel.com> with GitHub and choose **Add New > Project**, then import this repository.
2. Framework Preset: **Other**. Vercel may pick **Python** because of `pyproject.toml`: change it. Leave the build and install commands empty and do not add environment variables (never upload `.env`). `vercel.json` already sets the output folder to `site`.
3. Choose a neutral project name. If the name is taken, Vercel adds a suffix, so check the real address under **Domains** in the project. Another project may own the plain name.
4. Deploy, then put the resulting URL in the **Website** section above.

To preview locally, run `python -m http.server -d site` and open <http://localhost:8000>. Opening `index.html` directly from the disk does not work, because the page loads the lists with `fetch()`.

## Common setup on Windows

Create and activate a virtual environment, then install the project:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

In the VS Code terminal, the Python extension activates `.venv` automatically. If you move or rename the project folder, delete `.venv` and create it again.

If Windows Application Control blocks the commands below (the small `.exe` launchers created by pip), run the scripts through Python instead, for example `python src\epic_games.py`, `python src\gog_games.py`, `python src\steam_games.py` and `python src\publish_games.py`. The options work the same way.

## Epic

### Setup / prerequisites

The Epic exporter reads your library through [Legendary](https://github.com/derrod/legendary). Install it with the optional `epic` dependency, then sign in once:

```powershell
python -m pip install -e ".[epic]"
legendary auth
```

If Windows Application Control blocks `legendary.exe`, sign in with `python -m legendary.cli auth` instead. The exporter itself starts Legendary through Python, so it is not affected.

Optional: to leave entries out of the export, list their App IDs in `epic_exclude.txt`, one per line (`#` starts a comment).

### Run

```powershell
export-epic-games
```

### Results

The exporter writes two files with the columns `Title`, `App ID`, `Developer`, `Image URL`:

- `results/epic_games_windows.csv`: every game that is not Android-only.
- `results/epic_games_android.csv`: every game released on Android.

It also writes `site/data/epic_windows.json` and `site/data/epic_android.json` for the website.

A title owned on both platforms appears in both files.

If Epic's servers are slow and Legendary fails, the exporter retries up to 3 times before giving up. It stops with an error if Legendary is not installed or if you are not signed in (run `legendary auth` again). If an App ID in `epic_exclude.txt` is not in your library, it prints a warning listing those App IDs and continues. This is usually a typo, so check the value in `epic_exclude.txt`.

## GOG

### Setup / prerequisites

No extra package or account setup is needed. You need your GOG username and password to sign in during the run.

### Run

```powershell
export-gog-games
```

The command prints a GOG sign-in link:

1. Open the link in your browser and sign in.
2. Copy the URL of the page you land on (it contains `code=`) and paste it into the terminal.

The code works only once and expires quickly. If sign-in fails, run the command again.

### Results

The exporter writes `results/gog_games.csv` with the columns `Title`, `Product ID`, `Category`, `Store URL`, `Image URL`. `Category` and `Store URL` are empty when GOG does not provide them, for example for games not sold on their own. `site/data/gog_windows.json` is written for the website.

## Steam

### Setup / prerequisites

No extra package is needed. You need:

- A Steam Web API key, from <https://steamcommunity.com/dev/apikey>. Steam asks for a domain name: any value works, such as `localhost`. Keep the key private.
- Your SteamID64: the 17-digit number shown as **Steam ID** on your Steam **Account details** page.
- **Game details** set to **Public** in your Steam profile's privacy settings.

To avoid typing them at each run, copy `.env.example` to `.env` and fill in `STEAM_API_KEY` and `STEAM_ID`:

```powershell
Copy-Item .env.example .env
```

`.env` is ignored by git, so your key is not committed. Environment variables with the same names, if set, take precedence over `.env`.

### Run

```powershell
export-steam-games
```

If the key or the SteamID64 is not set in `.env` or the environment, the command asks for it. The key is typed hidden.

### Results

The exporter writes `results/steam_games.csv` with the columns `Title`, `App ID`, `Playtime (hours)`, `Store URL`, `Image URL`. Free games you have played are included. `site/data/steam_windows.json` is written for the website, without the playtime.

If no games are returned, check your SteamID64 and the **Game details** privacy setting.
