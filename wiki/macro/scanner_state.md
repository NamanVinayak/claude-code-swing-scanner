---
name: scanner state
last_updated: 2026-05-13
last_run_id: 20260513_210957
target_words: 500
stale_after_days: 3
word_count: 0
summary: current market breadth + signal density across the universe
---

# Scanner State

## TL;DR

40 candidates from 1,735-ticker universe: 17 long, 23 short. No scanner errors. Long side strong: top 3 (NBIS, TSEM, AAOI) are score-3 with full trifecta (`tv_strong_buy` + `tv_breakout_up` + `tv_trending_up`); all saw large single-day moves (+15.7%, +22.6%, +18.5% respectively). Remaining 14 longs are score-2 (`tv_strong_buy` + `tv_trending_up` mostly). Short side: 5 score-2 names with multi-setup confluence (DT, BIRK, DOCS, RCAT, EVLV); 18 score-1 shorts dominated by `sector_laggard_decline`. Capitol Trades: 17 tickers with congressional buys in the universe; zero overlap with advancing candidates.

## Sector breadth

Sector labels not present in JSON. Breakdown by ticker identity:

**Longs (17)**

| Sector (inferred) | Tickers | Count |
|---|---|---|
| Semis / Optical / PCB | NBIS, TSEM, AAOI, COHR, TTMI, VICR | 6 |
| Industrials / Infrastructure | PWR, CMI, ATI | 3 |
| Consumer Staples | COST | 1 |
| Industrial Gases / Materials | LIN | 1 |
| Healthcare REIT | WELL | 1 |
| Energy Midstream | TRGP | 1 |
| Media / Entertainment | LYV | 1 |
| Biotech | BIIB | 1 |
| Internet / Tech | BIDU, VRSN | 2 |

**Shorts (23)**

| Sector (inferred) | Tickers | Count |
|---|---|---|
| Defense / Aerospace / Drones | KTOS, BAH, RCAT, AUGO | 4 |
| Healthcare / Biotech / MedTech | INSM, ERAS, ATEC | 3 |
| Consumer Discretionary | BIRK, KMX, CAR, BFAM | 4 |
| Software / SaaS | DT, DOCS | 2 |
| Industrials / Infrastructure | FLS, PRIM, BMI | 3 |
| EV / Mobility / Tech | EVLV, LCID, VISN, INTR | 4 |
| Telecom / Comms | GILT, GPGI | 2 |
| Agriculture / Chemicals | FMC | 1 |

## Signal density

Hits across the 1,735-ticker universe:

- `tv_strong_buy`: 400 hits (capped at config max)
- `tv_strong_sell`: 400 hits (capped at config max)
- `tv_overbought`: 400 hits (capped at config max)
- `tv_oversold`: 336 hits
- `tv_trending_down`: 335 hits
- `tv_trending_up`: 202 hits
- `tv_breakout_down`: 28 hits
- `tv_breakout_up`: 15 hits
- `capitol_buys` (30-day): 17 tickers with congressional purchases
- Total signal hits: 2,116 across 1,735 unique tickers
- Short setups added (setup-based screener): 25

Dropped before scoring: 516 below min price ($5), 156 below min volume (500k), 567 below min market cap ($1B), 0 missing metadata, 74 conflicted (mixed long/short signals). 219 directional long singletons + 186 short singletons below the 2-reason threshold.

## Anomalies

1. **Three signal kinds hit the 400-count cap** (`tv_strong_buy`, `tv_strong_sell`, `tv_overbought`). True universe-wide counts unknown — cap-bound on all three. Under-counts possible for each.

2. **Long side has 3 score-3 breakout names with extreme intraday moves.** TSEM +22.6%, AAOI +18.5%, NBIS +15.7% on the day. All three carry full trifecta. Chasing multi-day after such moves warrants Stage 2 gap/extension scrutiny.

3. **Short quality thin at score-1 tier.** 18 of 23 shorts are score-1 (`sector_laggard_decline` single-setup). Only 5 names have multi-setup confluence (DT, BIRK, DOCS, RCAT, EVLV). Single-setup shorts carry elevated timing risk; Stage 2 should apply a high bar to score-1 names.

4. **Capitol Trades: zero candidate overlap.** 17 congressional-buy tickers in universe but none advanced as candidates. No insider-buy tailwind on any long candidate.

5. **Setup pattern history unavailable.** `wiki/meta/setup_patterns.md` has fewer than 5 closed trades with realized P&L. Cannot calibrate win rates for `stage4_momentum_breakdown`, `bearish_episodic_pivot`, or `sector_laggard_decline` setups dominating the short side.

6. **Macro regime page is a bootstrap placeholder.** Cannot cross-check signal composition against current risk regime.

## Last updated

20260513_210957 — 2026-05-13T14:10:00-07:00
