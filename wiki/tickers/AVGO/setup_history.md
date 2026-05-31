---
name: AVGO setup history
ticker: AVGO
last_updated: 2026-05-28
last_run_id: 20260528_213204
target_words: 800
stale_after_days: 90
summary: Per-trade setup outcomes for AVGO — one row per closed trade
---

# AVGO — Setup History

| date | setup_type | screener_signals | watch_level | outcome | one-line lesson |
|---|---|---|---|---|---|
| 2026-05-28 | breakout | tv_strong_buy + tv_trending_up | $422.50 | open (trade_id=29, entry $423.34, stop $413.50, target $440.50) | Position open; June 3 earnings binary within hold window flagged as primary risk — 7 AM judge rejected on this basis, 11:30 AM run approved; outcome pending. |

## Notes

First trade on AVGO (trade_id=29). Scanner flagged tv_strong_buy and tv_trending_up on 2026-05-28. The 7:00 AM b_decide run explicitly rejected AVGO on `earnings_binary_within_hold_window` (June 3 AC, days_until_next=6, expected_holding_days=5 means position sits 2 days before the binary). The 11:30 AM b_decide_power run approved at conviction=5. Position entered at $423.34 (10:12 ET). Daily trend was not confirmed at entry (ADX=11.56, MACD bearish, OBV down) — hourly-only strength with thin tape (hourly relative_volume=0.09). Primary risk remains the earnings binary: daily ATR=$16.51 vs stop band $9.84 means normal pre-earnings volatility can tag the stop before the print.
