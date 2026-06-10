---
name: scanner state
last_updated: 2026-06-10
last_run_id: 20260610_211035
target_words: 500
stale_after_days: 3
word_count: 0
summary: current market breadth + signal density across the universe
---

# Scanner State

## TL;DR

40 candidates from 1,664-ticker universe: 12 long, 28 short. No scanner errors (`errors[]` empty). Long side dominated by `tv_trending_up` (12 of 12) + `tv_strong_buy` (11 of 12); 1 name (PSA) on `tv_breakout_up`. Short side: 26 single-reason candidates (score=1), only 2 dual-confirmed (SMCI, LAZ — both `stage4_momentum_breakdown` + `bearish_episodic_pivot`). Zero congressional buys (`capitol_buys`=0).

## Sector breadth

Sector labels not present in JSON. Notable groupings by ticker identity:

**Longs (12)** — Semiconductors/Tech (AMAT, KLAC, CRDO), Retail (ROST, BURL, DRI), Energy (PSX), Insurance/Financials (ALL, AIZ), REITs (PSA, EXR), Media (TKO).

**Shorts (28)** — heavy mining/metals cluster (AU, AG, NXE, SSRM, HL), retail/consumer (CHWY, ACI, LMND, YUMC), semis (FORM, CELC, AXTI), financial/index (SLM, INTU, TYL), crypto-adjacent (MSTR, BMNR, CRCL, SMCI).

## Signal density

Hits across the 1,664-ticker universe (raw from diagnostic):

- `tv_strong_buy`: 400 hits (capped at config max)
- `tv_strong_sell`: 400 hits (capped at config max)
- `tv_oversold`: 377 hits
- `tv_overbought`: 250 hits
- `tv_trending_down`: 341 hits
- `tv_trending_up`: 147 hits
- `tv_breakout_down`: 11 hits
- `tv_breakout_up`: 9 hits
- `capitol_buys` (30-day): 0 tickers
- Total signal hits: 1,935 across 1,664 unique tickers with any signal
- Short setups added by setup-based screener: 48

Dropped before scoring: 529 below min price ($5), 211 below min volume (500k), 551 below min market cap ($1B), 0 missing metadata, 28 conflicted (mixed long/short signals), 182 long singletons + 151 short singletons below the 2-reason threshold, 0 below-threshold drops.

## Anomalies

1. **Short side outnumbers long 28:12.** Of the 48 setup-based shorts added, only 28 survived to candidates — 26 are single-reason `sector_laggard_decline`/`stage4_momentum_breakdown`/`bearish_episodic_pivot` (score=1, lowest conviction). Only SMCI and LAZ are dual-confirmed.

2. **`tv_strong_buy` and `tv_strong_sell` both hit the 400-count cap** simultaneously — true universe counts for both unknown. `tv_oversold` (377) is also near-capped while `tv_overbought` (250) is well below cap, a reversal from the prior run (2026-05-28: overbought capped at 400, oversold at 168).

3. **AXTI flagged `sector_laggard_decline` (a bearish setup) yet is +8.8% on the day** — same contradiction pattern as KTOS in the 2026-05-28 run. Stage 2 should drop or flag this.

4. **SMCI: -28.0% on the day**, the largest single-day move in this candidate set, dual-confirmed short (`stage4_momentum_breakdown` + `bearish_episodic_pivot`). Stage 2 must verify whether the short opportunity remains or is already exhausted (cf. PLAB precedent from 2026-05-28).

5. **Zero `capitol_buys` this run** vs. 5 tickers with congressional purchases on 2026-05-28 (none of which qualified into candidates either).

6. **Macro regime page is still a bootstrap placeholder** (last_updated 2026-05-03, body pending). No calibration available for whether today's short-heavy output (28:12) conflicts with the macro backdrop.

7. **Setup pattern history remains thin.** `wiki/meta/setup_patterns.md` reports only 4 resolved trades in the last 30 days (1 directional loss: ROK breakout stop_hit). Win rates for `sector_laggard_decline`, `stage4_momentum_breakdown`, and `bearish_episodic_pivot` — the dominant short setups in today's output — still cannot be empirically calibrated.

## Last updated

20260610_211035 — 2026-06-10T14:10:35-07:00
