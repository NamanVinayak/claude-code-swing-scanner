# CLAUDE.md — System B (new-artist)

Guidance for Claude Code when working in **this** repository (System B, experimental). **Keep this file slim.**

## What this project is

**This is System B — an experimental swing-trader-style fork of the production hedge-fund system.** It runs in parallel with, and entirely separate from, System A.

| | System A (production) | System B (this folder) |
|---|---|---|
| Folder | `/Users/naman/Downloads/artist/` | `/Users/naman/Downloads/new-artist/` |
| GitHub | `NamanVinayak/claude-code-hedge-fund` | `NamanVinayak/claude-code-swing-scanner` |
| Turso DB | `hedge-fund-namanvinayak` | `hedge-fund-experimental` |
| Dashboard | https://namanvinayak.github.io/claude-code-hedge-fund/ | https://namanvinayak.github.io/claude-code-swing-scanner/ |
| Decision producer | 14 Cloud Routines, fixed watchlist | Local Desktop Scheduled Tasks, universe scanner (TBD) |
| Status | Live since 2026-04-30 | Scaffolded 2026-05-03; brain not yet built |

**Production is untouched.** Treat `~/Downloads/artist/` as read-only reference. Do not import from it. Do not push to its remote. Do not modify its files.

## Why System B exists

System A is built around a fixed watchlist (19 tickers, hardcoded). It analyzes each name on a schedule. **It is not how real swing traders work** — they scan the whole market for setups daily, then pick the cleanest 1–3.

System B replicates the back-end (data layer, simulator, dashboard, wiki memory) but replaces the front-end with a **swing-trader-style brain**:
- Universe scanner (TradingView MCP + Capitol Trades + Finnhub) finds candidates from ~1000 names
- Adversarial bull/bear/judge debate decides which to actually trade (per-ticker, parallel, fresh context — Lopez-Lira / AlphaAgents inspired)
- Capital allocation rules (1% per-trade risk, 4% total open risk, 60% deployment cap, scaling phase) enforced by the judge
- Wiki memory layer carries learnings forward (per-ticker thesis + setup history + lessons + budget state)

After 2–3 weeks of parallel paper trading, comparison dashboard shows which brain produces better outcomes.

## Architecture — current vs planned

### Inherited from System A (unchanged in this fork)
- `ai_hedge/data/` — yfinance, SEC EDGAR, Finnhub, indicators, cache
- `ai_hedge/personas/` — facts builders, helper functions, persona prompts (System A's; not used by System B's brain yet)
- `ai_hedge/wiki/` — memory layer (inject, loader, manifest, templates, lint)
- `tracker/` — Turso client, simulator, ingester, watchlist config, dashboard
- `dashboard/` — Jinja2 dashboard renderer
- `scripts/` — wiki bootstrap, compactor, drift checks, etc.

### To be built (System B's brain)
- `ai_hedge/data/tradingview.py` — TradingView MCP wrapper + screener helpers (Task 2)
- `ai_hedge/data/capitol_trades.py` — congressional disclosure scraper (Task 3)
- Wiki layer for System B with new pages: `setup_history`, `scanner_state`, `setup_patterns`, `budget_state` (Task 6.5)
- Stage 1 — Sunset Scanner (Task 4)
- Stage 2 — Pre-market Reviewer (Task 5)
- Stage 3 — Adversarial Decision (4 prompts: 2 bull + 2 bear + judge) (Task 6)
- Stage 4 — End-of-Day Journal (Task 7)
- Desktop Scheduled Tasks setup (Task 8)
- Cross-system comparison dashboard (Task 9)

See `HANDOFF.md` for the live build status.

## The four-stage pipeline (planned, not yet built)

```
Stage 1 — Sunset Scanner             ~2:00 PM PT  (mostly mechanical, 1 LLM synthesizer)
  → mechanical screen of Russell 1000 / S&P via TradingView MCP signals
  → cross-reference with Capitol Trades + Finnhub earnings
  → outputs tomorrow_watchlist.json (30–50 candidates)

Stage 2 — Pre-market Reviewer        ~5:30 AM PT  (10–15 parallel mini-agents)
  → narrow yesterday's candidates by overnight news + pre-market action
  → per-ticker mini-agent: "setup still valid? watch level? invalidation level?"
  → outputs today_watchlist.json (top 5–10)

Stage 3 — Adversarial Decision       ~7:00 AM PT  AND  ~11:30 AM PT
  → for each surviving candidate (max 5):
      2 Bull agents (parallel) + 2 Bear agents (parallel)  — fresh context each, 7-day news cutoff
      1 Judge agent: reads all 4, applies budget rules, decides go/no-go
  → max 3 trade decisions per fire (max 6 per day)
  → outputs runs/<id>/decisions.json (same schema as System A — flows into simulator)

Stage 4 — End-of-Day Journal         ~1:30 PM PT  (1 agent)
  → reads today's filled / missed / fizzled
  → updates per-ticker wiki, meta/lessons, meta/setup_patterns, meta/budget_state
  → auto-bootstraps wiki pages for new tickers
```

All times Pacific. Active-day compute: ~65–70 LLM dispatches. Quiet days: 2–3.

## Capital allocation framework (planned, lives in `wiki/meta/budget_state.md`)

```
Starting paper capital:     $25,000
Risk per trade (max):       1.0% of account
Total open risk (cap):      4.0% of account
Max simultaneous positions: 5
Max % deployed:             60% (40% cash floor)
Single-position cap:        15% of account

Daily loss stop:            -2% account → pause for the day
Weekly loss stop:           -5% account → system review

Scaling (paper too):
  Week 1–2:  max 1 open, 0.5% risk per trade
  Week 3–4:  max 3 open, 0.75% risk per trade
  Month 2+:  full framework

Volatility adjustment:
  VIX > 25  → cut size 50%
  VIX > 30  → no new entries
```

Read by every Stage 3 judge before approving. Updated nightly by Stage 4.

## Where detail lives

| Need | Read |
|---|---|
| Build status, what's delegated, what's next | `HANDOFF.md` |
| External setup steps (GitHub repo, Turso DB, secrets, gh-pages) | `SETUP_NOTES.md` |
| Inherited pipeline internals | `ai_hedge/CLAUDE.md` |
| Inherited wiki / simulator / dashboard | `tracker/CLAUDE.md` |
| Original (System A) architecture | `ARCHITECTURE.md` (inherited, not yet diverged) |
| Original (System A) run instructions | `RUN_PLAYBOOK.md` (inherited; System B will replace with its own) |

## Environment

- Python 3.14, venv at `.venv/`
- `import ai_hedge` works from anywhere (editable install)
- `.env.example` is the template; user creates `.env` with second Turso DB credentials
- Same data layer as System A — yfinance, SEC EDGAR, Finnhub free tier
- New: TradingView MCP (server installed by user; wrapper in Task 2)

## Smoke tests (verify scaffold)

```bash
.venv/bin/python -c "from ai_hedge.data.api import get_prices; print(len(get_prices('AAPL', '2024-01-01', '2024-03-01')), 'bars')"
.venv/bin/python -c "from ai_hedge.wiki.inject import is_wiki_enabled; print('wiki:', is_wiki_enabled())"
.venv/bin/python -m ai_hedge.runner.prepare --tickers AAPL --run-id smoke_test --mode swing && rm -rf runs/smoke_test
```

## Git remote (single)

This folder has exactly **one** remote: `origin` → `NamanVinayak/claude-code-swing-scanner` (placeholder until user creates the GitHub repo per `SETUP_NOTES.md` step 1).

```bash
git remote -v   # should show ONLY origin pointing at claude-code-swing-scanner
```

If any other remote shows up, something pulled it back in by mistake.

## Boundary rule

- Do **not** import from `/Users/naman/Downloads/artist/` in any code in this project.
- Bug fixes can flow forward via periodic `git fetch` + manual cherry-pick from System A.
- No live shared modules. No shared DB. No shared dashboard.
- The two systems must remain independent in production state — a bug in System B must not be able to corrupt System A's track record.

## Conventions

- All Agent dispatches: `model: sonnet`. Do NOT use `model: haiku`.
- `.agents/` is for OpenCode — Claude Code does NOT auto-load it.
- `graphify-out/` is gitignored and unused.
- After every Playwright worker, delete `.playwright-mcp/storageState*.json` (token leak prevention).
- System B's "decision producer" runs as **macOS Desktop Scheduled Tasks** (not Cloud Routines). Mac must be on during the trading window (5:30 AM – 2:30 PM Pacific).

---

_Last updated: 2026-05-03 — initial scaffold. Brain not yet built. See HANDOFF.md for next steps._
