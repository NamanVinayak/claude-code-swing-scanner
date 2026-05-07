"""One-time idempotent correction for trades 7/8/9 affected by the
pre-2026-05-07 simulator time-travel bug.

Background: prior to commit <fix>, the simulator's `last_checked` floor for
freshly-inserted trades fell back to NY-midnight, so it filled orders against
1-minute bars from market open even when the trade was actually inserted
hours later. Three live paper trades were tainted:

  ROK (id=7, 2026-05-06): sim filled @ $445.27 at 9:30 ET (impossible).
       Real life: order existed at 10:11 ET; first bar that touched the entry
       zone was at 10:30 ET with low $446.93. So the trade WOULD have entered,
       just at $446.93 instead of $445.27.

  CMI (id=8, 2026-05-06): sim filled @ $689.69 at 9:30 ET (impossible).
       Real life: order existed at 10:11 ET; CMI never re-entered the entry
       zone after that. Position is fictional. Reset to status='expired'.

  TLN (id=9, 2026-05-07): sim filled @ $411.50 at 9:30 ET, then "stopped" at
       $397 for -$174. Both impossible — order existed at 10:10 ET; TLN was
       already at $391 by then and never returned to the entry zone.
       Reset to status='expired', clear the fake -$174 PnL.

Each correction writes an audit row to the `fills` table for traceability.

Idempotent: each correction is gated by a sentinel check on the row's current
state. If a row has already been corrected, the script skips it and prints
"already corrected, skipping". Safe to re-run.

Usage:
    .venv/bin/python scripts/fix_pre_simulator_bug_trades.py            # apply
    .venv/bin/python scripts/fix_pre_simulator_bug_trades.py --dry-run  # preview
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv()

from tracker.turso_client import _execute, log_fill, update_trade

# Each correction has:
#   trade_id: Turso row id
#   ticker: for sanity check (refuse to update if ticker mismatches)
#   sentinel: a (column, expected_old_value) tuple. If the row's current value
#             matches the expected_old_value, the correction has not been
#             applied yet. If it doesn't match, we assume already corrected.
#   set: dict of column -> new value to apply via update_trade()
#   fill_event: audit row appended to `fills` table for traceability

CORRECTIONS: list[dict[str, Any]] = [
    {
        "trade_id": 7,
        "ticker": "ROK",
        "sentinel": ("entered_at", "2026-05-06T13:30:00+00:00"),
        "set": {
            "entry_fill_price": 446.93,
            "entered_at": "2026-05-06T14:30:00+00:00",
        },
        "fill_event": {
            "event_type": "retroactive_correction_entry",
            "price": 446.93,
            "bar_timestamp": "2026-05-06T14:30:00+00:00",
            "reason": "pre-fix bug: original fill at 9:30 ET impossible (order created 10:11 ET); corrected to 10:30 ET first real touch",
        },
    },
    {
        "trade_id": 8,
        "ticker": "CMI",
        "sentinel": ("status", "entered"),
        "set": {
            "status": "expired",
            "entry_fill_price": None,
            "exit_fill_price": None,
            "pnl": None,
            "entered_at": None,
            "closed_at": "2026-05-06T20:00:00+00:00",  # 16:00 ET market close
        },
        "fill_event": {
            "event_type": "retroactive_correction_expired",
            "price": 0.0,  # log_fill requires non-null price; sentinel value
            "bar_timestamp": "2026-05-06T20:00:00+00:00",
            "reason": "pre-fix bug: never re-entered entry zone $684.06-$690.94 after order existed at 10:11 ET; CMI ran up to $715.54 close, no fill possible in real life",
        },
    },
    {
        "trade_id": 9,
        "ticker": "TLN",
        "sentinel": ("status", "stop_hit"),
        "set": {
            "status": "expired",
            "entry_fill_price": None,
            "exit_fill_price": None,
            "pnl": None,
            "entered_at": None,
            "closed_at": "2026-05-07T20:00:00+00:00",  # 16:00 ET market close
        },
        "fill_event": {
            "event_type": "retroactive_correction_expired",
            "price": 0.0,
            "bar_timestamp": "2026-05-07T20:00:00+00:00",
            "reason": "pre-fix bug: never re-entered entry zone $409.44-$413.56 after order existed at 10:10 ET; fake stop-out at $397 erased; -$174 PnL was fictional",
        },
    },
]


def _fetch_row(trade_id: int) -> dict[str, Any] | None:
    rows = _execute("SELECT * FROM trades WHERE id = ?", [trade_id])
    if not rows:
        return None
    return rows[0]


def _print_diff(label: str, before: dict[str, Any], after: dict[str, Any]) -> None:
    print(f"\n  {label}:")
    keys = sorted(set(before) | set(after))
    for k in keys:
        b = before.get(k)
        a = after.get(k)
        if b != a:
            print(f"    {k}: {b!r} -> {a!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without writing to Turso",
    )
    args = parser.parse_args()

    print(f"{'DRY-RUN: ' if args.dry_run else ''}Pre-simulator-bug correction for trades 7/8/9")
    print("=" * 70)

    applied = 0
    skipped = 0
    not_found = 0

    for correction in CORRECTIONS:
        trade_id = correction["trade_id"]
        ticker = correction["ticker"]
        sentinel_col, sentinel_val = correction["sentinel"]

        row = _fetch_row(trade_id)
        if row is None:
            print(f"\n[id={trade_id} {ticker}] NOT FOUND in trades table — skipping")
            not_found += 1
            continue

        if row.get("ticker") != ticker:
            print(
                f"\n[id={trade_id}] ticker mismatch: row says {row.get('ticker')!r}, "
                f"correction expects {ticker!r}. Refusing to update."
            )
            skipped += 1
            continue

        current = row.get(sentinel_col)
        if current != sentinel_val:
            print(
                f"\n[id={trade_id} {ticker}] already corrected "
                f"(sentinel {sentinel_col}={current!r} != expected old {sentinel_val!r}). Skipping."
            )
            skipped += 1
            continue

        # Build a preview of what will change
        new_state = {k: v for k, v in row.items()}
        new_state.update(correction["set"])
        _print_diff(f"[id={trade_id} {ticker}] BEFORE -> AFTER", row, new_state)

        if args.dry_run:
            print(f"  (dry-run) would call update_trade({trade_id}, ...) and log_fill(...)")
            applied += 1
            continue

        # Apply the correction
        update_trade(trade_id, **correction["set"])

        # Audit trail
        fe = correction["fill_event"]
        log_fill(
            trade_id=trade_id,
            event_type=fe["event_type"],
            price=fe["price"],
            bar_timestamp=fe["bar_timestamp"],
            reason=fe["reason"],
        )
        print(f"  APPLIED.")
        applied += 1

    print("\n" + "=" * 70)
    print(
        f"Summary: {applied} {'would apply' if args.dry_run else 'applied'}, "
        f"{skipped} skipped, {not_found} not found."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
