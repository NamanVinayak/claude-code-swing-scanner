"""CLI entry point for Stage 1 Sunset Scanner.

Usage:
    .venv/bin/python -m ai_hedge.runner.b_stage1 [--run-id <id>] [--max-candidates 40] [--no-capitol-trades]

Writes:
    runs/<run_id>/tomorrow_watchlist.json
    runs/<run_id>/scanner_diagnostic.json

Exit code 0 on success. Exit code 1 on hard failure (no candidates returned at all).
"""
import argparse
import logging
import sys

from ai_hedge.scanners.sunset_scanner import ScanConfig, run_sunset_scan, write_scan_outputs


def main():
    parser = argparse.ArgumentParser(description="Run Stage 1 Sunset Scanner for System B.")
    parser.add_argument("--run-id", default=None, help="Run ID (default: auto-generated timestamp)")
    parser.add_argument("--max-candidates", type=int, default=40)
    parser.add_argument("--min-reasons", type=int, default=2)
    parser.add_argument("--no-capitol-trades", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = ScanConfig(
        max_candidates=args.max_candidates,
        min_reasons_to_advance=args.min_reasons,
        capitol_trades_enabled=not args.no_capitol_trades,
    )

    result = run_sunset_scan(config, run_id=args.run_id)

    paths = write_scan_outputs(result)
    print(f"\nStage 1 Sunset Scanner complete:")
    print(f"  run_id:           {result.run_id}")
    print(f"  universe_size:    {result.universe_size}")
    print(f"  candidates:       {len(result.candidates)}")
    print(f"  elapsed:          {result.elapsed_seconds:.1f}s")
    print(f"  errors:           {len(result.errors)}")
    if result.errors:
        for e in result.errors:
            print(f"    - {e}")
    print(f"  outputs:")
    for label, path in paths.items():
        print(f"    {label:25} {path}")
    print()

    if not result.candidates:
        print("WARNING: No candidates returned. Possible causes: scanner sources down, filters too strict, or actual quiet day.")
        sys.exit(1)


if __name__ == "__main__":
    main()
