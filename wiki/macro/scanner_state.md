---
name: scanner state
last_updated: 2026-05-13
last_run_id: 20260513_084338
target_words: 500
stale_after_days: 3
word_count: 0
summary: current market breadth + signal density across the universe
---

# Scanner State

## TL;DR

40 candidates from 1,760-ticker universe: 9 long, 31 short. No scanner errors. Long side: all 9 are score-2 (`tv_strong_buy` + one confirming signal); CI is the only breakout candidate (`tv_strong_buy` + `tv_breakout_up`); the other 8 are trend-continuation (`tv_strong_buy` + `tv_trending_up`). Short side heavily skewed to score-1 (26 of 31); score-2 shorts — LIF, INTR, BRSL, CDRE, DFH — all carry multi-setup confluence (`stage4_momentum_breakdown` + `bearish_episodic_pivot` the most common pairing). Notable single-day moves: DFH -13.4%, HUBG -12.5%, LIF -10.8%, ASTS -11.6%, BRSL -9.6%, CDRE -9.5% on short side; INSM +11.7% and SCCO +3.5% on respective sides. Capitol Trades: 12 tickers with congressional buys in the universe; zero overlap with advancing candidates.

## Sector breadth

Sector labels not present in JSON. Breakdown by ticker identity:

**Longs (9)**

| Sector (inferred) | Tickers | Count |
|---|---|---|
| Industrials / Machinery | DE, CMI, MTZ | 3 |
| Semis / Optical Networking | LITE, AAOI, TTMI | 3 |
| Consumer / Retail | COST | 1 |
| Mining / Materials | SCCO | 1 |
| Healthcare / Insurance | CI | 1 |

**Shorts (31)**

Sector data not available in this run's JSON. Short-side names span healthcare/biotech (INSM, PODD, INSP, OLMA, ERAS, ATEC), tech/software (FSLY, VISN, CNXC, TYL), industrials/transportation (HUBG, PRIM, PATK), consumer (BOOT, FIGS, LCID, ONON, CAR), and diversified small-cap laggards. Inferences only — do not treat as ground truth.

## Signal density

Hits across the 1,760-ticker universe:

- `tv_strong_buy`: 400 hits (capped at config max)
- `tv_strong_sell`: 400 hits (capped at config max)
- `tv_overbought`: 400 hits (capped at config max)
- `tv_trending_down`: 336 hits
- `tv_trending_up`: 203 hits
- `tv_oversold`: 277 hits
- `tv_breakout_down`: 20 hits
- `tv_breakout_up`: 9 hits — lowest of this cycle; only 1 long candidate advanced on this signal
- `capitol_buys` (30-day): 12 tickers with congressional purchases
- Total signal hits: 2,045 across 1,760 unique tickers
- Short setups added (setup-based screener): 33

Dropped before scoring: 488 below min price ($5), 175 below min volume (500k), 657 below min market cap ($1B), 0 missing metadata, 60 conflicted (mixed signals). 227 directional long singletons + 144 short singletons below the 2-reason threshold.

## Anomalies

1. **Three signal kinds hit the 400-count cap** (`tv_strong_buy`, `tv_strong_sell`, `tv_overbought`). True universe-wide counts unknown for all three — same cap-binding as prior runs.

2. **Short candidates outnumber longs 31:9** — most lopsided ratio recorded so far (prior run was 28:12). Macro regime page is a bootstrap placeholder; cross-check against regime not possible.

3. **`tv_breakout_up` at only 9 hits** — lowest signal in the run. Long side lacks broad breakout participation; trend-continuation (`tv_trending_up`) is carrying the long thesis on 8 of 9 candidates.

4. **Short quality thin.** 26 of 31 shorts are score-1 (minimum threshold, single setup). Only 5 (LIF, INTR, BRSL, CDRE, DFH) have multi-setup confluence. Stage 2 should apply a high bar to score-1 names — single-setup shorts carry execution timing risk.

5. **Capitol Trades: zero candidate overlap.** 12 congressional-buy tickers exist in the universe but none advanced as candidates. No insider-buy tailwind on any Stage 3 long.

6. **Setup pattern history unavailable.** `wiki/meta/setup_patterns.md` has fewer than 5 closed trades with realized P&L. Cannot calibrate win rates for `stage4_momentum_breakdown` or `sector_laggard_decline` setups that dominate the short side.

## Last updated

20260513_084338 — 2026-05-13T01:43:38-07:00
