# Game List Extractor

Python command-line tools that export owned games from Epic, GOG, and Steam to CSV files, and a small website that shows the lists.

## Website

My game list is published at: **<https://my-game-list-cadetto.vercel.app>** (hosted free on Vercel). It has the tabs All / Epic / GOG / Steam, with a Windows / Android switch on the Epic tab, a title search, and an **Add me as a friend** box with my Steam, Epic and GOG names. It works on phones too.

## Project layout

```
src/
  epic_games.py     Epic exporter
  gog_games.py      GOG exporter
  steam_games.py    Steam exporter
  export_utils.py   Shared helpers (CSV writing, site data writing, .env loading)
  publish_games.py  Checks the site data, then commits and pushes it
site/               Static website (index.html, style.css, app.js)
site/data/          Published game lists as JSON, written by the exporters (committed)
site/profiles.json  Hand-edited friend names shown on the site (Steam, Epic, GOG)
vercel.json         Tells Vercel to serve the site/ folder
results/            CSV files written by the exporters (created on first run, ignored by git)
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

"Title","App ID","Developer"
"Borderlands 2","Dodo","2K Games, Inc."
```

To open a file in Google Sheets, use **File > Import > Upload**. It handles the quotes and the commas inside values.

## Publishing the website

Each exporter also writes its list to `site/data/` (for example `site/data/epic_windows.json`). The website reads those files. To update it:

1. Run the exporters you want to refresh.
2. When an exporter finishes, it compares the new lists with the last published version and prints, per platform and device, the games added, removed and updated. It then asks `Publish to the website now? This will commit and push these changes to GitHub. [y/N]`. Answer `y` to check the data, commit and push `site/data/`; the commit message contains the same summary. Press Enter or answer `n` to keep the change local. If no game changed, it says so and does not ask anything.
3. If the Vercel project is connected to this repository (see the setup below), it redeploys automatically after the push.

Add `--no-publish` to an exporter (for example `export-steam-games --no-publish`) to skip the question. `publish-games` does the same check, commit and push on its own, for example to publish several refreshed lists in one commit.

By default only the game lists in `site/data/` are published. Changes to the website itself (`site/index.html`, `style.css`, `app.js`) and to `site/profiles.json` are listed as "NOT included" so that unfinished page edits are never pushed with a list update. When you want to publish them, run `publish-games --site`.

### What is published

Only game information: title, store ID, developer or category, store link, the extract date and counts, per platform and device. The exporters never write anything else. Never published by the exporters: `.env`, the Steam API key and SteamID64, any account name or credentials, playtime, and the CSV files in `results/`.

The one exception is the optional **Add me as a friend** section, filled by hand in `site/profiles.json`: a Steam friend code, an Epic display name and a GOG username, so that people can add you. Edit or delete that file to change or remove the section. Only put names there that you are happy for strangers to see: never a login name, email, password or API key. Note that a Steam friend code is your Steam account number, from which your SteamID64 can be worked out.

The publishing step refuses to publish if a list file contains any other field; if `profiles.json` is not valid, lacks a `platform`, `label` or `value`, or has fields other than `platform`, `label`, `value`, `note` and `url`; if any file contains a value from your `.env`; if the friend code worked out from your `STEAM_ID` appears anywhere in `profiles.json` except as the value of the entry labelled "Friend code"; or if other files are staged. The page also asks search engines not to index it.

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

The exporter writes two files with the columns `Title`, `App ID`, `Developer`:

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

The exporter writes `results/gog_games.csv` with the columns `Title`, `Product ID`, `Category`, `Store URL`. `Category` and `Store URL` are empty when GOG does not provide them, for example for games not sold on their own. `site/data/gog_windows.json` is written for the website.

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

The exporter writes `results/steam_games.csv` with the columns `Title`, `App ID`, `Playtime (hours)`, `Store URL`. Free games you have played are included. `site/data/steam_windows.json` is written for the website, without the playtime.

If no games are returned, check your SteamID64 and the **Game details** privacy setting.
