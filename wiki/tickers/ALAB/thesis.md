---
name: ALAB thesis
ticker: ALAB
last_updated: 2026-05-20
last_run_id: 20260520_233859
target_words: 600
stale_after_days: 30
summary: Astera Labs — gap_and_go long thesis entered 2026-05-20 on analyst PT upgrades (RBC $250, Evercore $297); expired unfilled at 16:00 ET
---

# ALAB — Thesis

## TL;DR

Astera Labs (NASDAQ: ALAB) is a semiconductor connectivity solutions company serving AI infrastructure (PCIe, CXL, and Ethernet connectivity for hyperscaler data centers). On 2026-05-19 the stock gapped +13.14% on dual analyst price-target upgrades (RBC raised PT to $250; Evercore raised PT to $297). System B initiated a gap_and_go long on 2026-05-20 with a limit entry at $256. **EXPIRED unfilled 2026-05-20**: the limit order never filled before the Gate 7 expiry at 16:00 ET. This is a structural timing outcome — price did not prove the bears right; the trade simply never got a fill.

## Entry thesis (2026-05-20, trade_id=25)

- **Setup**: gap_and_go. Price gapped +13.14% on 2026-05-19 with daily relative_volume=1.59 and hourly relative_volume=2.21 confirming institutional participation. Limit buy set at $256 for continuation into the gap.
- **Catalyst**: RBC raised price target to $250 and Evercore raised price target to $297 on 2026-05-19 — dual sell-side upgrades the same day driving the gap. Analyst distribution at decision time: 16 Buy / 7 Hold / 0 Sell. No near-term earnings risk (days_until_next=76).
- **Technicals at decision time**: daily ADX_14=44.63 (plus_di=30.77 vs minus_di=4.39, strong uptrend); MACD bullish_crossover=true; ema_aligned_uptrend on both daily and hourly timeframes. Bears flagged extension: RSI_7=76.3, z_score_50=1.89, bollinger pct_b=1.0918.
- **Stop**: $248 (below the gap-day open / prior-resistance level).
- **Target**: $278.
- **Expected holding period**: 6 trading days.
- **Conviction**: 6/10. Slight bull edge: b_bull_b=8, b_bull_a=7 vs b_bear_a=7, b_bear_b=7; p_bull=0.5167.
- **Size class**: small_scaled (19 shares). Gate-3 qty=31 would produce notional $7,936 exceeding the 15% cap ($3,750); scaled to M=floor(5000/256)=19 shares, risk_M=$152, notional=$4,864 within the 20% extended cap. Uses 61% of risk budget.
- **Risk**: $152 (0.61% of account).

## Bear risks monitored

- Extension at entry: z_score_50=1.89 and bollinger pct_b=1.0918 — ALAB was already stretched above its 50-day band the day after the gap. A gap-and-go setup on an already-extended name requires the continuation momentum to be immediate.
- RSI_7=76.3 — overbought on the short-term oscillator, same pattern flagged in prior TLN and ROK trades.
- Gap fade risk: if the +13.14% move attracted profit-taking sellers on day 2, the $256 limit zone may never see a revisit.

## What falsified the prior thesis

**2026-05-20 — EXPIRED, trade_id=25, $0 P&L:**

The limit order at $256 was set for a gap_and_go continuation entry on the day after ALAB's +13.14% catalyst gap. The order never filled before the Gate 7 expiry at 16:00 ET. This is NOT a thesis failure — price did not reach the stop, and the bears' extension argument was not confirmed by a directional reversal. The most likely structural cause: b_decide ran at approximately 3:39 PM ET (12:39 PM PT), leaving less than 25 minutes of trading before the market close. Even if ALAB pulled back intraday toward $256, the window was too narrow for a limit fill. The gap_and_go setup did not offer a limit-fill opportunity before expiry, likely because the prior-day gap held most of its gains into close. This is the same structural timing problem as TLN (trade_id=9) — Gate 7 entry_valid_until is the right guardrail, but the underlying issue is that b_decide running at 12:39 PM PT leaves same-day gap_and_go setups with almost no fill window.

## Open questions

- Is ALAB's AI infrastructure demand thesis (PCIe/CXL connectivity for hyperscalers) still intact? The dual analyst upgrade suggests yes — RBC and Evercore both see meaningful upside above the 2026-05-19 close.
- Worth re-evaluating if price pulls back to a better technical entry (e.g., 20-day EMA or below RSI 65) in the next 1–2 weeks, as the fundamental thesis has not been falsified.
- Structural question: should gap_and_go setups be excluded from b_decide_power (11:30 AM PT / 2:30 PM ET) since the fill window is too tight? Or should the entry limit be set wider to increase fill probability on continuation gaps?
