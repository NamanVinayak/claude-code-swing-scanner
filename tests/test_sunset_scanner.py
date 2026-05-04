"""Live-network tests for ai_hedge/scanners/sunset_scanner.py.

Most tests hit TradingView and/or Capitol Trades. They require internet access.
If a source is temporarily down, the scanner degrades gracefully — tests still
pass as long as the result structure is correct.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ai_hedge.scanners.sunset_scanner import (
    Candidate,
    ScanConfig,
    ScanResult,
    run_sunset_scan,
    write_scan_outputs,
)

_PROJECT_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# 1. Basic shape
# ---------------------------------------------------------------------------

def test_run_sunset_scan_returns_scan_result_object():
    """run_sunset_scan() returns a well-formed ScanResult."""
    result = run_sunset_scan()
    assert isinstance(result, ScanResult), f"expected ScanResult, got {type(result)}"
    assert result.universe_size > 50, (
        f"expected universe_size > 50, got {result.universe_size} "
        "(may indicate screen_universe failed)"
    )
    assert isinstance(result.candidates, list), "candidates must be a list"
    assert result.elapsed_seconds > 0, "elapsed_seconds must be positive"
    assert isinstance(result.signal_counts, dict), "signal_counts must be a dict"
    assert len(result.signal_counts) > 0, "signal_counts must have at least one entry"
    assert isinstance(result.run_id, str) and result.run_id, "run_id must be a non-empty string"
    assert isinstance(result.scan_timestamp_pt, str) and result.scan_timestamp_pt, \
        "scan_timestamp_pt must be a non-empty string"


# ---------------------------------------------------------------------------
# 2. Candidate field integrity
# ---------------------------------------------------------------------------

def test_candidates_have_required_fields():
    """Every candidate has non-empty ticker, exchange, last_close > 0, and score >= min_reasons."""
    config = ScanConfig(min_reasons_to_advance=2)
    result = run_sunset_scan(config)

    for c in result.candidates:
        assert isinstance(c, Candidate), f"expected Candidate, got {type(c)}"
        assert c.ticker, f"ticker must be non-empty; got {c.ticker!r}"
        assert c.exchange, f"exchange must be non-empty for {c.ticker}"
        assert c.last_close > 0, f"last_close must be positive for {c.ticker}; got {c.last_close}"
        assert isinstance(c.reasons, list), f"reasons must be a list for {c.ticker}"
        assert len(c.reasons) >= config.min_reasons_to_advance, (
            f"{c.ticker}: score={c.score} < min_reasons={config.min_reasons_to_advance}; "
            f"reasons={c.reasons}"
        )


# ---------------------------------------------------------------------------
# 3. Sort order
# ---------------------------------------------------------------------------

def test_candidates_sorted_by_score_then_market_cap():
    """Candidates are sorted: score descending, then market_cap descending on ties."""
    result = run_sunset_scan()
    candidates = result.candidates

    for i in range(len(candidates) - 1):
        a, b = candidates[i], candidates[i + 1]
        assert a.score >= b.score, (
            f"sort violation at index {i}: {a.ticker} score={a.score} < "
            f"{b.ticker} score={b.score}"
        )
        if a.score == b.score:
            mc_a = a.market_cap_usd or 0.0
            mc_b = b.market_cap_usd or 0.0
            assert mc_a >= mc_b, (
                f"tiebreak violation at index {i}: {a.ticker} market_cap={mc_a} < "
                f"{b.ticker} market_cap={mc_b} (same score={a.score})"
            )


# ---------------------------------------------------------------------------
# 4. max_candidates cap
# ---------------------------------------------------------------------------

def test_max_candidates_respected():
    """Scan with max_candidates=10 returns at most 10 candidates."""
    config = ScanConfig(max_candidates=10)
    result = run_sunset_scan(config)
    assert len(result.candidates) <= 10, (
        f"expected <= 10 candidates, got {len(result.candidates)}"
    )


# ---------------------------------------------------------------------------
# 5. No Capitol Trades flag
# ---------------------------------------------------------------------------

def test_no_capitol_trades_flag():
    """capitol_trades_enabled=False produces no capitol_* reasons and no capitol_buys key."""
    config = ScanConfig(capitol_trades_enabled=False)
    result = run_sunset_scan(config)

    for c in result.candidates:
        capitol_reasons = [r for r in c.reasons if r.startswith("capitol_")]
        assert not capitol_reasons, (
            f"{c.ticker} has capitol reason(s) even with capitol_trades_enabled=False: "
            f"{capitol_reasons}"
        )

    assert "capitol_buys" not in result.signal_counts, (
        "signal_counts should not contain 'capitol_buys' when capitol_trades_enabled=False; "
        f"got signal_counts={result.signal_counts}"
    )


# ---------------------------------------------------------------------------
# 6. min_reasons filter
# ---------------------------------------------------------------------------

def test_min_reasons_filter_works():
    """Scan with min_reasons_to_advance=3 returns only candidates with score >= 3."""
    config = ScanConfig(min_reasons_to_advance=3)
    result = run_sunset_scan(config)

    for c in result.candidates:
        assert c.score >= 3, (
            f"{c.ticker} score={c.score} < 3; reasons={c.reasons}"
        )


# ---------------------------------------------------------------------------
# 7. File output
# ---------------------------------------------------------------------------

def test_write_scan_outputs_creates_files(tmp_path):
    """write_scan_outputs writes both JSON files with expected top-level keys."""
    config = ScanConfig(max_candidates=10)
    result = run_sunset_scan(config)
    paths = write_scan_outputs(result, runs_dir=str(tmp_path))

    # Both paths returned
    assert "tomorrow_watchlist" in paths, "missing 'tomorrow_watchlist' in returned paths"
    assert "scanner_diagnostic" in paths, "missing 'scanner_diagnostic' in returned paths"

    watchlist_path = Path(paths["tomorrow_watchlist"])
    diagnostic_path = Path(paths["scanner_diagnostic"])

    assert watchlist_path.exists(), f"tomorrow_watchlist.json not found at {watchlist_path}"
    assert diagnostic_path.exists(), f"scanner_diagnostic.json not found at {diagnostic_path}"

    # Parse and check keys
    watchlist = json.loads(watchlist_path.read_text())
    for key in ("run_id", "scan_timestamp_pt", "universe_size", "candidate_count", "candidates"):
        assert key in watchlist, f"tomorrow_watchlist.json missing key: {key!r}"
    assert isinstance(watchlist["candidates"], list), "candidates must be a list"

    diagnostic = json.loads(diagnostic_path.read_text())
    for key in ("run_id", "scan_timestamp_pt", "universe_size", "candidate_count",
                "signal_counts", "errors", "elapsed_seconds", "config"):
        assert key in diagnostic, f"scanner_diagnostic.json missing key: {key!r}"
    assert isinstance(diagnostic["signal_counts"], dict), "signal_counts must be a dict"
    assert isinstance(diagnostic["errors"], list), "errors must be a list"

    # Files land in the correct run subdirectory
    assert watchlist_path.parent.name == result.run_id, (
        f"expected files under runs/<run_id>/, got {watchlist_path.parent}"
    )


# ---------------------------------------------------------------------------
# 8. Synthesizer prompt file
# ---------------------------------------------------------------------------

def test_synthesizer_prompt_file_exists():
    """b_scanner_synthesizer.md exists, has model: sonnet front-matter, and all five sections."""
    prompt_path = (
        _PROJECT_ROOT
        / "ai_hedge"
        / "personas"
        / "prompts"
        / "b_scanner_synthesizer.md"
    )
    assert prompt_path.exists(), f"synthesizer prompt not found at {prompt_path}"

    content = prompt_path.read_text()

    # YAML front-matter must include model: sonnet
    assert "model: sonnet" in content, (
        "b_scanner_synthesizer.md must have 'model: sonnet' in its YAML front-matter"
    )

    # All five required section headers must be present
    required_sections = [
        "## TL;DR",
        "## Sector breadth",
        "## Signal density",
        "## Anomalies",
        "## Last updated",
    ]
    for section in required_sections:
        assert section in content, (
            f"b_scanner_synthesizer.md is missing required section: {section!r}"
        )


# ---------------------------------------------------------------------------
# 9. CLI --help
# ---------------------------------------------------------------------------

def test_cli_runner_help():
    """b_stage1 CLI responds to --help with exit code 0 and expected flags."""
    venv_python = str(_PROJECT_ROOT / ".venv" / "bin" / "python")
    proc = subprocess.run(
        [venv_python, "-m", "ai_hedge.runner.b_stage1", "--help"],
        capture_output=True,
        text=True,
        cwd=str(_PROJECT_ROOT),
    )
    assert proc.returncode == 0, (
        f"--help exited with code {proc.returncode}; stderr: {proc.stderr}"
    )
    assert "--max-candidates" in proc.stdout, (
        f"expected '--max-candidates' in help output; got:\n{proc.stdout}"
    )
