# b_decide ABORT 20260527_183946

Status: ABORTED — no agents dispatched, no decisions generated.

- approved: 0
- rejected: 0 (judge: 0, writer-budget: 0)
- fired at: Wed May 27, 2026 11:39 AM PT (scheduled decide_power)

Why aborted:
1. Stage 3 init resolved to runs/20260527_124910/ — this morning's b_premarket
   run, but today_watchlist.json is empty (0 candidates).
2. b_premarket aborted at 5:49 AM PT (cda21076) because Stage 1 watchlist
   was 34.3h stale. No fresh b_scan since Monday 2026-05-25 (Memorial Day
   Tuesday gap).
3. Earlier today: decide_open at 7:01 AM PT (217ca639) aborted for the
   same reason. This decide_power fire is the second abort of the day
   against the same stale watchlist.
4. Today's 2:00 PM PT b_scan should produce a fresh watchlist if Mac stays
   awake — that will unblock tomorrow's pipeline.

No Turso writes. No agent dispatches.
