---
name: scanner state
last_updated: 2026-06-19
last_run_id: 20260619_211137
target_words: 500
stale_after_days: 3
word_count: 0
summary: current market breadth + signal density across the universe
---

# Scanner State

## TL;DR

40 candidates from 1,652-ticker universe: 26 long, 14 short. No scanner errors (`errors[]` empty). Long side strongly bid — 7 names scored 3 (triple-confirmed: `tv_strong_buy` + `tv_breakout_up` + `tv_trending_up`); 19 scored 2. Short side all score=1 (single-reason, lowest conviction): 7 `sector_laggard_decline`, 5 `stage4_momentum_breakdown`, 1 `bearish_episodic_pivot`, 1 mixed. Zero congressional buys (`capitol_buys`=0).

## Sector breadth

Sector labels not present in JSON. Notable groupings by ticker identity:

**Longs (26) — dominant themes:**
- Semiconductors/EDA: TSM, ASML, ARM, ALAB, TTMI, TER, CRDO, ENTG, SIMO, ACLS
- Industrials/Capital Equipment: CAT, GEV, ETN, CMI, ROK, WAB, AME, NDSN, VSEC
- Energy/Power: BE, TLN
- Healthcare/Diagnostics: NTRA, ALGN
- Financials/Services: ECG, TOL (homebuilder), APH (connector hardware)

**Shorts (14):**
- Software/SaaS: INTU, ZS, VRSK, INSM
- Crypto/Fintech: MSTR, FUTU, CRCL
- Telecom: VG, CHTR
- Media/Advertising: OMC
- Mining/Metals: CDE
- Space/Satellite: PL
- Financials: FIG

## Signal density

Hits across the 1,652-ticker universe (raw from diagnostic):

- `tv_strong_buy`: 400 hits (capped at config max)
- `tv_strong_sell`: 400 hits (capped at config max)
- `tv_trending_down`: 351 hits
- `tv_overbought`: 318 hits
- `tv_oversold`: 295 hits
- `tv_trending_up`: 239 hits
- `tv_breakout_up`: 51 hits
- `tv_breakout_down`: 29 hits
- `capitol_buys` (30-day): 0 tickers
- Total signal hits: 2,083 across 1,652 unique tickers with any signal
- Short setups added by setup-based screener: 48

Dropped before scoring: 534 below min price ($5), 161 below min volume (500k), 516 below min market cap ($1B), 0 missing metadata, 68 conflicted, 209 long singletons + 138 short singletons below 2-reason threshold, 0 below-threshold drops.

## Anomalies

1. **Long side dominates 26:14 with unusually strong conviction.** 7 longs hit score=3 (all three signals: `tv_strong_buy` + `tv_breakout_up` + `tv_trending_up`) — that trifecta concentration is a risk-on breadth signal. Lead names include TSM (+6.9%), BE (+15.4%), GEV (+5.8%), ALAB (+11.3%), ENTG (+13.6%).

2. **`tv_strong_buy` and `tv_strong_sell` both capped at 400** simultaneously — true universe counts unknown for both. In a normal day one typically dominates; dual-cap suggests polarized market internals.

3. **`tv_overbought` (318) exceeds `tv_oversold` (295)** — consistent with a market that has run. Breakout entries on already-extended names (high RSI/z-score) have historically underperformed per `setup_patterns.md` (breakout win rate 25% last 90 days, only 1 of 4 closed trades profitable). Stage 2 should screen for extended entries.

4. **All 14 short candidates are single-reason (score=1).** No dual-confirmed short exists in this output. `sector_laggard_decline` (7 names) and `stage4_momentum_breakdown` (5 names) have no empirical win rate in the database — sample size is still zero closed shorts.

5. **Zero `capitol_buys`** — 0 congressional purchases in the last 30 days for any universe ticker. Consistent with prior runs.

6. **Macro regime page is a bootstrap placeholder** (last_updated 2026-05-03). No calibration available for whether long-heavy, overbought-skewed output conflicts with any macro backdrop.

## Last updated

20260619_211137 — 2026-06-19T14:11:41-07:00
