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
    parser.add_argument(
        "--merge-news",
        action="store_true",
        help="Merge news researcher outputs into bull/bear facts files. "
             "Run AFTER Step 1.5 (news researchers) and BEFORE Step 2 (bull/bear dispatch). "
             "Added for Fix 4 — news researcher merge.",
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

    if args.merge_news:
        # -------------------------------------------------------------------
        # Merge-news mode: pull runs/<id>/news/<TICKER>.json into bull/bear
        # facts bundles. Added for Fix 4 — news researcher merge.
        # -------------------------------------------------------------------
        from ai_hedge.scanners.adversarial_facts_builder import (
            merge_news_into_perspective_facts,
        )

        try:
            result = merge_news_into_perspective_facts(run_id, runs_dir=runs_dir)
        except Exception as exc:
            print(f"ERROR: merge_news_into_perspective_facts failed: {exc}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)

        print(f"\nStage 3 news merge complete:")
        print(f"  run_id:                  {run_id}")
        print(f"  tickers merged:          {len(result.get('tickers_merged', []))}")
        print(f"  tickers w/o news file:   {len(result.get('tickers_no_news_file', []))}")
        for t, info in result.get("per_ticker", {}).items():
            print(f"  {t:>6}: finnhub={info.get('finnhub_count', 0)} web={info.get('web_count', 0)} merged={info.get('merged_count', 0)} source={info.get('news_source', '?')}")
        return

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

        # Resolve the run_id we will actually operate on. The orchestrator
        # passes a tentative (now-)id; if no today_watchlist.json exists for
        # that id, fall back to the latest run dir that does. This keeps
        # Stage 3 output co-located with the Stage 2 run that produced the
        # watchlist and avoids creating empty phantom run directories.
        runs_root = Path(runs_dir)
        passed_path = runs_root / run_id / "today_watchlist.json"
        if passed_path.exists():
            resolved_run_id = run_id
        else:
            candidates = sorted(
                (
                    p for p in runs_root.iterdir()
                    if p.is_dir() and (p / "today_watchlist.json").exists()
                ),
                key=lambda p: p.name,
                reverse=True,
            )
            if not candidates:
                print(
                    "ERROR: no run directory contains today_watchlist.json; "
                    "Stage 2 must produce a watchlist before Stage 3 can run.",
                    file=sys.stderr,
                )
                sys.exit(1)
            resolved_run_id = candidates[0].name
            logger.info(
                "Tentative run_id %s has no today_watchlist.json; using latest Stage 2 run %s",
                run_id, resolved_run_id,
            )

        # Write the sentinel BEFORE any other side effects so the orchestrator
        # can read the resolved id even if a later step fails.
        runs_root.mkdir(parents=True, exist_ok=True)
        (runs_root / ".last_resolved_run_id").write_text(resolved_run_id)

        run_id = resolved_run_id

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
