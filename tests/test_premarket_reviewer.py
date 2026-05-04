"""Tests for ai_hedge/scanners/premarket_reviewer.py and related plumbing.

Most evaluate_candidate tests use synthetic snapshots to avoid network calls.
Tests that exercise the full pipeline (review_premarket, write_review_outputs)
may make light network calls or write to the local runs/ directory.
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ai_hedge.scanners.premarket_reviewer import (
    FilterDecision,
    PreMarketReviewResult,
    PreMarketSnapshot,
    evaluate_candidate,
    load_latest_stage1_watchlist,
    review_premarket,
    write_review_outputs,
)

_PROJECT_ROOT = Path(__file__).parent.parent
_PROMPTS_DIR = _PROJECT_ROOT / "ai_hedge" / "personas" / "prompts"


def _make_snapshot(
    ticker: str = "TEST",
    last_regular_close: float = 100.0,
    premarket_last: float | None = 101.0,
    overnight_gap_pct: float | None = 1.0,
    premarket_volume: int | None = 50_000,
    avg_premarket_volume_10d: float | None = 40_000.0,
) -> PreMarketSnapshot:
    return PreMarketSnapshot(
        ticker=ticker,
        last_regular_close=last_regular_close,
        premarket_last=premarket_last,
        overnight_gap_pct=overnight_gap_pct,
        premarket_volume=premarket_volume,
        avg_premarket_volume_10d=avg_premarket_volume_10d,
        fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def _make_watchlist(
    run_id: str,
    tickers: list[str],
    scan_timestamp_pt: str | None = None,
    universe_size: int = 500,
) -> dict:
    if scan_timestamp_pt is None:
        scan_timestamp_pt = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return {
        "run_id": run_id,
        "scan_timestamp_pt": scan_timestamp_pt,
        "universe_size": universe_size,
        "candidate_count": len(tickers),
        "candidates": [
            {
                "ticker": t,
                "exchange": "NASDAQ",
                "last_close": 100.0,
                "market_cap_usd": 5_000_000_000.0,
                "volume": 1_000_000,
                "change_pct_today": 0.5,
                "score": 2,
                "reasons": ["tv_breakout_up", "tv_strong_buy"],
                "tradingview_recommendation": "STRONG_BUY",
                "capitol_buys_30d": 0,
                "capitol_buys_politicians": [],
            }
            for t in tickers
        ],
    }


# ---------------------------------------------------------------------------
# 1. load_latest_stage1_watchlist — finds most recent
# ---------------------------------------------------------------------------

def test_load_latest_stage1_watchlist_finds_most_recent(tmp_path):
    """load_latest_stage1_watchlist returns the newest watchlist by mtime."""
    older_dir = tmp_path / "run_001"
    older_dir.mkdir()
    newer_dir = tmp_path / "run_002"
    newer_dir.mkdir()

    older_file = older_dir / "tomorrow_watchlist.json"
    older_file.write_text(json.dumps({"run_id": "run_001", "candidates": []}))

    # Small sleep to guarantee distinct mtimes
    time.sleep(0.05)

    newer_file = newer_dir / "tomorrow_watchlist.json"
    newer_file.write_text(json.dumps({"run_id": "run_002", "candidates": []}))

    run_id, data = load_latest_stage1_watchlist(runs_dir=str(tmp_path))

    assert run_id == "run_002", f"expected run_002, got {run_id!r}"
    assert data["run_id"] == "run_002"


# ---------------------------------------------------------------------------
# 2. load_latest_stage1_watchlist — raises on empty dir
# ---------------------------------------------------------------------------

def test_load_latest_raises_when_no_watchlist(tmp_path):
    """load_latest_stage1_watchlist raises FileNotFoundError when no watchlist exists."""
    with pytest.raises(FileNotFoundError):
        load_latest_stage1_watchlist(runs_dir=str(tmp_path))


# ---------------------------------------------------------------------------
# 3. evaluate_candidate — drops on gap up
# ---------------------------------------------------------------------------

def test_evaluate_candidate_drops_on_gap_up():
    """Overnight gap > +5% fires gap_up_exhausted and drops the candidate."""
    snap = _make_snapshot(overnight_gap_pct=8.0, premarket_last=108.0)
    decision = evaluate_candidate("TEST", snapshot=snap, earnings_recent_days=None)

    assert decision.keep is False, "should not keep a >5% gapped-up name"
    assert "gap_up_exhausted" in decision.drop_reasons, (
        f"expected gap_up_exhausted in drop_reasons; got {decision.drop_reasons}"
    )


# ---------------------------------------------------------------------------
# 4. evaluate_candidate — drops on gap down
# ---------------------------------------------------------------------------

def test_evaluate_candidate_drops_on_gap_down():
    """Overnight gap < -5% fires gap_down_setup_broken and drops the candidate."""
    snap = _make_snapshot(overnight_gap_pct=-7.0, premarket_last=93.0)
    decision = evaluate_candidate("TEST", snapshot=snap, earnings_recent_days=None)

    assert decision.keep is False, "should not keep a >5% gapped-down name"
    assert "gap_down_setup_broken" in decision.drop_reasons, (
        f"expected gap_down_setup_broken in drop_reasons; got {decision.drop_reasons}"
    )


# ---------------------------------------------------------------------------
# 5. evaluate_candidate — drops on volume vacuum
# ---------------------------------------------------------------------------

def test_evaluate_candidate_drops_on_volume_vacuum():
    """Volume < 50% of 10d avg fires premarket_volume_vacuum."""
    snap = _make_snapshot(
        overnight_gap_pct=0.5,
        premarket_volume=12_000,
        avg_premarket_volume_10d=40_000.0,  # ratio = 0.30 < 0.50
    )
    decision = evaluate_candidate("TEST", snapshot=snap, earnings_recent_days=None)

    assert decision.keep is False, "should not keep low-volume name"
    assert "premarket_volume_vacuum" in decision.drop_reasons, (
        f"expected premarket_volume_vacuum in drop_reasons; got {decision.drop_reasons}"
    )


# ---------------------------------------------------------------------------
# 6. evaluate_candidate — keeps clean setup
# ---------------------------------------------------------------------------

def test_evaluate_candidate_keeps_clean_setup():
    """A clean setup (small gap, adequate volume, no recent earnings) survives."""
    snap = _make_snapshot(
        overnight_gap_pct=0.5,
        premarket_volume=48_000,
        avg_premarket_volume_10d=40_000.0,  # ratio = 1.20 > 0.50
    )
    decision = evaluate_candidate("TEST", snapshot=snap, earnings_recent_days=None)

    assert decision.keep is True, f"should keep clean setup; got drop_reasons={decision.drop_reasons}"
    assert decision.drop_reasons == [], f"clean setup should have no drop reasons; got {decision.drop_reasons}"


# ---------------------------------------------------------------------------
# 7. evaluate_candidate — soft-keep on data unavailable
# ---------------------------------------------------------------------------

def test_evaluate_candidate_soft_keep_on_data_unavailable():
    """premarket_last=None triggers data_unavailable soft-keep (keep=True)."""
    snap = _make_snapshot(premarket_last=None, overnight_gap_pct=None)
    decision = evaluate_candidate("TEST", snapshot=snap, earnings_recent_days=None)

    assert decision.keep is True, "data unavailable should result in soft-keep (keep=True)"
    assert "data_unavailable" in decision.drop_reasons, (
        f"expected data_unavailable in drop_reasons; got {decision.drop_reasons}"
    )


# ---------------------------------------------------------------------------
# 8. review_premarket — stale Stage 1 drops all with stage1_too_old
# ---------------------------------------------------------------------------

def test_review_premarket_with_stale_stage1_drops_all(tmp_path):
    """Watchlist older than max_age_hours drops all candidates with stage1_too_old."""
    stale_ts = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat(timespec="seconds")
    watchlist = _make_watchlist("run_stale", ["AAPL", "MSFT"], scan_timestamp_pt=stale_ts)

    watchlist_path = tmp_path / "tomorrow_watchlist.json"
    watchlist_path.write_text(json.dumps(watchlist))

    result = review_premarket(
        source_path=str(watchlist_path),
        run_id="test_stale",
        max_age_hours=24.0,
    )

    assert result.survivors == [], f"expected no survivors for stale watchlist; got {result.survivors}"
    assert len(result.decisions) == 2

    for d in result.decisions:
        assert d.keep is False, f"{d.ticker} should be dropped"
        assert "stage1_too_old" in d.drop_reasons, (
            f"{d.ticker}: expected stage1_too_old; got {d.drop_reasons}"
        )


# ---------------------------------------------------------------------------
# 9. write_review_outputs — creates expected files
# ---------------------------------------------------------------------------

def test_write_review_outputs_creates_facts_files(tmp_path):
    """write_review_outputs creates premarket_filtered.json and one facts file per survivor."""
    tickers = ["AAPL", "MSFT", "NVDA"]
    watchlist = _make_watchlist("run_write_test", tickers)
    watchlist_path = tmp_path / "tomorrow_watchlist.json"
    watchlist_path.write_text(json.dumps(watchlist))

    snap = _make_snapshot(overnight_gap_pct=0.5)
    decisions = [
        FilterDecision(
            ticker=t,
            keep=True,
            drop_reasons=[],
            snapshot=_make_snapshot(ticker=t, overnight_gap_pct=0.5),
            earnings_recent_days=None,
        )
        for t in tickers
    ]

    result = PreMarketReviewResult(
        run_id="run_write_test",
        review_timestamp_pt=datetime.now(timezone.utc).isoformat(),
        source_run_id="run_write_test",
        source_path=str(watchlist_path),
        candidates_in=len(tickers),
        survivors=tickers,
        decisions=decisions,
        errors=[],
        elapsed_seconds=1.0,
    )

    paths = write_review_outputs(result, runs_dir=str(tmp_path))

    # premarket_filtered.json must exist
    filtered_path = tmp_path / "run_write_test" / "premarket_filtered.json"
    assert filtered_path.exists(), f"premarket_filtered.json not found at {filtered_path}"
    assert "premarket_filtered" in paths

    # One facts file per survivor
    facts_dir = tmp_path / "run_write_test" / "facts"
    assert facts_dir.exists(), f"facts directory not found at {facts_dir}"

    for ticker in tickers:
        facts_file = facts_dir / f"b_premarket__{ticker}.json"
        assert facts_file.exists(), f"facts file not found for {ticker}: {facts_file}"
        assert f"facts__{ticker}" in paths


# ---------------------------------------------------------------------------
# 10. test_facts_bundle_shape
# ---------------------------------------------------------------------------

def test_facts_bundle_shape(tmp_path):
    """Each facts file has the required top-level keys."""
    required_keys = {"ticker", "stage1_score", "premarket", "earnings", "scanner_universe", "wiki_context"}

    tickers = ["GOOG"]
    watchlist = _make_watchlist("run_shape_test", tickers)
    watchlist_path = tmp_path / "tomorrow_watchlist.json"
    watchlist_path.write_text(json.dumps(watchlist))

    decisions = [
        FilterDecision(
            ticker="GOOG",
            keep=True,
            drop_reasons=[],
            snapshot=_make_snapshot(ticker="GOOG", overnight_gap_pct=0.3),
            earnings_recent_days=None,
        )
    ]

    result = PreMarketReviewResult(
        run_id="run_shape_test",
        review_timestamp_pt=datetime.now(timezone.utc).isoformat(),
        source_run_id="run_shape_test",
        source_path=str(watchlist_path),
        candidates_in=1,
        survivors=["GOOG"],
        decisions=decisions,
        errors=[],
        elapsed_seconds=0.5,
    )

    write_review_outputs(result, runs_dir=str(tmp_path))

    facts_file = tmp_path / "run_shape_test" / "facts" / "b_premarket__GOOG.json"
    assert facts_file.exists(), f"facts file not found: {facts_file}"

    data = json.loads(facts_file.read_text())
    for key in required_keys:
        assert key in data, f"facts bundle missing required key: {key!r}"

    assert data["ticker"] == "GOOG"
    assert isinstance(data["premarket"], dict)
    assert isinstance(data["earnings"], dict)
    assert isinstance(data["scanner_universe"], dict)
    assert isinstance(data["wiki_context"], dict)


# ---------------------------------------------------------------------------
# 11. test_wiki_injection_runs
# ---------------------------------------------------------------------------

def test_wiki_injection_runs():
    """After write_review_outputs, each facts file has a non-empty wiki_context key.

    This test writes to the real runs/ directory so inject_context can find the files
    (inject_context hardcodes Path('runs') / run_id / 'facts' relative to CWD).
    The run is cleaned up after the test.
    """
    import os

    run_id = "test_wiki_inject_tmp"
    run_dir = _PROJECT_ROOT / "runs" / run_id
    facts_dir = run_dir / "facts"

    try:
        tickers = ["AAPL"]
        watchlist = _make_watchlist(run_id, tickers)
        watchlist_path = run_dir / "tomorrow_watchlist.json"
        run_dir.mkdir(parents=True, exist_ok=True)
        watchlist_path.write_text(json.dumps(watchlist))

        decisions = [
            FilterDecision(
                ticker="AAPL",
                keep=True,
                drop_reasons=[],
                snapshot=_make_snapshot(ticker="AAPL", overnight_gap_pct=0.2),
                earnings_recent_days=None,
            )
        ]

        result = PreMarketReviewResult(
            run_id=run_id,
            review_timestamp_pt=datetime.now(timezone.utc).isoformat(),
            source_run_id=run_id,
            source_path=str(watchlist_path),
            candidates_in=1,
            survivors=["AAPL"],
            decisions=decisions,
            errors=[],
            elapsed_seconds=0.1,
        )

        # Run from project root so inject_context finds runs/<run_id>/facts/
        original_cwd = os.getcwd()
        os.chdir(str(_PROJECT_ROOT))
        try:
            write_review_outputs(result, runs_dir="runs")
        finally:
            os.chdir(original_cwd)

        facts_file = facts_dir / "b_premarket__AAPL.json"
        assert facts_file.exists(), f"facts file not found: {facts_file}"

        data = json.loads(facts_file.read_text())
        wc = data.get("wiki_context", {})
        assert wc != {}, (
            "wiki_context should be non-empty after injection "
            "(expected slices dict even for new ticker); got {}"
        )
        # For new tickers: {"slices": {...}, "new_ticker": True}
        # For known tickers with wiki pages: {"slices": {...}}
        assert "slices" in wc or "skipped" in wc, (
            f"wiki_context should contain 'slices' or be a skip report; got {wc}"
        )
    finally:
        # Clean up the test run
        import shutil
        if run_dir.exists():
            shutil.rmtree(run_dir)


# ---------------------------------------------------------------------------
# 12. test_prompt_files_exist_and_have_required_sections
# ---------------------------------------------------------------------------

def test_prompt_files_exist_and_have_required_sections():
    """Both prompt files exist, have YAML front-matter with model: sonnet, and mention required keys."""
    # b_premarket.md
    premarket_path = _PROMPTS_DIR / "b_premarket.md"
    assert premarket_path.exists(), f"b_premarket.md not found at {premarket_path}"

    premarket_content = premarket_path.read_text()
    assert "model: sonnet" in premarket_content, "b_premarket.md must have 'model: sonnet'"

    for key in ("ticker", "setup_valid", "setup_type", "watch_level", "invalidation_level",
                "catalyst_note", "conviction"):
        assert key in premarket_content, (
            f"b_premarket.md is missing required output-schema key: {key!r}"
        )

    # b_premarket_synthesizer.md
    synth_path = _PROMPTS_DIR / "b_premarket_synthesizer.md"
    assert synth_path.exists(), f"b_premarket_synthesizer.md not found at {synth_path}"

    synth_content = synth_path.read_text()
    assert "model: sonnet" in synth_content, "b_premarket_synthesizer.md must have 'model: sonnet'"

    for key in ("today_watchlist", "meta", "total_evaluated", "total_kept", "dropped_count",
                "ranking_rationale"):
        assert key in synth_content, (
            f"b_premarket_synthesizer.md is missing required output-schema key: {key!r}"
        )


# ---------------------------------------------------------------------------
# 13. test_cli_runner_help
# ---------------------------------------------------------------------------

def test_cli_runner_help():
    """b_stage2 CLI responds to --help with exit code 0 and expected flags."""
    venv_python = str(_PROJECT_ROOT / ".venv" / "bin" / "python")
    proc = subprocess.run(
        [venv_python, "-m", "ai_hedge.runner.b_stage2", "--help"],
        capture_output=True,
        text=True,
        cwd=str(_PROJECT_ROOT),
    )
    assert proc.returncode == 0, (
        f"--help exited with code {proc.returncode}; stderr: {proc.stderr}"
    )
    assert "--watchlist" in proc.stdout, (
        f"expected '--watchlist' in help output; got:\n{proc.stdout}"
    )
