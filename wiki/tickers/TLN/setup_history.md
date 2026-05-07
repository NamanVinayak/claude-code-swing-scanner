---
name: TLN setup history
ticker: TLN
last_updated: 2026-05-07
last_run_id: 20260507_213926
target_words: 800
stale_after_days: 90
summary: Per-trade setup outcomes for TLN — one row per closed trade
---

# TLN — Setup History

| date | setup_type | screener_signals | watch_level | outcome | one-line lesson |
|---|---|---|---|---|---|
| 2026-05-07 | breakout_up | tv_strong_buy + tv_trending_up + tv_breakout_up | $411.50 | EXPIRED no fill | order placed 10:10 ET after TLN crashed below $409; hourly cooling (roc_5d=-3.5%) and 20.1% overextension were real bear signals that intraday momentum was exhausted |

## Notes

First decision (trade_id=9) on 2026-05-07 — breakout long on Q1 2026 EBITDA beat ($473M), MS PT $498, and PJM capacity revenue lock ($1.07B). **Order expired without filling.** Same structural pattern as CMI (trade_id=8, 2026-05-06): b_decide_open fires at 10:00 ET, order insertion takes additional minutes, and by 10:10 ET TLN had already crashed from the breakout high to ~$391 — well below the $409.44 entry band. Never recovered. Gate 7 (`entry_valid_until`) added 2026-05-07 should prevent recurrence by forcing tight expiry windows on gap/breakout setups. No realized P&L.
