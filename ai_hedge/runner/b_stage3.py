"""CLI entry point for Stage 3 Adversarial Decision — facts-builder phase.

Usage:
    .venv/bin/python -m ai_hedge.runner.b_stage3 --run-id <id>
    .venv/bin/python -m ai_hedge.runner.b_stage3 --run-id <id> --finalize

Modes:
    Default: build all Stage 3 facts files (perspectives + judge) and inject wiki
             context. The orchestrator then dispatches the 4 perspective agents
             (parallel) per ticker and the judge agent (once per ticker); their
             outputs go to runs/<run_id>/agent_outputs/.

    --finalize: call decisions_writer.write_decisions(run_id) to produce
                decisions.json from the orchestrator's judge_output.json.

Exit codes:
    0  success
    2  today_watchlist.json is empty (no candidates to evaluate)
    1  hard failure (file missing, parse error, etc.)

The runner is idempotent in default mode: running it twice on the same run_id
rewrites the facts files with fresh wiki context.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Stage 3 Adversarial Decision facts builder for System B.",
    )
    parser.add_argument("--run-id", required=True, help="Run ID matching the Stage 2 output")
    parser.add_argument(
        "--finalize",
        action="store_true",
        help="Write decisions.json from judge_output.json (run after orchestrator dispatches judge)",
    )
    parser.add_argument("--runs-dir", default="runs", help="Root runs directory (default: runs)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger = logging.getLogger(__name__)
    run_id: str = args.run_id
    runs_dir: str = args.runs_dir

    if args.finalize:
        # -------------------------------------------------------------------
        # Finalize mode: convert judge_output.json → decisions.json
        # -------------------------------------------------------------------
        from ai_hedge.scanners.decisions_writer import write_decisions

        judge_output = Path(runs_dir) / run_id / "judge_output.json"
        if not judge_output.exists():
            print(
                f"ERROR: judge_output.json not found at {judge_output}. "
                "Run the orchestrator first to dispatch judge agents.",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            decisions_path = write_decisions(run_id, runs_dir=runs_dir)
        except Exception as exc:
            print(f"ERROR: Failed to write decisions.json: {exc}", file=sys.stderr)
            sys.exit(1)

        # Load and print summary
        decisions_data = json.loads(Path(decisions_path).read_text())
        approved = decisions_data.get("decisions", {})
        rejected = decisions_data.get("rejected", [])

        print(f"\nStage 3 finalize complete:")
        print(f"  run_id:            {run_id}")
        print(f"  decisions.json:    {decisions_path}")
        print(f"  approved trades:   {len(approved)}")
        print(f"  rejected:          {len(rejected)}")
        if approved:
            print(f"  tickers approved:  {', '.join(approved.keys())}")
        print()

    else:
        # -------------------------------------------------------------------
        # Default mode: build facts files + inject wiki context
        # -------------------------------------------------------------------
        from ai_hedge.scanners.adversarial_facts_builder import build_all_stage3_facts

        # Write metadata.json so ingest_decisions.py knows mode = b_swing
        run_dir = Path(runs_dir) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        meta_path = run_dir / "metadata.json"
        if not meta_path.exists():
            meta_path.write_text(json.dumps({
                "run_id": run_id,
                "mode": "b_swing",
                "stage": "stage3",
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }, indent=2))

        try:
            summary = build_all_stage3_facts(run_id, runs_dir=runs_dir)
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            print(f"ERROR: Stage 3 facts builder failed: {exc}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)

        tickers = summary.get("tickers", [])
        if not tickers:
            print("Stage 3: today_watchlist.json is empty — no candidates to evaluate.")
            sys.exit(2)

        print(f"\nStage 3 facts builder complete:")
        print(f"  run_id:                  {run_id}")
        print(f"  tickers:                 {', '.join(tickers)}")
        print(f"  perspective files:       {summary.get('perspective_files_written', 0)}")
        print(f"  judge files:             {summary.get('judge_files_written', 0)}")
        print(f"  facts_dir:               {summary.get('facts_dir', '')}")
        wiki = summary.get("wiki_injection", {})
        if wiki.get("skipped"):
            print(f"  wiki injection:          SKIPPED ({wiki.get('reason', '')})")
        else:
            print(f"  wiki injection:          {wiki.get('count', 0)} files updated")
        print()
        print("Next step: orchestrator dispatches 4 perspective agents per ticker (parallel),")
        print("then one judge agent per ticker. Run --finalize after judge outputs are ready.")
        print()


if __name__ == "__main__":
    main()
