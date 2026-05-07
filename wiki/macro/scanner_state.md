---
name: scanner state
last_updated: 2026-05-07
last_run_id: 20260507_211015
target_words: 500
stale_after_days: 3
word_count: 0
summary: current market breadth + signal density across the universe
---

# Scanner State

## TL;DR

40 candidates from 1,592-ticker universe: 12 long, 28 short. No scanner errors. Long side: 2 score-3 names (NET, MKSI — triple `tv_strong_buy` + `tv_breakout_up` + `tv_trending_up`); remainder are score-2. Short side heavily weighted toward score-1 (22 of 28); only GPGI scored 3 (all three setup types: `stage4_momentum_breakdown` + `bearish_episodic_pivot` + `sector_laggard_decline`, -25.9%). Notable single-day moves: CRWD +8.0%, PANW +7.0%, HWM +6.3%, MIDD +11.0% on long side; FSLY -38.2%, GPGI -25.9%, FUTU -13.8%, INTR -14.5% on short side. Capitol Trades: 4 tickers with congressional buys in the universe; zero overlap with advancing candidates.

## Sector breadth

Sector labels inferred from ticker identity (not in JSON).

**Longs (12)**

| Sector | Tickers | Count |
|---|---|---|
| Tech / Cybersecurity / Networking | NET, PANW, CRWD | 3 |
| Semis / Semi Equip | NVDA, MKSI | 2 |
| Industrials | HWM, ROK, MIDD | 3 |
| Consumer / Retail | COST | 1 |
| Telecom / Materials | GLW | 1 |
| Healthcare / Biotech | NTRA, BIIB | 2 |

**Shorts (28)**

| Sector | Tickers | Count |
|---|---|---|
| Tech / Software / Internet | FUTU, RBLX, CHTR, PAYP, CHKP, FSLY, SRAD, LBRDK | 8 |
| Industrials / Machinery | WHR, RRX, MIDD*, PRIM, DOO | 4 |
| Healthcare / Biotech | PODD, PCVX, NVST, CHYM | 4 |
| Consumer Discretionary | TPR, BROS, CELH, COKE | 4 |
| Energy / Chemicals | WLK, PPC | 2 |
| Aero / Defense / Space | KTOS, ASTS | 2 |
| Diversified / Other | GPGI, INTR, VG, CAR | 4 |

Short side: tech/software (8) and healthcare (4) are the two largest clusters.

## Signal density

Hits across the 1,592-ticker universe:

- `tv_strong_buy`: 400 hits (capped at config max)
- `tv_strong_sell`: 400 hits (capped at config max)
- `tv_overbought`: 400 hits (capped at config max)
- `tv_trending_down`: 322 hits
- `tv_trending_up`: 201 hits
- `tv_oversold`: 172 hits
- `tv_breakout_down`: 23 hits
- `tv_breakout_up`: 21 hits
- `capitol_buys` (30-day): 4 tickers with congressional purchases
- Total signal hits: 1,939 across 1,592 unique tickers
- Short setups added (setup-based screener): 46

Dropped before scoring: 459 below min price ($5), 161 below min volume (500k), 605 below min market cap ($1B), 0 missing metadata, 72 conflicted (mixed long/short signals). 155 directional singletons long + 128 singletons short below 2-reason threshold.

## Anomalies

1. **Three signal kinds hit the 400-count cap** (`tv_strong_buy`, `tv_strong_sell`, `tv_overbought`). True universe-wide counts unknown for all three — cap-binding again as in yesterday's run.

2. **Short candidates outnumber longs 28:12** — a notable skew. Yesterday's run was 17 short vs. 23 long. The inversion could reflect broad distribution / sector rotation, but macro regime page remains a bootstrap placeholder so cross-check against regime is not possible.

3. **Short side quality thin.** 22 of 28 shorts are score-1 (minimum threshold). Only GPGI (score-3) and FUTU, WHR, INTR (score-2) have multi-signal confluence. Pre-market reviewer should apply high bar to score-1 names — single-setup shorts carry execution timing risk.

4. **FSLY -38.2% is an outlier move.** Advancing as short via `bearish_episodic_pivot` + `sector_laggard_decline`. Gap of this magnitude may have already exhausted the short opportunity by pre-market — Stage 2 should assess remaining short float and whether the gap will gap-and-grind or gap-and-reverse.

5. **Capitol Trades: zero candidate overlap.** 4 congressional-buy tickers exist in the universe but none advanced as candidates. No insider-buy tailwind available for Stage 3 longs.

6. **Macro regime and setup pattern history unavailable.** Both `wiki/macro/regime.md` and `wiki/meta/setup_patterns.md` remain bootstrap placeholders. Cannot cross-check signal mix against regime or historical win rates.

## Last updated

20260507_211015 — 2026-05-07T14:10:15-07:00
