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
| Decision producer | 14 Cloud Routines, fixed watchlist | 5 Local Desktop Scheduled Routines, universe scanner |
| Status | Live since 2026-04-30 | **LIVE since 2026-05-04** |

**Production is untouched.** Treat `~/Downloads/artist/` as read-only reference. Do not import from it. Do not push to its remote. Do not modify its files.

## Why System B exists

System A is built around a fixed watchlist (19 tickers, hardcoded). It analyzes each name on a schedule. **It is not how real swing traders work** — they scan the whole market for setups daily, then pick the cleanest 1–3.

System B replicates the back-end (data layer, simulator, dashboard, wiki memory) but replaces the front-end with a **swing-trader-style brain**:
- Universe scanner (TradingView MCP + Capitol Trades + Finnhub) finds candidates from ~1000 names
- Adversarial bull/bear/judge debate decides which to actually trade (per-ticker, parallel, fresh context — Lopez-Lira / AlphaAgents inspired)
- Capital allocation rules (1% per-trade risk, 4% total open risk, 60% deployment cap, scaling phase) enforced by the judge
- Wiki memory layer carries learnings forward (per-ticker thesis + setup history + lessons + budget state)

After 2–3 weeks of parallel paper trading, the user compares the two systems' dashboards side-by-side (no third unified dashboard — comparison-by-flipping-tabs is the architecture).

## Architecture — fully built and live

### Inherited from System A (unchanged in this fork)
- `ai_hedge/data/` — yfinance, SEC EDGAR, Finnhub, indicators, cache
- `ai_hedge/personas/` — facts builders, helper functions (System A's persona prompts present but not used by System B; safe to ignore)
- `ai_hedge/wiki/` — memory layer (inject, loader, manifest, templates, lint) — **adapted**: AGENT_MANIFEST replaced with System B's 8 stage keys; 4 new page templates added.
- `tracker/` — Turso client, simulator, ingester (with ingester fixed to pass `target_price_2`)
- `dashboard/` — Jinja2 renderer (relabeled for System B; `build.py` modified to render per-ticker pages from union of watchlist and traded-tickers)

### Built for System B (all live)
- `ai_hedge/data/tradingview.py` — TradingView screener + indicator wrapper (no API key needed)
- `ai_hedge/data/capitol_trades.py` — Congressional disclosure scraper
- `ai_hedge/scanners/sunset_scanner.py` — Stage 1 mechanical screening
- `ai_hedge/scanners/premarket_reviewer.py` — Stage 2 pre-market filter + facts builder
- `ai_hedge/scanners/adversarial_facts_builder.py` — Stage 3 facts orchestration
- `ai_hedge/scanners/budget_calculator.py` — capital allocation rules engine
- `ai_hedge/scanners/decisions_writer.py` — judge output → decisions.json (System A simulator schema)
- `ai_hedge/scanners/journal_facts_builder.py`, `journal_writer.py` — Stage 4 wiki updates + journal facts
- `ai_hedge/runner/b_stage1.py` through `b_stage4.py` — CLI entry points for the four stages
- `ai_hedge/personas/prompts/b_*.md` — 9 prompt files for sub-agents (scanner synthesizer, premarket mini-agent + synthesizer, 2 bulls, 2 bears, judge, journal)
- `.claude/skills/b_scan/`, `b_premarket/`, `b_decide/`, `b_journal/` — 4 SKILL.md slash commands (the orchestration glue)
- `wiki/meta/budget_state.md`, `setup_patterns.md`, `macro/scanner_state.md` — System B's new wiki pages
- `scripts/wiki_bootstrap_system_b.py` — bootstrap helper

See `HANDOFF.md` for the dated build log.

## The four-stage pipeline (LIVE)

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

## Capital allocation framework (LIVE, lives in `wiki/meta/budget_state.md`)

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
- `.env` exists with real Turso credentials (gitignored). `.env.example` is the template.
- Data layer: yfinance, SEC EDGAR, Finnhub (free tier), TradingView (via `tradingview-ta`, no API key), Capitol Trades (scraped, no API key)

## Live operations

**5 Desktop Scheduled Routines configured in Claude Code app (Mon–Fri):**

| Routine | Time PT | Slash command | Model |
|---|---|---|---|
| Scanning | 2:00 PM | `/b_scan` | Sonnet 4.6 |
| Premarket | 5:30 AM | `/b_premarket` | Sonnet 4.6 |
| Decide_open | 7:00 AM | `/b_decide` | **Opus 4.7 (1M context)** |
| Decide_power | 11:30 AM | `/b_decide` | **Opus 4.7 (1M context)** |
| B_journal | 2:30 PM | `/b_journal` | Sonnet 4.6 |

**Why this split (decided 2026-05-04):** the two `decide` routines hold multi-ticker orchestrator context (up to 5 tickers × 4 sub-agent outputs + wiki + facts + budget) which can blow past Sonnet's 200k window and truncate silently — these touch real capital, so they get Opus 1M's safety margin. `b_scan`, `b_premarket`, `b_journal` are structurally smaller in context (mechanical filtering, single-ticker mini-agents, or post-mortem on a single day's trades) — Sonnet is sufficient. **Upgrade trigger:** if any Sonnet routine's transcripts show single-turn token counts approaching 150k, move it to Opus 1M.

Working directory for all: `/Users/naman/Downloads/new-artist`.

**Mac-on requirement:** 5:30 AM – 2:30 PM Pacific weekdays. Routines fire only while machine awake.

**Dashboard refresh:** `dashboard.yml` workflow has a `push: branches: [main]` trigger added — every routine commit immediately rebuilds the dashboard (~1 min). Cron `*/5 * * * *` stays as safety net.

**Smoke tests (verify still healthy):**

```bash
.venv/bin/python -c "from ai_hedge.data.api import get_prices; print(len(get_prices('AAPL', '2024-01-01', '2024-03-01')), 'bars')"
.venv/bin/python -c "from ai_hedge.wiki.inject import is_wiki_enabled; print('wiki:', is_wiki_enabled())"
.venv/bin/python -c "from tracker.turso_client import get_all_trades; print('trades:', len(get_all_trades()))"
```

## Git remote (single)

This folder has exactly **one** remote: `origin` → `NamanVinayak/claude-code-swing-scanner` (PUBLIC, GitHub Pages enabled).

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

_Last updated: 2026-05-04 — System B is **LIVE**. All build complete, cloud setup done, 5 Desktop Scheduled Routines configured. First fire = b_premarket Mon 2026-05-04 at 5:30 AM PT. See `HANDOFF.md` for the full dated build log._
