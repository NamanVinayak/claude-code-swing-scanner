---
name: CMI thesis
ticker: CMI
last_updated: 2026-05-07
last_run_id: manual_correction_post_simulator_bugfix
target_words: 600
stale_after_days: 30
summary: Cummins — Q1 beat-and-raise breakout thesis from 2026-05-06; entry order expired without filling (price gapped above the entry zone post-decision and never returned)
---

# CMI — Thesis

## TL;DR

Cummins Inc. (NYSE: CMI) is a global manufacturer of diesel/natural gas engines, filtration, and power solutions. **Entry order placed 2026-05-06 expired without filling** — CMI gapped through the entry zone at the open and never returned to it once the order was live. Thesis is preserved here for re-use if the setup re-presents.

> **Correction note (2026-05-07)**: This page originally claimed CMI was entered long at $689.69 on 2026-05-06. That "fill" was an artifact of the pre-2026-05-07 simulator time-travel bug — the order didn't exist in Turso until 10:11 ET, and yfinance 1-minute bars confirm CMI never re-entered the $684.06–$690.94 entry zone after that point (lowest post-decision price was $696.85; CMI ran up to a $715.54 close). Status corrected from `entered` to `expired` via `scripts/fix_pre_simulator_bug_trades.py`. No real fill ever occurred.

## Entry thesis (2026-05-06, trade_id=8) — EXPIRED, NO FILL

- **Setup**: breakout_up. TradingView signals: tv_strong_buy + tv_trending_up. Watch level $685.00 (entry midpoint $687.50, tolerance band $684.06–$690.94).
- **What actually happened**: order was placed at 10:11 ET on 2026-05-06. By that time CMI had already gapped through the entry zone and was trading at ~$697. It never came back into the band — closed the day at $715.54. Order expired at end-of-session without filling.
- **Catalyst (still valid for the thesis itself)**: Q1 2026 revenue $8.4B (+3% YoY), beat on adjusted EPS, record Power Systems quarter driven by data-center backup-power demand. Management raised FY26 guidance (revenue growth 8–11%, adjusted EPS $6.15). Returned $519M to shareholders. Truist raised PT to $730.
- **Technicals at decision time**: daily ADX_14 = 45.36 (+DI 37.31 vs -DI 4.58, very strong trend), MACD bullish (line 24.44 > signal 23.14, histogram +1.30), ema_aligned_uptrend = true, relative_volume = 1.8 with OBV trending up (no divergence). RSI_14 = 75.21 (elevated).
- **Stop (planned, never armed)**: $672.00.
- **Target 1 / Target 2 (planned)**: $722.00 / $738.00.
- **Conviction at decision**: 6/10. Technical bull (7) + catalyst bull (8) outweigh bears (7 tech, 6 fundamental). Combined p_bull = 0.5357. Expected return per share = +$11.28.
- **Size class (planned)**: small_scaled (7 shares).
- **Realized P&L**: $0. Order never filled.

## Lesson for the system, not for the trade

The 2026-05-06 b_decide_open routine fired at 7:00 AM PT (= 10:00 AM ET, 30 minutes after market open). The catalyst was already priced in by the time the order went live — CMI gapped above the entry zone before the agent could place it. This is a structural mismatch between the schedule and the setup type: post-earnings gap-and-go breakouts can't be chased 30+ minutes after the open. Either fire decide_open earlier (premarket data only), or have the judge set tighter `entry_valid_until` windows (now possible via Gate 7 added 2026-05-07) that cancel the order if not filled within 5–15 minutes.

## Bear risks (still on the watchlist)

- RSI_14 = 75.21, z_score_50 = 1.9, hourly bollinger pct_b = 1.2827 — overbought extension.
- Insider selling flagged in early May 2026 articles — softer EPS trajectory noted alongside higher sales.
- Premarket conviction at decision was only 5 (zero premarket volume on setup day); open-range confirmation was supposedly required, but the simulator bypassed that requirement by retroactively filling at 9:30 ET.

## What falsified the prior thesis

_No prior thesis to falsify — first decision for this ticker._

## Open questions

- If CMI re-presents the setup (pullback into $685–$695, then re-break of $700), is the thesis still valid given the original entry was missed?
- Does data-center Power Systems demand sustain into Q2 2026 or was this a one-quarter surge?
- Insider selling: is it routine trimming post-run or a forward-looking signal from management?
