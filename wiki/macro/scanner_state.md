---
name: scanner state
last_updated: 2026-05-04
last_run_id: 20260504_141022
target_words: 500
stale_after_days: 3
word_count: 0
summary: current market breadth + signal density across the universe
---

# Scanner State

## TL;DR

500-ticker universe screened; 3 candidates advanced (SNDK, STX, PWR). No scanner errors. Dominant signal: `tv_trending_up` (25 in-universe hits). All 3 candidates qualified on exactly 2 reasons each (the minimum threshold). Candidate count is unusually low — normal runs typically surface 10–40 names. Pre-market reviewer (Stage 2) should treat this as a thin tape.

## Sector breadth

Sector data not available in this run. Candidate exchange breakdown:

| Ticker | Exchange | Last Close | Market Cap | Change % |
|---|---|---|---|---|
| SNDK | NASDAQ | $1,255.86 | $185.4B | +5.80% |
| STX | NASDAQ | $738.54 | $165.6B | +1.60% |
| PWR | NYSE | $757.34 | $113.6B | +2.04% |

All three are large-cap names (>$100B). Both SNDK and STX are storage/semiconductor hardware — the output is sector-concentrated in tech hardware even though sector labels are absent from the JSON.

## Signal density

Signal hits across the 500-ticker universe:

- `tv_trending_up`: 25 hits
- `tv_overbought`: 6 hits
- `tv_strong_sell`: 5 hits
- `tv_oversold`: 3 hits
- `tv_strong_buy`: 1 hit
- `tv_breakout_up`: 1 hit
- `tv_trending_down`: 0 hits
- `tv_breakout_down`: 0 hits
- `capitol_buys` (30-day): 24 tickers with congressional purchases

Skipped (not in universe): 272 tickers.

No candidate carries any `capitol_buys_30d` — the 24 congressional buy signals did not overlap with the 3 advancing candidates.

## Anomalies

1. **Extremely low candidate count.** Only 3 candidates from 500 tickers. Config requires `min_reasons_to_advance: 2`, `max_candidates: 40`. 3 is well below the expected 10–40 range. Either the market is showing unusually narrow momentum or the signal filters are catching very little today. Stage 2 should not be expected to narrow to 5–10 from 3 — it will pass through all 3 or fewer.

2. **SNDK +5.80% on the day.** Highest single-day move among candidates and the only `tv_breakout_up` hit in the universe. Worth flagging for gap-fade risk by pre-market.

3. **Macro regime context unavailable.** `wiki/macro/regime.md` is a bootstrap placeholder — no regime data is populated. Cannot cross-check signal mix against current risk posture.

4. **Setup pattern history unavailable.** `wiki/meta/setup_patterns.md` has no trade history yet (system went live 2026-05-04). Cannot assess win-rate risk for `tv_overbought` setups driving STX and PWR.

5. **272 skipped tickers** — more than half the nominal universe did not pass price/volume/market-cap filters. This reduces effective screening coverage.

## Last updated

20260504_141022 — 2026-05-04T14:10:26-07:00
