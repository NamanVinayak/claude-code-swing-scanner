---
name: budget state
last_updated: 2026-05-03
last_run_id: bootstrap
target_words: 800
stale_after_days: 2
word_count: 0
summary: live capital state and the rules that guard it
---

# Budget State

## TL;DR

Starting capital $25,000. No trades executed yet. System in scaling week 1–2 (half-size). All rules active.

## Rules (locked)

- Risk per trade max:       1.0% of account
- Total open risk cap:      4.0% of account
- Max simultaneous positions: 5
- Max % deployed:           60% (40% cash floor)
- Single-position cap:      15% of account
- Daily loss stop:          -2% account → pause for the day
- Weekly loss stop:         -5% account → system review
- Scaling: half-size weeks 1–2, three-quarter weeks 3–4, full from month 2
- Volatility: VIX > 25 → cut size 50%; VIX > 30 → no new entries

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

- Phase: scaling_week_1_2
- Size multiplier: 0.5

## Volatility regime

- VIX bucket: _pending (check at run time)_
- Size adjustment: none (default)

## Last updated

_pending_
