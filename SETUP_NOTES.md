# System B (new-artist) — Manual Setup Runbook

Everything below must be done **by you**, outside of any worker terminal.
The scaffold (venv, editable install, git remote) is already done — this doc covers the external steps.

---

## 1. Create the GitHub repo

- Go to https://github.com/new
- Repo name: `claude-code-swing-scanner` (under user `NamanVinayak`)
- Visibility: Private (recommended) or Public
- Do NOT initialize with README, .gitignore, or license (we already have a working tree)
- After creation, push the existing working tree:

```bash
cd /Users/naman/Downloads/new-artist
git push -u origin main
```

---

## 2. Create the new Turso database

```bash
turso db create hedge-fund-experimental
turso db show hedge-fund-experimental    # copy the libsql URL
turso db tokens create hedge-fund-experimental   # copy the token
```

Then create your `.env` from the template:

```bash
cp /Users/naman/Downloads/new-artist/.env.example /Users/naman/Downloads/new-artist/.env
# Edit .env and fill in:
#   TURSO_DATABASE_URL = the libsql URL from turso db show
#   TURSO_AUTH_TOKEN   = the token from turso db tokens create
```

Initialize the tables in the new DB:

```bash
cd /Users/naman/Downloads/new-artist
.venv/bin/python -c "from tracker.turso_client import create_all_tables; create_all_tables()"
```

---

## 3. Set GitHub Actions secrets in the new repo

Go to: https://github.com/NamanVinayak/claude-code-swing-scanner/settings/secrets/actions

Add:
- `TURSO_DATABASE_URL` = same value as your `.env`
- `TURSO_AUTH_TOKEN`   = same value as your `.env`
- `FINNHUB_API_KEY`    = (optional; same as System A if you want)

These secrets are used by `dashboard.yml` and any future cron workflows.

---

## 4. Create the gh-pages branch for the dashboard

Run these commands exactly (they create an orphan branch with a placeholder):

```bash
cd /Users/naman/Downloads/new-artist
git checkout --orphan gh-pages
git rm -rf .
echo "<h1>System B dashboard placeholder</h1>" > index.html
git add index.html
git commit -m "Initialize gh-pages branch"
git push -u origin gh-pages
git checkout main
```

Then in the GitHub repo settings:
- Go to Settings → Pages
- Set source to `gh-pages` branch, root folder
- Save

Eventual dashboard URL: https://namanvinayak.github.io/claude-code-swing-scanner/

---

## 5. Boundary rule (important)

This project is a fork of `/Users/naman/Downloads/artist/`. After this scaffold step, code in `new-artist/` evolves independently.

- Bug fixes can flow forward via periodic `git fetch` from the artist repo + manual cherry-pick
- **Do not import anything from `/Users/naman/Downloads/artist/` in this project's code**
- No live shared modules between System A and System B

---

## 6. Sanity check after manual setup

Run these to confirm everything is wired up:

```bash
# Correct remote
cd /Users/naman/Downloads/new-artist && git remote -v
# Expected: origin  https://github.com/NamanVinayak/claude-code-swing-scanner.git (fetch)

# Real Turso credentials in .env
cat .env | grep TURSO
# Expected: real URLs/tokens, not placeholders

# Empty DB (fresh — no rows yet)
.venv/bin/python -c "from tracker.turso_client import get_all_trades; print(len(get_all_trades()))"
# Expected: 0

# Smoke test still passes
.venv/bin/python -c "from ai_hedge.data.api import get_prices; print(len(get_prices('AAPL', '2024-01-01', '2024-03-01')), 'bars')"
# Expected: 41 bars
```
