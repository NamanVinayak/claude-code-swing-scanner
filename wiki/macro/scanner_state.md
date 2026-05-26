---
name: scanner state
last_updated: 2026-05-25
last_run_id: 20260526_023245
target_words: 500
stale_after_days: 3
word_count: 0
summary: current market breadth + signal density across the universe
---

# Scanner State

## TL;DR

40 candidates from 1,607-ticker universe: 14 long, 26 short. No scanner errors (`errors[]` empty). Long side: 2 breakout-confirmed longs (SNPS +4.1%, CRDO +12.9%) via `tv_breakout_up` + `tv_trending_up`; 12 score-2 longs on `tv_strong_buy` + `tv_trending_up`. Notable: CRDO highest single-day change (+12.94%) among all candidates. Short side dominated by `sector_laggard_decline` (18 of 26); 8 `stage4_momentum_breakdown`; 2 dual-confirmed shorts (BJ, CAE) hitting both `stage4_momentum_breakdown` + `bearish_episodic_pivot`. Zero tickers with congressional buys advanced to the candidate list. Capitol Trades returned 5 tickers with buys in the 30-day window; none qualified.

## Sector breadth

Sector labels not present in JSON. Breakdown by ticker identity:

**Longs (14)**

| Sector (inferred) | Tickers | Count |
|---|---|---|
| Pharma / Healthcare | LLY | 1 |
| Financials / Banking | BMO | 1 |
| Semiconductors / EDA | SNPS, NXPI, TSEM, CRDO | 4 |
| Energy / Midstream | TRGP, DTM | 2 |
| AI / Data Center Infra | NBIS | 1 |
| Industrials / Precision | NOVT | 1 |
| REITs | ESS | 1 |
| Hospitality | H | 1 |
| Biotech | ASND | 1 |
| Trucking / Transport | LSTR | 1 |

**Shorts (26)**

| Sector (inferred) | Tickers | Count |
|---|---|---|
| Consumer / Retail / Food | BJ, WING, PLNT, YSS, ERAS | 5 |
| Biotech / Pharma | SMMT, GKOS | 2 |
| Telecom | CHTR, TLK | 2 |
| Fintech / Software | INTU, KVYO, CAI, CHYM | 4 |
| Industrials | CAE, IBP, ESAB, PRIM | 4 |
| Insurance | PGR | 1 |
| Protein / Food Processing | JBS | 1 |
| Construction / Distribution | QXO, LBRDK | 2 |
| Tech / Other | AUGO, CAR, ATAT, MAIN, XNDU | 5 |

## Signal density

Hits across the 1,607-ticker universe (raw from diagnostic):

- `tv_strong_buy`: 400 hits (capped at config max)
- `tv_strong_sell`: 400 hits (capped at config max)
- `tv_overbought`: 400 hits (capped at config max)
- `tv_trending_down`: 295 hits
- `tv_trending_up`: 213 hits
- `tv_oversold`: 212 hits
- `tv_breakout_down`: 13 hits
- `tv_breakout_up`: 8 hits
- `capitol_buys` (30-day): 5 tickers with congressional purchases
- Total signal hits: 1,941 across 1,607 unique tickers
- Short setups added by setup-based screener: 50

Dropped before scoring: 478 below min price ($5), 151 below min volume (500k), 600 below min market cap ($1B), 0 missing metadata, 70 conflicted (mixed long/short signals), 165 long singletons + 129 short singletons below 2-reason threshold.

## Anomalies

1. **Three signal kinds hit the 400-count cap** (`tv_strong_buy`, `tv_strong_sell`, `tv_overbought`). True counts for all three unknown. `tv_overbought` capping at 400 while `tv_oversold` sits at 212 is an asymmetric read — more overbought names than oversold at the universe level, consistent with a rally tape.

2. **`tv_breakout_up` at 8 hits — thin.** Only 3 long candidates used a breakout signal (SNPS, CRDO, LSTR). With the long pipeline relying heavily on `tv_strong_buy` + `tv_trending_up` momentum, breakout confirmation is scarce.

3. **Semiconductor cluster on longs.** 4 of 14 longs (SNPS, NXPI, TSEM, CRDO) are semiconductors. CRDO's +12.94% same-day move warrants a check for earnings or catalyst before Stage 2 advances it — gap-and-go after a catalyst is a different setup risk than a clean breakout.

4. **`sector_laggard_decline` dominates shorts.** 18 of 26 shorts carry that single reason (score=1). Only 2 shorts (BJ, CAE) have dual confirmation. Low-conviction single-reason shorts should be treated as weak signals in Stage 2.

5. **Conflicted drops up.** 70 tickers dropped for mixed long/short signals, vs 40 in the prior run (20260519_211633). More cross-signal noise in the universe — market breadth is internally contradictory.

6. **Setup pattern history unavailable.** `wiki/meta/setup_patterns.md` has fewer than 5 closed trades with realized P&L. Cannot calibrate win rates for `stage4_momentum_breakdown`, `sector_laggard_decline`, or `bearish_episodic_pivot`.

## Last updated

20260526_023245 — 2026-05-25T19:32:48-07:00
