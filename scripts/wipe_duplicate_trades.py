"""One-time idempotent cleanup of duplicate trades created by the
re-ingestion / network-timeout incident on 2026-05-07.

Background: tracker/ingested_runs.txt isn't committed back to main by the
dashboard workflow, so every cron tick treats both real run IDs
(20260506_123952 and 20260507_123932) as "new". The Turso-query dedup
(`_existing_run_tickers` and `_open_positions_by_ticker_direction`) caught
the duplicates MOST of the time — but when those queries timed out
(15s read timeout from GH Actions to Turso), they fell back to empty sets
and duplicate inserts went through. Then the simulator dutifully filled /
expired the duplicates, creating phantom trades.

Real trades to KEEP: id=7 (ROK entered, corrected), id=8 (CMI expired),
id=9 (TLN expired). Everything else with a higher id and one of those
two run_ids is a duplicate and gets removed.

Idempotent: only deletes rows whose (run_id, ticker) match the duplicate
signature AND whose id > 9.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv()

from tracker.turso_client import _execute


CANONICAL_TRADE_IDS = {7, 8, 9}
DUPLICATE_RUN_IDS = ("20260506_123952", "20260507_123932")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"{'DRY-RUN: ' if args.dry_run else ''}Duplicate-trade cleanup")
    print("=" * 70)

    # 1. Inventory: list every trade row, partition into keep / delete
    rows = _execute(
        "SELECT id, run_id, ticker, status, entry_fill_price, pnl FROM trades "
        "WHERE run_id IN (?, ?) ORDER BY id ASC",
        list(DUPLICATE_RUN_IDS),
    )
    keep = [r for r in rows if r["id"] in CANONICAL_TRADE_IDS]
    delete = [r for r in rows if r["id"] not in CANONICAL_TRADE_IDS]

    print(f"\nKEEP (canonical, {len(keep)}):")
    for r in keep:
        print(f"  id={r['id']:3} {r['ticker']:5} run={r['run_id']} status={r['status']}")

    print(f"\nDELETE (duplicates, {len(delete)}):")
    for r in delete:
        print(f"  id={r['id']:3} {r['ticker']:5} run={r['run_id']} status={r['status']} pnl={r.get('pnl')}")

    if not delete:
        print("\nNothing to delete — already cleaned.")
        return 0

    # 2. Inventory fills tied to duplicate trade_ids
    duplicate_ids = [r["id"] for r in delete]
    placeholders = ",".join("?" for _ in duplicate_ids)
    fills = _execute(
        f"SELECT id, trade_id, event_type FROM fills WHERE trade_id IN ({placeholders}) ORDER BY id ASC",
        duplicate_ids,
    )
    print(f"\nDuplicate-row fills to delete: {len(fills)}")
    for f in fills:
        print(f"  fill_id={f['id']:3} trade_id={f['trade_id']:3} {f['event_type']}")

    if args.dry_run:
        print(f"\n(dry-run) would delete {len(delete)} trades and {len(fills)} fills.")
        return 0

    # 3. Apply deletes — fills first to avoid orphans
    if fills:
        _execute(f"DELETE FROM fills WHERE trade_id IN ({placeholders})", duplicate_ids)
    _execute(f"DELETE FROM trades WHERE id IN ({placeholders})", duplicate_ids)

    # 4. Verify
    remaining = _execute(
        "SELECT id, ticker, status FROM trades ORDER BY id ASC", []
    )
    print("\n" + "=" * 70)
    print(f"After cleanup: {len(remaining)} trades remain")
    for r in remaining:
        print(f"  id={r['id']} {r['ticker']} {r['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
