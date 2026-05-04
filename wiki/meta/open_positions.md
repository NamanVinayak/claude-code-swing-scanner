---
name: open positions snapshot
last_updated: 2026-05-03
last_run_id: bootstrap
target_words: 600
stale_after_days: 2
word_count: 0
summary: Structured ledger view of currently-open and pending swing trades. Refreshed nightly.
---

# Open Positions — Snapshot

Snapshot taken: _pending_. Refreshed nightly by Stage 4 (b_journal).

## Summary

- Open positions: 0
- Pending orders: 0
- Net long count: 0
- Net short count: 0
- Tickers held: _none_

## Open positions

_none_

## Pending orders

_none_

## Field definitions

- **Dir**: `long` or `short`.
- **Entry**: actual fill price for open positions; limit price for pending orders.
- **Current**: most recent traded price at snapshot time.
- **Days**: trading days between entry and snapshot (open positions only).
- **Unreal $/%**: unrealized P&L from entry to current price.
- **Run**: the run_id that originated this position.
