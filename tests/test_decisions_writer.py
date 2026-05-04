"""Tests for ai_hedge/scanners/decisions_writer.py and prompt file checks."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ai_hedge.scanners.decisions_writer import write_decisions

_PROJECT_ROOT = Path(__file__).parent.parent
_PROMPTS_DIR = _PROJECT_ROOT / "ai_hedge" / "personas" / "prompts"


def _write_judge_output(tmp_path: Path, run_id: str, payload: dict) -> Path:
    """Write judge_output.json to the run dir."""
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    p = run_dir / "judge_output.json"
    p.write_text(json.dumps(payload, indent=2))
    return p


_APPROVED_TRADE = {
    "ticker": "STX",
    "direction": "long",
    "entry_price": 48.00,    # low-priced entry to stay under single-position and risk caps
    "stop_loss": 46.00,      # risk_per_share=$2; quantity=5 → risk=$10 (well under $125 cap)
    "target_price": 54.00,
    "target_price_2": 58.00,
    "quantity": 5,           # notional=5*$48=$240 (well under $3,750 single-position cap)
    "expected_holding_days": 7,
    "setup_type": "breakout",
    "conviction": 7,
    "rationale": "Technical bull dominated; bear acknowledged volume concern but confirmed by price action.",
    "risk_usd": 10.00,
}

_REJECTED_TRADE = {
    "ticker": "NVDA",
    "reason": "expected_return_negative",
}


# ---------------------------------------------------------------------------
# 17. write_decisions — from judge output fixture
# ---------------------------------------------------------------------------

def test_write_decisions_from_judge_output_fixture(tmp_path):
    """write_decisions produces decisions.json with correct ingester-compatible schema."""
    run_id = "test_write"
    judge_payload = {
        "approved": [_APPROVED_TRADE, {
            **_APPROVED_TRADE,
            "ticker": "AAPL",
            "entry_price": 180.0,
            "stop_loss": 175.0,
            "target_price": 192.0,
            "quantity": 12,
            "risk_usd": 60.0,
        }],
        "rejected": [_REJECTED_TRADE],
        "summary": "2 approved, 1 rejected.",
    }
    _write_judge_output(tmp_path, run_id, judge_payload)

    decisions_path = write_decisions(run_id, runs_dir=str(tmp_path))

    assert Path(decisions_path).exists(), f"decisions.json not written at {decisions_path}"

    data = json.loads(Path(decisions_path).read_text())

    # Top-level required keys
    for key in ("run_id", "mode", "generated_at", "decisions", "rejected"):
        assert key in data, f"decisions.json missing key: {key!r}"

    assert data["run_id"] == run_id

    # decisions must be a DICT keyed by ticker (ingester format)
    decisions = data["decisions"]
    assert isinstance(decisions, dict), f"decisions must be a dict; got {type(decisions)}"

    # STX and AAPL approved
    assert "STX" in decisions, "STX not in decisions dict"
    assert "AAPL" in decisions, "AAPL not in decisions dict"

    stx = decisions["STX"]
    # action must be "buy" for long direction (ingester reads "buy" not "enter_long")
    assert stx["action"] == "buy", f"expected action='buy', got {stx['action']!r}"
    assert stx["direction"] == "long"
    assert stx["entry_price"] == 48.00
    assert stx["stop_loss"] == 46.00
    assert stx["target_price"] == 54.00
    assert stx["quantity"] == 5
    assert "timeframe" in stx
    assert "confidence" in stx


# ---------------------------------------------------------------------------
# 18. write_decisions — budget double-check catches over-limit trade
# ---------------------------------------------------------------------------

def test_write_decisions_double_checks_budget(tmp_path):
    """A trade that would exceed total_open_risk_cap is moved to rejected."""
    run_id = "test_budget_check"

    # Craft a trade with absurdly high quantity to exceed risk cap
    # Account = $25,000, total_open_risk_cap = 4% = $1,000
    # risk_per_share = abs(48 - 46) = 2
    # To exceed $1,000 risk cap: quantity > 500, so use quantity=1000
    big_trade = {
        **_APPROVED_TRADE,
        "quantity": 1000,   # 1000 * $2 risk_per_share = $2,000 >> $1,000 cap
        "risk_usd": 2000.0,
    }
    judge_payload = {
        "approved": [big_trade],
        "rejected": [],
        "summary": "1 approved (should fail budget check)",
    }
    _write_judge_output(tmp_path, run_id, judge_payload)

    decisions_path = write_decisions(run_id, runs_dir=str(tmp_path))
    data = json.loads(Path(decisions_path).read_text())

    decisions = data["decisions"]
    rejected = data["rejected"]

    # The big trade should have been moved to rejected
    assert "STX" not in decisions or decisions.get("STX", {}).get("quantity", 0) < 200, (
        "Oversized trade should have been moved to rejected"
    )
    assert any(
        r.get("ticker") == "STX" and "budget_check_failed" in r.get("reason", "")
        for r in rejected
    ), f"Expected budget_check_failed in rejected; got {rejected}"


# ---------------------------------------------------------------------------
# 19. write_decisions — empty approved list writes empty decisions
# ---------------------------------------------------------------------------

def test_write_decisions_empty_approved_writes_empty_decisions(tmp_path):
    """judge_output with no approved trades writes decisions.json with empty decisions dict."""
    run_id = "test_empty"
    judge_payload = {
        "approved": [],
        "rejected": [_REJECTED_TRADE],
        "summary": "No trades approved today.",
    }
    _write_judge_output(tmp_path, run_id, judge_payload)

    decisions_path = write_decisions(run_id, runs_dir=str(tmp_path))
    assert Path(decisions_path).exists()

    data = json.loads(Path(decisions_path).read_text())
    assert data["decisions"] == {}, f"expected empty dict; got {data['decisions']}"
    assert isinstance(data["rejected"], list)


# ---------------------------------------------------------------------------
# 20. All 5 prompts exist with required front-matter and schema keys
# ---------------------------------------------------------------------------

_PROMPT_REQUIREMENTS = {
    "b_bull_a.md": ["bull_strength", "entry_zone", "top_3_arguments", "risks_acknowledged", "web_sources_last_7d"],
    "b_bull_b.md": ["bull_strength", "entry_zone", "top_3_arguments", "risks_acknowledged", "web_sources_last_7d"],
    "b_bear_a.md": ["bear_strength", "setup_invalidation_levels", "top_3_arguments", "bull_acknowledgements"],
    "b_bear_b.md": ["bear_strength", "thesis_crack_level", "top_3_arguments", "bull_acknowledgements"],
    "b_judge.md": ["approved", "rejected", "summary", "entry_price", "stop_loss", "target_price", "quantity", "conviction", "rationale", "risk_usd"],
}


def test_all_5_prompts_exist_with_required_keys():
    """Each prompt file exists, has model: sonnet front-matter, and required output-schema keys."""
    for fname, required_keys in _PROMPT_REQUIREMENTS.items():
        p = _PROMPTS_DIR / fname
        assert p.exists(), f"Prompt file missing: {p}"

        content = p.read_text()

        assert "model: sonnet" in content, (
            f"{fname}: missing 'model: sonnet' in YAML front-matter"
        )

        for key in required_keys:
            assert key in content, (
                f"{fname}: missing required output-schema key '{key}'"
            )


# ---------------------------------------------------------------------------
# 21. CLI runner --help
# ---------------------------------------------------------------------------

def test_cli_runner_help():
    """b_stage3 CLI responds to --help with exit code 0 and expected flags."""
    venv_python = str(_PROJECT_ROOT / ".venv" / "bin" / "python")
    proc = subprocess.run(
        [venv_python, "-m", "ai_hedge.runner.b_stage3", "--help"],
        capture_output=True,
        text=True,
        cwd=str(_PROJECT_ROOT),
    )
    assert proc.returncode == 0, (
        f"--help exited with code {proc.returncode}; stderr: {proc.stderr}"
    )
    assert "--run-id" in proc.stdout, f"expected '--run-id' in help; got:\n{proc.stdout}"
    assert "--finalize" in proc.stdout, f"expected '--finalize' in help; got:\n{proc.stdout}"
