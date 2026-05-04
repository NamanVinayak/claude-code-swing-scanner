"""CLI entry point for Stage 2 Pre-market Reviewer.

Usage:
    .venv/bin/python -m ai_hedge.runner.b_stage2 [--watchlist <path>] [--run-id <id>]
                                                 [--gap-pct 5.0] [--vol-floor 0.5]

Writes:
    runs/<run_id>/premarket_filtered.json
    runs/<run_id>/facts/b_premarket__<TICKER>.json   (one per survivor, with wiki_context injected)

Exit code:
    0 if at least 1 survivor
    2 if 0 survivors but no errors (genuine "no clean setups today")
    1 on hard failure (cannot read source watchlist, etc.)
"""
import argparse
import logging
import sys

from ai_hedge.scanners.premarket_reviewer import (
    PreMarketReviewResult,
    review_premarket,
    write_review_outputs,
)


def _print_summary_table(result: PreMarketReviewResult) -> None:
    """Print a summary table: ticker | kept | drop_reasons | gap% | vol_ratio."""
    header = f"{'ticker':<8} {'kept':<6} {'gap%':>7} {'vol_ratio':>10}  drop_reasons"
    print(header)
    print("-" * 70)
    for d in result.decisions:
        kept_str = "YES" if d.keep else "no"
        snap = d.snapshot
        gap_str = (
            f"{snap.overnight_gap_pct:+.2f}" if (snap and snap.overnight_gap_pct is not None) else "n/a"
        )
        vol_ratio_str = "n/a"
        if snap and snap.premarket_volume is not None and snap.avg_premarket_volume_10d:
            vol_ratio_str = f"{snap.premarket_volume / snap.avg_premarket_volume_10d:.2f}"
        reasons_str = ", ".join(d.drop_reasons) if d.drop_reasons else "—"
        print(f"{d.ticker:<8} {kept_str:<6} {gap_str:>7} {vol_ratio_str:>10}  {reasons_str}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage 2 Pre-market Reviewer for System B.")
    parser.add_argument(
        "--watchlist", default=None,
        help="Path to tomorrow_watchlist.json (default: auto-discover latest in runs/)",
    )
    parser.add_argument("--run-id", default=None, help="Run ID (default: auto-generated timestamp)")
    parser.add_argument("--gap-pct", type=float, default=5.0, help="Gap threshold percent (default: 5.0)")
    parser.add_argument("--vol-floor", type=float, default=0.5, help="Volume floor ratio (default: 0.5)")
    parser.add_argument("--earnings-hours", type=float, default=12.0,
                        help="Earnings recency window in hours (default: 12.0)")
    parser.add_argument("--max-age-hours", type=float, default=24.0,
                        help="Max age of Stage 1 watchlist in hours (default: 24.0)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        result = review_premarket(
            source_path=args.watchlist,
            run_id=args.run_id,
            gap_threshold_pct=args.gap_pct,
            volume_floor_ratio=args.vol_floor,
            earnings_recency_hours=args.earnings_hours,
            max_age_hours=args.max_age_hours,
        )
    except Exception as exc:
        print(f"ERROR: Stage 2 failed to start: {exc}", file=sys.stderr)
        sys.exit(1)

    if result.errors and result.candidates_in == 0:
        print(f"ERROR: Could not read Stage 1 watchlist. Errors:", file=sys.stderr)
        for e in result.errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    paths = write_review_outputs(result)

    print(f"\nStage 2 Pre-market Reviewer complete:")
    print(f"  run_id:             {result.run_id}")
    print(f"  source_run_id:      {result.source_run_id}")
    print(f"  candidates_in:      {result.candidates_in}")
    print(f"  survivors:          {len(result.survivors)}")
    print(f"  elapsed:            {result.elapsed_seconds:.1f}s")
    if result.errors:
        print(f"  errors:             {len(result.errors)}")
        for e in result.errors:
            print(f"    - {e}")
    print(f"  outputs:")
    for label, path in paths.items():
        print(f"    {label:30} {path}")
    print()

    print("Decision summary:")
    _print_summary_table(result)

    if result.survivors:
        print(f"Survivors ({len(result.survivors)}): {', '.join(result.survivors)}")
        sys.exit(0)
    else:
        print("No survivors — no clean setups today.")
        sys.exit(2)


if __name__ == "__main__":
    main()
