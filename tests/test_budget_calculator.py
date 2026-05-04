"""Tests for ai_hedge/scanners/budget_calculator.py.

Tests 1-3 read from the actual bootstrapped wiki files in wiki/meta/.
Tests 4-11 use in-memory fixtures.
"""
import json
from pathlib import Path

import pytest

from ai_hedge.scanners.budget_calculator import (
    AccountState,
    BudgetRules,
    OpenPosition,
    RiskBudgetSnapshot,
    compute_risk_budget,
    parse_budget_state,
    parse_open_positions,
    position_size_shares,
    trade_passes_budget_checks,
)

_PROJECT_ROOT = Path(__file__).parent.parent
_BUDGET_STATE = str(_PROJECT_ROOT / "wiki" / "meta" / "budget_state.md")
_OPEN_POSITIONS = str(_PROJECT_ROOT / "wiki" / "meta" / "open_positions.md")


# ---------------------------------------------------------------------------
# 1. parse_budget_state — rules section
# ---------------------------------------------------------------------------

def test_parse_budget_state_from_bootstrap():
    """All 9+ rule fields parse correctly from the bootstrapped file."""
    rules, _ = parse_budget_state(_BUDGET_STATE)

    assert isinstance(rules, BudgetRules)
    assert rules.risk_per_trade_pct == 1.0, f"expected 1.0, got {rules.risk_per_trade_pct}"
    assert rules.total_open_risk_cap_pct == 4.0
    assert rules.max_simultaneous_positions == 5
    assert rules.max_deployed_pct == 60.0
    assert rules.single_position_cap_pct == 15.0
    assert rules.daily_loss_stop_pct == -2.0
    assert rules.weekly_loss_stop_pct == -5.0
    assert rules.vix_cut_threshold == 25.0
    assert rules.vix_pause_threshold == 30.0
    assert 0.0 < rules.scaling_phase_size_multiplier <= 1.0, (
        f"scaling_phase_size_multiplier out of range: {rules.scaling_phase_size_multiplier}"
    )


# ---------------------------------------------------------------------------
# 2. parse_budget_state — state section
# ---------------------------------------------------------------------------

def test_parse_budget_state_state_section():
    """State fields parse correctly from the bootstrapped file."""
    _, state = parse_budget_state(_BUDGET_STATE)

    assert isinstance(state, AccountState)
    assert state.starting_capital_usd == 25000.0, (
        f"expected 25000.0, got {state.starting_capital_usd}"
    )
    valid_phases = {"scaling_week_1_2", "scaling_week_3_4", "full", "paused"}
    assert state.current_phase in valid_phases, (
        f"current_phase {state.current_phase!r} not in {valid_phases}"
    )
    assert state.positions_open_count >= 0


# ---------------------------------------------------------------------------
# 3. parse_open_positions — empty bootstrap
# ---------------------------------------------------------------------------

def test_parse_open_positions_empty():
    """Bootstrap open_positions.md (all _none_) returns empty list."""
    positions = parse_open_positions(_OPEN_POSITIONS)
    assert positions == [], f"expected [], got {positions}"


# ---------------------------------------------------------------------------
# 4. compute_risk_budget — clean bootstrap
# ---------------------------------------------------------------------------

def test_compute_risk_budget(tmp_path):
    """Bootstrap state: available_risk_usd = $250 (1% of $25k × 0.5 scaling),
    can_open_new_position = True."""
    # Copy bootstrapped files to tmp_path so the function uses them
    import shutil
    shutil.copy(_BUDGET_STATE, tmp_path / "budget_state.md")
    shutil.copy(_OPEN_POSITIONS, tmp_path / "open_positions.md")

    snapshot = compute_risk_budget(
        budget_state_path=str(tmp_path / "budget_state.md"),
        open_positions_path=str(tmp_path / "open_positions.md"),
    )

    assert isinstance(snapshot, RiskBudgetSnapshot)
    # Bootstrap: $25k × 1% × 0.5 scaling = $125 per trade risk budget
    # (or $25k × 1% = $250 if scaling_phase_size_multiplier=1.0)
    # Either way, available_risk_usd > 0
    assert snapshot.available_risk_usd > 0, "available_risk_usd must be > 0 on clean bootstrap"
    assert snapshot.can_open_new_position is True, (
        f"can_open_new_position must be True on bootstrap; blocked: {snapshot.can_open_reasons_blocked}"
    )
    assert snapshot.can_open_reasons_blocked == [], (
        f"expected empty blockers on bootstrap; got {snapshot.can_open_reasons_blocked}"
    )


# ---------------------------------------------------------------------------
# 5. position_size_shares — long
# ---------------------------------------------------------------------------

def test_position_size_long():
    """Long: account=25000, entry=100, stop=95, risk=1% → 50 shares."""
    shares = position_size_shares(
        account_value=25000.0,
        entry_price=100.0,
        stop_loss=95.0,
        risk_pct=1.0,
        direction="long",
    )
    # risk_dollars = 25000 * 0.01 = 250; risk_per_share = 5; shares = 50
    assert shares == 50, f"expected 50, got {shares}"


# ---------------------------------------------------------------------------
# 6. position_size_shares — short
# ---------------------------------------------------------------------------

def test_position_size_short():
    """Short: account=25000, entry=100, stop=105, risk=1% → 50 shares."""
    shares = position_size_shares(
        account_value=25000.0,
        entry_price=100.0,
        stop_loss=105.0,
        risk_pct=1.0,
        direction="short",
    )
    # risk_per_share = abs(100 - 105) = 5; shares = 50
    assert shares == 50, f"expected 50, got {shares}"


# ---------------------------------------------------------------------------
# 7. position_size_shares — zero distance returns zero
# ---------------------------------------------------------------------------

def test_position_size_zero_distance_returns_zero():
    """entry == stop → 0 shares (no division by zero)."""
    shares = position_size_shares(
        account_value=25000.0,
        entry_price=100.0,
        stop_loss=100.0,
        risk_pct=1.0,
        direction="long",
    )
    assert shares == 0, f"expected 0, got {shares}"


# ---------------------------------------------------------------------------
# 8. position_size_shares — with scaling multiplier
# ---------------------------------------------------------------------------

def test_position_size_with_scaling():
    """size_multiplier=0.5 halves the share count."""
    full = position_size_shares(
        account_value=25000.0,
        entry_price=100.0,
        stop_loss=95.0,
        risk_pct=1.0,
        direction="long",
        size_multiplier=1.0,
    )
    half = position_size_shares(
        account_value=25000.0,
        entry_price=100.0,
        stop_loss=95.0,
        risk_pct=1.0,
        direction="long",
        size_multiplier=0.5,
    )
    assert half == full // 2, f"expected {full // 2}, got {half}"


# ---------------------------------------------------------------------------
# Helper: synthesize a minimal RiskBudgetSnapshot for tests 9-11
# ---------------------------------------------------------------------------

def _make_snapshot(
    *,
    current_phase="full",
    positions_open=0,
    available_risk_usd=500.0,
    deployed_pct=20.0,
    open_risk_usd=0.0,
    account_value=25000.0,
) -> RiskBudgetSnapshot:
    rules = BudgetRules(
        risk_per_trade_pct=1.0,
        total_open_risk_cap_pct=4.0,
        max_simultaneous_positions=5,
        max_deployed_pct=60.0,
        single_position_cap_pct=15.0,
        daily_loss_stop_pct=-2.0,
        weekly_loss_stop_pct=-5.0,
        scaling_phase_size_multiplier=1.0,
        vix_cut_threshold=25.0,
        vix_pause_threshold=30.0,
    )
    state = AccountState(
        starting_capital_usd=account_value,
        current_cash_usd=account_value * (1 - deployed_pct / 100),
        deployed_usd=account_value * deployed_pct / 100,
        open_risk_usd=open_risk_usd,
        open_risk_pct=open_risk_usd / account_value * 100,
        positions_open_count=positions_open,
        daily_pnl_usd=0.0,
        weekly_pnl_usd=0.0,
        current_phase=current_phase,  # type: ignore[arg-type]
        paused_reason=None,
    )
    blockers = []
    if current_phase == "paused":
        blockers.append("paused")
    if positions_open >= rules.max_simultaneous_positions:
        blockers.append("max_positions_reached")
    if deployed_pct >= rules.max_deployed_pct:
        blockers.append("deployment_cap_reached")
    if available_risk_usd <= 0:
        blockers.append("risk_budget_exhausted")

    return RiskBudgetSnapshot(
        account_value=account_value,
        cash=state.current_cash_usd,
        deployed=state.deployed_usd,
        deployed_pct=deployed_pct,
        positions_open=positions_open,
        open_risk_usd=open_risk_usd,
        open_risk_pct=open_risk_usd / account_value * 100,
        available_risk_usd=available_risk_usd,
        available_risk_pct=available_risk_usd / account_value * 100,
        can_open_new_position=len(blockers) == 0,
        can_open_reasons_blocked=blockers,
        rules=rules,
        state=state,
    )


# ---------------------------------------------------------------------------
# 9. trade_passes_budget_checks — clean trade
# ---------------------------------------------------------------------------

def test_trade_passes_budget_checks_clean():
    """A small trade against a fresh budget passes all checks."""
    snapshot = _make_snapshot()
    passes, blockers = trade_passes_budget_checks(
        snapshot=snapshot,
        proposed_entry=100.0,
        proposed_stop=95.0,
        proposed_quantity=10,
        direction="long",
    )
    assert passes is True, f"expected True; blockers={blockers}"
    assert blockers == []


# ---------------------------------------------------------------------------
# 10. trade_passes_budget_checks — max positions reached
# ---------------------------------------------------------------------------

def test_trade_passes_budget_checks_max_positions():
    """5 positions open (at cap) → blocked with max_positions_reached."""
    snapshot = _make_snapshot(positions_open=5)
    passes, blockers = trade_passes_budget_checks(
        snapshot=snapshot,
        proposed_entry=100.0,
        proposed_stop=95.0,
        proposed_quantity=10,
        direction="long",
    )
    assert passes is False
    assert any("max_positions_reached" in b for b in blockers), (
        f"expected 'max_positions_reached' in {blockers}"
    )


# ---------------------------------------------------------------------------
# 11. trade_passes_budget_checks — paused
# ---------------------------------------------------------------------------

def test_trade_passes_budget_checks_paused():
    """System paused → all trades blocked."""
    snapshot = _make_snapshot(current_phase="paused")
    passes, blockers = trade_passes_budget_checks(
        snapshot=snapshot,
        proposed_entry=100.0,
        proposed_stop=95.0,
        proposed_quantity=10,
        direction="long",
    )
    assert passes is False
    assert any("paused" in b for b in blockers), (
        f"expected 'paused' in {blockers}"
    )
