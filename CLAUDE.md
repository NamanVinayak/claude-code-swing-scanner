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
  → SIGNAL-FIRST universe: union of TradingView signal hits → per-ticker sanity filter
  → direction-aware: each candidate tagged "long" or "short"; conflicted (1L+1S) dropped
  → cross-reference with Capitol Trades (long-side only); Finnhub earnings via Stage 2
  → outputs tomorrow_watchlist.json (~10–15 candidates with `direction` field)

Stage 2 — Pre-market Reviewer        ~5:30 AM PT  (10–15 parallel mini-agents)
  → narrow yesterday's candidates by overnight news + pre-market action
  → per-ticker mini-agent: "setup still valid? watch level? invalidation level?"
  → outputs today_watchlist.json (top 5–10)

Stage 3 — Adversarial Decision       ~7:00 AM PT  AND  ~11:30 AM PT
  → for each surviving candidate (no per-fire count cap):
      2 Bull agents (parallel) + 2 Bear agents (parallel)  — fresh context each, 7-day news cutoff
      1 Judge agent: reads all 4, applies budget rules, decides go/no-go
  → all judge approvals flow to the writer; capital rules (max_simultaneous_positions=5,
     total_open_risk=4%, deployment_cap=60%, single_position_cap=15%/20%) are the only
     authoritative limits on how many trades land.
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

Scaling: SKIPPED for paper trading (full size from day one).
  Rationale: scaling exists to limit DOLLAR LOSSES while finding bugs. Paper has no
  dollars at stake, so scaling just slows down data gathering. Capital rules above
  are sufficient guardrails. Re-enable in `wiki/meta/budget_state.md` (toggle Phase
  back to scaling_week_1_2) if/when transitioning to real money.

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

## 2026-05-04 (evening) — architecture overhaul (Phases A–H, all shipped)

First live `b_scan` (Mon 2:10 PM PT) returned only 3 candidates, two of which only triggered via `tv_overbought` (a SHORT signal mis-treated as a long). Same-day rewrite via 12 worker dispatches across 6 batches, plus follow-up Phase G (full indicator buffet) and Phase H (WebSearch fallback). 7 commits, all on `origin/main`.

| Commit | Phase | What |
|---|---|---|
| `7318182f` | A + B | Signal-first universe, direction taxonomy, fail-empty budget bypass fix |
| `d5be5882` | C + D + E1 | Bull/bear prompts parameterized for direction; `[STALE]` handling; recent_news_7d |
| `1060d04c` | C + D | Judge: Gate 0 direction consensus, direction-aware expected-return math, `[STALE]` marker pipeline in `inject.py` |
| `3c27f4cb` | E2 + E3 | Cache TTLs 600/300 → 60; Capitol dedup namespacing; integration test script |
| `ec134820` | G | Full indicator buffet (daily + hourly) + insider trades + earnings in Stage 3 facts; Pydantic loud-crash validation; forward 3-day earnings blackout |
| `1a597380` | H | All Stage 3 prompts: MUST use WebSearch when `recent_news_7d` empty (no more silent "no news" fallback) |

### Key architectural changes

- **Universe is signal-first.** No top-N-by-mcap pre-filter. Pull TradingView signals, union tickers, apply min price/mcap/volume per-ticker. `signals_max_per_kind=400` in `ScanConfig`.
- **Direction (long/short) flows through every stage.** `tomorrow_watchlist.json` → `today_watchlist.json` → perspective facts → judge output → decisions.json. Bulls/bears parameterized; judge has `Gate 0 — direction consensus` check.
- **Stage 3 facts now mirror System A's swing buffet.** `adversarial_facts_builder._build_market_data_bundle()` pulls daily prices (400d) + hourly bars (1mo), computes full daily + hourly indicator suites (RSI/MACD/BB/ATR/ADX/S-R/Fib/momentum/etc.), insider trades, market cap, recent OHLCV, days_until_next earnings. Bulls/bears now cite real numbers from `daily_indicators.rsi.rsi_14` etc., not vibes.
- **Pydantic validation on every Stage 3 LLM output.** Bull/bear/judge schemas in `ai_hedge/schemas.py`. `decisions_writer._parse_approved_trade` validates via `JudgeApprovedTrade` and logs ERROR with full traceback on malformation. No more silent degradation.
- **Forward earnings blackout.** Stage 2 drops candidates with `days_until_next_earnings ≤ 3` (new `DropReason: earnings_blackout_3d`).
- **Wiki staleness wired.** `inject.py` prepends `[STALE — last updated YYYY-MM-DD, threshold N days exceeded. Verify via web search before relying on these claims.]` into rendered text when a slice is past `stale_after_days`. All 7 prompts (bulls/bears/judge/premarket/journal) recognize the marker and lower confidence accordingly.
- **WebSearch fallback for news.** All 5 Stage 3 prompts now MUST attempt WebSearch when `recent_news_7d` is empty before falling back to technicals-only.
- **Capital protection fail-empty.** `decisions_writer.py:171-173`: if `compute_risk_budget()` raises, ALL trades rejected with `budget_unavailable: <exception>` reason. Was previously fail-OPEN (silently approved everything).

### What runs tomorrow morning

`b_premarket` at 5:30 AM PT reads the latest `runs/*/tomorrow_watchlist.json` — that's `runs/20260504_171717/` (manually triggered after the overhaul shipped, 12 long candidates, 0 shorts).

The 2:10 PM auto-routine ran on the OLD broken code (`runs/20260504_141022/`, 3 candidates). That run is superseded but kept in history.

### Phase F (deferred — explicitly NOT fixed today)

Short-side signal taxonomy is structurally narrow: `find_signals()` sorts each kind by a different column, so top-N short pulls sample disjoint slices. Even at `signals_max_per_kind=500`, today's scan produced 0 short candidates from 240 single-short stocks. Needs new short-friendly signals (bearish divergence, near-resistance rejection, distribution patterns) and/or asymmetric `min_reasons_to_advance` for shorts. Not blocking long-side trading.

### Other deferred items

- **Volatility-adjusted position limits** (System A pattern from `risk_manager.py:272–370`) — defer until paper week 3+ when we have real per-ticker vol data.
- **Self-grading / agent track records** — needs months of history first.
- **Wiki compactor** — operational hygiene; no urgency until wiki bloats.
- **`days_since_last` earnings field** — `earnings_calendar.py` only exposes "until next" today. Easy add later if prompts need historical earnings spacing.
- **Direction dissent mechanism** — currently if Stage 1 misclassifies direction, agents can lower conviction but can't propose flipping. Phase I candidate.

### Fast smoke test

```bash
.venv/bin/python scripts/verify_b_scan_post_fix.py
```
Expected: PASS with 12 health checks (4 original + 8 Phase G), candidate count 10–15, top candidate's facts bundle shows real `daily_indicators.rsi.rsi_14`, `hourly_indicators`, `recent_insider_trades` (list), `earnings.days_until_next` populated.

---

_Last updated: 2026-05-04 (evening) — System B is **LIVE on the overhauled architecture**. All Phases A–H shipped (7 commits). Tomorrow's b_premarket fires at 5:30 AM PT against `runs/20260504_171717/tomorrow_watchlist.json` (12 long candidates from manual post-overhaul scan). See `HANDOFF.md` for the dated build log._

---

## 2026-05-05 (full day) — first live day, 7 bug fixes shipped, 0 trades yet

First live trading day on the overhauled architecture surfaced 7+ real bugs that all got fixed same-day. **Zero trades executed today** — morning b_decide fire (live, 7:01 AM PT) rejected all 4 candidates on the 15% cap; afternoon manual smoke test (3 PM) approved 3 trades that the writer's defensive check then rejected for the same cap reason; the cap reconciliation fix shipped at 3 PM but wasn't re-run live. Tomorrow morning is the next chance.

### Eight commits shipped today (pipeline-affecting; the others are routine output)

| Commit | What |
|---|---|
| `74998769` | Fix 1+2+3+4: UTC run IDs / sentinel-file run resolution / small_scaled position class / dedicated news researcher agent |
| `6c1e24f0` | Fix 5+6+7: budget_calculator honors position_size_class / b_stage3 sort filter excludes test dirs / SKILL.md aggregator matches actual judge wrapper schema |
| `2c70b92d` | Fix 8: scaling phase skipped for paper / per-fire count cap removed / decisions_writer simulates per-trade snapshot via `dataclasses.replace()` |

### Key behavioral changes (matters for every future session)

1. **Run IDs are UTC.** All 4 SKILL files use `date -u`. Dashboard `build.py` already parsed UTC. Today's existing runs (PT-stamped) will keep displaying with wrong dates — that's a one-day legacy. Future runs display correctly.

2. **`b_stage3.py` is now the source of truth for the run dir.** Bash passes a tentative UTC ID; python decides which dir to actually use (the latest one with `today_watchlist.json`); writes resolved id to `runs/.last_resolved_run_id` BEFORE side effects. Bash reads sentinel back. `_RUN_ID_PATTERN = re.compile(r"^\d{8}_\d{6}$")` filters out test dirs / sentinel files / scratch dirs.

3. **Capital allocation framework changed:**
   - **`small_scaled` exception** — `position_size_class` is now a Pydantic field on `JudgeApprovedTrade`. When `small_scaled`, single-position cap is 20% (not 15%). Risk per trade unchanged. Carved into `budget_calculator.SMALL_SCALED_CAP_PCT=20.0`.
   - **No per-fire count cap** — removed the `if len(approved) > 3` slice from `b_decide/SKILL.md` aggregator. Capital rules in writer are sole limit.
   - **Per-trade snapshot simulation** — `decisions_writer` mutates `working_snapshot` via `dataclasses.replace()` after each approval so trade #N+1 sees state after trade #N (positions_open incremented, available_risk_usd decremented, deployed incremented). Without this, all trades saw original "0 positions" snapshot and writer over-approved.
   - **Scaling phase skipped for paper.** `wiki/meta/budget_state.md` Phase=`full`, multiplier=1.0. Rationale: scaling protects DOLLAR losses; paper has none. To re-enable for real money, toggle `Phase` back to `scaling_week_1_2` in `budget_state.md`.

4. **Dedicated news researcher agent** — `ai_hedge/personas/prompts/b_news_researcher.md` (143 lines, mirrors System A's `web_researcher.md`). Single-purpose: WebSearch with mandatory raw-save to `runs/<id>/web_research/raw/{ticker}_*.json`, structured output to `runs/<id>/news/{ticker}.json`. New Pydantic classes: `NewsResearcherOutput`, `NewsItem`, `AnalystConsensus`, `EarningsContext` (raw_search_files validated `min_length=1`).

5. **`b_decide` Step 1.5** — between facts build and bull/bear dispatch, dispatches one news researcher per ticker in parallel, verifies raw files + news output exist (FATAL if not), then runs `b_stage3.py --run-id $RUN_ID --merge-news` to populate `recent_news_7d` in bull/bear facts (URL-deduped union with Finnhub data, plus `news_source` provenance field).

6. **Bull/bear prompts cleaned** — removed Phase H "MUST WebSearch" hedge, removed `["none-cited"]` placeholder, rerouted wiki-staleness handling through researcher's bundle. They no longer have a WebSearch decision to make. Step 2's prompt template explicitly says "Do NOT invoke WebSearch."

### Operational requirement (cause of today's missed routines)

**Mac MUST stay awake during 5:30 AM – 2:30 PM PT weekdays.** Today's 11:30 AM and 2:00 PM scheduled routines never fired because the Claude Desktop app was closed. There is no failure notification — only absence of a commit reveals it.

### Smoke test for tomorrow

If you want to verify the new architecture without waiting for 5:30 AM:

```bash
# Manual trigger /b_decide via the slash command — it'll resolve to the latest premarket dir,
# dispatch news researchers, run perspectives, and produce decisions.json.
# Costs ~5 min of pipeline time. Trades approved are paper-only (no market hours required).
```

Expected end state if all fixes work: `runs/<id>/news/{T}.json` populated for every ticker, `runs/<id>/web_research/raw/` contains ≥3 files per ticker, `runs/<id>/decisions.json` has 1+ approved trades with `position_size_class` set, Turso has 1+ rows in trades table, dashboard shows position with "scaled" badge if applicable.

### What's queued for tomorrow morning (2026-05-06, 5:30 AM PT)

`b_premarket` reads `runs/20260505_213211/tomorrow_watchlist.json` — 10 long candidates, top 3 (ROK, RRX, JAZZ) with full signal trifecta. Several high-priced names mean `small_scaled` will likely get exercised in production for the first time.

### Deferred (still — no change today)

Phase F (short-side signal taxonomy), volatility-adjusted limits, self-grading, wiki compactor, `days_since_last` earnings, direction dissent (Phase I), formal DB migrations, b_journal summary key-mismatch (small bug surfaced today during manual trigger, non-blocking).

---

_Last updated: 2026-05-05 (~3:00 PM PT). System B is **LIVE with all known bugs fixed**. 0 trades in Turso to date. Tomorrow's 5:30 AM `b_premarket` is the first chance for a real paper trade to land. See `HANDOFF.md` "## 2026-05-05" section for fix-by-fix detail and tomorrow's resume-from-here checklist._

---

## 2026-05-07 (evening) — time-travel simulator bug fixed; agent-driven entry expiry shipped

Today's 7 AM `b_decide` approved one trade (TLN, $411.50 entry, $397 stop, 12 shares) and the simulator recorded it as filled at 9:30 AM ET (market open) and stopped out at 9:45 AM ET for -$174. Investigation against yfinance 1-minute bars revealed both the entry AND the stop-out were retroactively backfilled — the trade was actually inserted into Turso at 10:10 AM ET, by which time TLN had already crashed to ~$391 (well below the $409.44 entry tolerance band) and never returned to the entry zone. The simulator was filling orders against bars from before the orders existed.

Same bug analysis applied to the two open positions from the prior day:

| Trade | Sim said | Reality (after order existed in DB) | Real distortion |
|---|---|---|---|
| ROK (id=7) | Filled @ $445.27 at 9:30 ET | Touched zone exactly once at 10:30 ET, low $446.93 | ~$18 too profitable |
| CMI (id=8) | Filled @ $689.69 at 9:30 ET | Never re-entered entry zone after 10:11 ET | Entire position fictional |
| TLN (id=9) | Filled @ $411.50 at 9:30 ET, stopped @ $397, -$174 | Never re-entered entry zone after 10:10 ET | Fake $174 loss |

### What shipped (one work session, plan in `~/.claude/plans/humming-meandering-hickey.md`)

**Bug fix.** `tracker/simulator.py:_floor_for_fresh_trade()` replaces the prior `start_of_today` fallback. Fresh trades now floor their bar-scan at `decision_made_at + 60s` (the agent's finished-deciding timestamp + a small broker-side buffer). New `decision_made_at` column on `trades` table; sourced from `decisions.json.generated_at` by the ingester.

**Agent-driven entry expiry.** New Gate 7 in `b_judge.md`: judge sets per-trade `entry_valid_until` (ISO 8601 UTC) based on setup type, conviction, time of day, volatility. New optional field on `JudgeApprovedTrade` Pydantic schema (`schemas.py`), `TradeDecision` dataclass (`decisions_writer.py`), and `entry_valid_until` column in Turso `trades` table. Simulator runs an expiry pass at the top of the per-trade loop: pending trades past expiry get `status='expired'`, `pnl=NULL`, `exit_fill_price=NULL`, audit row in `fills`. If judge sets `entry_valid_until=null`, simulator falls back to a safety cap of 16:00 ET on the decision day (mirrors a real broker's day-order default).

**Retroactive correction.** `scripts/fix_pre_simulator_bug_trades.py` (idempotent, sentinel-gated) updated the 3 tainted rows in Turso:
- ROK (id=7): `entry_fill_price` 445.27 → 446.93, `entered_at` 13:30 → 14:30 UTC. Still status=`entered`.
- CMI (id=8): status `entered` → `expired`, fills cleared, `closed_at` set to 16:00 ET 2026-05-06. Real life: never filled.
- TLN (id=9): status `stop_hit` → `expired`, $-174 PnL erased, fills cleared. Real life: never filled.

Each correction wrote a `retroactive_correction_*` row to the `fills` audit log with the reason.

**Downstream consumers — already supported `expired` status.** Verified during planning: `dashboard/build.py`, `closed.html`, `ticker.html`, `base.html` (yellow EXPIRED badge CSS), `wiki_daily_update.py`, `journal_facts_builder.py`, `journal_writer.py` all already accept and display the `expired` status. No template/journal/wiki code changes needed — just the simulator now produces it.

### Files changed

- `tracker/turso_client.py` — added `decision_made_at`, `entry_valid_until` to `TRADE_COLUMNS` and `CREATE TABLE`
- `tracker/ingest_decisions.py` — `_ensure_schema()` migrations for both columns; extracts `generated_at` from decisions.json into `decision_made_at`; passes `entry_valid_until` through
- `tracker/simulator.py` — `_floor_for_fresh_trade()` and `_safety_cap_expiry()` helpers; expiry pass before bar loop; new `expired_count` counter in summary line
- `ai_hedge/schemas.py` — `entry_valid_until: str | None = None` on `JudgeApprovedTrade`
- `ai_hedge/personas/prompts/b_judge.md` — Gate 7 (Entry validity window); field added to output schema example (long & short) and field-description list
- `ai_hedge/scanners/decisions_writer.py` — `entry_valid_until` on `TradeDecision` dataclass; pass-through in `_parse_approved_trade()` and `decisions_dict`
- `scripts/fix_pre_simulator_bug_trades.py` — NEW. Idempotent retroactive correction
- `tracker/CLAUDE.md` — Simulator section updated; columns documented

### Smoke tests run live

- Schema migration: `_ensure_schema()` against live Turso → both columns present on rows 7/8/9
- Simulator helpers: 5 unit tests pass (floor with/without `decision_made_at`, malformed parse, safety cap math)
- Pydantic round-trip: `JudgeApprovedTrade` accepts string + null + omitted; `_parse_approved_trade` propagates correctly
- Retroactive script: dry-run shows expected diffs; live apply succeeded; second run is no-op (idempotent sentinel)
- Simulator dry-run post-correction: only 1 ticker (ROK) being monitored as expected; CMI and TLN now expired

### What runs tomorrow morning (2026-05-08, 5:30 AM PT)

The first `b_decide` fire after this fix should produce a `decisions.json` where every approved trade has an `entry_valid_until` field. Ingester writes it to Turso along with `decision_made_at = generated_at`. Simulator processes bars only AFTER decision time + 60s, never from market open. If price doesn't enter the zone before `entry_valid_until`, trade ends as `status=expired` with the existing yellow EXPIRED badge on the dashboard.

If the judge agent emits `entry_valid_until: null`, the simulator's safety cap kicks in at 16:00 ET on the decision day. Watch for that the first day or two — if every judge output is using null, that's a prompt-tuning signal.

### Out of scope (not fixed today, listed for memory)

- `b_decide_open` schedule still fires at 7:00 AM PT (= 30 min after market open). Discussion of whether to move earlier or change the entry-fill rule from limit to market-at-decision is deferred.
- Stop-fill realism: simulator still fills exits at the exact stop trigger price, ignoring slippage on violent candles. Separate future fix.
- Journal prompt does not yet treat expired trades as a distinct learning signal ("decided too late?"). Optional v2 polish.
- 3 pre-existing test failures in `tests/test_turso_client.py` (mocks vs HTTP path mismatch) confirmed to be unrelated to this fix; existed on `main` before today.

---

_Last updated: 2026-05-07 (evening). System B is **LIVE with the time-travel bug fixed and agent-driven entry expiry shipped**. Turso state: ROK still entered at corrected price ($446.93), CMI/TLN both `expired` with no PnL. Tomorrow's 5:30 AM `b_premarket` is the first run of the corrected pipeline._
