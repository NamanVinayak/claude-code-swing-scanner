---
name: setup patterns
last_updated: 2026-06-10
last_run_id: 20260610_214001
target_words: 400
stale_after_days: 30
word_count: 0
summary: empirical win rate per setup type, last 30/90 days
---

# Setup Patterns

## TL;DR

Breakout is the dominant setup by trade count (4/6 last 30d, 7/9 last 90d) but win rate is weak (25% / 14.3%) and 90d total P&L is negative (-$198.61), driven by three `expired` trades with no realized P&L plus three stop-outs on extended/overbought names (LAMR, ROK, FSLY). The single breakout win (AVGO, +$293.26) was a clean target_hit. breakdown and gap_and_go each have one sample (both expired, $0) — too few to draw conclusions.

## Last 30 days

| setup_type | trades | wins | win_rate | avg_pnl | total_pnl |
|---|---|---|---|---|---|
| breakout | 4 | 1 | 25.0% | $8.17 | $32.69 |
| breakdown | 1 | 0 | 0.0% | $0.00 | $0.00 |
| gap_and_go | 1 | 0 | 0.0% | $0.00 | $0.00 |

## Last 90 days

| setup_type | trades | wins | win_rate | avg_pnl | total_pnl |
|---|---|---|---|---|---|
| breakout | 7 | 1 | 14.3% | -$28.37 | -$198.61 |
| breakdown | 1 | 0 | 0.0% | $0.00 | $0.00 |
| gap_and_go | 1 | 0 | 0.0% | $0.00 | $0.00 |

## Notes

Last 30 days produced 6 resolved trades: AVGO breakout target_hit +$293.26 (the only win, clean expected-return setup that hit target_2 in 4 days), LAMR breakout stop_hit -$123.84, ROK breakout stop_hit -$136.73, CPAY breakout expired $0, ALAB gap_and_go expired $0, SYM breakdown expired $0. Last 90 days adds 3 more: FSLY short breakout stop_hit -$231.30 (same-day reversal), TLN breakout expired $0, CMI breakout expired $0 — all pre-Gate-7. Net 90d realized P&L across all setups is -$198.61, carried entirely by the breakout bucket (6 stop_hits/expireds vs 1 win). The 5 expireds across all setups (CPAY, ALAB, SYM, TLN, CMI) are structural failures (late order placement relative to entry_valid_until window) rather than thesis failures — Gate 7 (entry_valid_until) addresses this going forward. The 3 stop_hits with realized losses (LAMR, ROK, FSLY) all involved extended/overbought entries (ROK RSI_7=76.57 at entry, FSLY relative_volume=3.44 same-day reversal, LAMR rsi_divergence.bearish=true) — pattern signal: breakout entries on names already extended (high RSI / z-score) are vulnerable to mean-reversion stop-outs or immediate reversal before reaching target. 1 open position: BSX short (breakdown, entered 2026-05-28, target $45.50/$43.12, stop $51.20).

## Last updated

2026-06-10
