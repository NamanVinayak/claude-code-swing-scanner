---
name: scanner state
last_updated: 2026-05-05
last_run_id: 20260505_213211
target_words: 500
stale_after_days: 3
word_count: 0
summary: current market breadth + signal density across the universe
---

# Scanner State

## TL;DR

10 candidates from 1,569-ticker universe. All 10 long — zero short setups survived the 2-reason threshold. No scanner errors. Dominant signal pair: `tv_strong_buy` + `tv_trending_up` (appears across 6 of 10 candidates). Top-3 scorers (ROK, RRX, JAZZ) all carry the triple: `tv_strong_buy` + `tv_breakout_up` + `tv_trending_up`. Notable day-of moves: NET +9.0%, EXPD +9.6%, ROK +8.9%. No Capitol Trades overlap — 4 congressional-buy tickers found, none advancing.

## Sector breadth

Sector labels not available in this run's JSON. Exchange and market-cap breakdown of all 10 candidates:

| Ticker | Exchange | Last Close | Mkt Cap | Change % | Score |
|---|---|---|---|---|---|
| ROK | NYSE | $435.93 | $49.0B | +8.90% | 3 |
| RRX | NYSE | $222.02 | $14.8B | +4.48% | 3 |
| JAZZ | NASDAQ | $212.26 | $13.3B | +2.02% | 3 |
| CMI | NYSE | $675.00 | $93.3B | +2.78% | 2 |
| NET | NYSE | $244.43 | $86.0B | +9.04% | 2 |
| MPC | NYSE | $260.51 | $76.7B | +3.16% | 2 |
| CRDO | NASDAQ | $193.57 | $35.7B | +7.50% | 2 |
| MTSI | NASDAQ | $303.57 | $22.8B | +4.06% | 2 |
| EXPD | NYSE | $153.08 | $20.4B | +9.57% | 2 |
| DVA | NYSE | $157.04 | $10.4B | +1.92% | 2 |

Range: $10.4B (DVA) to $93.3B (CMI). NYSE-heavy (7 of 10). Three candidates scored 3; seven at minimum threshold of 2.

## Signal density

Hits across the 1,569-ticker universe:

- `tv_strong_buy`: 400 hits (capped at config max)
- `tv_strong_sell`: 400 hits (capped at config max)
- `tv_overbought`: 400 hits (capped at config max)
- `tv_trending_down`: 301 hits
- `tv_trending_up`: 227 hits
- `tv_oversold`: 173 hits
- `tv_breakout_up`: 26 hits
- `tv_breakout_down`: 17 hits
- `capitol_buys` (30-day): 4 tickers with congressional purchases

Dropped before scoring: 457 below min price ($5), 169 below min volume (500k), 546 below min market cap ($1B), 0 missing metadata, 68 conflicted (mixed long/short signals). 161 directional singletons long and 158 directional singletons short failed the 2-reason threshold.

## Anomalies

1. **Three signal kinds hit the 400-count cap** (`tv_strong_buy`, `tv_strong_sell`, `tv_overbought`). Actual universe-wide counts for these signals are unknown — the cap was binding on all three. Pre-market reviewer should not infer directional bias from capped counts alone.

2. **Zero short candidates.** 158 directional singletons short and 17 `tv_breakout_down` hits produced zero surviving short candidates. With 301 `tv_trending_down` and 400 `tv_strong_sell` hits (capped) in a 1,569-ticker universe, the short side is not stacking to the 2-reason minimum. Consistent with prior run (20260504_171717 also returned 0 shorts).

3. **Three candidates with single-day moves ≥ 9%.** EXPD +9.6%, NET +9.0%, ROK +8.9% are all advancing with 2-reason scores. Pre-market reviewer should assess gap-fade risk vs. continuation for each; these may be news-driven moves.

4. **Capitol Trades non-overlap.** 4 congressional-buy tickers found; none advanced to candidates. Not an error.

5. **Macro regime and setup pattern history unavailable.** Both `wiki/macro/regime.md` and `wiki/meta/setup_patterns.md` remain bootstrap placeholders. Cannot cross-check signal mix against regime or historical win rates.

## Last updated

20260505_213211 — 2026-05-05T14:32:11-07:00
