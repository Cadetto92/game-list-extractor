# Game List Extractor

Python command-line tools that export owned games from Epic, GOG, and Steam to CSV files, and a small website that shows the lists.

## Website

My game list is published at: **<https://REPLACE-WITH-VERCEL-URL.vercel.app>** (hosted free on Vercel, tabs All / Epic / GOG / Steam, with a Windows / Android switch on the Epic tab).

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
vercel.json         Tells Vercel to serve the site/ folder
results/            CSV files written by the exporters (created on first run, ignored by git)
epic_exclude.txt    App IDs to leave out of the Epic export
.env.example        Template for the Steam settings in .env
```

Run the commands from the project directory: they read `epic_exclude.txt` and `.env` from the current directory and write to `results/` inside it.

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
2. When an exporter finishes, it compares the new lists with the last published version and prints, per platform and device, the games added, removed and updated. It then asks `Publish to the website now? This will commit and push these changes to GitHub. [Y/n]`. Press Enter (or `y`) to check the data, commit and push `site/`; the commit message contains the same summary. Answer `n` to keep the change local. If no game changed, it says so and does not ask anything.
3. Vercel redeploys automatically after the push.

Add `--no-publish` to an exporter (for example `export-steam-games --no-publish`) to skip the question. `publish-games` does the same check, commit and push on its own, for example to publish several refreshed lists in one commit.

### What is published

Only game information: title, store ID, developer or category, store link, the extract date and counts, per platform and device. Never published: `.env`, the Steam API key and SteamID64, any account name or credentials, playtime, and the CSV files in `results/`. The publishing step refuses to publish if a list file contains any other field, or a value from your `.env`, or if other files are staged. The page also asks search engines not to index it.

To avoid exposing a personal email address in commits, set your GitHub no-reply address: `git config user.email "<id>+<username>@users.noreply.github.com"`.

### One-time Vercel setup

1. Sign in at <https://vercel.com> with GitHub and choose **Add New > Project**, then import this repository.
2. Framework Preset: **Other**. Leave the build command empty. `vercel.json` already sets the output folder to `site`.
3. Deploy, then put the resulting URL in the **Website** section above.

To preview locally: `python -m http.server -d site`, then open <http://localhost:8000>.

## Common setup on Windows

Create and activate a virtual environment, then install the project:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

In the VS Code terminal, the Python extension activates `.venv` automatically. If you move or rename the project folder, delete `.venv` and create it again.

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
