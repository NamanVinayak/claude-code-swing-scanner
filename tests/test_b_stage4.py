"""Tests for Stage 4 — End-of-Day Journal.

Covers:
  - journal_facts_builder.build_journal_facts (Turso reads mocked via overrides)
  - journal_writer.derive_phase
  - journal_writer.aggregate_patterns
  - journal_writer.append_lessons (idempotent dedup via trade_id markers)
  - journal_writer.update_budget_state_md (preserves Rules block)
  - journal_writer.bootstrap_ticker_wiki (creates skeleton pages)
  - journal_writer.apply_journal_writes (end-to-end)
  - b_stage4.py CLI prompt presence + JSON schema mentioned
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from ai_hedge.scanners.journal_facts_builder import (
    JournalFacts,
    build_journal_facts,
    write_journal_facts,
)
from ai_hedge.scanners.journal_writer import (
    SYSTEM_B_STARTED_AT,
    LessonInput,
    aggregate_patterns,
    append_lessons,
    apply_journal_writes,
    bootstrap_ticker_wiki,
    derive_phase,
    existing_trade_ids,
    render_open_positions_md,
    render_setup_patterns_md,
    update_budget_state_md,
)

PROJECT_ROOT = Path(__file__).parent.parent
PROMPTS_DIR = PROJECT_ROOT / "ai_hedge" / "personas" / "prompts"


# ---------------------------------------------------------------------------
# Mock Turso row factories
# ---------------------------------------------------------------------------

def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _closed_row(
    *, trade_id: int, ticker: str, setup_type: str, direction: str = "long",
    quantity: int = 5, entry: float = 100.0, exit_price: float = 105.0,
    stop: float = 96.0, target: float = 110.0,
    pnl: float = 25.0, status: str = "target_hit",
    closed_at: str | None = None, entered_at: str | None = None,
    rationale: str = "test rationale",
) -> dict:
    return {
        "id": trade_id,
        "run_id": f"run_{trade_id}",
        "mode": "b_swing",
        "ticker": ticker,
        "direction": direction,
        "quantity": quantity,
        "entry_price": entry,
        "entry_fill_price": entry,
        "exit_fill_price": exit_price,
        "stop_loss": stop,
        "target_price": target,
        "pnl": pnl,
        "status": status,
        "confidence": 7,
        "entered_at": entered_at or "2026-05-01T16:00:00+00:00",
        "closed_at": closed_at or _now_utc_iso(),
        "raw_decision": json.dumps({
            "setup_type": setup_type,
            "rationale": rationale,
            "expected_holding_days": 5,
        }),
    }


def _open_row(
    *, trade_id: int, ticker: str, setup_type: str = "trending_up",
    direction: str = "long", quantity: int = 3,
    entry: float = 100.0, stop: float = 96.0, target: float = 110.0,
    entered_at: str | None = None,
) -> dict:
    return {
        "id": trade_id,
        "run_id": f"run_{trade_id}",
        "mode": "b_swing",
        "ticker": ticker,
        "direction": direction,
        "quantity": quantity,
        "entry_price": entry,
        "entry_fill_price": entry,
        "stop_loss": stop,
        "target_price": target,
        "target_price_2": None,
        "status": "entered",
        "confidence": 7,
        "timeframe": "7d",
        "entered_at": entered_at or _now_utc_iso(),
        "raw_decision": json.dumps({
            "setup_type": setup_type,
            "rationale": "open trade rationale",
            "expected_holding_days": 7,
        }),
    }


# ---------------------------------------------------------------------------
# build_journal_facts
# ---------------------------------------------------------------------------

def test_build_journal_facts_basic(tmp_path: Path):
    """Facts builder should aggregate closed/open trades and detect new tickers."""
    closed = [
        _closed_row(trade_id=1, ticker="TSLA", setup_type="breakout_up", pnl=50.0),
        _closed_row(trade_id=2, ticker="AMZN", setup_type="overbought_reversal",
                    pnl=-30.0, status="stop_hit"),
    ]
    open_pos = [_open_row(trade_id=3, ticker="AAPL")]

    # Wiki root is tmp; AAPL/TSLA/AMZN have no ticker dirs → all "new".
    facts = build_journal_facts(
        run_id="test_run",
        runs_dir=str(tmp_path / "runs"),
        wiki_root=str(tmp_path / "wiki"),
        closed_today_override=closed,
        open_positions_override=open_pos,
        closed_30d_override=closed,
        closed_90d_override=closed,
    )

    assert len(facts.closed_today) == 2
    assert len(facts.open_positions) == 1
    assert facts.realized_pnl_today_usd == 20.0  # 50 - 30
    assert "TSLA" in facts.tickers_today and "AMZN" in facts.tickers_today
    # AAPL was opened today (entered_at = now), so it joins tickers_today
    assert "AAPL" in facts.tickers_today
    # No wiki/tickers/<T>/ dir exists → all 3 are new
    assert set(facts.new_tickers_today) == {"TSLA", "AMZN", "AAPL"}
    assert facts.closed_today[0].setup_type == "breakout_up"
    assert facts.closed_today[1].won is False
    assert facts.closed_today[0].won is True


def test_build_journal_facts_writes_files(tmp_path: Path):
    facts = build_journal_facts(
        run_id="write_test",
        runs_dir=str(tmp_path / "runs"),
        wiki_root=str(tmp_path / "wiki"),
        closed_today_override=[],
        open_positions_override=[],
        closed_30d_override=[],
        closed_90d_override=[],
    )
    paths = write_journal_facts(facts, runs_dir=str(tmp_path / "runs"))

    assert Path(paths["journal_facts"]).exists()
    assert Path(paths["global_facts"]).exists()
    payload = json.loads(Path(paths["journal_facts"]).read_text())
    assert payload["run_id"] == "write_test"
    assert payload["closed_today"] == []
    global_payload = json.loads(Path(paths["global_facts"]).read_text())
    assert global_payload["ticker"] == "GLOBAL"


# ---------------------------------------------------------------------------
# derive_phase
# ---------------------------------------------------------------------------

def test_derive_phase_scaling_week_1():
    """Day 0 → scaling_week_1_2."""
    p = derive_phase(
        today_pt=SYSTEM_B_STARTED_AT,
        daily_pnl_usd=0.0, weekly_pnl_usd=0.0,
        starting_capital_usd=25_000.0,
    )
    assert p.phase == "scaling_week_1_2"
    assert p.size_multiplier == 0.5


def test_derive_phase_week_3():
    """Day 14 → scaling_week_3_4 (mult 0.75)."""
    p = derive_phase(
        today_pt=SYSTEM_B_STARTED_AT + timedelta(days=14),
        daily_pnl_usd=10.0, weekly_pnl_usd=20.0,
        starting_capital_usd=25_000.0,
    )
    assert p.phase == "scaling_week_3_4"
    assert p.size_multiplier == 0.75


def test_derive_phase_full():
    p = derive_phase(
        today_pt=SYSTEM_B_STARTED_AT + timedelta(days=30),
        daily_pnl_usd=10.0, weekly_pnl_usd=20.0,
        starting_capital_usd=25_000.0,
    )
    assert p.phase == "full"
    assert p.size_multiplier == 1.0


def test_derive_phase_paused_daily():
    """Daily P&L below stop → paused."""
    p = derive_phase(
        today_pt=SYSTEM_B_STARTED_AT,
        daily_pnl_usd=-600.0,  # -2.4% of $25k
        weekly_pnl_usd=-600.0,
        starting_capital_usd=25_000.0,
    )
    assert p.phase == "paused"
    assert p.size_multiplier == 0.0
    assert "daily" in (p.paused_reason or "").lower()


def test_derive_phase_paused_weekly():
    p = derive_phase(
        today_pt=SYSTEM_B_STARTED_AT,
        daily_pnl_usd=0.0,
        weekly_pnl_usd=-1500.0,  # -6% of $25k
        starting_capital_usd=25_000.0,
    )
    assert p.phase == "paused"
    assert "weekly" in (p.paused_reason or "").lower()


# ---------------------------------------------------------------------------
# aggregate_patterns
# ---------------------------------------------------------------------------

def test_aggregate_patterns_groups_by_setup(tmp_path: Path):
    facts = build_journal_facts(
        run_id="agg_test",
        runs_dir=str(tmp_path / "runs"),
        wiki_root=str(tmp_path / "wiki"),
        closed_today_override=[],
        open_positions_override=[],
        closed_30d_override=[
            _closed_row(trade_id=1, ticker="A", setup_type="breakout_up", pnl=50),
            _closed_row(trade_id=2, ticker="B", setup_type="breakout_up", pnl=-30),
            _closed_row(trade_id=3, ticker="C", setup_type="trending_up", pnl=10),
        ],
        closed_90d_override=[],
    )
    rows = aggregate_patterns(facts.closed_last_30d)
    by_setup = {r.setup_type: r for r in rows}
    assert by_setup["breakout_up"].trades == 2
    assert by_setup["breakout_up"].wins == 1
    assert by_setup["breakout_up"].win_rate_pct == 50.0
    assert by_setup["breakout_up"].total_pnl_usd == 20.0
    assert by_setup["trending_up"].trades == 1
    assert by_setup["trending_up"].win_rate_pct == 100.0


# ---------------------------------------------------------------------------
# append_lessons (idempotency)
# ---------------------------------------------------------------------------

LESSONS_BLANK = """---
name: trade lessons
last_updated: 2026-05-03
last_run_id: bootstrap
target_words: 1500
stale_after_days: 90
word_count: 0
summary: bla
---

## Patterns (auto-generated by Sunday compactor, last 30 days)

| Setup Type | Trades | Wins | Win Rate | Avg P&L | Total P&L |
|---|---|---|---|---|---|
| _no data yet_ | — | — | — | — | — |

## Lessons

_No lessons yet — System B has not executed any trades._
"""


def test_existing_trade_ids_finds_markers():
    md = "- some lesson <!-- trade_id=42 -->\n- another <!-- trade_id=7 -->\n"
    assert existing_trade_ids(md) == {42, 7}


def test_append_lessons_replaces_placeholder():
    new_md, ids = append_lessons(
        current_md=LESSONS_BLANK,
        new_lessons=[LessonInput(trade_id=1, line="2026-05-04 | TSLA | bo | +$50 | works")],
        today=date(2026, 5, 4),
        last_run_id="run_x",
    )
    assert ids == [1]
    assert "_No lessons yet" not in new_md
    assert "trade_id=1" in new_md
    assert "TSLA" in new_md


def test_append_lessons_idempotent():
    """Re-running with the same trade_id should not duplicate the bullet."""
    once_md, ids1 = append_lessons(
        current_md=LESSONS_BLANK,
        new_lessons=[LessonInput(trade_id=1, line="2026-05-04 | TSLA | bo | +$50 | works")],
        today=date(2026, 5, 4),
        last_run_id="run_x",
    )
    twice_md, ids2 = append_lessons(
        current_md=once_md,
        new_lessons=[LessonInput(trade_id=1, line="2026-05-04 | TSLA | bo | +$50 | works")],
        today=date(2026, 5, 4),
        last_run_id="run_y",
    )
    assert ids1 == [1]
    assert ids2 == []  # already present
    # Marker appears exactly once
    assert twice_md.count("trade_id=1") == 1


def test_append_lessons_appends_to_existing_section():
    base = LESSONS_BLANK.replace(
        "_No lessons yet — System B has not executed any trades._",
        "- 2026-05-03 | NVDA | breakout | -$63 | original lesson <!-- trade_id=99 -->",
    )
    new_md, ids = append_lessons(
        current_md=base,
        new_lessons=[LessonInput(trade_id=1, line="2026-05-04 | TSLA | bo | +$50 | works")],
        today=date(2026, 5, 4),
        last_run_id="run_x",
    )
    assert ids == [1]
    assert "trade_id=99" in new_md
    assert "trade_id=1" in new_md


# ---------------------------------------------------------------------------
# update_budget_state_md (preserves Rules)
# ---------------------------------------------------------------------------

def test_update_budget_state_preserves_rules():
    bs_path = PROJECT_ROOT / "wiki" / "meta" / "budget_state.md"
    text = bs_path.read_text()

    phase = derive_phase(
        today_pt=SYSTEM_B_STARTED_AT + timedelta(days=5),
        daily_pnl_usd=10.0, weekly_pnl_usd=20.0,
        starting_capital_usd=25_000.0,
    )
    new_text = update_budget_state_md(
        current_md=text,
        starting_capital_usd=25_000.0,
        cash_usd=23_000.0,
        deployed_usd=2_000.0,
        open_risk_usd=200.0,
        open_risk_pct=0.8,
        positions_open=2,
        daily_pnl_usd=10.0,
        weekly_pnl_usd=20.0,
        phase=phase,
        today=date(2026, 5, 8),
        last_run_id="b_journal_test",
    )

    # Rules section remains intact verbatim
    assert "Risk per trade max:       1.0%" in new_text
    assert "Max simultaneous positions: 5" in new_text
    assert "VIX > 25" in new_text or "VIX  > 25" in new_text or "VIX>25" in new_text
    # State updated
    assert "Cash on hand | $23,000" in new_text
    assert "Deployed | $2,000.00" in new_text
    assert "Phase: scaling_week_1_2" in new_text
    assert "last_run_id: b_journal_test" in new_text


def test_update_budget_state_keeps_front_matter_well_formed():
    """Closing `---` fence must land on its own line (regression test)."""
    bs_path = PROJECT_ROOT / "wiki" / "meta" / "budget_state.md"
    text = bs_path.read_text()
    phase = derive_phase(
        today_pt=SYSTEM_B_STARTED_AT, daily_pnl_usd=0.0, weekly_pnl_usd=0.0,
        starting_capital_usd=25_000.0,
    )
    new_text = update_budget_state_md(
        current_md=text,
        starting_capital_usd=25_000.0, cash_usd=25_000.0, deployed_usd=0.0,
        open_risk_usd=0.0, open_risk_pct=0.0, positions_open=0,
        daily_pnl_usd=0.0, weekly_pnl_usd=0.0, phase=phase,
        today=date(2026, 5, 4), last_run_id="run_fm",
    )
    # No YAML key may be glued to the closing fence.
    head_lines = new_text.splitlines()[:15]
    for line in head_lines:
        assert not (line.endswith("---") and line != "---" and ":" in line), \
            f"front-matter close fence glued to a key: {line!r}"
    # Closing fence followed by a blank line and the body heading.
    assert "summary:" in new_text
    summary_idx = next(i for i, line in enumerate(head_lines) if line.startswith("summary:"))
    # The line immediately after summary should be the close fence on its own.
    assert head_lines[summary_idx + 1] == "---"


def test_budget_state_paused_writes_paused_reason():
    bs_path = PROJECT_ROOT / "wiki" / "meta" / "budget_state.md"
    text = bs_path.read_text()
    phase = derive_phase(
        today_pt=SYSTEM_B_STARTED_AT + timedelta(days=5),
        daily_pnl_usd=-600.0,
        weekly_pnl_usd=-600.0,
        starting_capital_usd=25_000.0,
    )
    new_text = update_budget_state_md(
        current_md=text,
        starting_capital_usd=25_000.0,
        cash_usd=24_400.0,
        deployed_usd=0.0,
        open_risk_usd=0.0,
        open_risk_pct=0.0,
        positions_open=0,
        daily_pnl_usd=-600.0,
        weekly_pnl_usd=-600.0,
        phase=phase,
        today=date(2026, 5, 8),
        last_run_id="run_paused",
    )
    assert "Paused: yes" in new_text
    assert "daily" in new_text.lower()


# ---------------------------------------------------------------------------
# bootstrap_ticker_wiki
# ---------------------------------------------------------------------------

def test_bootstrap_ticker_wiki_creates_skeletons(tmp_path: Path):
    written = bootstrap_ticker_wiki("ABCD", wiki_root=tmp_path, last_run_id="run_b")
    # All 5 page kinds created
    assert len(written) == 5
    for kind in ("thesis", "technicals", "catalysts", "trades", "setup_history"):
        assert (tmp_path / "tickers" / "ABCD" / f"{kind}.md").exists()


def test_bootstrap_ticker_wiki_idempotent(tmp_path: Path):
    bootstrap_ticker_wiki("ABCD", wiki_root=tmp_path, last_run_id="run_a")
    second = bootstrap_ticker_wiki("ABCD", wiki_root=tmp_path, last_run_id="run_b")
    assert second == []  # nothing new written


# ---------------------------------------------------------------------------
# apply_journal_writes (end-to-end deterministic side effects)
# ---------------------------------------------------------------------------

def _stage_wiki(tmp: Path) -> Path:
    """Copy real wiki/meta/* into tmp_path/wiki for an isolated run."""
    wiki_root = tmp / "wiki"
    (wiki_root / "meta").mkdir(parents=True)
    (wiki_root / "tickers").mkdir(parents=True)
    (wiki_root / "macro").mkdir(parents=True)
    real_meta = PROJECT_ROOT / "wiki" / "meta"
    for name in ("lessons.md", "setup_patterns.md", "open_positions.md", "budget_state.md"):
        shutil.copyfile(real_meta / name, wiki_root / "meta" / name)
    shutil.copyfile(
        PROJECT_ROOT / "wiki" / "macro" / "regime.md",
        wiki_root / "macro" / "regime.md",
    )
    return wiki_root


def test_apply_journal_writes_full(tmp_path: Path):
    wiki_root = _stage_wiki(tmp_path)

    closed = [
        _closed_row(trade_id=10, ticker="ZZZA", setup_type="breakout_up", pnl=50.0),
        _closed_row(trade_id=11, ticker="ZZZB", setup_type="trending_up",
                    pnl=-25.0, status="stop_hit"),
    ]
    open_pos = [_open_row(trade_id=12, ticker="ZZZC", setup_type="trending_up")]

    facts = build_journal_facts(
        run_id="run_apply",
        runs_dir=str(tmp_path / "runs"),
        wiki_root=str(wiki_root),
        closed_today_override=closed,
        open_positions_override=open_pos,
        closed_30d_override=closed,
        closed_90d_override=closed,
    )

    llm_output = {
        "lessons": [
            {"trade_id": 10, "line": "2026-05-08 | ZZZA | breakout_up | +$50.00 | clean breakout above 50d on 1.5x volume."},
            {"trade_id": 11, "line": "2026-05-08 | ZZZB | trending_up | -$25.00 | stop trip — momentum stalled at prior swing high; thesis still fine."},
        ],
        "pattern_notes": "Breakouts fired this week; mean-reversion shorts struggled on persistent risk-on.",
        "sizing_notes": "Position sizing nominal; no changes.",
        "open_position_notes": "ZZZC long is fresh — give it 3 sessions before any trail.",
    }

    summary = apply_journal_writes(
        facts=facts,
        llm_output=llm_output,
        current_prices={"ZZZC": 102.0},
        starting_capital_usd=25_000.0,
        wiki_root=wiki_root,
        today_pt=date(2026, 5, 8),
        last_run_id="run_apply",
    )

    assert summary.lessons_appended_ids == [10, 11]
    assert summary.lessons_skipped_ids == []
    assert set(summary.new_tickers_bootstrapped) == {"ZZZA", "ZZZB", "ZZZC"}
    assert summary.setup_patterns_refreshed
    assert summary.open_positions_refreshed
    assert summary.budget_state_refreshed

    lessons_md = (wiki_root / "meta" / "lessons.md").read_text()
    assert "trade_id=10" in lessons_md
    assert "trade_id=11" in lessons_md

    sp_md = (wiki_root / "meta" / "setup_patterns.md").read_text()
    assert "breakout_up" in sp_md
    assert "## Last 30 days" in sp_md
    assert "Breakouts fired this week" in sp_md  # pattern_notes injected

    op_md = (wiki_root / "meta" / "open_positions.md").read_text()
    assert "ZZZC" in op_md
    assert "Net long count: 1" in op_md

    bs_md = (wiki_root / "meta" / "budget_state.md").read_text()
    assert "last_run_id: run_apply" in bs_md
    # Rules block intact
    assert "Risk per trade max:       1.0%" in bs_md
    # State updated based on facts: deployed = 100*3 = 300
    assert "Deployed | $300.00" in bs_md
    assert "Positions open | 1" in bs_md

    # Bootstrap pages exist
    for ticker in ("ZZZA", "ZZZB", "ZZZC"):
        assert (wiki_root / "tickers" / ticker / "trades.md").exists()
        assert (wiki_root / "tickers" / ticker / "setup_history.md").exists()


def test_apply_journal_writes_idempotent(tmp_path: Path):
    """Running --finalize twice must not duplicate lessons or break files."""
    wiki_root = _stage_wiki(tmp_path)
    closed = [_closed_row(trade_id=20, ticker="QQQA", setup_type="breakout_up", pnl=10.0)]

    facts = build_journal_facts(
        run_id="run_idem",
        runs_dir=str(tmp_path / "runs"),
        wiki_root=str(wiki_root),
        closed_today_override=closed,
        open_positions_override=[],
        closed_30d_override=closed,
        closed_90d_override=closed,
    )
    llm = {"lessons": [{"trade_id": 20, "line": "2026-05-08 | QQQA | bo | +$10.00 | clean."}]}

    s1 = apply_journal_writes(
        facts=facts, llm_output=llm,
        wiki_root=wiki_root, today_pt=date(2026, 5, 8), last_run_id="run_idem",
    )
    s2 = apply_journal_writes(
        facts=facts, llm_output=llm,
        wiki_root=wiki_root, today_pt=date(2026, 5, 8), last_run_id="run_idem_2",
    )
    assert s1.lessons_appended_ids == [20]
    assert s2.lessons_appended_ids == []
    assert s2.lessons_skipped_ids == [20]
    md = (wiki_root / "meta" / "lessons.md").read_text()
    assert md.count("trade_id=20") == 1


def test_apply_journal_writes_empty_day(tmp_path: Path):
    """Quiet day: no closed trades, no open positions. Pages still refresh."""
    wiki_root = _stage_wiki(tmp_path)
    facts = build_journal_facts(
        run_id="run_quiet",
        runs_dir=str(tmp_path / "runs"),
        wiki_root=str(wiki_root),
        closed_today_override=[],
        open_positions_override=[],
        closed_30d_override=[],
        closed_90d_override=[],
    )
    summary = apply_journal_writes(
        facts=facts, llm_output={"lessons": [], "pattern_notes": "Insufficient data."},
        wiki_root=wiki_root, today_pt=date(2026, 5, 8), last_run_id="run_quiet",
    )
    assert summary.lessons_appended_ids == []
    assert summary.setup_patterns_refreshed
    assert summary.open_positions_refreshed
    assert summary.budget_state_refreshed
    sp_md = (wiki_root / "meta" / "setup_patterns.md").read_text()
    assert "Insufficient data" in sp_md


def test_fallback_lessons_when_no_llm(tmp_path: Path):
    """When journal_output.json is missing, fallback bullets carry trade_id markers."""
    wiki_root = _stage_wiki(tmp_path)
    closed = [_closed_row(trade_id=30, ticker="WWWA", setup_type="breakout_up", pnl=5.0)]
    facts = build_journal_facts(
        run_id="run_fallback",
        runs_dir=str(tmp_path / "runs"),
        wiki_root=str(wiki_root),
        closed_today_override=closed,
        open_positions_override=[],
        closed_30d_override=closed,
        closed_90d_override=closed,
    )
    summary = apply_journal_writes(
        facts=facts, llm_output=None,
        wiki_root=wiki_root, today_pt=date(2026, 5, 8), last_run_id="run_fallback",
    )
    assert summary.lessons_appended_ids == [30]
    md = (wiki_root / "meta" / "lessons.md").read_text()
    assert "trade_id=30" in md
    assert "auto-generated" in md


# ---------------------------------------------------------------------------
# Prompt + CLI assertions
# ---------------------------------------------------------------------------

def test_b_journal_prompt_exists_and_has_required_keys():
    p = PROMPTS_DIR / "b_journal.md"
    assert p.exists()
    txt = p.read_text()
    for required in ("lessons", "trade_id", "setup_type", "pattern_notes",
                     "sizing_notes", "open_position_notes", "wiki_context"):
        assert required in txt, f"Prompt missing required key: {required}"
    assert "Output ONLY the JSON" in txt or "no code fences" in txt.lower()


def test_b_stage4_cli_help_runs():
    """Smoke: the runner module imports and --help works."""
    result = subprocess.run(
        [sys.executable, "-m", "ai_hedge.runner.b_stage4", "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    assert "Stage 4" in result.stdout
    assert "--finalize" in result.stdout
    assert "--smoke" in result.stdout


def test_b_stage4_smoke_quiet_exit_code(tmp_path: Path):
    """Run --smoke in a fresh tmp tree — closed_today has 2 trades, open has 1.
    Should exit 0 and produce journal_facts.json."""
    runs = tmp_path / "runs"
    runs.mkdir()
    # Smoke uses real wiki for excerpts, so cwd must be project root.
    result = subprocess.run(
        [sys.executable, "-m", "ai_hedge.runner.b_stage4",
         "--run-id", "smoke_t",
         "--smoke",
         "--runs-dir", str(runs),
         "--wiki-root", str(PROJECT_ROOT / "wiki")],
        cwd=str(PROJECT_ROOT),
        capture_output=True, text=True, timeout=30,
    )
    # Smoke run must be deterministic — closed_today is always populated.
    assert result.returncode == 0, result.stderr
    facts_path = runs / "smoke_t" / "journal_facts.json"
    assert facts_path.exists()
    payload = json.loads(facts_path.read_text())
    assert len(payload["closed_today"]) == 2
    assert len(payload["open_positions"]) == 1
