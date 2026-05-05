---
name: scanner state
last_updated: 2026-05-04
last_run_id: 20260504_171717
target_words: 500
stale_after_days: 3
word_count: 0
summary: current market breadth + signal density across the universe
---

# Scanner State

## TL;DR

12 candidates from 1,601-ticker universe. All 12 long — zero short setups survived the 2-reason threshold. No scanner errors. Dominant signal pair: `tv_strong_buy` + `tv_trending_up` (9 of 12 candidates carry both). One standout: NBIS +14.2% on the day. Capitol Trades returned 7 tickers with congressional buys, none overlapping with the 12 candidates.

## Sector breadth

Sector labels not available in the JSON. Exchange and market-cap breakdown of all 12 candidates:

| Ticker | Exchange | Last Close | Mkt Cap | Change % | Score |
|---|---|---|---|---|---|
| PRIM | NYSE | $185.55 | $10.1B | +2.88% | 3 |
| TSM | NYSE | $401.61 | $1,750B | +0.99% | 2 |
| COST | NASDAQ | $1,012.79 | $449B | +0.11% | 2 |
| LITE | NASDAQ | $976.18 | $69.7B | +2.76% | 2 |
| ALL | NYSE | $219.87 | $56.6B | +1.51% | 2 |
| NBIS | NASDAQ | $176.42 | $44.4B | +14.20% | 2 |
| MTSI | NASDAQ | $291.72 | $21.9B | +2.65% | 2 |
| MKSI | NASDAQ | $291.53 | $19.6B | +4.35% | 2 |
| TLN | NASDAQ | $384.64 | $17.5B | +3.35% | 2 |
| JAZZ | NASDAQ | $208.06 | $13.1B | +2.63% | 2 |
| DVA | NYSE | $154.08 | $10.2B | +1.60% | 2 |
| ECG | NYSE | $150.93 | $7.7B | +1.20% | 2 |

Range: $7.7B (ECG) to $1.75T (TSM). NASDAQ-heavy (8 of 12). Only PRIM scored 3; remaining 11 at minimum threshold of 2.

## Signal density

Hits across the 1,601-ticker universe:

- `tv_strong_buy`: 400 hits (capped at config max)
- `tv_strong_sell`: 400 hits (capped at config max)
- `tv_overbought`: 400 hits (capped at config max)
- `tv_trending_down`: 294 hits
- `tv_trending_up`: 205 hits
- `tv_oversold`: 163 hits
- `tv_breakout_up`: 15 hits
- `tv_breakout_down`: 15 hits
- `capitol_buys` (30-day): 7 tickers with congressional purchases

Dropped before scoring: 432 below min price ($5), 163 below min volume (500k), 570 below min market cap ($1B), 59 conflicted (mixed long/short signals). 164 directional singletons long and 201 directional singletons short failed the 2-reason threshold.

## Anomalies

1. **Three signal kinds hit the 400-count cap** (`tv_strong_buy`, `tv_strong_sell`, `tv_overbought`). Config ceiling is 400 per kind. Actual universe-wide counts for these signals are unknown — the cap was binding. This is potentially anomalous breadth on the buy side; or simply a large-universe artifact. Pre-market reviewer should not infer directional bias from capped counts alone.

2. **Zero short candidates.** 201 directional singletons short failed the 2-reason minimum, and 15 `tv_breakout_down` hits produced no surviving candidates. In a 1,601-ticker universe with 294 `tv_trending_down` hits and 400 `tv_strong_sell` hits (capped), zero shorts advancing is notable. Either short setups are not stacking signals or the conflicted-drop filter (59 tickers) is absorbing them.

3. **NBIS +14.2%.** Single-day move is the largest in the candidate list by a wide margin. `tv_strong_buy` + `tv_trending_up` only — no breakout signal. Pre-market reviewer should assess whether this is a news catalyst or a gap-fade risk.

4. **Capitol Trades non-overlap.** 7 congressional buy tickers did not advance any candidate. Not an error — confirms no political-trade overlay on this batch.

5. **Macro regime and setup pattern history unavailable.** Both `wiki/macro/regime.md` and `wiki/meta/setup_patterns.md` are bootstrap placeholders. Cannot cross-check signal mix against regime or assess win-rate risk for the `tv_strong_buy` + `tv_trending_up` combo that dominates this run.

## Last updated

20260504_171717 — 2026-05-04T17:17:17-07:00
