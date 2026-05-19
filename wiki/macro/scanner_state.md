---
name: scanner state
last_updated: 2026-05-19
last_run_id: 20260519_211633
target_words: 500
stale_after_days: 3
word_count: 0
summary: current market breadth + signal density across the universe
---

# Scanner State

## TL;DR

40 candidates from 1,644-ticker universe: 11 long, 29 short. No scanner errors (`errors[]` empty). Long side: 2 score-3 trifectas (ALL, ALAB — `tv_strong_buy` + `tv_breakout_up` + `tv_trending_up`); 9 score-2 longs on `tv_strong_buy` + `tv_trending_up` only. Energy names (XOM, CVX, VLO, PSX) again prominent on the long column. Short side dominated by `sector_laggard_decline` (21 of 29); 7 `stage4_momentum_breakdown`; 1 `bearish_episodic_pivot` (WRBY, -11% on day). 7 tickers with congressional buys in the 30-day window; 0 advanced as candidates.

## Sector breadth

Sector labels not present in JSON. Breakdown by ticker identity:

**Longs (11)**

| Sector (inferred) | Tickers | Count |
|---|---|---|
| Energy / Refining | XOM, CVX, VLO, PSX, FANG | 5 |
| Financials / Insurance | ALL, CPAY | 2 |
| Semiconductors / Tech | ALAB, ARM | 2 |
| Healthcare / Biotech | RVMD | 1 |
| Media / Outdoor Ads | LAMR | 1 |

**Shorts (29)**

| Sector (inferred) | Tickers | Count |
|---|---|---|
| Consumer / Retail / Food | RBLX, W, WING, PLNT, WRBY | 5 |
| Fintech / Payments | STNE, CAI, INFQ | 3 |
| Healthcare / Biotech | SMMT, ERAS | 2 |
| EV / Mobility / China Tech | LI, BILI, HSAI, LCID | 4 |
| Industrials / Defense | AS, KTOS, KRMN, PRIM, IBP | 5 |
| Tech / Software | QXO, AUGO, FSLY, CHYM | 4 |
| Other | JHX, CAR, MMYT, GPGI, YSS, ENHA | 6 |

## Signal density

Hits across the 1,644-ticker universe (raw from diagnostic):

- `tv_strong_buy`: 400 hits (capped at config max)
- `tv_strong_sell`: 400 hits (capped at config max)
- `tv_oversold`: 400 hits (capped at config max)
- `tv_trending_down`: 357 hits
- `tv_overbought`: 243 hits
- `tv_trending_up`: 132 hits
- `tv_breakout_down`: 18 hits
- `tv_breakout_up`: 5 hits
- `capitol_buys` (30-day): 7 tickers with congressional purchases
- Total signal hits: 1,955 across 1,644 unique tickers
- Short setups added by setup-based screener: 35

Dropped before scoring: 527 below min price ($5), 169 below min volume (500k), 600 below min market cap ($1B), 0 missing metadata, 40 conflicted (mixed long/short signals). 200 directional long singletons + 97 short singletons below the 2-reason threshold.

## Anomalies

1. **Three signal kinds hit the 400-count cap** (`tv_strong_buy`, `tv_strong_sell`, `tv_oversold`). True counts for all three unknown. Prior run (20260519_030512) had only two capped signals — `tv_oversold` hitting the cap now is new. Signals are elevated across the board.

2. **`tv_breakout_up` at 5 hits — new session low.** Prior low was 8 (run 20260519_030512). Long setups requiring a breakout confirmation are structurally scarce; Stage 2 should treat ALL and ALAB's breakout signals with extra scrutiny.

3. **Energy/refining concentration on longs.** 5 of 11 longs (XOM, CVX, VLO, PSX, FANG) are energy/refining. Same sector cluster as prior run. Macro regime page is a bootstrap placeholder — cannot verify against macro context. Stage 2 should check commodity/oil macro before advancing the full cluster.

4. **Capitol Trades signal collapsed.** Prior run reported 22 congressional-buy tickers; this run shows only 7. No candidates with `capitol_buys_30d > 0` in the final list. No cluster (5+ politicians on one name) detected.

5. **Short side: `sector_laggard_decline` dominates.** 21 of 29 shorts tagged with that single reason (score=1 each). No multi-reason short in the list. Low signal density means short setups are weaker conviction than prior run's mix.

6. **Setup pattern history unavailable.** `wiki/meta/setup_patterns.md` has fewer than 5 closed trades with realized P&L. Cannot calibrate win rates for `stage4_momentum_breakdown`, `sector_laggard_decline`, or `bearish_episodic_pivot`.

## Last updated

20260519_211633 — 2026-05-19T14:16:33-07:00
