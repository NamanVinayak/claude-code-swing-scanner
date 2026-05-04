"""Tests for ai_hedge/scanners/adversarial_facts_builder.py."""
import json
from pathlib import Path

import pytest

from ai_hedge.scanners.adversarial_facts_builder import (
    TodayWatchlistEntry,
    build_all_stage3_facts,
    build_judge_facts,
    build_perspective_facts,
    load_today_watchlist,
)

_PROJECT_ROOT = Path(__file__).parent.parent
_PERSPECTIVE_AGENTS = ("b_bull_a", "b_bull_b", "b_bear_a", "b_bear_b")

_SAMPLE_ENTRY = TodayWatchlistEntry(
    ticker="STX",
    setup_type="breakout",
    watch_level=731.50,
    invalidation_level=718.00,
    catalyst_note="Breaking above 52-week resistance with strong volume.",
    conviction=7,
    source_reasons=["tv_breakout_up", "tv_strong_buy"],
)

_SAMPLE_WATCHLIST = [
    _SAMPLE_ENTRY,
    TodayWatchlistEntry(
        ticker="NVDA",
        setup_type="pullback_to_support",
        watch_level=850.0,
        invalidation_level=830.0,
        catalyst_note="Pullback to 50 DMA support after earnings beat.",
        conviction=8,
        source_reasons=["tv_oversold", "tv_trending_up"],
    ),
]


def _write_watchlist_fixture(tmp_path: Path, entries: list[TodayWatchlistEntry] | None = None) -> Path:
    """Write a synthetic today_watchlist.json to tmp_path/today_watchlist.json."""
    if entries is None:
        entries = _SAMPLE_WATCHLIST

    data = {
        "today_watchlist": [
            {
                "ticker": e.ticker,
                "setup_type": e.setup_type,
                "setup_valid": "yes",
                "watch_level": e.watch_level,
                "invalidation_level": e.invalidation_level,
                "catalyst_note": e.catalyst_note,
                "conviction": e.conviction,
                "source_reasons": e.source_reasons,
                "mini_agent_notes": "test fixture",
            }
            for e in entries
        ]
    }
    wl_path = tmp_path / "today_watchlist.json"
    wl_path.write_text(json.dumps(data, indent=2))
    return wl_path


# ---------------------------------------------------------------------------
# 12. load_today_watchlist — from fixture
# ---------------------------------------------------------------------------

def test_load_today_watchlist_from_fixture(tmp_path):
    """load_today_watchlist returns list of TodayWatchlistEntry with correct fields."""
    run_id = "test_run"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    _write_watchlist_fixture(run_dir)

    entries = load_today_watchlist(run_id, runs_dir=str(tmp_path))

    assert isinstance(entries, list)
    assert len(entries) == 2

    stx = next((e for e in entries if e.ticker == "STX"), None)
    assert stx is not None, "STX not found in loaded entries"
    assert stx.setup_type == "breakout"
    assert stx.watch_level == 731.50
    assert stx.invalidation_level == 718.00
    assert stx.conviction == 7
    assert "tv_breakout_up" in stx.source_reasons


# ---------------------------------------------------------------------------
# 13. build_perspective_facts — writes 4 files per ticker
# ---------------------------------------------------------------------------

def test_build_perspective_facts_writes_4_files_per_ticker(tmp_path):
    """build_perspective_facts writes 4 files (one per perspective agent) with identical content."""
    run_id = "test_run"

    facts_dir_path = build_perspective_facts(
        run_id, _SAMPLE_ENTRY, runs_dir=str(tmp_path)
    )

    facts_dir = Path(facts_dir_path)
    for agent in _PERSPECTIVE_AGENTS:
        p = facts_dir / f"{agent}__STX.json"
        assert p.exists(), f"Missing: {p}"

    # All 4 should have identical content (same ticker, same fields)
    contents = []
    for agent in _PERSPECTIVE_AGENTS:
        p = facts_dir / f"{agent}__STX.json"
        data = json.loads(p.read_text())
        contents.append(data)

    # Verify key fields
    for data in contents:
        assert data["ticker"] == "STX"
        assert data["setup_type"] == "breakout"
        assert data["watch_level"] == 731.50
        assert data["invalidation_level"] == 718.00
        assert data["conviction"] == 7
        assert "wiki_context" in data

    # Content equality (excluding filename)
    assert contents[0] == contents[1] == contents[2] == contents[3], (
        "All 4 perspective files should have identical content"
    )


# ---------------------------------------------------------------------------
# 14. build_judge_facts — one file per ticker (option b)
# ---------------------------------------------------------------------------

def test_build_judge_facts_writes_one_file_per_ticker(tmp_path):
    """build_judge_facts writes one b_judge__{T}.json per entry."""
    run_id = "test_run"

    facts_dir_path = build_judge_facts(
        run_id, _SAMPLE_WATCHLIST, runs_dir=str(tmp_path)
    )
    facts_dir = Path(facts_dir_path)

    # One file per ticker
    for entry in _SAMPLE_WATCHLIST:
        p = facts_dir / f"b_judge__{entry.ticker}.json"
        assert p.exists(), f"Missing judge facts: {p}"

    # Each file has the required keys
    for entry in _SAMPLE_WATCHLIST:
        p = facts_dir / f"b_judge__{entry.ticker}.json"
        data = json.loads(p.read_text())

        assert data["ticker"] == entry.ticker
        assert "candidates" in data
        assert isinstance(data["candidates"], list)
        assert len(data["candidates"]) == len(_SAMPLE_WATCHLIST)
        assert "perspectives" in data
        assert "risk_budget" in data
        assert "market_context" in data
        assert "wiki_context" in data


# ---------------------------------------------------------------------------
# 15. build_all_stage3_facts — wiki_context injected (or skipped gracefully)
# ---------------------------------------------------------------------------

def test_build_all_stage3_facts_runs_wiki_injection(tmp_path):
    """build_all_stage3_facts writes all files; each has a wiki_context key."""
    run_id = "test_all_facts"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    _write_watchlist_fixture(run_dir)

    summary = build_all_stage3_facts(run_id, runs_dir=str(tmp_path))

    assert summary["run_id"] == run_id
    assert len(summary["tickers"]) == 2
    assert summary["perspective_files_written"] == len(_PERSPECTIVE_AGENTS) * 2
    assert summary["judge_files_written"] == 2

    # Each written facts file must have wiki_context key
    facts_dir = Path(tmp_path) / run_id / "facts"
    for ticker in ["STX", "NVDA"]:
        for agent in _PERSPECTIVE_AGENTS:
            p = facts_dir / f"{agent}__{ticker}.json"
            assert p.exists(), f"Missing: {p}"
            data = json.loads(p.read_text())
            assert "wiki_context" in data, f"{p}: missing wiki_context"

        judge_p = facts_dir / f"b_judge__{ticker}.json"
        assert judge_p.exists()
        data = json.loads(judge_p.read_text())
        assert "wiki_context" in data


# ---------------------------------------------------------------------------
# 16. build_all_stage3_facts — empty watchlist handled gracefully
# ---------------------------------------------------------------------------

def test_build_all_stage3_facts_handles_empty_watchlist(tmp_path):
    """Empty today_watchlist.json returns summary with 0 files, no crash."""
    run_id = "test_empty"
    run_dir = tmp_path / run_id
    run_dir.mkdir()

    # Write empty watchlist
    wl = run_dir / "today_watchlist.json"
    wl.write_text(json.dumps({"today_watchlist": []}))

    summary = build_all_stage3_facts(run_id, runs_dir=str(tmp_path))

    assert summary["tickers"] == []
    assert summary["perspective_files_written"] == 0
    assert summary["judge_files_written"] == 0
