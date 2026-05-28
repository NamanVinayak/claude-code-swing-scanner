---
name: scanner state
last_updated: 2026-05-28
last_run_id: 20260528_211443
target_words: 500
stale_after_days: 3
word_count: 0
summary: current market breadth + signal density across the universe
---

# Scanner State

## TL;DR

40 candidates from 1,589-ticker universe: 9 long, 31 short. No scanner errors (`errors[]` empty). Long side: 4 names on `tv_strong_buy`, 8 on `tv_trending_up`, 6 on `tv_breakout_up` (overlapping scores; no triple-confirmed name at score=3). Short side dominated by `sector_laggard_decline` (24 of 31 shorts carry that single reason, score=1); only 2 shorts dual-confirmed — SYM (`stage4_momentum_breakdown` + `bearish_episodic_pivot`, -9.0% on day) and PLAB (`bearish_episodic_pivot` + `sector_laggard_decline`, -36.4% on day). Zero congressional buys in 30-day window advanced to the candidate list.

## Sector breadth

Sector labels not present in JSON. Breakdown by ticker identity:

**Longs (9)**

| Sector (inferred) | Tickers | Count |
|---|---|---|
| Hospitality / Travel | MAR, HLT, H | 3 |
| Semiconductors / Tech | SNDK | 1 |
| Metals / Mining | SCCO | 1 |
| Financial Data / Index | MSCI | 1 |
| Media / Entertainment | TKO | 1 |
| Aerospace / Aviation | FTAI | 1 |
| IT Distribution | SNX | 1 |

**Shorts (31)**

| Sector (inferred) | Tickers | Count |
|---|---|---|
| Biotech / Pharma | SMMT, TNGX, TMDX, ALHC, OPCH | 5 |
| Fintech / MarTech | FUTU, KVYO, FSLY, WIX | 4 |
| Industrials / Construction | VLTO, PRIM, SITE, ATMU, GPGI | 5 |
| Consumer / Retail | PLNT, SHAK, WAY, WHR | 4 |
| Energy | CRK, NOG | 2 |
| Defense / Aerospace | SYM, KTOS | 2 |
| Semiconductors | PLAB, XRAY | 2 |
| Financial Services | STEP, INTU | 2 |
| Media / Comm | ORKA | 1 |
| Healthcare Services | NIQ | 1 |
| Travel / Consumer | TBBB | 1 |
| Shipping | P | 1 |
| REZI | REZI | 1 |

## Signal density

Hits across the 1,589-ticker universe (raw from diagnostic):

- `tv_strong_buy`: 400 hits (capped at config max)
- `tv_strong_sell`: 400 hits (capped at config max)
- `tv_overbought`: 400 hits (capped at config max)
- `tv_trending_down`: 270 hits
- `tv_trending_up`: 211 hits
- `tv_oversold`: 168 hits
- `tv_breakout_up`: 25 hits
- `tv_breakout_down`: 8 hits
- `capitol_buys` (30-day): 5 tickers with congressional purchases (none qualified into candidates)
- Total signal hits: 1,882 across 1,589 unique tickers
- Short setups added by setup-based screener: 45

Dropped before scoring: 454 below min price ($5), 153 below min volume (500k), 616 below min market cap ($1B), 0 missing metadata, 61 conflicted (mixed long/short signals), 163 long singletons + 133 short singletons below 2-reason threshold.

## Anomalies

1. **Short side swamps long side 31:9.** Most unusual skew in recorded runs. `sector_laggard_decline` produced 24 single-reason shorts (score=1); these are the lowest-conviction setup type. Stage 2 should apply a firm quality filter — dual-reason shorts only unless setup is especially clean.

2. **Three signal kinds hit the 400-count cap** (`tv_strong_buy`, `tv_strong_sell`, `tv_overbought`). True universe counts unknown. `tv_overbought` capping while `tv_oversold` sits at 168 — continued overbought skew from prior runs.

3. **Two episodic-pivot shorts with extreme daily moves.** PLAB -36.4% ($34.02) and SYM -9.0% ($48.81) — both already flushed hard on the scan day. Stage 2 must verify whether the entry-to-short opportunity remains or is exhausted.

4. **KTOS flagged `stage4_momentum_breakdown` yet +13.8% on day.** Rising price on a breakdown signal is contradictory. Stage 2 should drop or flag this as suspicious; the short thesis requires follow-through selling, not strength.

5. **Macro regime page is a bootstrap placeholder** (last_updated 2026-05-03, body pending). No calibration available for whether the current short-heavy output conflicts with the macro backdrop.

6. **Setup pattern history unavailable.** Fewer than 5 closed trades with realized P&L. Win rates for `sector_laggard_decline`, `stage4_momentum_breakdown`, and `bearish_episodic_pivot` cannot be calibrated empirically.

## Last updated

20260528_211443 — 2026-05-28T14:14:43-07:00
