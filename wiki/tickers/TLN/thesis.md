---
name: TLN thesis
ticker: TLN
last_updated: 2026-05-07
last_run_id: 20260507_213926
target_words: 600
stale_after_days: 30
summary: Talen Energy — post-Q1-beat breakout thesis from 2026-05-07; entry order expired without filling (order placed at 10:10 ET after TLN had already moved through the entry zone and crashed below it)
---

# TLN — Thesis

## TL;DR

Talen Energy (NASDAQ: TLN) is a power generation company with significant nuclear capacity and exposure to PJM capacity markets. **Entry order placed 2026-05-07 expired without filling** — order was inserted into Turso at ~10:10 ET, by which time TLN had already crashed to ~$391 (well below the $409.44 entry band lower bound). The stock never recovered to the entry zone before day-end. Thesis preserved here for re-use if the setup re-presents.

## Entry thesis (2026-05-07, trade_id=9) — EXPIRED, NO FILL

- **Setup**: breakout_up. TradingView signals: strong ADX trend + momentum signals. Watch level $411.50 entry midpoint; tolerance band approximately $409.44–$413.56.
- **What actually happened**: order was placed at ~10:10 ET on 2026-05-07. By that time TLN had already sold off sharply from the pre-decision high and was trading at ~$391 — well below the entry zone. It never recovered to the $409+ band before the 16:00 ET day-order expiry.
- **Catalyst (still valid for the thesis itself)**: Q1 2026 EBITDA $473M beat; Morgan Stanley price target $498; PJM 2027/2028 capacity auction revenue locked at $1.07B providing multi-year earnings visibility. Zero earnings risk for 92 days removes event-driven volatility.
- **Technicals at decision time**: daily ADX_14 = 27.55 (+DI 34.80 vs -DI 15.25, directional trend confirmed), MACD histogram +5.29, ema_aligned_uptrend = true, relative_volume = 1.74 on the breakout day, momentum roc_5d = +16.5%. Hourly indicators showed cooling: hourly roc_5d = -3.5%.
- **Extension risk (bears were right)**: bollinger pct_b = 1.0672 (outside upper band), z_score_50 = 2.75, dist_from_50sma_pct = 20.1% — bears flagged overextension and the hourly cooling was a real signal that intraday momentum was fading before the order was placed.
- **Stop (planned, never armed)**: $397.00.
- **Target (planned)**: $442.00.
- **Conviction at decision**: 7/10. Combined p_bull = 0.5550 (bull_a=7 vs bear_a=6; bull_b=8 vs bear_b=6). Expected return per share = +$10.48. Bears' extension argument was real but judged overridden by catalyst stack.
- **Size class (planned)**: small_scaled (12 shares). High-priced name — Gate-3 qty 17 shares would exceed 15% cap; scaled to 12 shares, using 70% of risk budget, notional $4,938 (19.75% extended cap).
- **Realized P&L**: $0. Order never filled.

## Lesson for the system

The structural issue is the same as CMI (2026-05-06): the b_decide_open routine fires at 7:00 AM PT (10:00 AM ET), 30 minutes after the open, and order insertion into Turso takes additional minutes. High-momentum post-catalyst names can gap, reverse, or crater well before the order goes live. Gate 7 (`entry_valid_until`) — added 2026-05-07 — should force judges to set tight expiry windows (e.g., 15–30 minutes from decision time) on gap-continuation setups where hourly momentum is already cooling. If TLN had an `entry_valid_until` of 10:25 ET, the order would have been expired cleanly before the intraday crash rather than sitting as a pending limit through the day.

## Bear risks (still on the watchlist)

- Heavy extension from 50-day SMA (20.1%) — mean-reversion risk on any macro risk-off day.
- Hourly RSI cooling (roc_5d = -3.5%) suggested breakout momentum was fading intraday.
- Talen is a mid-cap power generator with concentrated nuclear assets — regulatory and capacity-market policy risk.

## What falsified the prior thesis

_No prior thesis to falsify — first decision for this ticker._

## Open questions

- If TLN pulls back to the $390–$400 zone (closer to the 20-day or 50-day SMA), does the catalyst stack (PJM revenue lock, Q1 beat) still justify a re-entry on a lower-risk base formation?
- Does the MS $498 PT imply enough upside from a retest entry ($390–$400) to meet the 2:1 reward/risk threshold?
- Is the PJM 2027/2028 capacity revenue truly locked, or is it subject to regulatory revision?
