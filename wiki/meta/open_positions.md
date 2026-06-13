---
name: open positions snapshot
last_updated: 2026-06-13
last_run_id: 20260613_224659
target_words: 600
stale_after_days: 2
word_count: 0
summary: Structured ledger view of currently-open and pending swing trades. Refreshed nightly.
---

# Open Positions — Snapshot

Snapshot taken: `2026-06-13T15:53:12.091355-07:00`. Refreshed nightly by Stage 4 (b_journal).

## Summary

- Open positions: 1
- Pending orders: 0
- Net long count: 0
- Net short count: 1
- Tickers held: BSX

## Open positions

| Ticker | Dir | Qty | Entry | Current | Stop | Target | Days | Unreal $ | Unreal % | Run |
|---|---|---|---|---|---|---|---|---|---|---|
| BSX | short | 100 | 49.60 | 46.91 | 51.20 | 45.50 | 16 | +269.50 | +5.43% | 20260528_123903 |

## Pending orders

_none_

## Field definitions

- **Dir**: `long` or `short`.
- **Entry**: actual fill price for open positions; limit price for pending orders.
- **Current**: most recent traded price at snapshot time.
- **Days**: trading days between entry and snapshot (open positions only).
- **Unreal $/%**: unrealized P&L from entry to current price.
- **Run**: the run_id that originated this position.
