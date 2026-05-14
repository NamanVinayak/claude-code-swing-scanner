---
name: scanner state
last_updated: 2026-05-14
last_run_id: 20260514_211306
target_words: 500
stale_after_days: 3
word_count: 0
summary: current market breadth + signal density across the universe
---

# Scanner State

## TL;DR

36 candidates from 1,702-ticker universe: 5 long, 31 short. No scanner errors. Long side light: NBIS is the only score-3 name (trifecta: `tv_strong_buy` + `tv_breakout_up` + `tv_trending_up`, +6.7% on the day, $55.7B cap); MRVL, BE, ALAB, CINF are score-2 (`tv_breakout_up` or `tv_strong_buy` + `tv_trending_up`). Short side heavy: 31 shorts, dominated by `sector_laggard_decline` (23 of 31). Zero congressional-buy overlap with any advancing candidate.

## Sector breadth

Sector labels not present in JSON. Breakdown by ticker identity:

**Longs (5)**

| Sector (inferred) | Tickers | Count |
|---|---|---|
| Semis / AI Infrastructure | NBIS, MRVL, ALAB | 3 |
| Energy / Fuel Cells | BE | 1 |
| Insurance / Financials | CINF | 1 |

**Shorts (31)**

| Sector (inferred) | Tickers | Count |
|---|---|---|
| Healthcare / Biotech / MedTech | INSM, ERAS, GPCR, WGS, CRVS, ATEC | 6 |
| EV / Mobility / Tech | LCID, VISN, INTR, AUGO | 4 |
| Consumer Discretionary | RBLX, NCLH, PLNT, CAR, WWW | 5 |
| Defense / Aerospace / Drones | KTOS, KRMN, RCAT | 3 |
| Industrials / Infrastructure | PRIM, IBP, BMI | 3 |
| Telecom / Comms | LBRDK, GPGI, WB | 3 |
| Software / SaaS | FSLY, CLBT | 2 |
| Agriculture / Chemicals | FMC | 1 |
| Financial Services / Other | PDFS, BTGO | 2 |
| Misc / Other | BILI | 1 |

## Signal density

Hits across the 1,702-ticker universe:

- `tv_strong_buy`: 400 hits (capped at config max)
- `tv_strong_sell`: 400 hits (capped at config max)
- `tv_overbought`: 400 hits (capped at config max)
- `tv_trending_down`: 320 hits
- `tv_oversold`: 274 hits
- `tv_trending_up`: 213 hits
- `tv_breakout_down`: 21 hits
- `tv_breakout_up`: 9 hits
- `capitol_buys` (30-day): 27 tickers with congressional purchases
- Total signal hits: 2,037 across 1,702 unique tickers
- Short setups added (setup-based screener): 31

Dropped before scoring: 483 below min price ($5), 152 below min volume (500k), 647 below min market cap ($1B), 0 missing metadata, 68 conflicted (mixed long/short signals). 218 directional long singletons + 129 short singletons below the 2-reason threshold.

## Anomalies

1. **Three signal kinds hit the 400-count cap** (`tv_strong_buy`, `tv_strong_sell`, `tv_overbought`). True universe-wide counts unknown — cap-bound on all three. `tv_trending_down` (320) and `tv_oversold` (274) both elevated; `tv_breakout_up` unusually low at 9.

2. **Long side thin.** Only 5 longs advanced vs. 31 shorts. `tv_breakout_up` at 9 hits is the lowest breakout count seen to date (prior run: 15). NBIS is the only score-3 long; all others are score-2.

3. **Short side dominated by single-setup `sector_laggard_decline` (23 of 31).** `stage4_momentum_breakdown` produced 5 names; `bearish_episodic_pivot` produced 3 (PDFS -10.7%, CRVS -13.8%, BTGO -17.2% on the day — extreme intraday moves, episodic pivot quality to verify at Stage 2). Single-setup shorts carry elevated timing risk.

4. **Capitol Trades: zero candidate overlap.** 27 congressional-buy tickers in universe but none advanced as candidates. No insider-buy tailwind on any long.

5. **Setup pattern history unavailable.** `wiki/meta/setup_patterns.md` has fewer than 5 closed trades with realized P&L. Cannot calibrate win rates for `sector_laggard_decline`, `stage4_momentum_breakdown`, or `bearish_episodic_pivot` setups.

6. **Macro regime page is a bootstrap placeholder.** Cannot cross-check long/short signal skew against current risk regime.

## Last updated

20260514_211306 — 2026-05-14T14:13:06-07:00
