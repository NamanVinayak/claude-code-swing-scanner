"""Tests for tracker/ingest_decisions.py — field passthrough into insert_trade.

Focus: Stage 3's decisions.json fields (target_price_2, direction, setup_type,
expected_holding_days, risk_usd) must reach Turso so the simulator's two-target
trailing logic can fire.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tracker import ingest_decisions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_decisions(runs_dir: Path, run_id: str, decisions: dict, mode: str = "b_swing") -> Path:
    """Write a decisions.json fixture and matching metadata.json."""
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "mode": mode,
        "decisions": decisions,
        "rejected": [],
        "summary": "fixture",
    }
    (run_dir / "decisions.json").write_text(json.dumps(payload, indent=2))
    (run_dir / "metadata.json").write_text(json.dumps({"mode": mode}))
    return run_dir


def _base_decision(**overrides) -> dict:
    """A complete Stage 3 decision dict matching decisions_writer's schema."""
    base = {
        "action": "buy",
        "direction": "long",
        "entry_price": 48.0,
        "stop_loss": 46.0,
        "target_price": 54.0,
        "target_price_2": 58.0,
        "quantity": 5,
        "timeframe": "7d",
        "confidence": 7,
        "account_risk_pct": 1.0,
        "entry_tolerance_pct": 0.5,
        "setup_type": "breakout",
        "rationale": "test",
        "risk_usd": 10.0,
        "expected_holding_days": 7,
    }
    base.update(overrides)
    return base


@pytest.fixture
def isolated_ingester(tmp_path, monkeypatch):
    """Patch ingester module constants + DB calls so main() runs hermetically.

    Yields (runs_dir, captured_inserts) where captured_inserts is a list that
    insert_trade calls accumulate into. create_all_tables and the existing-row
    lookups are stubbed.
    """
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    ingested_file = tmp_path / "ingested_runs.txt"

    monkeypatch.setattr(ingest_decisions, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(ingest_decisions, "INGESTED_FILE", ingested_file)
    monkeypatch.setattr(ingest_decisions, "_existing_run_tickers", lambda run_id: set())
    monkeypatch.setattr(ingest_decisions, "_open_positions_by_ticker_direction", lambda: set())

    captured: list[dict] = []

    def fake_insert_trade(d):
        captured.append(d)
        return len(captured)  # fake row id

    def fake_create_all_tables():
        pass

    # main() does `from tracker.turso_client import create_all_tables, insert_trade`
    # so patch the names on tracker.turso_client (where the import resolves from).
    import tracker.turso_client as tc
    monkeypatch.setattr(tc, "insert_trade", fake_insert_trade)
    monkeypatch.setattr(tc, "create_all_tables", fake_create_all_tables)

    yield runs_dir, captured


# ---------------------------------------------------------------------------
# 1. target_price_2 passthrough (the actual bug)
# ---------------------------------------------------------------------------

def test_ingest_passes_target_price_2_through(isolated_ingester):
    runs_dir, captured = isolated_ingester
    _write_decisions(runs_dir, "run_1", {"STX": _base_decision(target_price_2=125.0)})

    ingest_decisions.main()

    assert len(captured) == 1, f"expected 1 insert; got {len(captured)}"
    assert captured[0]["target_price_2"] == 125.0, (
        f"target_price_2 should pass through; got {captured[0]['target_price_2']!r}"
    )


def test_ingest_handles_missing_target_price_2(isolated_ingester):
    """A decision without target_price_2 (e.g. legacy fixtures) defaults to None."""
    runs_dir, captured = isolated_ingester
    dec = _base_decision()
    dec.pop("target_price_2")
    _write_decisions(runs_dir, "run_legacy", {"STX": dec})

    ingest_decisions.main()

    assert len(captured) == 1
    assert captured[0]["target_price_2"] is None


def test_ingest_handles_explicit_null_target_price_2(isolated_ingester):
    """JSON null on target_price_2 stays None — single-target trade."""
    runs_dir, captured = isolated_ingester
    _write_decisions(runs_dir, "run_null", {"STX": _base_decision(target_price_2=None)})

    ingest_decisions.main()

    assert len(captured) == 1
    assert captured[0]["target_price_2"] is None


# ---------------------------------------------------------------------------
# 2. Direction / setup_type / expected_holding_days passthrough
# ---------------------------------------------------------------------------

def test_ingest_passes_direction_short(isolated_ingester):
    runs_dir, captured = isolated_ingester
    _write_decisions(runs_dir, "run_short", {
        "STX": _base_decision(action="short", direction="short", entry_price=50.0, stop_loss=52.0, target_price=46.0)
    })

    ingest_decisions.main()

    assert len(captured) == 1
    assert captured[0]["direction"] == "short"


def test_ingest_preserves_setup_type_in_raw_decision(isolated_ingester):
    """setup_type has no typed column; it must survive in raw_decision JSON."""
    runs_dir, captured = isolated_ingester
    _write_decisions(runs_dir, "run_setup", {"STX": _base_decision(setup_type="breakout")})

    ingest_decisions.main()

    assert len(captured) == 1
    raw = json.loads(captured[0]["raw_decision"])
    assert raw["setup_type"] == "breakout"


def test_ingest_preserves_expected_holding_days_in_raw_decision(isolated_ingester):
    runs_dir, captured = isolated_ingester
    _write_decisions(runs_dir, "run_hold", {"STX": _base_decision(expected_holding_days=7)})

    ingest_decisions.main()

    assert len(captured) == 1
    raw = json.loads(captured[0]["raw_decision"])
    assert raw["expected_holding_days"] == 7


def test_ingest_preserves_risk_usd_in_raw_decision(isolated_ingester):
    runs_dir, captured = isolated_ingester
    _write_decisions(runs_dir, "run_risk", {"STX": _base_decision(risk_usd=10.0)})

    ingest_decisions.main()

    assert len(captured) == 1
    raw = json.loads(captured[0]["raw_decision"])
    assert raw["risk_usd"] == 10.0


# ---------------------------------------------------------------------------
# 3. Idempotency must still work
# ---------------------------------------------------------------------------

def test_ingest_idempotency_preserved(isolated_ingester):
    """Running the ingester twice on the same run inserts only once."""
    runs_dir, captured = isolated_ingester
    _write_decisions(runs_dir, "run_dup", {"STX": _base_decision(target_price_2=200.0)})

    ingest_decisions.main()
    ingest_decisions.main()

    assert len(captured) == 1, f"second run should be a no-op; got {len(captured)} inserts"
    assert captured[0]["target_price_2"] == 200.0


# ---------------------------------------------------------------------------
# 4. End-to-end: every field the simulator needs lands on the row
# ---------------------------------------------------------------------------

def test_ingest_full_field_passthrough(isolated_ingester):
    """One sanity check that confirms all the fields the bug touched arrive together."""
    runs_dir, captured = isolated_ingester
    _write_decisions(runs_dir, "run_full", {
        "STX": _base_decision(
            target_price_2=58.0,
            direction="long",
            setup_type="trend_continuation",
            expected_holding_days=10,
            risk_usd=10.0,
        )
    })

    ingest_decisions.main()

    assert len(captured) == 1
    row = captured[0]
    assert row["target_price_2"] == 58.0
    assert row["direction"] == "long"
    assert row["entry_price"] == 48.0
    assert row["stop_loss"] == 46.0
    assert row["target_price"] == 54.0
    assert row["quantity"] == 5
    assert row["timeframe"] == "7d"
    assert row["confidence"] == 7
    assert row["status"] == "pending"

    raw = json.loads(row["raw_decision"])
    assert raw["setup_type"] == "trend_continuation"
    assert raw["expected_holding_days"] == 10
    assert raw["risk_usd"] == 10.0
