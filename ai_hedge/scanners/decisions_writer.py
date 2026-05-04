"""Decisions writer — produces runs/<run_id>/decisions.json in the schema
tracker/ingest_decisions.py expects.

The judge agent (LLM) writes its raw output to runs/<run_id>/judge_output.json.
This module reads that file and produces decisions.json with the right field
names so the existing simulator and ingester pick it up.

Schema verified against tracker/ingest_decisions.py:
  decisions_data["decisions"] is a DICT keyed by ticker (not a list).
  Each value has action="buy" (for long) or action="short".
  Other fields read by the ingester: entry_price, stop_loss, target_price,
  quantity, timeframe, confidence, entry_tolerance_pct, account_risk_pct.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from ai_hedge.scanners.budget_calculator import compute_risk_budget, trade_passes_budget_checks

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TradeDecision:
    """One approved trade in System A simulator's schema."""
    ticker: str
    action: Literal["buy", "short"]      # ingester reads "buy" or "short"
    direction: Literal["long", "short"]
    entry_price: float
    stop_loss: float
    target_price: float
    target_price_2: float | None
    quantity: int
    expected_holding_days: int   # swing range: 2-20
    setup_type: str
    conviction: int              # 1-10
    rationale: str               # one paragraph
    risk_usd: float              # quantity * abs(entry - stop)


def _parse_approved_trade(item: dict) -> TradeDecision | None:
    """Parse one element from judge_output.approved into a TradeDecision.

    Returns None if any required field is missing or invalid.
    """
    try:
        ticker = str(item.get("ticker", "")).upper().strip()
        if not ticker:
            return None

        direction_raw = str(item.get("direction", "long")).lower()
        if direction_raw not in ("long", "short"):
            logger.warning("Trade %s: unknown direction %r — skipping", ticker, direction_raw)
            return None
        direction: Literal["long", "short"] = direction_raw  # type: ignore[assignment]

        # Map direction to action for ingester compatibility
        action: Literal["buy", "short"] = "buy" if direction == "long" else "short"

        entry_price = float(item["entry_price"])
        stop_loss = float(item["stop_loss"])
        target_price = float(item["target_price"])
        target_price_2_raw = item.get("target_price_2")
        target_price_2 = float(target_price_2_raw) if target_price_2_raw is not None else None
        quantity = int(item["quantity"])
        expected_holding_days = int(item.get("expected_holding_days", 7))
        setup_type = str(item.get("setup_type", "unknown"))
        conviction = int(item.get("conviction", 5))
        rationale = str(item.get("rationale", ""))
        risk_usd = float(item.get("risk_usd", quantity * abs(entry_price - stop_loss)))

        return TradeDecision(
            ticker=ticker,
            action=action,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_price=target_price,
            target_price_2=target_price_2,
            quantity=quantity,
            expected_holding_days=expected_holding_days,
            setup_type=setup_type,
            conviction=conviction,
            rationale=rationale,
            risk_usd=risk_usd,
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Could not parse approved trade %r: %s", item, exc)
        return None


def write_decisions(
    run_id: str,
    *,
    judge_output_path: str | None = None,
    runs_dir: str = "runs",
) -> str:
    """Read judge_output.json (orchestrator-produced) and write decisions.json.

    The judge_output.json shape expected (orchestrator combines per-ticker outputs):
    {
      "approved": [
        {ticker, direction, entry_price, stop_loss, target_price,
         target_price_2, quantity, conviction, setup_type,
         rationale, expected_holding_days, risk_usd},
        ...
      ],
      "rejected": [{ticker, reason}, ...],
      "summary": "..."
    }

    Returns the path written.

    Defensive budget double-check: any approved trade that fails budget checks
    is moved to rejected with reason 'budget_check_failed' and a warning is logged.
    """
    run_dir = Path(runs_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    if judge_output_path is None:
        judge_output_path = str(run_dir / "judge_output.json")

    raw = json.loads(Path(judge_output_path).read_text())

    approved_raw: list[dict] = raw.get("approved", []) or []
    rejected_raw: list[dict] = list(raw.get("rejected", []) or [])
    summary: str = str(raw.get("summary", ""))

    # Parse approved trades
    trades: list[TradeDecision] = []
    for item in approved_raw:
        td = _parse_approved_trade(item)
        if td is None:
            rejected_raw.append({
                "ticker": item.get("ticker", "unknown"),
                "reason": "parse_failed",
            })
            continue
        trades.append(td)

    # Defensive budget re-check
    budget_snapshot = None
    try:
        budget_snapshot = compute_risk_budget()
    except Exception as exc:
        logger.warning("Could not compute budget for double-check: %s", exc)

    final_approved: list[TradeDecision] = []
    if budget_snapshot is not None:
        for td in trades:
            passes, blockers = trade_passes_budget_checks(
                snapshot=budget_snapshot,
                proposed_entry=td.entry_price,
                proposed_stop=td.stop_loss,
                proposed_quantity=td.quantity,
                direction=td.direction,
            )
            if passes:
                final_approved.append(td)
            else:
                reason_str = "budget_check_failed: " + "; ".join(blockers)
                logger.warning(
                    "Trade %s failed post-judge budget check: %s", td.ticker, reason_str
                )
                rejected_raw.append({"ticker": td.ticker, "reason": reason_str})
    else:
        # No budget snapshot — pass all through (can't verify)
        final_approved = trades

    # Hard cap: max 3 per fire — sort by conviction descending then take top 3
    if len(final_approved) > 3:
        logger.warning(
            "Judge approved %d trades but hard cap is 3; culling to top 3 by conviction",
            len(final_approved),
        )
        final_approved.sort(key=lambda t: -t.conviction)
        culled = final_approved[3:]
        final_approved = final_approved[:3]
        for td in culled:
            rejected_raw.append({"ticker": td.ticker, "reason": "max_decisions_per_fire_exceeded"})

    # Build decisions dict (ingester format: dict keyed by ticker)
    decisions_dict: dict[str, dict] = {}
    for td in final_approved:
        decisions_dict[td.ticker] = {
            "action": td.action,
            "direction": td.direction,
            "entry_price": td.entry_price,
            "stop_loss": td.stop_loss,
            "target_price": td.target_price,
            "target_price_2": td.target_price_2,
            "quantity": td.quantity,
            "timeframe": f"{td.expected_holding_days}d",
            "confidence": td.conviction,
            "account_risk_pct": 1.0,
            "entry_tolerance_pct": 0.5,
            "setup_type": td.setup_type,
            "rationale": td.rationale,
            "risk_usd": td.risk_usd,
            "expected_holding_days": td.expected_holding_days,
        }

    # Read mode from metadata.json if present (ingester reads mode from there)
    mode = "b_swing"
    meta_path = run_dir / "metadata.json"
    if meta_path.exists():
        try:
            mode = json.loads(meta_path.read_text()).get("mode", "b_swing")
        except Exception:
            pass

    output = {
        "run_id": run_id,
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decisions": decisions_dict,
        "rejected": rejected_raw,
        "summary": summary,
    }

    decisions_path = run_dir / "decisions.json"
    decisions_path.write_text(json.dumps(output, indent=2, default=str))
    logger.info(
        "Wrote decisions.json: %d approved, %d rejected → %s",
        len(decisions_dict),
        len(rejected_raw),
        decisions_path,
    )
    return str(decisions_path)
