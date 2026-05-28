---
name: scanner state
last_updated: 2026-05-27
last_run_id: 20260527_224037
target_words: 500
stale_after_days: 3
word_count: 0
summary: current market breadth + signal density across the universe
---

# Scanner State

## TL;DR

40 candidates from 1,603-ticker universe: 16 long, 24 short. No scanner errors (`errors[]` empty). Long side led by 3 triple-confirmed breakout names (UNP, MAR, HLT via `tv_strong_buy` + `tv_breakout_up` + `tv_trending_up`); remainder on `tv_strong_buy` + `tv_trending_up` or `tv_breakout_up` + `tv_trending_up`. Short side: 3 dual-confirmed episodic pivots (PDD -10.4%, BSX -12.5%, ZS -31.5%) carrying both `stage4_momentum_breakdown` + `bearish_episodic_pivot`; 20 shorts are single-reason `sector_laggard_decline` (score=1). Zero congressional buys advanced to the candidate list (4 total buys in 30-day window, none qualified).

## Sector breadth

Sector labels not present in JSON. Breakdown by ticker identity:

**Longs (16)**

| Sector (inferred) | Tickers | Count |
|---|---|---|
| Railroads / Transport | UNP, NSC, JBHT, XPO, FDX | 5 |
| Hospitality / Travel | MAR, HLT, H | 3 |
| Semiconductors / Tech | AVGO, TSM, VICR | 3 |
| Consumer / Auto | TSLA | 1 |
| Financial Data / Index | MSCI, CPAY | 2 |
| Specialty Materials | CRS | 1 |
| Industrials | MIDD | 1 |

**Shorts (24)**

| Sector (inferred) | Tickers | Count |
|---|---|---|
| China / E-commerce | PDD | 1 |
| Medical Devices | BSX, PODD | 2 |
| Cybersecurity / SaaS | ZS | 1 |
| Financials / Brokers | SCHW | 1 |
| Semiconductors | GFS | 1 |
| Biotech / Pharma | INSM, SMMT, ERAS | 3 |
| Fintech / MarTech | FUTU, KVYO, CAI | 3 |
| Industrials / Construction | PNR, IBP, PRIM, SITE, REZI, BWIN | 6 |
| Consumer / Apparel | ANF, PLNT, WAY | 3 |
| Other / Mixed | CHYM, GPGI, ORKA | 3 |

## Signal density

Hits across the 1,603-ticker universe (raw from diagnostic):

- `tv_strong_buy`: 400 hits (capped at config max)
- `tv_strong_sell`: 400 hits (capped at config max)
- `tv_overbought`: 400 hits (capped at config max)
- `tv_trending_down`: 286 hits
- `tv_trending_up`: 213 hits
- `tv_oversold`: 192 hits
- `tv_breakout_up`: 18 hits
- `tv_breakout_down`: 10 hits
- `capitol_buys` (30-day): 4 tickers with congressional purchases
- Total signal hits: 1,919 across 1,603 unique tickers
- Short setups added by setup-based screener: 47

Dropped before scoring: 501 below min price ($5), 161 below min volume (500k), 553 below min market cap ($1B), 0 missing metadata, 54 conflicted (mixed long/short signals), 160 long singletons + 158 short singletons below 2-reason threshold.

## Anomalies

1. **Three signal kinds hit the 400-count cap** (`tv_strong_buy`, `tv_strong_sell`, `tv_overbought`). True universe counts for all three are unknown. `tv_overbought` capping at 400 while `tv_oversold` sits at 192 — asymmetric overbought skew, consistent with a rally-side tape.

2. **Three large-cap shorts down sharply on the day.** ZS -31.5% ($126.41), BSX -12.5% ($50.46), PDD -10.4% ($86.61) all carry dual short setup flags. These are episodic-pivot setups; Stage 2 should verify whether the move is already exhausted before advancing.

3. **`tv_breakout_up` at 18 hits** — up from 8 in the prior run (20260526_023245). Three top longs carry the trifecta (score=3): UNP, MAR, HLT. Breakout confirmation is broader this scan.

4. **Transport / railroad cluster on longs.** UNP, NSC, JBHT, XPO, FDX — 5 of 16 longs from the same macro-sensitive sector. Stage 2 should check whether this is a sector rotation trade or a single catalyst driving the group.

5. **`sector_laggard_decline` dominates shorts.** 20 of 24 shorts carry that single reason (score=1). Low-conviction single-reason shorts; only 3 shorts have dual confirmation (PDD, BSX, ZS).

6. **Conflicted drops at 54** — down from 70 in the prior run (20260526_023245). Slightly less cross-signal noise.

7. **Setup pattern history unavailable.** `wiki/meta/setup_patterns.md` has fewer than 5 closed trades with realized P&L. Win rates for `stage4_momentum_breakdown`, `sector_laggard_decline`, and `bearish_episodic_pivot` cannot be calibrated from empirical data.

## Last updated

20260527_224037 — 2026-05-27T15:40:37-07:00
