"""Budget calculator — parses wiki/meta/budget_state.md and open_positions.md
and computes how much risk is available for new trades right now.

The judge agent reads the output of these functions in its facts bundle.
LLM decisions are bounded by hard math; the LLM cannot exceed limits the
judge sees here.

WARNING: parsers in this module are tightly coupled to the markdown templates
in ai_hedge/wiki/templates.py (budget_state_template) and the bootstrap-script
output for open_positions.md. If those templates change, update the parsers.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class BudgetRules:
    """The locked-in capital allocation rules. Parsed from budget_state.md."""
    risk_per_trade_pct: float        # 1.0
    total_open_risk_cap_pct: float   # 4.0
    max_simultaneous_positions: int  # 5
    max_deployed_pct: float          # 60.0
    single_position_cap_pct: float   # 15.0
    daily_loss_stop_pct: float       # -2.0
    weekly_loss_stop_pct: float      # -5.0
    scaling_phase_size_multiplier: float  # 0.5 if scaling_week_1_2, 0.75 if _3_4, 1.0 otherwise
    vix_cut_threshold: float         # 25
    vix_pause_threshold: float       # 30


@dataclass(frozen=True)
class AccountState:
    """Live account snapshot. Parsed from budget_state.md."""
    starting_capital_usd: float
    current_cash_usd: float
    deployed_usd: float
    open_risk_usd: float
    open_risk_pct: float
    positions_open_count: int
    daily_pnl_usd: float | None
    weekly_pnl_usd: float | None
    current_phase: Literal["scaling_week_1_2", "scaling_week_3_4", "full", "paused"]
    paused_reason: str | None  # set if current_phase == "paused"


@dataclass(frozen=True)
class OpenPosition:
    """One open position parsed from open_positions.md."""
    ticker: str
    direction: Literal["long", "short"]
    entry_price: float
    stop_loss: float
    quantity: int
    risk_usd: float
    sector: str | None


@dataclass(frozen=True)
class RiskBudgetSnapshot:
    """Computed snapshot of how much new risk is available right now."""
    account_value: float
    cash: float
    deployed: float
    deployed_pct: float
    positions_open: int
    open_risk_usd: float
    open_risk_pct: float
    available_risk_usd: float    # min(account*4% - open_risk, account*1%) clamped to >=0
    available_risk_pct: float
    can_open_new_position: bool  # true if positions < max AND deployed < cap AND not paused
    can_open_reasons_blocked: list[str]  # ["max_positions_reached", "deployment_cap_reached", ...]
    rules: BudgetRules
    state: AccountState


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_section(text: str, header: str) -> str:
    """Extract content of a markdown section `## {header}` up to the next `##` or EOF."""
    pattern = re.compile(
        r"##\s+" + re.escape(header) + r"\s*\n(.*?)(?=\n##\s|\Z)",
        re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else ""


def _parse_dollar(s: str) -> float:
    """Parse '$25,000' or '$0 (0.0% of account)' or '-$500' to float."""
    s = s.strip()
    # Strip leading $ or -$ and any trailing parenthetical
    m = re.match(r"[-–]?\$?([\d,]+(?:\.\d+)?)", s)
    if not m:
        raise ValueError(f"Cannot parse dollar value from: {s!r}")
    value = float(m.group(1).replace(",", ""))
    if s.startswith("-") or s.startswith("–"):
        value = -value
    return value


def _parse_pct(s: str) -> float:
    """Parse '1.0%' or '-2%' → float (keeps sign, strips %)."""
    s = s.strip()
    m = re.match(r"([-–]?[\d.]+)\s*%", s)
    if not m:
        raise ValueError(f"Cannot parse pct from: {s!r}")
    value = float(m.group(1).replace("–", "-"))
    return value


def _require(val, name: str):
    """Raise ValueError if val is None."""
    if val is None:
        raise ValueError(f"budget_state.md: missing required field '{name}'")
    return val


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def parse_budget_state(
    path: str = "wiki/meta/budget_state.md",
) -> tuple[BudgetRules, AccountState]:
    """Parse the budget_state.md markdown file.

    Returns the parsed rules + current state. Raises ValueError if the file
    structure has drifted from the template (parser fails fast on schema changes).
    """
    text = Path(path).read_text()

    # --- Rules section -------------------------------------------------------
    rules_text = _get_section(text, "Rules (locked)")
    if not rules_text:
        raise ValueError("budget_state.md: missing '## Rules (locked)' section")

    def _find_rule(pattern: str, label: str) -> str:
        m = re.search(pattern, rules_text, re.IGNORECASE)
        if not m:
            raise ValueError(f"budget_state.md: missing required rule '{label}'")
        return m.group(1)

    risk_per_trade_pct = float(_find_rule(
        r"Risk per trade max:\s*([\d.]+)\s*%", "Risk per trade max"
    ))
    total_open_risk_cap_pct = float(_find_rule(
        r"Total open risk cap:\s*([\d.]+)\s*%", "Total open risk cap"
    ))
    max_simultaneous_positions = int(_find_rule(
        r"Max simultaneous positions:\s*(\d+)", "Max simultaneous positions"
    ))
    max_deployed_pct = float(_find_rule(
        r"Max %\s*deployed:\s*([\d.]+)\s*%", "Max % deployed"
    ))
    single_position_cap_pct = float(_find_rule(
        r"Single-position cap:\s*([\d.]+)\s*%", "Single-position cap"
    ))
    daily_loss_stop_pct = float(_find_rule(
        r"Daily loss stop:\s*([-–\d.]+)\s*%", "Daily loss stop"
    ).replace("–", "-"))
    weekly_loss_stop_pct = float(_find_rule(
        r"Weekly loss stop:\s*([-–\d.]+)\s*%", "Weekly loss stop"
    ).replace("–", "-"))

    # VIX thresholds from the Volatility rule line
    vix_m = re.search(r"VIX\s*[>]\s*(\d+)\s*[→\-]+\s*cut size", rules_text, re.IGNORECASE)
    vix_cut_threshold = float(vix_m.group(1)) if vix_m else 25.0

    vix_p = re.search(r"VIX\s*[>]\s*(\d+)\s*[→\-]+\s*no new entries", rules_text, re.IGNORECASE)
    vix_pause_threshold = float(vix_p.group(1)) if vix_p else 30.0

    # --- Scaling phase section -----------------------------------------------
    scaling_text = _get_section(text, "Scaling phase")
    phase_match = re.search(
        r"Phase:\s*(scaling_week_1_2|scaling_week_3_4|full|paused)", scaling_text
    )
    if not phase_match:
        raise ValueError("budget_state.md: missing 'Phase:' in '## Scaling phase' section")
    current_phase_raw = phase_match.group(1)

    multiplier_map = {
        "scaling_week_1_2": 0.5,
        "scaling_week_3_4": 0.75,
        "full": 1.0,
        "paused": 0.0,
    }
    # Prefer explicit Size multiplier line if present
    mult_match = re.search(r"Size multiplier:\s*([\d.]+)", scaling_text)
    if mult_match:
        scaling_phase_size_multiplier = float(mult_match.group(1))
    else:
        scaling_phase_size_multiplier = multiplier_map.get(current_phase_raw, 1.0)

    rules = BudgetRules(
        risk_per_trade_pct=risk_per_trade_pct,
        total_open_risk_cap_pct=total_open_risk_cap_pct,
        max_simultaneous_positions=max_simultaneous_positions,
        max_deployed_pct=max_deployed_pct,
        single_position_cap_pct=single_position_cap_pct,
        daily_loss_stop_pct=daily_loss_stop_pct,
        weekly_loss_stop_pct=weekly_loss_stop_pct,
        scaling_phase_size_multiplier=scaling_phase_size_multiplier,
        vix_cut_threshold=vix_cut_threshold,
        vix_pause_threshold=vix_pause_threshold,
    )

    # --- Current account state section ----------------------------------------
    state_text = _get_section(text, "Current account state")
    if not state_text:
        raise ValueError("budget_state.md: missing '## Current account state' section")

    def _table_row(section_text: str, field_label: str) -> str | None:
        """Extract value cell from a markdown table row matching field_label."""
        m = re.search(
            r"\|\s*" + re.escape(field_label) + r"\s*\|\s*([^|\n]+?)\s*\|",
            section_text,
            re.IGNORECASE,
        )
        return m.group(1).strip() if m else None

    starting_raw = _table_row(state_text, "Starting capital")
    starting_capital_usd = _parse_dollar(_require(starting_raw, "Starting capital"))

    cash_raw = _table_row(state_text, "Cash on hand")
    current_cash_usd = _parse_dollar(_require(cash_raw, "Cash on hand"))

    deployed_raw = _table_row(state_text, "Deployed")
    deployed_usd = _parse_dollar(_require(deployed_raw, "Deployed"))

    # "Open risk | $0 (0.0% of account)" — extract dollar + pct
    risk_raw = _table_row(state_text, "Open risk")
    open_risk_raw = _require(risk_raw, "Open risk")
    open_risk_usd = _parse_dollar(open_risk_raw)
    pct_in_risk = re.search(r"\(([\d.]+)%", open_risk_raw)
    open_risk_pct = float(pct_in_risk.group(1)) if pct_in_risk else (
        (open_risk_usd / starting_capital_usd * 100.0) if starting_capital_usd else 0.0
    )

    pos_raw = _table_row(state_text, "Positions open")
    positions_open_count = int(_require(pos_raw, "Positions open").replace(",", ""))

    # --- Today's status section -----------------------------------------------
    status_text = _get_section(text, "Today's status")

    paused_match = re.search(r"Paused:\s*(\S+)", status_text, re.IGNORECASE)
    paused_str = paused_match.group(1).lower().rstrip(".,") if paused_match else "no"
    # Detect paused reason (e.g., "Paused: yes — hit daily loss stop")
    paused_reason_match = re.search(
        r"Paused:\s*yes\s*[-–—]+\s*(.+)", status_text, re.IGNORECASE
    )
    paused_reason = paused_reason_match.group(1).strip() if paused_reason_match else None

    daily_pnl_usd: float | None = None
    daily_match = re.search(r"Daily P&L:\s*([^\n]+)", status_text, re.IGNORECASE)
    if daily_match:
        try:
            daily_pnl_usd = _parse_dollar(daily_match.group(1).strip())
        except ValueError:
            daily_pnl_usd = None

    weekly_pnl_usd: float | None = None
    weekly_match = re.search(r"Weekly P&L:\s*([^\n]+)", status_text, re.IGNORECASE)
    if weekly_match:
        try:
            weekly_pnl_usd = _parse_dollar(weekly_match.group(1).strip())
        except ValueError:
            weekly_pnl_usd = None

    # Determine phase (paused overrides scaling phase)
    if paused_str in ("yes", "true", "1"):
        current_phase: Literal["scaling_week_1_2", "scaling_week_3_4", "full", "paused"] = "paused"
    else:
        phase_valid: set[str] = {"scaling_week_1_2", "scaling_week_3_4", "full", "paused"}
        if current_phase_raw in phase_valid:
            current_phase = current_phase_raw  # type: ignore[assignment]
        else:
            current_phase = "full"

    state = AccountState(
        starting_capital_usd=starting_capital_usd,
        current_cash_usd=current_cash_usd,
        deployed_usd=deployed_usd,
        open_risk_usd=open_risk_usd,
        open_risk_pct=open_risk_pct,
        positions_open_count=positions_open_count,
        daily_pnl_usd=daily_pnl_usd,
        weekly_pnl_usd=weekly_pnl_usd,
        current_phase=current_phase,
        paused_reason=paused_reason,
    )

    return rules, state


def parse_open_positions(
    path: str = "wiki/meta/open_positions.md",
) -> list[OpenPosition]:
    """Parse open_positions.md. Returns empty list if no positions or bootstrap state.

    Robust to absent file (returns []). Raises ValueError on malformed table rows.
    """
    p = Path(path)
    if not p.exists():
        return []

    text = p.read_text()
    section = _get_section(text, "Open positions")

    # Bootstrap / empty state
    if not section or "_none_" in section or "0 positions" in section:
        return []

    # Look for a markdown table — header row followed by separator followed by data
    lines = section.splitlines()
    data_rows: list[str] = []
    header_cols: list[str] = []
    past_separator = False

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not past_separator:
            if all(re.match(r"^[-:]+$", c) for c in cells if c):
                past_separator = True
                continue
            # This is the header row
            header_cols = [c.lower().replace(" ", "_") for c in cells]
        else:
            data_rows.append(stripped)

    if not data_rows:
        return []

    positions: list[OpenPosition] = []
    for row in data_rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if not any(c for c in cells):
            continue
        if "_pending_" in cells[0]:
            continue

        def _cell(idx: int, name: str) -> str:
            if idx >= len(cells):
                raise ValueError(
                    f"open_positions.md: row '{row}' missing column {idx} ({name})"
                )
            return cells[idx].strip()

        try:
            ticker = _cell(0, "ticker").upper()
            dir_raw = _cell(1, "direction").lower()
            if dir_raw not in ("long", "short"):
                raise ValueError(
                    f"open_positions.md: unknown direction '{dir_raw}' for {ticker}"
                )
            direction: Literal["long", "short"] = dir_raw  # type: ignore[assignment]
            entry_price = float(_cell(2, "entry").replace("$", "").replace(",", ""))
            stop_loss = float(_cell(3, "stop").replace("$", "").replace(",", ""))
            quantity = int(_cell(4, "quantity").replace(",", ""))
            risk_usd = float(_cell(5, "risk_usd").replace("$", "").replace(",", ""))
            sector_raw = _cell(6, "sector") if len(cells) > 6 else ""
            sector = sector_raw if sector_raw and sector_raw != "_" else None
        except (ValueError, IndexError) as exc:
            raise ValueError(
                f"open_positions.md: malformed row '{row}': {exc}"
            ) from exc

        positions.append(OpenPosition(
            ticker=ticker,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            quantity=quantity,
            risk_usd=risk_usd,
            sector=sector,
        ))

    return positions


def compute_risk_budget(
    *,
    budget_state_path: str = "wiki/meta/budget_state.md",
    open_positions_path: str = "wiki/meta/open_positions.md",
) -> RiskBudgetSnapshot:
    """Compute the live risk budget snapshot the judge reads."""
    rules, state = parse_budget_state(budget_state_path)
    positions = parse_open_positions(open_positions_path)

    account_value = state.starting_capital_usd  # use starting as account value baseline
    cash = state.current_cash_usd
    deployed = state.deployed_usd
    deployed_pct = (deployed / account_value * 100.0) if account_value else 0.0

    open_risk_usd = state.open_risk_usd
    open_risk_pct = state.open_risk_pct

    # Available risk = min(total_cap - used, per_trade_max) * size_multiplier, floor 0
    total_risk_cap_usd = account_value * rules.total_open_risk_cap_pct / 100.0
    per_trade_risk_usd = account_value * rules.risk_per_trade_pct / 100.0 * rules.scaling_phase_size_multiplier
    available_risk_usd = max(0.0, min(total_risk_cap_usd - open_risk_usd, per_trade_risk_usd))
    available_risk_pct = (available_risk_usd / account_value * 100.0) if account_value else 0.0

    blocked: list[str] = []
    if state.current_phase == "paused":
        blocked.append("paused")
    if state.positions_open_count >= rules.max_simultaneous_positions:
        blocked.append("max_positions_reached")
    if deployed_pct >= rules.max_deployed_pct:
        blocked.append("deployment_cap_reached")
    if available_risk_usd <= 0:
        blocked.append("risk_budget_exhausted")

    return RiskBudgetSnapshot(
        account_value=account_value,
        cash=cash,
        deployed=deployed,
        deployed_pct=deployed_pct,
        positions_open=state.positions_open_count,
        open_risk_usd=open_risk_usd,
        open_risk_pct=open_risk_pct,
        available_risk_usd=available_risk_usd,
        available_risk_pct=available_risk_pct,
        can_open_new_position=len(blocked) == 0,
        can_open_reasons_blocked=blocked,
        rules=rules,
        state=state,
    )


def position_size_shares(
    *,
    account_value: float,
    entry_price: float,
    stop_loss: float,
    risk_pct: float,
    direction: Literal["long", "short"],
    size_multiplier: float = 1.0,
) -> int:
    """Compute integer share count for a proposed trade.

        risk_dollars = account_value * (risk_pct / 100) * size_multiplier
        risk_per_share = abs(entry_price - stop_loss)
        shares = floor(risk_dollars / risk_per_share)

    Returns 0 if entry == stop (zero-distance) or risk_dollars <= 0.
    """
    risk_per_share = abs(entry_price - stop_loss)
    if risk_per_share == 0.0:
        return 0
    risk_dollars = account_value * (risk_pct / 100.0) * size_multiplier
    if risk_dollars <= 0:
        return 0
    return math.floor(risk_dollars / risk_per_share)


SMALL_SCALED_CAP_PCT = 20.0  # extended single-position cap for small_scaled trades (Fix 3)


def trade_passes_budget_checks(
    *,
    snapshot: RiskBudgetSnapshot,
    proposed_entry: float,
    proposed_stop: float,
    proposed_quantity: int,
    direction: Literal["long", "short"],
    position_size_class: Literal["standard", "small_scaled"] = "standard",
) -> tuple[bool, list[str]]:
    """Apply hard budget checks to a proposed trade.

    Returns (passes, blockers) where blockers is a list of human-readable
    reasons the trade was rejected (empty if passes=True).

    Checks (in order, all must pass):
      1. Account is not paused
      2. Open positions < max_simultaneous_positions
      3. New trade risk <= available_risk_usd
      4. Single-position notional <= effective_cap, where:
           - standard: account * single_position_cap_pct (15%)
           - small_scaled: account * SMALL_SCALED_CAP_PCT (20%)
      5. Total deployed (after this trade) <= account * max_deployed_pct
      6. Quantity >= 1
    """
    blockers: list[str] = []

    if snapshot.state.current_phase == "paused":
        blockers.append("paused")

    if snapshot.positions_open >= snapshot.rules.max_simultaneous_positions:
        blockers.append("max_positions_reached")

    trade_risk_usd = proposed_quantity * abs(proposed_entry - proposed_stop)
    if trade_risk_usd > snapshot.available_risk_usd:
        blockers.append(
            f"risk_budget_exceeded (trade_risk=${trade_risk_usd:.2f} > "
            f"available=${snapshot.available_risk_usd:.2f})"
        )

    notional = proposed_entry * proposed_quantity
    effective_cap_pct = (
        SMALL_SCALED_CAP_PCT
        if position_size_class == "small_scaled"
        else snapshot.rules.single_position_cap_pct
    )
    single_cap = snapshot.account_value * effective_cap_pct / 100.0
    if notional > single_cap:
        blockers.append(
            f"single_position_cap_exceeded (notional=${notional:.2f} > "
            f"cap=${single_cap:.2f}, class={position_size_class}, cap_pct={effective_cap_pct:.0f}%)"
        )

    new_deployed = snapshot.deployed + notional
    deploy_cap = snapshot.account_value * snapshot.rules.max_deployed_pct / 100.0
    if new_deployed > deploy_cap:
        blockers.append(
            f"deployment_cap_reached (would_deploy=${new_deployed:.2f} > cap=${deploy_cap:.2f})"
        )

    if proposed_quantity < 1:
        blockers.append("zero_quantity")

    passes = len(blockers) == 0
    return passes, blockers
