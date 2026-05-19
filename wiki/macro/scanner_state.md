---
name: scanner state
last_updated: 2026-05-18
last_run_id: 20260519_030512
target_words: 500
stale_after_days: 3
word_count: 0
summary: current market breadth + signal density across the universe
---

# Scanner State

## TL;DR

40 candidates from 1,635-ticker universe: 11 long, 29 short. No scanner errors (`errors[]` empty). Long side dominated by `tv_strong_buy` + `tv_trending_up` pairs — 10 of 11 longs carry that trifecta-minus-breakout combo, all score-2. One breakout long: MASI (`tv_breakout_up` + `tv_trending_up`). Energy names (XOM, CVX, VLO, PSX) leading the long column, all up 1.6–3.1% on the day. Short side: 29 shorts hit the max_candidates=40 cap after 43 setups were initially found. Single congressional buy: UNP (Rohit Khanna), 30-day window.

## Sector breadth

Sector labels not present in JSON. Breakdown by ticker identity:

**Longs (11)**

| Sector (inferred) | Tickers | Count |
|---|---|---|
| Energy / Refining | XOM, CVX, VLO, PSX | 4 |
| Transportation / Rail | UNP, NSC, JBHT | 3 |
| Financials / Insurance | RY, ALL, CPAY | 3 |
| Healthcare / MedTech | MASI | 1 |

**Shorts (29)**

| Sector (inferred) | Tickers | Count |
|---|---|---|
| Consumer / Retail / Food | TSCO, M, CAR, WING, WAY | 5 |
| Fintech / Payments | CTSH, STNE, DLO, CAI, SRAD | 5 |
| Healthcare / Biotech | SMMT, ERAS, ZLAB | 3 |
| EV / Mobility / China Tech | LI, BILI, PONY | 3 |
| Industrials / Defense | AS, KTOS, PRIM | 3 |
| Telecom / Comms | GPGI, INFQ, NIQ | 3 |
| Software / Diversified | QXO, AUGO, FSLY | 3 |
| Other | NCLH, JPC, YSS | 3 |

## Signal density

Hits across the 1,635-ticker universe:

- `tv_strong_buy`: 400 hits (capped at config max)
- `tv_strong_sell`: 400 hits (capped at config max)
- `tv_oversold`: 355 hits
- `tv_trending_down`: 355 hits
- `tv_overbought`: 285 hits
- `tv_trending_up`: 159 hits
- `tv_breakout_down`: 31 hits
- `tv_breakout_up`: 8 hits
- `capitol_buys` (30-day): 22 tickers with congressional purchases
- Total signal hits: 1,993 across 1,635 unique tickers
- Short setups found by setup-based screener: 43 (29 carried through to max_candidates cap)

Dropped before scoring: 565 below min price ($5), 140 below min volume (500k), 542 below min market cap ($1B), 0 missing metadata, 57 conflicted (mixed long/short signals). 212 directional long singletons + 108 short singletons below the 2-reason threshold.

## Anomalies

1. **Two signal kinds hit the 400-count cap** (`tv_strong_buy`, `tv_strong_sell`). True universe-wide counts unknown. `tv_oversold` (355) and `tv_trending_down` (355) both elevated. `tv_breakout_up` at 8 hits — lowest seen, even below the prior low of 9 (run 20260514). Breakout-up setups are structurally scarce in this scan.

2. **Long side thin on score.** All 11 longs are score-2 (no score-3 trifecta names). MASI is the only breakout name. Energy concentration (4 of 11 longs) — sector-specific tailwind or rotational move; Stage 2 should verify.

3. **Short setup screener produced 43 names but max_candidates cap truncated to 29.** Shorts were cut at the cap; lower-ranked short setups were dropped without review. `stage4_momentum_breakdown`: 10 names advancing. `sector_laggard_decline`: 19 names advancing. No `bearish_episodic_pivot` candidates in final list.

4. **Capitol Trades: minimal overlap.** 22 congressional-buy tickers in universe, only 1 (UNP) advanced as a long candidate. No cluster (5+ politicians on same name) detected.

5. **Setup pattern history unavailable.** `wiki/meta/setup_patterns.md` has fewer than 5 closed trades with realized P&L. Cannot calibrate win rates for `stage4_momentum_breakdown` or `sector_laggard_decline`.

6. **Macro regime page is a bootstrap placeholder.** Cannot cross-check long/short signal skew against current risk regime.

## Last updated

20260519_030512 — 2026-05-18T20:05:12-07:00
