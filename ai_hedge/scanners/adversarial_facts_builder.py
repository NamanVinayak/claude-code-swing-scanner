"""Stage 3 facts builders — produces facts files for the 4 perspective agents
and the judge. Wiki injection is called automatically.

No LLM dispatch in this module.

Judge approach: one b_judge__{T}.json per ticker (option b). This fits
the existing inject_context manifest pattern: inject_context walks AGENT_MANIFEST,
finds b_judge__{T}.json, and injects wiki_context for (b_judge, T). The
orchestrator dispatches one judge per ticker, giving it that ticker's
4-perspective outputs plus the pre-computed risk budget.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ai_hedge.scanners.budget_calculator import compute_risk_budget

logger = logging.getLogger(__name__)

_PERSPECTIVE_AGENTS = ("b_bull_a", "b_bull_b", "b_bear_a", "b_bear_b")


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TodayWatchlistEntry:
    """One entry from today_watchlist.json (Stage 2 synthesizer output)."""
    ticker: str
    setup_type: str
    watch_level: float | None
    invalidation_level: float | None
    catalyst_note: str
    conviction: int          # 1-10 from Stage 2
    source_reasons: list[str]


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def load_today_watchlist(run_id: str, runs_dir: str = "runs") -> list[TodayWatchlistEntry]:
    """Load runs/<run_id>/today_watchlist.json. Raises FileNotFoundError if missing."""
    path = Path(runs_dir) / run_id / "today_watchlist.json"
    if not path.exists():
        raise FileNotFoundError(f"today_watchlist.json not found: {path}")

    raw = json.loads(path.read_text())

    # Synthesizer output nests under "today_watchlist" key; accept flat list too
    items = raw if isinstance(raw, list) else raw.get("today_watchlist", [])

    entries: list[TodayWatchlistEntry] = []
    for item in items:
        ticker = str(item.get("ticker", "")).upper().strip()
        if not ticker:
            continue
        # Normalize setup_valid: skip "no" entries (shouldn't be in watchlist but be safe)
        if item.get("setup_valid", "yes").lower() == "no":
            logger.warning("Skipping %s: setup_valid=no in today_watchlist", ticker)
            continue
        wl = item.get("watch_level")
        inv = item.get("invalidation_level")
        entries.append(TodayWatchlistEntry(
            ticker=ticker,
            setup_type=str(item.get("setup_type", "unknown")),
            watch_level=float(wl) if wl is not None else None,
            invalidation_level=float(inv) if inv is not None else None,
            catalyst_note=str(item.get("catalyst_note", "")),
            conviction=int(item.get("conviction", 5)),
            source_reasons=list(item.get("source_reasons", [])),
        ))

    return entries


def _entry_to_dict(entry: TodayWatchlistEntry) -> dict[str, Any]:
    return {
        "ticker": entry.ticker,
        "setup_type": entry.setup_type,
        "watch_level": entry.watch_level,
        "invalidation_level": entry.invalidation_level,
        "catalyst_note": entry.catalyst_note,
        "conviction": entry.conviction,
        "source_reasons": entry.source_reasons,
    }


def build_perspective_facts(
    run_id: str,
    entry: TodayWatchlistEntry,
    *,
    runs_dir: str = "runs",
) -> str:
    """Build facts files for all 4 perspective agents for one ticker.

    Writes 4 identical-content files:
        runs/<run_id>/facts/b_bull_a__<TICKER>.json
        runs/<run_id>/facts/b_bull_b__<TICKER>.json
        runs/<run_id>/facts/b_bear_a__<TICKER>.json
        runs/<run_id>/facts/b_bear_b__<TICKER>.json

    Each agent has the same per-ticker context; their framing differs via their
    prompt, not via what they read. Returns the facts directory path.
    """
    facts_dir = Path(runs_dir) / run_id / "facts"
    facts_dir.mkdir(parents=True, exist_ok=True)

    bundle = {
        "ticker": entry.ticker,
        "setup_type": entry.setup_type,
        "watch_level": entry.watch_level,
        "invalidation_level": entry.invalidation_level,
        "catalyst_note": entry.catalyst_note,
        "conviction": entry.conviction,
        "source_reasons": entry.source_reasons,
        "wiki_context": {},
    }
    content = json.dumps(bundle, indent=2, default=str)

    for agent in _PERSPECTIVE_AGENTS:
        path = facts_dir / f"{agent}__{entry.ticker}.json"
        path.write_text(content)
        logger.debug("Wrote perspective facts: %s", path)

    return str(facts_dir)


def build_judge_facts(
    run_id: str,
    entries: list[TodayWatchlistEntry],
    *,
    runs_dir: str = "runs",
) -> str:
    """Build one judge facts file per ticker.

    Approach (b): writes runs/<run_id>/facts/b_judge__{T}.json for each ticker.
    Each file contains the full candidate list, an empty perspectives stub (the
    orchestrator fills this before dispatching the judge), and the live risk
    budget snapshot. inject_context will inject ticker-specific wiki context.

    Returns the facts directory path.
    """
    facts_dir = Path(runs_dir) / run_id / "facts"
    facts_dir.mkdir(parents=True, exist_ok=True)

    # Compute risk budget once — shared across all judge files
    risk_budget_dict: dict[str, Any] = {}
    try:
        snapshot = compute_risk_budget()
        # Serialize to a plain dict; dataclasses → nested dicts
        def _to_plain(obj) -> Any:
            if hasattr(obj, "__dataclass_fields__"):
                return {k: _to_plain(v) for k, v in asdict(obj).items()}
            if isinstance(obj, list):
                return [_to_plain(i) for i in obj]
            return obj

        risk_budget_dict = _to_plain(snapshot)
    except Exception as exc:
        logger.warning("Could not compute risk budget: %s — using empty dict", exc)
        risk_budget_dict = {"error": str(exc)}

    candidates_list = [_entry_to_dict(e) for e in entries]

    for entry in entries:
        # Perspectives stub: orchestrator fills b_bull_a/b/b_bear_a/b output here
        perspectives_stub: dict[str, Any] = {
            agent: None for agent in _PERSPECTIVE_AGENTS
        }

        bundle = {
            "ticker": entry.ticker,
            "candidates": candidates_list,
            "perspectives": perspectives_stub,
            "risk_budget": risk_budget_dict,
            "market_context": "",
            "wiki_context": {},
        }

        path = facts_dir / f"b_judge__{entry.ticker}.json"
        path.write_text(json.dumps(bundle, indent=2, default=str))
        logger.debug("Wrote judge facts: %s", path)

    return str(facts_dir)


def build_all_stage3_facts(
    run_id: str,
    *,
    runs_dir: str = "runs",
) -> dict[str, Any]:
    """End-to-end builder: loads today_watchlist.json, builds all perspective
    facts files for each ticker, builds the judge facts, runs wiki injection
    on every file. Returns a summary dict with paths + counts.
    """
    from ai_hedge.wiki.inject import inject_context

    entries = load_today_watchlist(run_id, runs_dir=runs_dir)

    if not entries:
        logger.warning("today_watchlist.json is empty — no Stage 3 facts to build")
        return {
            "run_id": run_id,
            "tickers": [],
            "perspective_files_written": 0,
            "judge_files_written": 0,
            "wiki_injection": {"skipped": True, "reason": "empty_watchlist"},
        }

    tickers = [e.ticker for e in entries]
    perspective_count = 0
    judge_count = 0

    for entry in entries:
        build_perspective_facts(run_id, entry, runs_dir=runs_dir)
        perspective_count += len(_PERSPECTIVE_AGENTS)

    build_judge_facts(run_id, entries, runs_dir=runs_dir)
    judge_count = len(entries)

    # Single inject_context call — walks all agents in AGENT_MANIFEST, finds
    # all written files, and merges wiki_context into each.
    inject_result = inject_context(run_id, tickers, mode="b_bull_a")
    logger.info("Wiki injection result: %s", inject_result)

    facts_dir = Path(runs_dir) / run_id / "facts"
    return {
        "run_id": run_id,
        "tickers": tickers,
        "perspective_files_written": perspective_count,
        "judge_files_written": judge_count,
        "facts_dir": str(facts_dir),
        "wiki_injection": inject_result,
    }
