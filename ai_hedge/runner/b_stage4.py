"""CLI entry point for Stage 4 — End-of-Day Journal.

Two modes:

    Default (build facts):
        .venv/bin/python -m ai_hedge.runner.b_stage4 --run-id <id>
      → reads Turso, writes runs/<id>/journal_facts.json
        and runs/<id>/facts/b_journal__GLOBAL.json,
        runs wiki injection (b_journal manifest),
        prints a summary. Orchestrator then dispatches the b_journal LLM.

    Finalize (apply side effects):
        .venv/bin/python -m ai_hedge.runner.b_stage4 --run-id <id> --finalize
      → reads runs/<id>/journal_output.json (orchestrator-produced)
        and runs/<id>/journal_facts.json,
        applies all wiki side effects (lessons append, setup_patterns,
        open_positions, budget_state, ticker bootstrap),
        prints a summary.

Smoke / dry-run mode:
        .venv/bin/python -m ai_hedge.runner.b_stage4 --run-id <id> --smoke
      → uses tracker mock data when Turso isn't reachable; useful for
        verifying the pipeline end-to-end without hitting cloud DB.

Exit codes:
    0  success
    2  default mode succeeded but closed_today is empty AND no open positions
       (no journal entries to write — quiet day; orchestrator may skip dispatch)
    1  hard failure (file missing, parse error, Turso failure, etc.)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PT_TZ = ZoneInfo("America/Los_Angeles")


def _build_default_run_id() -> str:
    """Same shape as Stage 3 default run-id."""
    return f"b_journal_{datetime.now(PT_TZ).strftime('%Y%m%d_%H%M%S')}"


def _maybe_fetch_prices(tickers: list[str]) -> dict[str, float | None]:
    """Best-effort current-price fetch (yfinance). Failures degrade to None."""
    if not tickers:
        return {}
    try:
        from ai_hedge.data.api import get_current_price
    except ImportError:
        return {t: None for t in tickers}

    out: dict[str, float | None] = {}
    for t in tickers:
        try:
            out[t] = get_current_price(t)
        except Exception as exc:  # noqa: BLE001 — yfinance is flaky
            logging.warning("Could not fetch current price for %s: %s", t, exc)
            out[t] = None
    return out


def _write_metadata(run_dir: Path, run_id: str) -> None:
    meta_path = run_dir / "metadata.json"
    if meta_path.exists():
        return
    meta_path.write_text(json.dumps({
        "run_id": run_id,
        "mode": "b_swing",
        "stage": "stage4",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, indent=2))


def _run_default(args: argparse.Namespace) -> int:
    """Build the journal facts bundle, run wiki injection, print summary."""
    from ai_hedge.scanners.journal_facts_builder import (
        build_journal_facts,
        write_journal_facts,
    )
    from ai_hedge.wiki.inject import inject_context

    run_id: str = args.run_id or _build_default_run_id()
    run_dir = Path(args.runs_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_metadata(run_dir, run_id)

    today_pt = date.fromisoformat(args.date) if args.date else None

    overrides: dict[str, Any] = {}
    if args.smoke:
        overrides = _smoke_turso_overrides()

    try:
        facts = build_journal_facts(
            run_id,
            today_pt=today_pt,
            runs_dir=args.runs_dir,
            **overrides,
        )
    except Exception as exc:
        print(f"ERROR: Stage 4 facts build failed: {exc}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    paths = write_journal_facts(facts, runs_dir=args.runs_dir)

    inject_result = inject_context(run_id, ["GLOBAL"], mode="b_journal")

    print()
    print("Stage 4 facts builder complete:")
    print(f"  run_id:                  {run_id}")
    print(f"  journal_date_pt:         {facts.journal_date_pt}")
    print(f"  closed_today:            {len(facts.closed_today)}")
    print(f"  open_positions:          {len(facts.open_positions)}")
    print(f"  closed_last_30d:         {len(facts.closed_last_30d)}")
    print(f"  closed_last_90d:         {len(facts.closed_last_90d)}")
    print(f"  tickers_today:           {', '.join(facts.tickers_today) or '—'}")
    print(f"  new_tickers_today:       {', '.join(facts.new_tickers_today) or '—'}")
    print(f"  realized_pnl_today_usd:  ${facts.realized_pnl_today_usd:+,.2f}")
    print()
    print(f"  journal_facts.json:      {paths['journal_facts']}")
    print(f"  b_journal__GLOBAL.json:  {paths['global_facts']}")

    if inject_result.get("skipped"):
        print(f"  wiki injection:          SKIPPED ({inject_result.get('reason', '')})")
    else:
        print(f"  wiki injection:          {inject_result.get('count', 0)} files updated")
    print()

    if not facts.closed_today and not facts.open_positions:
        print("Quiet day: no closed trades and no open positions. Orchestrator may skip LLM dispatch.")
        return 2

    print("Next step: orchestrator dispatches b_journal LLM agent against journal_facts.json,")
    print("           writes runs/<run_id>/journal_output.json, then run --finalize.")
    print()
    return 0


def _run_finalize(args: argparse.Namespace) -> int:
    """Apply all wiki side effects from journal_output.json."""
    from ai_hedge.scanners.journal_facts_builder import JournalFacts
    from ai_hedge.scanners.journal_writer import apply_journal_writes

    run_id: str = args.run_id
    run_dir = Path(args.runs_dir) / run_id

    facts_path = run_dir / "journal_facts.json"
    if not facts_path.exists():
        print(f"ERROR: journal_facts.json not found at {facts_path}.", file=sys.stderr)
        print("       Run the default Stage 4 mode first.", file=sys.stderr)
        return 1

    output_path = run_dir / "journal_output.json"
    llm_output: dict[str, Any] | None = None
    if output_path.exists():
        try:
            llm_output = json.loads(output_path.read_text())
        except json.JSONDecodeError as exc:
            print(f"ERROR: journal_output.json is not valid JSON: {exc}", file=sys.stderr)
            return 1
    else:
        if not args.allow_no_llm:
            print(f"ERROR: journal_output.json missing at {output_path}.", file=sys.stderr)
            print("       Pass --allow-no-llm to apply with deterministic fallback bullets.", file=sys.stderr)
            return 1

    facts = _load_journal_facts(facts_path)

    today_pt = date.fromisoformat(args.date) if args.date else None
    today_pt = today_pt or datetime.now(PT_TZ).date()

    prices = _maybe_fetch_prices([p.ticker for p in facts.open_positions]) if not args.no_prices else {}

    try:
        summary = apply_journal_writes(
            facts=facts,
            llm_output=llm_output,
            current_prices=prices,
            starting_capital_usd=args.starting_capital,
            wiki_root=Path(args.wiki_root),
            today_pt=today_pt,
            last_run_id=run_id,
        )
    except Exception as exc:
        print(f"ERROR: apply_journal_writes failed: {exc}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    print()
    print("Stage 4 finalize complete:")
    print(f"  run_id:                       {run_id}")
    print(f"  llm_output_used:              {bool(llm_output)}")
    print(f"  new_tickers_bootstrapped:     {', '.join(summary.new_tickers_bootstrapped) or '—'}")
    print(f"  pages_bootstrapped:           {len(summary.pages_bootstrapped)}")
    print(f"  lessons_appended:             {summary.lessons_appended_ids}")
    print(f"  lessons_skipped (already in): {summary.lessons_skipped_ids}")
    print(f"  setup_patterns_refreshed:     {summary.setup_patterns_refreshed}")
    print(f"  open_positions_refreshed:     {summary.open_positions_refreshed}")
    print(f"  budget_state_refreshed:       {summary.budget_state_refreshed}")
    print(f"  paths_written:")
    for p in summary.paths_written:
        print(f"    - {p}")
    print()
    return 0


def _load_journal_facts(path: Path):
    """Re-hydrate JournalFacts dataclasses from journal_facts.json on disk."""
    from ai_hedge.scanners.journal_facts_builder import (
        ClosedTrade, OpenTrade, JournalFacts,
    )

    raw = json.loads(path.read_text())

    def _ct(d: dict) -> ClosedTrade:
        return ClosedTrade(
            trade_id=int(d.get("trade_id", 0)),
            ticker=str(d.get("ticker", "")),
            direction=str(d.get("direction", "")),
            setup_type=str(d.get("setup_type", "unknown")),
            quantity=int(d.get("quantity", 0)),
            entry_price=d.get("entry_price"),
            exit_price=d.get("exit_price"),
            stop_loss=d.get("stop_loss"),
            target_price=d.get("target_price"),
            pnl=d.get("pnl"),
            status=str(d.get("status", "")),
            confidence=d.get("confidence"),
            rationale=str(d.get("rationale", "")),
            expected_holding_days=d.get("expected_holding_days"),
            entered_at=d.get("entered_at"),
            closed_at=d.get("closed_at"),
            days_held=d.get("days_held"),
            won=bool(d.get("won", False)),
            run_id=d.get("run_id"),
        )

    def _ot(d: dict) -> OpenTrade:
        return OpenTrade(
            trade_id=int(d.get("trade_id", 0)),
            ticker=str(d.get("ticker", "")),
            direction=str(d.get("direction", "")),
            setup_type=str(d.get("setup_type", "unknown")),
            quantity=int(d.get("quantity", 0)),
            entry_price=d.get("entry_price"),
            stop_loss=d.get("stop_loss"),
            target_price=d.get("target_price"),
            target_price_2=d.get("target_price_2"),
            confidence=d.get("confidence"),
            timeframe=d.get("timeframe"),
            entered_at=d.get("entered_at"),
            run_id=d.get("run_id"),
        )

    return JournalFacts(
        run_id=str(raw.get("run_id", "")),
        journal_date_pt=str(raw.get("journal_date_pt", "")),
        generated_at_utc=str(raw.get("generated_at_utc", "")),
        closed_today=[_ct(x) for x in raw.get("closed_today", [])],
        open_positions=[_ot(x) for x in raw.get("open_positions", [])],
        closed_last_30d=[_ct(x) for x in raw.get("closed_last_30d", [])],
        closed_last_90d=[_ct(x) for x in raw.get("closed_last_90d", [])],
        tickers_today=list(raw.get("tickers_today", [])),
        new_tickers_today=list(raw.get("new_tickers_today", [])),
        realized_pnl_today_usd=float(raw.get("realized_pnl_today_usd", 0.0)),
        wiki_excerpts=raw.get("wiki_excerpts", {}),
        wiki_context=raw.get("wiki_context", {}),
    )


def _smoke_turso_overrides() -> dict[str, Any]:
    """Return mock Turso rows for --smoke runs.

    Two synthetic closed trades + one open position. trade_id values are
    chosen NOT to collide with real Turso rows on a fresh DB (high integers).
    """
    today = datetime.now(PT_TZ).date().isoformat()
    now_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    closed_today = [
        {
            "id": 9001,
            "run_id": "smoke_journal_run",
            "mode": "b_swing",
            "ticker": "TSLA",
            "direction": "long",
            "quantity": 5,
            "entry_price": 220.00,
            "entry_fill_price": 220.10,
            "target_price": 235.00,
            "stop_loss": 215.00,
            "status": "target_hit",
            "exit_fill_price": 235.05,
            "pnl": 74.75,
            "confidence": 7,
            "entered_at": "2026-05-02T16:30:00+00:00",
            "closed_at": now_utc,
            "raw_decision": json.dumps({
                "setup_type": "breakout_up",
                "rationale": "Bull breakout above 50-day SMA on volume; macro risk-on.",
                "expected_holding_days": 5,
            }),
        },
        {
            "id": 9002,
            "run_id": "smoke_journal_run",
            "mode": "b_swing",
            "ticker": "AMZN",
            "direction": "short",
            "quantity": 1,
            "entry_price": 268.00,
            "entry_fill_price": 268.20,
            "target_price": 245.00,
            "stop_loss": 273.00,
            "status": "stop_hit",
            "exit_fill_price": 273.10,
            "pnl": -49.00,
            "confidence": 6,
            "entered_at": "2026-05-03T16:30:00+00:00",
            "closed_at": now_utc,
            "raw_decision": json.dumps({
                "setup_type": "overbought_reversal",
                "rationale": "RSI 82 with bearish divergence on 4h.",
                "expected_holding_days": 4,
            }),
        },
    ]

    open_positions = [
        {
            "id": 9003,
            "run_id": "smoke_journal_run",
            "mode": "b_swing",
            "ticker": "AAPL",
            "direction": "long",
            "quantity": 3,
            "entry_price": 280.00,
            "entry_fill_price": 280.50,
            "target_price": 295.00,
            "target_price_2": None,
            "stop_loss": 274.00,
            "status": "entered",
            "confidence": 8,
            "timeframe": "7d",
            "entered_at": now_utc,
            "raw_decision": json.dumps({
                "setup_type": "trending_up",
                "rationale": "Riding 200-day SMA reclaim; conviction 8.",
                "expected_holding_days": 7,
            }),
        },
    ]

    return {
        "closed_today_override": closed_today,
        "open_positions_override": open_positions,
        "closed_30d_override": closed_today,
        "closed_90d_override": closed_today,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Stage 4 End-of-Day Journal for System B.",
    )
    parser.add_argument("--run-id", default=None,
                        help="Run ID (default: auto-generated b_journal_<timestamp>)")
    parser.add_argument("--finalize", action="store_true",
                        help="Apply wiki side effects from journal_output.json")
    parser.add_argument("--runs-dir", default="runs", help="Root runs directory (default: runs)")
    parser.add_argument("--wiki-root", default="wiki", help="Wiki root (default: wiki)")
    parser.add_argument("--starting-capital", type=float, default=25_000.0,
                        help="Account starting capital in USD (default: 25000)")
    parser.add_argument("--date", default=None,
                        help="Override 'today' as YYYY-MM-DD (PT). Useful for backfill.")
    parser.add_argument("--smoke", action="store_true",
                        help="Use mock Turso rows (no DB read). Default mode only.")
    parser.add_argument("--allow-no-llm", action="store_true",
                        help="In --finalize mode, proceed without journal_output.json "
                             "(uses deterministic fallback bullets).")
    parser.add_argument("--no-prices", action="store_true",
                        help="Skip yfinance current-price lookup in --finalize.")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.finalize:
        if not args.run_id:
            print("ERROR: --finalize requires --run-id.", file=sys.stderr)
            return 1
        return _run_finalize(args)

    return _run_default(args)


if __name__ == "__main__":
    sys.exit(main())
