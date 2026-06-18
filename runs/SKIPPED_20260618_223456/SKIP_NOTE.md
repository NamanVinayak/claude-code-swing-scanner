# b_decide SKIPPED — 2026-06-18 (power-hour fire)

Tentative run_id: 20260618_223456 (UTC)
Resolved run_id:  20260529_123901  (latest available today_watchlist.json — 20 DAYS OLD)

## Why skipped (fail-closed)

1. **Stale watchlist.** Today is 2026-06-18 PT. The most recent `today_watchlist.json`
   is from `20260529_123901` (2026-05-29) — 20 calendar days old. Stage 2
   (`b_premarket`) has not produced a fresh watchlist since then. The most recent
   `tomorrow_watchlist.json` (`20260610_211035`) was never promoted to a today's
   list either. Dispatching adversarial debate against month-old candidates would
   anchor decisions on dead setups; entry/stop levels are no longer meaningful.

2. **Malformed open_positions.md.** `compute_risk_budget()` raises on the BSX
   row in `wiki/meta/open_positions.md` line 27:
   `invalid literal for int() with base 10: '46.91'`. With the budget snapshot
   empty, the judge cannot compute available_risk_usd / deployed_pct and the
   writer's fail-closed budget gate would reject every approval anyway.

## Pattern continuity

Fourth consecutive b_decide skip with the same reasoning:
- f502c129  b_decide SKIPPED 2026-06-10 (stale watchlist + malformed open_positions)
- 292bf72c  b_decide SKIPPED 2026-06-10 (same)
- 1b5d5443  b_decide SKIPPED 2026-06-13 (stale watchlist 15d, fail-closed)
- (this one) b_decide SKIPPED 2026-06-18 (stale watchlist 20d, fail-closed)

The upstream fixes (revive b_premarket cadence; harden journal_writer table
emission for open_positions.md) belong outside this scheduled task.

## What was NOT done

- No news researchers dispatched.
- No bull/bear/judge agents dispatched.
- No decisions.json written. No Turso ingest will occur for this fire.
- No mutation to `wiki/` or `runs/20260529_123901/`.

## Smoke check (for the next investigator)

```
ls -t runs/*/today_watchlist.json | head -3
ls -t runs/*/tomorrow_watchlist.json | head -3
grep -n '^| ' wiki/meta/open_positions.md | head -5
.venv/bin/python -c "from ai_hedge.scanners.budget_calculator import compute_risk_budget; print(compute_risk_budget())"
```
