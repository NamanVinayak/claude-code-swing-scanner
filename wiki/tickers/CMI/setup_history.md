---
name: CMI setup history
ticker: CMI
last_updated: 2026-05-07
last_run_id: manual_correction_post_simulator_bugfix
target_words: 800
stale_after_days: 90
summary: Per-trade setup outcomes for CMI — one row per closed trade
---

# CMI — Setup History

| date | setup_type | screener_signals | watch_level | outcome | one-line lesson |
|---|---|---|---|---|---|
| 2026-05-06 | breakout_up | tv_strong_buy + tv_trending_up | $685.00 | EXPIRED no fill | catalyst priced in pre-decision; gap chased orders past entry zone |

## Notes

First decision (trade_id=8) on 2026-05-06 — breakout long on Q1 2026 beat-and-raise with record Power Systems quarter. **Order expired without filling.** The original simulator record showing a 9:30 ET fill at $689.69 was an artifact of the pre-2026-05-07 time-travel bug, corrected via `scripts/fix_pre_simulator_bug_trades.py`. Real-life: CMI gapped past the $684.06–$690.94 entry zone before the order existed in Turso (decision was made at 10:11 ET, low-of-day after that was $696.85), and never returned. Status now `expired`, no realized P&L.
