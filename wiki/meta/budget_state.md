---
name: budget state
last_updated: 2026-05-05
last_run_id: bootstrap
target_words: 800
stale_after_days: 2
word_count: 0
summary: live capital state and the rules that guard it
---

# Budget State

## TL;DR

Starting capital $25,000. No trades executed yet. System operating under FULL framework (scaling phase skipped — paper-trading does not need dollar-loss protection). All capital rules active.

## Rules (locked)

- Risk per trade max:       1.0% of account
- Total open risk cap:      4.0% of account
- Max simultaneous positions: 5
- Max % deployed:           60% (40% cash floor)
- Single-position cap:      15% of account
- Daily loss stop:          -2% account → pause for the day
- Weekly loss stop:         -5% account → system review
- Scaling: SKIPPED for paper trading. Full size from day one. (Re-enable if/when transitioning to real money — toggle `Phase` below to `scaling_week_1_2`.)
- Volatility: VIX > 25 → cut size 50%; VIX > 30 → no new entries

### Position size classes

Gate 4 (single-position cap) has two outcome classes:

- **`standard`** — notional ≤ 15% of account at the Gate-3 quantity. Full risk-budget utilization. The default path; applies to most candidates.
- **`small_scaled`** — Gate-3 quantity would push notional past 15%, BUT a smaller quantity `M` exists where:
  - `M × entry_price ≤ 20% of account` (extended cap), AND
  - `M × risk_per_share ≥ 40% of risk_budget` (still uses meaningful risk)

  Judge downsizes `quantity` to `M`, sets `position_size_class = "small_scaled"`, and notes the scale-down in the rationale. Risk per trade is unchanged (≤ 0.5% × scaling multiplier of account); only notional concentration is bumped from 15% → up to 20%.

  Why this exists: high-priced names (e.g. $400+ stocks) on a $25k account run into discrete-share constraints — the minimum-viable share count at full risk budget exceeds the 15% notional cap before the position is otherwise meaningful. The 20% cap with a 40%-of-risk-budget floor unlocks these names without softening per-trade risk discipline.

If neither path fits (notional > 20% even at minimum-viable quantity), reject with `single_position_cap_exceeded`.

The 60%-deployment cap and 4%-total-open-risk cap still apply to all classes, so portfolio-level concentration remains bounded.

## Current account state

| field | value |
|---|---|
| Starting capital | $25,000 |
| Cash on hand | $25,000 |
| Deployed | $0 |
| Open risk | $0 (0.0% of account) |
| Positions open | 0 |

## Today's status

- Paused: no
- Daily P&L: $0
- Weekly P&L: $0

## Scaling phase

- Phase: full
- Size multiplier: 1.0

## Volatility regime

- VIX bucket: _pending (check at run time)_
- Size adjustment: none (default)

## Last updated

_pending_
