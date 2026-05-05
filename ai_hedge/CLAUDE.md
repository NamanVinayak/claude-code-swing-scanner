# ai_hedge/ — Pipeline Internals

Detail for agents working inside `ai_hedge/`. The root `CLAUDE.md` has the high-level pipeline.

## Data flow

1. `prepare.py` fetches raw data per ticker → `runs/<id>/raw/<TICKER>.json`
2. `prepare.py` saves run metadata → `runs/<id>/metadata.json` (mode, tickers, dates)
3. `facts_builder.py` runs deterministic helpers per persona × ticker → `runs/<id>/facts/<persona>__<ticker>.json`
   - `growth_analyst_agent` is fully deterministic — its signal goes straight to `runs/<id>/signals/growth_analyst_agent.json`
4. If swing/research: `swing_facts_builder.py` builds swing facts (daily + hourly indicators)
5. If daytrade/research: `dt_facts_builder.py` builds DT facts + intraday data
6. LLM subagents read facts + prompts, write `runs/<id>/signals/<agent>.json`
7. `aggregate.py` runs deterministic agents (fundamentals/technicals/valuation/sentiment/risk_manager + technicals_intraday for daytrade/research), writes `runs/<id>/signals_combined.json`
8. Final agent writes `runs/<id>/decisions.json`
9. Explainer writes `runs/<id>/explanation.json`
10. `finalize.py` prints + writes `runs/<id>/summary.json`

## Key modules

| Module | Role |
|---|---|
| `data/api.py` | Public data functions (daily/intraday prices, financials, news, insider trades) |
| `data/providers/` | yfinance, SEC EDGAR, Finnhub providers |
| `data/providers/yfinance_intraday.py` | Intraday 1m/5m/15m/1h candles |
| `data/indicators.py` | pandas_ta indicators — single source of truth (RSI, MACD, Bollinger, VWAP, STC, Squeeze, SuperTrend, real OBV, RSI divergence, Fib extensions, pivot S/R). Takes `timeframe="daily"|"hourly"` for scaled params. |
| `data/earnings_calendar.py` | `days_until_next_earnings(ticker)` — yfinance, 24h cache. Risk manager uses this for 3-day blackout. |
| `data/cache.py` | SQLite cache with per-entry TTL (no stale prices) |
| `personas/helpers.py` | 79 deterministic helper functions (adapted from upstream, NOT verbatim — verify before claiming so) |
| `personas/facts_builder.py` | Invest-mode facts builder |
| `personas/swing_facts_builder.py` | Swing-mode facts (delegates indicator math to `data/indicators.py`) |
| `personas/dt_facts_builder.py` | Day-trade facts (1mo of 5m bars + indicators) |
| `personas/prompts/` | System prompts for all agents |
| `personas/prompts/explainer.md` | Explainer prompt (educational output, all modes) |
| `personas/prompts/wiki_curator.md`, `wiki_bootstrap.md` | Wiki memory layer prompts |
| `wiki/` | Wiki memory package: `inject.py`, `loader.py`, `manifest.py`, `templates.py`, `lint.py` |
| `deterministic/` | fundamentals, technicals, valuation, sentiment, risk_manager |
| `deterministic/technicals_intraday.py` | Intraday technicals (daytrade/research) |
| `schemas.py` | Pydantic signal schemas |
| `portfolio/allowed_actions.py` | `compute_allowed_actions()` — same-direction stacking blocked via `current_positions` kwarg |
| `runner/run_index.py` | Single source of truth for runs at `runs/index.json` |

## Agents (beyond upstream)

Swing strategies (5): swing_trend_momentum, swing_mean_reversion, swing_breakout, swing_catalyst_news, swing_macro_context. Each owns a distinct angle — no overlap. Old 9-agent set archived at `personas/prompts/_archive/` (Apr 2026, Sin #3 fix).

Day-trade strategies (9): dt_vwap_trader, dt_momentum_scalper, dt_mean_reversion, dt_breakout_hunter, dt_gap_analyst, dt_volume_profiler, dt_pattern_reader, dt_stat_arb, dt_news_catalyst.

**Head Traders**: swing_head_trader, dt_head_trader — synthesize strategy signals before PM. Pydantic-guarded so silent JSON parse failures crash loud (Sin #20).

**Research Report Writer**: balanced bull/bear, no recommendation.

## Multi-timeframe analysis

- **Swing**: facts bundles include `daily_indicators` AND `hourly_indicators`. Hourly uses scaled params (RSI 21 not 14, MACD 24/52/18, etc.) via `compute_daily_indicators(df, timeframe="hourly")`. `degraded_indicators[]` tracks any silent pandas_ta failures so agents see the gap honestly.
- **Daytrade**: intraday extended from 5 days to ~22 trading days (`period="1mo"`) for deeper 5-min indicator history.

## Wiki memory layer (Phase 1)

- **Purpose**: persistent per-ticker thesis/catalyst/technicals/trades notes under `wiki/`, injected as `wiki_context` into swing facts so the head trader sees prior history across runs.
- **Gate**: `tracker/watchlist.json:settings.wiki_enabled` (currently TRUE — flipped 2026-04-29).
- **Bootstrap**: `scripts/wiki_bootstrap.py` populated 96 pages across 23 tickers.
- **Maintenance**: `scripts/wiki_compactor.py` invoked by `.agents/skills/wiki_maintenance/` skill (Sunday routine).

## Enhanced Pipeline (Web Research + Verification)

```
prepare.py
→ Step 2.5: Web Research Agent (macro + ticker news via WebSearch)
→ build facts (now includes web_context)
→ Step 2.8: Web Verification Agent (corrects metric deviations >20%)
→ LLM agents (enriched + verified)
→ aggregate → PM → explainer → finalize
```

- Prompts: `personas/prompts/web_researcher.md`, `web_verifier.md`
- Output: `runs/<id>/web_research/<TICKER>.json`, `runs/<id>/verification/<TICKER>.json`
- Facts bundles include `web_context` when web research is available

## holding_period and duration fields

First intentional deviation from upstream:
- Each invest persona prompt asks for `holding_period`
- Portfolio manager asks for `duration` for the overall portfolio
- All persona schemas in `schemas.py` include optional `holding_period`
- Swing/daytrade schemas have mode-appropriate time fields (`timeframe`, `time_window`)

## Upstream copy rule (HISTORICAL — partially obsolete)

Original intent was verbatim copy from `reference/ai-hedge-fund/`. The codebase has drifted: helper functions added/renamed/adapted; upstream has no `helpers.py`. **Do not assume any function is verbatim from upstream — verify.** Use `reference/` as inspiration, not ground truth.

---

## System B additions (the `b_*` swing-trader fork — read root CLAUDE.md for context)

System B is the experimental swing-trader fork running in this same repo. It reuses the data layer, indicators, wiki package, and personas helpers above, then layers a 4-stage pipeline on top with its own modules and prompts. Everything System B-specific lives at well-known prefixes:

### Modules added for System B

| Module | Stage | Role |
|---|---|---|
| `data/tradingview.py` | All | TradingView `tradingview-ta` wrapper. `screen_universe()`, `find_signals()`, `get_snapshot()`. **Plus 3 short-setup screeners** (`find_short_stage4_breakdown`, `find_short_episodic_pivot`, `find_short_sector_laggard`) that bypass the signal-overlap problem with custom filter expressions — see Stage 1 notes below. |
| `data/capitol_trades.py` | Stage 1 | Congressional disclosure scraper. Long-side enrichment only (politicians buying = bullish reason). |
| `scanners/sunset_scanner.py` | Stage 1 | Direction-aware funnel. Signal-overlap path produces longs; setup-based path produces shorts (`_collect_short_setup_candidates`). Both merge into one `tomorrow_watchlist.json` with `direction` field. |
| `scanners/premarket_reviewer.py` | Stage 2 | Mechanical filters (gap, premarket volume, earnings blackout) + per-ticker mini-agent dispatch. Output: `today_watchlist.json`. |
| `scanners/adversarial_facts_builder.py` | Stage 3 | Builds `b_news_researcher__{T}.json` + `b_bull_a/b__{T}.json` + `b_bear_a/b__{T}.json` + `b_judge__{T}.json` facts files. Exposes `merge_news_into_perspective_facts(run_id)` which is called via `b_stage3 --merge-news` between news researchers and bulls/bears. |
| `scanners/budget_calculator.py` | Stage 3 | Live capital snapshot from `wiki/meta/budget_state.md`. `trade_passes_budget_checks()` honors `position_size_class` (15% standard / 20% small_scaled). `SMALL_SCALED_CAP_PCT=20.0` constant. |
| `scanners/decisions_writer.py` | Stage 3 | Reads `judge_output.json`, validates via Pydantic (`JudgeApprovedTrade` from `schemas.py`), runs writer-side defensive budget check with **per-trade snapshot simulation via `dataclasses.replace()`** (so trade #N+1 sees state after trade #N opens). Produces `decisions.json` in System A simulator schema. |
| `scanners/journal_writer.py` | Stage 4 | End-of-day wiki updates. |

### Prompts added for System B (`personas/prompts/b_*.md`)

| Prompt | Used by | Single responsibility |
|---|---|---|
| `b_scanner_synthesizer.md` | Stage 1 | Ranks scanner candidates into final `tomorrow_watchlist.json` |
| `b_premarket.md` + `b_premarket_synthesizer.md` | Stage 2 | Per-ticker premarket validity check + final ranking |
| `b_news_researcher.md` | Stage 3 (Step 1.5) | **Single-purpose WebSearch agent.** Mandatory raw-save to `runs/<id>/web_research/raw/{T}_*.json`, structured output to `runs/<id>/news/{T}.json`. Bull/bear agents no longer have WebSearch capability — research is this agent's job. |
| `b_bull_a.md`, `b_bull_b.md`, `b_bear_a.md`, `b_bear_b.md` | Stage 3 | Direction-parameterized perspective agents. Read pre-merged `recent_news_7d` from facts (Finnhub + web research, deduped by URL). |
| `b_judge.md` | Stage 3 | Per-ticker judge. Outputs wrapper `{ticker, approved:[], rejected:[], summary}`. Approved trades carry `position_size_class: "standard"|"small_scaled"`. |
| `b_journal.md` | Stage 4 | Daily journal LLM agent (skipped on quiet days per skill spec). |

### CLI runners (`runner/b_stage*.py`)

`b_stage1.py` (scan), `b_stage2.py` (premarket), `b_stage3.py` (decide facts + sentinel + `--merge-news` + `--finalize`), `b_stage4.py` (journal). Each invoked from its corresponding `.claude/skills/b_*/SKILL.md`.

### Schemas added in `schemas.py`

- `JudgeApprovedTrade` — Stage 3 judge output validation. Has `position_size_class: Literal["standard", "small_scaled"] = "standard"` field (added 2026-05-05).
- `NewsResearcherOutput`, `NewsItem`, `AnalystConsensus`, `EarningsContext` — Stage 3 news researcher output validation. `raw_search_files` validated `min_length=1` (skipping WebSearch produces invalid output).

### Stage 1 short-side scanner (added 2026-05-05)

The signal-overlap approach was structurally broken for shorts (TradingView sorts each short signal list by a different metric → near-zero ticker overlap). The fix is `_collect_short_setup_candidates()` in `sunset_scanner.py` which calls 3 trader-validated setup screeners in parallel:

- `stage4_momentum_breakdown` — Minervini Stage 4 (close < SMA200 < SMA50 stack inverted, RelVol > 1.2, RSI > 30 squeeze protection)
- `bearish_episodic_pivot` — Stockbee BEP (change < -8% with 3x+ volume, market_cap > $1B)
- `sector_laggard_decline` — significant 1-month decline + below 50-day MA

Squeeze protection (RSI > 30 minimum) applied universally. Ticker hitting multiple setups gets all setup names accumulated as `short_reasons`. Disable via `ScanConfig(short_setups_enabled=False)`. Live test 2026-05-05: produced 27 shorts on a normal market day where signal-overlap path produced 0.
