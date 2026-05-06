---
name: scanner state
last_updated: 2026-05-06
last_run_id: 20260506_211026
target_words: 500
stale_after_days: 3
word_count: 0
summary: current market breadth + signal density across the universe
---

# Scanner State

## TL;DR

40 candidates from 1,529-ticker universe: 23 long, 17 short. No scanner errors. Long side dominated by `tv_trending_up` (present in all 23 longs) paired with either `tv_strong_buy` (13 longs) or `tv_breakout_up` (12 longs). Only 1 long scored 3 — TSM (+6.4%, triple: `tv_strong_buy` + `tv_breakout_up` + `tv_trending_up`). Short side: KVYO is sole score-3 short (all three setup types hit, -32.2%). Short-side populated for first time after setup-screener architecture introduced 2026-05-05. FTAI +16.9%, ARM +13.6%, GLW +12.0%, NBIS +10.9% are notable gap moves on the long side. PRIM -50.1%, KVYO -32.2%, NICE -22.5% on the short side — episodic pivot cluster. Capitol Trades: 5 tickers with congressional buys; only ASML advanced (Jared Moskowitz, 1 buy, score=2 long).

## Sector breadth

Sector labels inferred from ticker identity (not in JSON):

**Longs (23)**

| Sector | Tickers | Count |
|---|---|---|
| Semis / Semi Equip | TSM, ASML, LRCX, ADI, NBIS, MTSI, MKSI | 7 |
| Tech / Software / Networking | ARM, GLW, VRT, NET, CIEN, KEYS | 6 |
| Industrials | DE, UNP, ROK, DOV, RRX | 5 |
| Aero / Defense | FTAI, TLN | 2 |
| Financials | RY | 1 |
| Consumer / Entertainment | LYV | 1 |
| Healthcare | WST | 1 |

**Shorts (17)**

| Sector | Tickers | Count |
|---|---|---|
| Tech / Software | KVYO, NICE, ANET, VEEV, PTC, CHKP | 6 |
| Industrials | PRIM, CLH, J | 3 |
| Energy | DVN, CTRA | 2 |
| Consumer | CPNG | 1 |
| Healthcare | TECH | 1 |
| Financials | TSLX | 1 |
| Telecom / Space | VG, ASTS | 2 |
| Aero / Defense | KRMN | 1 |

Long side: semiconductors + tech concentration (13 of 23 candidates). Short side: tech/software breakdown dominant (6 of 17).

## Signal density

Hits across the 1,529-ticker universe:

- `tv_strong_buy`: 400 hits (capped at config max)
- `tv_strong_sell`: 400 hits (capped at config max)
- `tv_overbought`: 400 hits (capped at config max)
- `tv_trending_down`: 297 hits
- `tv_trending_up`: 242 hits
- `tv_oversold`: 172 hits
- `tv_breakout_up`: 47 hits
- `tv_breakout_down`: 25 hits
- `capitol_buys` (30-day): 5 tickers with congressional purchases
- Total signal hits: 1,983 across 1,529 unique tickers
- Short setups added (setup-based screener): 38

Dropped before scoring: 430 below min price ($5), 156 below min volume (500k), 518 below min market cap ($1B), 0 missing metadata, 70 conflicted (mixed long/short signals). 173 directional singletons long + 159 singletons short below 2-reason threshold.

## Anomalies

1. **Three signal kinds hit the 400-count cap** (`tv_strong_buy`, `tv_strong_sell`, `tv_overbought`). True universe-wide counts unknown — all three were cap-binding.

2. **Short-side now populated (38 setups, 17 candidates).** Prior runs returned 0 shorts. The setup-screener path (`stage4_momentum_breakdown`, `bearish_episodic_pivot`, `sector_laggard_decline`) is live and productive. 11 of 17 short candidates scored 1 — minimum threshold only. Pre-market reviewer should scrutinize score-1 shorts for setup quality.

3. **Four large single-day moves on long side.** FTAI +16.9%, ARM +13.6%, GLW +12.0%, NBIS +10.9% are all advancing. Pre-market reviewer should assess gap-fade risk vs. continuation for each.

4. **PRIM -50.1% is an outlier.** Advancing as short via `bearish_episodic_pivot` + `sector_laggard_decline`. Magnitude suggests news-driven gap rather than a clean setup — pre-market review should flag if gap has already exhausted short opportunity.

5. **Macro regime and setup pattern history unavailable.** Both `wiki/macro/regime.md` and `wiki/meta/setup_patterns.md` remain bootstrap placeholders. Cannot cross-check signal mix against regime or historical win rates.

## Last updated

20260506_211026 — 2026-05-06T14:10:26-07:00
