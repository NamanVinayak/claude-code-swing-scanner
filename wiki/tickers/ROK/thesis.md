---
name: ROK thesis
ticker: ROK
last_updated: 2026-05-18
last_run_id: 20260519_030755
target_words: 600
stale_after_days: 30
summary: Rockwell Automation — breakout long thesis entered 2026-05-06 on Q2 beat-and-raise catalyst; stopped out 2026-05-18 at $434.50 (-$136.73)
---

# ROK — Thesis

## TL;DR

Rockwell Automation (NYSE: ROK) is an industrial automation and information company. Entered long 2026-05-06 on a post-earnings breakout after a fiscal Q2 2026 beat-and-raise that produced a +10.72% gap on May 5. Thesis was momentum continuation on strong trend indicators and raised FY26 guidance. **CLOSED 2026-05-18**: stopped out at $434.50 after 12 days (expected 8), -$136.73. Overbought extension at entry (RSI_7=76.57, pct_b=1.2876) that bears flagged proved correct — post-earnings gap momentum faded without reaching target $469.

> **Correction note (2026-05-07)**: This page originally listed the entry as $445.27 from a 09:30 ET fill. That fill was an artifact of the pre-2026-05-07 simulator time-travel bug — the order was actually placed at 10:11 ET. Real-life first touch of the entry zone after the order existed was at 10:30 ET with low $446.93. Entry price corrected to **$446.93** / `entered_at = 2026-05-06T14:30:00Z` via `scripts/fix_pre_simulator_bug_trades.py`. Trade remains open.

## Entry thesis (2026-05-06, trade_id=7)

- **Setup**: breakout_up. TradingView trifecta (tv_strong_buy + tv_breakout_up + tv_trending_up). Entered at **$446.93** at 10:30 ET — first bar where price touched the entry zone after the order was live (watch level $443.50).
- **Catalyst**: Fiscal Q2 2026 beat — adjusted EPS reported vs consensus, margin expansion, higher volumes. Management raised FY26 adjusted EPS guide to $12.50–$13.10 and lifted organic/reported sales growth ranges citing warehouse automation, data center, and semiconductor demand. Stock gapped +10.72% on May 5.
- **Technicals at entry**: daily ADX_14 = 40.67 (+DI 37.78 vs -DI 11.65, strong trend), MACD bullish crossover (histogram +0.99), ema_aligned_uptrend = true, relative_volume = 2.54 on the gap day. RSI_7 = 76.57 (elevated but not disqualifying given catalyst strength).
- **Stop**: $434.50 (below gap-day close $435.93 — gap-fill failure level).
- **Target 1 / Target 2**: $469.00 / $481.00 (Target 1 is conservative vs fib_ext_1272 = $483.81).
- **Expected holding period**: 8 trading days.
- **Conviction**: 7/10. Bull/bear balance: all 4 perspectives echo long; catalyst bulls (bull_b=8) offset overbought concerns raised by bears.
- **Size class**: small_scaled (11 shares). High-priced name on $25k account — full Gate-3 qty of 24 shares would exceed 15% single-position cap; scaled to 11 shares using 20% extended cap, using 45% of risk budget.
- **Risk**: $112.75 (0.45% of account).

## Bear risks to monitor

- RSI_7 = 76.57, bollinger pct_b = 1.2876, z_score_50 = 2.19 — overbought extension. A pullback to fill part of the gap is possible.
- Truist Financial cut ROK stake by 24.5% in Q4 13F — institutional distribution noted but older than the Q2 catalyst.
- Earnings next in ~92 days — no near-term event risk.

## What falsified the prior thesis

**2026-05-18 — stop hit at $434.50, trade_id=7, -$136.73:**
The momentum continuation thesis was falsified by the overbought extension risk that bear_a identified at entry (RSI_7=76.57, bollinger pct_b=1.2876, z_score_50=2.19). The post-Q2-earnings gap momentum did not sustain through the 8-day expected holding window. Price drifted lower over 12 days and eventually closed below the gap-day low ($435.93), triggering the stop at $434.50. The bear concern that RSI extension and high z_score would lead to mean-reversion proved correct, even though the fundamental catalyst (beat-and-raise) was real. Lesson: strong earnings catalyst alone does not overcome stretched technicals at entry on a high-momentum name; wait for RSI to cool below 65 or for a pullback to the 20-day EMA before entering post-earnings breakouts.

## Open questions

- Is ROK's industrial automation demand cycle (warehouse, data center, semiconductor) durable, or was the Q2 beat a one-quarter catch-up?
- Would a re-entry make sense if RSI cools and price retests the gap-fill zone ($440–$445)?
