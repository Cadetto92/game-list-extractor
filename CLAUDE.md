# Notes for Claude Code sessions

Python tools that export owned games from Epic, GOG and Steam to CSV (private, `results/`) and to JSON in `site/data/`, plus a static website (`site/`) hosted free on Vercel. Read `README.md` first: it documents usage, publishing and the Vercel setup.

## Privacy rules (most important)

This repository is **public**. Only game lists and the optional friend names may be committed.

- Never commit or print: `.env`, the Steam API key, the SteamID64, login names, emails, passwords, playtime, anything from `results/`.
- Exporters write only whitelisted fields to `site/data/` (`GAME_FIELDS` in `src/export_utils.py`). Do not add fields such as playtime.
- `site/profiles.json` is the only place for account names (friend names, entered by hand by the owner). Do not fill it from `.env` or the exporters, and do not copy its values into other files.
- `src/publish_games.py` checks all of this before every publish. Keep those checks working when you change it, and never weaken them to make a publish pass.
- Commits must use the GitHub no-reply address (see the README). Do not put a personal email in commits, docs or code.
- When looking at `.env`, test values without printing them (for example, print only booleans).

## Workflow rules

- Do not commit or push unless the user asks. The user usually publishes with `publish-games` (or the prompt at the end of an exporter), which commits and pushes everything under `site/` (game lists, page code, `profiles.json`) after the privacy checks.
- Test publishing and git behaviour in a throwaway repository in the scratchpad, never in this repo.
- The `refs/agents/...` refs in `.git` are local checkpoints from the agent host. Leave them alone; they are not pushed.

## Conventions

- Plain Python 3.9+, standard library only (Legendary is an optional dependency for Epic). Site is vanilla HTML/CSS/JS with no build step; build page text with `textContent`, never `innerHTML`.
- User-facing text (README, messages, comments) is in English, short and plain. Keep the README in step with any behaviour change, including prompts and options.
- Messages must not suggest something is published when it is only saved locally.
- The site is dark, "geeky" themed and must stay responsive (check 390 px and 320 px wide). It is a plain list: a thumbnail, the title and a platform tag, no other columns. Thumbnails are hotlinked from the store CDNs (never downloaded or committed) and must have a fixed box so rows stay aligned.
- Keep tabs and tags visually different: tabs and switches are outlined rounded buttons; platform tags are flat square badges with a dot on each side. Epic Windows shows as "Epic" and only Android is named ("Epic (Android)"). An empty search shows "No game matches your search." and the footer link stays small and grey so it cannot be mistaken for a game.
- Windows 11, PowerShell, VS Code. Application Control may block pip's `.exe` launchers, so run scripts as `python src\<name>.py` and start Legendary through `python -m legendary.cli` (already done in `epic_games.py`).
- When reading git output on Windows, force UTF-8 (see `git()` in `publish_games.py`): titles contain symbols such as ® and ™.

## Checks before finishing a change

- `python -m py_compile src/*.py` and `node --check site/app.js`.
- Preview with `python -m http.server -d site` (opening `index.html` from disk does not work: `fetch()` is blocked).
- Re-run a privacy scan of everything that would be committed (`git ls-files --cached --others --exclude-standard`) before suggesting a commit.
