---
name: ROK thesis
ticker: ROK
last_updated: 2026-05-07
last_run_id: manual_correction_post_simulator_bugfix
target_words: 600
stale_after_days: 30
summary: Rockwell Automation — breakout long thesis entered 2026-05-06 on Q2 beat-and-raise catalyst
---

# ROK — Thesis

## TL;DR

Rockwell Automation (NYSE: ROK) is an industrial automation and information company. Entered long 2026-05-06 on a post-earnings breakout after a fiscal Q2 2026 beat-and-raise that produced a +10.72% gap on May 5. The thesis is momentum continuation: strong trend indicators, clear catalysts from raised FY26 guidance, and 92 days to next earnings removing near-term event risk.

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

_No prior thesis to falsify — first entry for this ticker._

## Open questions

- Will gap-day momentum extend above $450 in first 2–3 sessions, or does RSI exhaustion trigger a retest of $435–$440?
- Data center / warehouse automation cycle: is this a one-quarter beat or durable demand re-rating?
