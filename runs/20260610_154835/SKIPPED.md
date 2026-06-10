# b_decide SKIPPED — 2026-06-10 15:48 UTC (scheduled decide_open fire, ~08:48 PT)

**Status:** Agent dispatch aborted. No `decisions.json` written. No Turso writes. No new trades.

This is the **second** skipped fire today. The earlier one (`runs/20260610_095140/SKIPPED.md`, committed `d65af912`) documented the same staleness condition for the morning decide_power slot. Nothing in the pipeline has changed since.

## Why

1. **Stale watchlist (primary).** The Stage 3 facts builder fell back to **run `20260529_123901`** (today_watchlist from 2026-05-29) because no fresher `today_watchlist.json` exists. That's 12 calendar days old.

2. **Malformed open_positions.md (secondary, new).** `risk_budget` could not be computed:

   ```
   Could not compute risk budget: open_positions.md: malformed row
   '| BSX | short | 100 | 49.60 | 48.96 | 51.20 | 45.50 | 13 | +64.50 | +1.30% | 20260528_123903 |':
   invalid literal for int() with base 10: '48.96'
   ```

   The current `wiki/meta/open_positions.md` header has an extra `Current` column that the parser doesn't expect. Schema drift between the journal writer and the budget reader. Even if the watchlist were fresh, `decisions_writer.py:171-173` (fail-CLOSED budget unavailability) would reject every approved trade with `reason: budget_unavailable: …`. Doubly safe to skip.

Running adversarial agents now would still:

1. Burn ~50 LLM dispatches on a watchlist built from 12-day-old TradingView signals.
2. Have bull/bear/judge cite entry/stop/target prices anchored to 2026-05-28 closes — prices that have no relationship to today's market.
3. Overwrite the existing 2026-05-31 `decisions.json`, re-triggering Turso ingest with a fresh `generated_at` and `decision_made_at = now`, causing the simulator to try to fill stale entry zones against today's bars.
4. Even if all trades cleared the judge, the writer would reject them all on `budget_unavailable` due to (2).

Fail-CLOSED per project pattern ([feedback_fail_closed_dedup](../../../.claude/projects/-Users-naman-Downloads-new-artist/memory/feedback_fail_closed_dedup.md)): when input data integrity is unverifiable, abort rather than push potentially harmful writes.

## Pipeline gap evidence

Last commits per stage (from `git log`):

| Stage | Last commit | Calendar gap as of 2026-06-10 |
|---|---|---|
| `b_scan` (tomorrow_watchlist) | 2026-05-28 21:14 | **13 days** |
| `b_premarket` (today_watchlist) | 2026-05-29 12:39 | **12 days** |
| `b_decide` (decisions.json) | 2026-05-31 (run 20260529_123901) | **10 days** |
| `b_journal` | 2026-06-07 09:50 | 3 days |
| `b_journal` ran today (uncommitted) | 2026-06-10 (created `runs/20260610_100024/`) | today |

Only `b_journal` has fired recently. `b_scan`, `b_premarket`, and `b_decide` have all been silent since late May. Same diagnosis as the morning skip: Mac was likely asleep during 5:30 AM and 11:30 AM PT windows for ~10 trading days; the 2:30 PM PT journal slot caught some afternoons.

## Live Turso state (unaffected)

- Currently entered: **BSX short, 100 shares @ $49.60** (from prior runs, since 2026-05-28).
- Dashboard remains accurate. This skip changes no live position.

## What's needed before the next `b_decide` can fire safely

In order:

1. **Fix `wiki/meta/open_positions.md`.** Either drop the `Current` column from the header/rows, or update the budget parser to accept it. Until this is fixed, every `b_decide` fire (even with a fresh watchlist) will be neutered by `budget_unavailable`. This is the higher-priority fix because it would silently zero out a real day's trades.
2. **`b_scan`** — produce a fresh `tomorrow_watchlist.json` against current market data.
3. **`b_premarket`** — narrow yesterday's `tomorrow_watchlist.json` to today's `today_watchlist.json`.
4. **`b_decide`** — only then can adversarial debate produce trades grounded in current prices, with a working budget computation.

If running manually today (Wed 2026-06-10), the user would: fix `open_positions.md`, then run `/b_scan` (mid-afternoon), then `/b_premarket` next morning, then `/b_decide` after that.

## Pipeline-hardening suggestions (still not done)

The earlier skip already proposed a staleness guard in `ai_hedge/runner/b_stage3.py` — restating here because it's still the right fix:

```python
# In b_stage3.py resolver, after picking the fallback run:
import datetime
ts_str = run_id.split("_")[0]
run_date = datetime.datetime.strptime(ts_str, "%Y%m%d").date()
days_old = (datetime.date.today() - run_date).days
if days_old > 1:
    sys.exit(f"FATAL: latest today_watchlist is {days_old} days old. Run b_scan and b_premarket first.")
```

Additional new suggestion from today's secondary issue: the `open_positions.md` parser should either be tolerant of unknown extra columns, or schema-validate on write so the journal writer and budget reader can't drift apart silently. A pydantic round-trip on the ledger rows would make this fail loud at write-time instead of at the next b_decide.

---
