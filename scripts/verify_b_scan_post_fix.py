"""Integration verification for System B Stage 1 (Sunset Scanner).

Runs the live TradingView scan end-to-end and prints a structured
human-readable summary. Read-only: writes nothing to disk.

Usage:
    .venv/bin/python scripts/verify_b_scan_post_fix.py
"""
from __future__ import annotations

import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BAR = "=" * 60
SUB = "-" * 60


def _git_short_hash() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def main() -> int:
    pt_now = (
        datetime.now(timezone.utc)
        .astimezone(ZoneInfo("America/Los_Angeles"))
        .isoformat(timespec="seconds")
    )
    git_hash = _git_short_hash()

    try:
        from ai_hedge.scanners.sunset_scanner import run_sunset_scan, ScanConfig
    except Exception:
        print(BAR)
        print("SYSTEM B — STAGE 1 SCAN VERIFICATION")
        print(BAR)
        print(f"Run timestamp (PT): {pt_now}")
        print(f"Architecture commit: {git_hash}")
        print()
        print(BAR)
        print("ERROR")
        print(BAR)
        print("Failed to import sunset_scanner:")
        traceback.print_exc()
        return 1

    cfg = ScanConfig()

    print(BAR)
    print("SYSTEM B — STAGE 1 SCAN VERIFICATION")
    print(BAR)
    print(f"Run timestamp (PT): {pt_now}")
    print(f"Architecture commit: {git_hash}")
    print(
        f"Config: signals_max_per_kind={cfg.signals_max_per_kind}, "
        f"min_reasons={cfg.min_reasons_to_advance}, "
        f"directions={cfg.directions_enabled}"
    )
    print()

    t_start = time.monotonic()
    try:
        result = run_sunset_scan(cfg)
    except Exception:
        print(BAR)
        print("ERROR")
        print(BAR)
        print("run_sunset_scan raised an exception:")
        traceback.print_exc()
        return 1
    elapsed = time.monotonic() - t_start

    sc = result.signal_counts

    # ----- SIGNAL HARVEST -----
    print(SUB)
    print("SIGNAL HARVEST")
    print(SUB)
    raw_total = sc.get("signal_hits_total", 0)
    unique_total = sc.get("unique_tickers_with_any_signal", result.universe_size)
    print(f"Raw signal hits across 8 kinds:  {raw_total}")
    print(f"Unique tickers with any signal:  {unique_total}")
    print()
    print("Per-signal breakdown (in-pool counts after dedup):")
    signal_keys = [
        ("tv_strong_buy", "tv_strong_buy"),
        ("tv_strong_sell", "tv_strong_sell"),
        ("tv_oversold", "tv_oversold"),
        ("tv_overbought", "tv_overbought"),
        ("tv_breakout_up", "tv_breakout_up"),
        ("tv_breakout_down", "tv_breakout_down"),
        ("tv_trending_up", "tv_trending_up"),
        ("tv_trending_down", "tv_trending_down"),
        ("capitol_buys", "capitol_buys"),
    ]
    label_width = max(len(label) for label, _ in signal_keys) + 1
    for label, key in signal_keys:
        val = sc.get(key, 0)
        print(f"  {label + ':':<{label_width + 1}} {val}")
    print()

    # ----- SANITY FILTERING -----
    print(SUB)
    print("SANITY FILTERING")
    print(SUB)
    dropped_price = sc.get("dropped_min_price", 0)
    dropped_volume = sc.get("dropped_min_volume", 0)
    dropped_mcap = sc.get("dropped_min_market_cap", 0)
    print(f"Dropped — below min price (${cfg.min_price:.0f}):       {dropped_price}")
    print(
        f"Dropped — below min volume ({cfg.min_avg_volume // 1000}k):     {dropped_volume}"
    )
    print(
        f"Dropped — below min market cap "
        f"(${cfg.min_market_cap_usd / 1_000_000_000:.0f}B):  {dropped_mcap}"
    )
    print()

    # ----- DIRECTION-AWARE ADVANCEMENT -----
    print(SUB)
    print(f"DIRECTION-AWARE ADVANCEMENT (min_reasons={cfg.min_reasons_to_advance})")
    print(SUB)
    conflicted = sc.get("conflicted_drops", 0)
    singletons_long = sc.get("directional_singletons_long", 0)
    singletons_short = sc.get("directional_singletons_short", 0)
    long_count = sum(1 for c in result.candidates if c.direction == "long")
    short_count = sum(1 for c in result.candidates if c.direction == "short")
    advanced = len(result.candidates)
    print(f"Conflicted (1 long + 1 short, dropped):  {conflicted}")
    print(f"Singletons (long, dropped):              {singletons_long}")
    print(f"Singletons (short, dropped):             {singletons_short}")
    print()
    print(f"Advanced as candidates:                  {advanced}")
    print(f"  Long:                                  {long_count}")
    print(f"  Short:                                 {short_count}")
    print()

    # ----- TOP 10 -----
    print(SUB)
    print("TOP 10 CANDIDATES")
    print(SUB)
    print(f"  {'TICKER':<7} {'DIR':<6} {'PRICE':<12} REASONS")
    print(f"  {'-' * 6:<7} {'-' * 5:<6} {'-' * 10:<12} {'-' * 30}")
    if not result.candidates:
        print("  (no candidates returned)")
    else:
        for c in result.candidates[:10]:
            chosen = (
                c.long_reasons if c.direction == "long" else c.short_reasons
            )
            reasons_str = " + ".join(chosen) if chosen else "(none)"
            price_str = f"${c.last_close:,.2f}"
            print(
                f"  {c.ticker:<7} {(c.direction or '?'):<6} {price_str:<12} {reasons_str}"
            )
    print()

    # ----- HEALTH CHECK -----
    print(BAR)
    print("HEALTH CHECK")
    print(BAR)

    checks: list[tuple[bool, str]] = []

    cand_ok = advanced >= 5
    checks.append((cand_ok, f"Candidate count >= 5: {advanced}"))

    long_ok = long_count >= 1
    checks.append((long_ok, "At least one long candidate"))

    no_conflicted_in_output = all(
        not (c.long_reasons and c.short_reasons) for c in result.candidates
    )
    checks.append(
        (no_conflicted_in_output, "No conflicted candidates in output (sanity check)")
    )

    timing_ok = elapsed < 30.0
    checks.append((timing_ok, f"Scan completed in < 30s: {elapsed:.1f}s"))

    for ok, label in checks:
        mark = "✓" if ok else "✗"
        print(f"[{mark}] {label}")
    print(
        f"[note]   Short candidate count: {short_count} "
        "(expected 0 today due to Phase F structural overlap issue)"
    )
    print()

    # ----- PHASE G — STAGE 3 FACTS DEPTH CHECK -----
    print()
    print(BAR)
    print("PHASE G — STAGE 3 FACTS DEPTH CHECK")
    print(BAR)

    phase_g_checks: list[tuple[bool, str]] = []

    try:
        if not result.candidates:
            print("[SKIP] No candidates from scanner — Phase G needs at least 1 candidate.")
        else:
            import json as _json
            import tempfile
            import typing
            from pathlib import Path as _Path

            from ai_hedge.scanners.adversarial_facts_builder import (
                TodayWatchlistEntry,
                build_judge_facts,
                build_perspective_facts,
            )
            from ai_hedge.scanners.decisions_writer import _parse_approved_trade
            from ai_hedge.scanners.premarket_reviewer import DropReason

            top = result.candidates[0]
            top_ticker = top.ticker
            top_dir = top.direction or "long"
            print(f"Top candidate tested: {top_ticker} ({top_dir})")

            entry = TodayWatchlistEntry(
                ticker=top_ticker,
                setup_type="breakout",
                watch_level=top.last_close * 1.01,
                invalidation_level=top.last_close * 0.97,
                catalyst_note="integration test",
                conviction=7,
                source_reasons=top.long_reasons or top.short_reasons,
                direction=top_dir,
            )

            with tempfile.TemporaryDirectory() as td:
                build_perspective_facts("phaseg_test", entry, runs_dir=td)
                build_judge_facts("phaseg_test", [entry], runs_dir=td)
                facts_path = (
                    _Path(td) / "phaseg_test" / "facts" / f"b_bull_a__{top_ticker}.json"
                )
                judge_path = (
                    _Path(td) / "phaseg_test" / "facts" / f"b_judge__{top_ticker}.json"
                )
                bundle = _json.loads(facts_path.read_text())
                judge_bundle = _json.loads(judge_path.read_text())

            cp = bundle.get("current_price")
            cp_ok = cp is not None
            phase_g_checks.append((cp_ok, f"current_price populated: {cp}"))

            di = bundle.get("daily_indicators") or {}
            di_keys_lower = {str(k).lower() for k in di.keys()}
            di_has_required = bool(di) and all(
                any(req in k for k in di_keys_lower)
                for req in ("rsi", "macd", "bollinger")
            )
            phase_g_checks.append(
                (di_has_required, f"daily_indicators non-empty (has rsi/macd/bollinger): {di_has_required}")
            )

            hi = bundle.get("hourly_indicators")
            hi_present = isinstance(hi, dict)
            hi_count = len(hi) if isinstance(hi, dict) else 0
            phase_g_checks.append(
                (hi_present, f"hourly_indicators present (may be {{}} if low data): {hi_count}")
            )

            rp = bundle.get("recent_prices_5d") or []
            rp_count = len(rp)
            rp_ok = rp_count == 5
            phase_g_checks.append((rp_ok, f"recent_prices_5d count == 5: {rp_count}"))

            rit = bundle.get("recent_insider_trades")
            rit_ok = isinstance(rit, list)
            phase_g_checks.append(
                (rit_ok, f"recent_insider_trades is list: {type(rit).__name__}")
            )

            earnings = bundle.get("earnings") or {}
            earnings_field_ok = isinstance(earnings, dict) and ("days_until_next" in earnings)
            phase_g_checks.append(
                (earnings_field_ok, f"earnings.days_until_next field exists (value may be null): {earnings_field_ok}")
            )

            judge_di = judge_bundle.get("daily_indicators") or {}
            judge_cp = judge_bundle.get("current_price")
            judge_match = (judge_cp is not None) and bool(judge_di)
            phase_g_checks.append(
                (judge_match, f"judge bundle has same indicator fields: {judge_match}")
            )

            bad = {"ticker": "X", "direction": "long"}
            try:
                r = _parse_approved_trade(bad)
            except Exception:
                r = "raised"
            pyd_ok = r is None
            phase_g_checks.append(
                (pyd_ok, f"Pydantic rejects malformed trade (returns None): {pyd_ok}")
            )

            args = typing.get_args(DropReason)
            blackout_ok = "earnings_blackout_3d" in args
            phase_g_checks.append(
                (blackout_ok, f"earnings_blackout_3d in DropReason enum: {blackout_ok}")
            )

            for ok, label in phase_g_checks:
                mark = "✓" if ok else "✗"
                print(f"[{mark}] {label}")
    except Exception as exc:
        print(f"[✗] Phase G section raised: {exc}")
        traceback.print_exc()
        # Treat the entire section as one failure on top of any partial checks already recorded
        phase_g_checks.append((False, f"Phase G section raised: {type(exc).__name__}"))

    print()

    fails = sum(1 for ok, _ in checks if not ok) + sum(
        1 for ok, _ in phase_g_checks if not ok
    )
    if fails == 0:
        result_label = "PASS"
    elif fails <= 3:
        result_label = "PARTIAL"
    else:
        result_label = "FAIL"

    print(BAR)
    print(f"RESULT: {result_label}")
    print(BAR)

    if result.errors:
        print()
        print("Non-fatal errors during scan:")
        for err in result.errors:
            print(f"  - {err}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print()
        print(BAR)
        print("ERROR")
        print(BAR)
        traceback.print_exc()
        sys.exit(1)
