"""One-time idempotent cleanup of test-leaked rows in production Turso.

Background: tests/test_turso_client.py mocks get_connection() — a legacy code
path no longer used by tracker.turso_client. Every public function goes through
HTTP _execute/_insert_and_get_id calls instead. So the test's INSERTs land in
real Turso, leaving ghost trades on the live dashboard.

This script removes:
  - trades id=10 (run='run-3', NVDA)
  - trades id=11 (run='run-3', NVDA)
  - fills rows that reference trade_id IN (10, 11, 42) — all from the leaky
    test, all orphaned (trade_id=42 was never a real trade row).

Idempotent: each delete is gated by a sentinel check on the row's identity
(ticker == 'NVDA' AND run_id == 'run-3'). Will refuse to delete if a row's
identity does not match the expected leak signature.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv()

from tracker.turso_client import _execute


# Sentinel: only delete trade rows whose (run_id, ticker, entry_price) matches
# this exact signature. Refuses to delete anything else.
LEAK_SIGNATURE = {
    "run_id": "run-3",
    "ticker": "NVDA",
    "entry_price": 850.0,
}

# Trade rows expected to be leaked. The script verifies each row's signature
# matches LEAK_SIGNATURE before deleting.
EXPECTED_TRADE_IDS = [10, 11]

# Fill rows that reference trade_ids the leaky test wrote against. Includes
# trade_id=42 (which was hardcoded in the test's update_trade(42,...) and
# log_fill(42,...) calls, but no trade row id=42 ever existed in Turso).
LEAKED_TRADE_ID_REFERENCES_IN_FILLS = [10, 11, 42]


def _trade_signature(row: dict) -> dict:
    return {
        "run_id": row.get("run_id"),
        "ticker": row.get("ticker"),
        "entry_price": row.get("entry_price"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be deleted without actually deleting",
    )
    args = parser.parse_args()

    print(f"{'DRY-RUN: ' if args.dry_run else ''}Test-pollution cleanup for production Turso")
    print("=" * 70)

    deleted_trades = 0
    skipped_trades = 0

    for trade_id in EXPECTED_TRADE_IDS:
        rows = _execute("SELECT id, run_id, ticker, entry_price, status, quantity FROM trades WHERE id = ?", [trade_id])
        if not rows:
            print(f"\n[trades.id={trade_id}] not found — already cleaned, skipping")
            continue
        row = rows[0]
        sig = _trade_signature(row)
        if sig != LEAK_SIGNATURE:
            print(f"\n[trades.id={trade_id}] signature mismatch — refusing to delete")
            print(f"    found:    {sig}")
            print(f"    expected: {LEAK_SIGNATURE}")
            skipped_trades += 1
            continue
        print(f"\n[trades.id={trade_id}] {row['ticker']} run={row['run_id']!r} qty={row['quantity']} entry={row['entry_price']} status={row['status']}")
        if args.dry_run:
            print(f"  (dry-run) would DELETE FROM trades WHERE id = {trade_id}")
        else:
            _execute("DELETE FROM trades WHERE id = ?", [trade_id])
            print(f"  DELETED.")
        deleted_trades += 1

    print()
    print("-" * 70)
    print("Cleaning orphan/leaked rows from `fills` audit log...")
    deleted_fills = 0
    for tid in LEAKED_TRADE_ID_REFERENCES_IN_FILLS:
        # Show what we're about to delete first
        existing = _execute(
            "SELECT id, trade_id, event_type, price, bar_timestamp FROM fills WHERE trade_id = ?",
            [tid],
        )
        if not existing:
            print(f"\n[fills WHERE trade_id={tid}] none found, skipping")
            continue
        print(f"\n[fills WHERE trade_id={tid}] found {len(existing)} row(s):")
        for f in existing:
            print(f"    id={f['id']} type={f['event_type']} price={f['price']} ts={f.get('bar_timestamp')}")
        if args.dry_run:
            print(f"  (dry-run) would DELETE FROM fills WHERE trade_id = {tid}")
        else:
            _execute("DELETE FROM fills WHERE trade_id = ?", [tid])
            print(f"  DELETED {len(existing)} row(s).")
        deleted_fills += len(existing)

    print()
    print("=" * 70)
    print(
        f"Summary: {deleted_trades} trade row(s) "
        f"{'would be' if args.dry_run else ''} deleted, "
        f"{deleted_fills} fill row(s) {'would be' if args.dry_run else ''} deleted, "
        f"{skipped_trades} skipped on signature mismatch."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
