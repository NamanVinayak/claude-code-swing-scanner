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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from ai_hedge.data.api import (
    get_insider_trades,
    get_intraday_prices,
    get_market_cap,
    get_prices,
    intraday_to_df,
    prices_to_df,
)
from ai_hedge.data.earnings_calendar import days_until_next_earnings
from ai_hedge.data.indicators import compute_daily_indicators
from ai_hedge.scanners.budget_calculator import compute_risk_budget

logger = logging.getLogger(__name__)

_PERSPECTIVE_AGENTS = ("b_bull_a", "b_bull_b", "b_bear_a", "b_bear_b")
_NEWS_RESEARCHER_AGENT = "b_news_researcher"


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
    direction: str = "long"  # "long" or "short" — defaults to long for back-compat with old runs


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
        direction = str(item.get("direction", "long")).lower()
        if direction not in ("long", "short"):
            logger.warning(
                "Invalid direction %r for %s in today_watchlist; defaulting to 'long'",
                direction, ticker,
            )
            direction = "long"
        entries.append(TodayWatchlistEntry(
            ticker=ticker,
            setup_type=str(item.get("setup_type", "unknown")),
            watch_level=float(wl) if wl is not None else None,
            invalidation_level=float(inv) if inv is not None else None,
            catalyst_note=str(item.get("catalyst_note", "")),
            conviction=int(item.get("conviction", 5)),
            source_reasons=list(item.get("source_reasons", [])),
            direction=direction,
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
        "direction": entry.direction,
    }


def _fetch_recent_news_7d(ticker: str, *, max_items: int = 10) -> list[dict]:
    """Fetch the last 7 days of company news for a ticker.

    Returns a list of dicts with: title, source, date, url, sentiment.
    Empty list on any failure (no API key, network error, no news).
    Cap at max_items most recent.
    """
    from datetime import datetime, timedelta
    from ai_hedge.data.api import get_company_news

    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        start_str = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        news = get_company_news(ticker, end_date=today_str, start_date=start_str, limit=max_items)
    except Exception as exc:
        logger.warning("recent_news_7d fetch failed for %s: %s", ticker, exc)
        return []

    result = []
    for n in news[:max_items]:
        result.append({
            "title": n.title,
            "source": n.source,
            "date": n.date,
            "url": n.url,
            "sentiment": n.sentiment,
        })
    return result


def _build_market_data_bundle(ticker: str) -> dict:
    """Pull prices, compute indicators, fetch insiders + earnings + market cap.

    Defensive — returns a partial bundle on partial failure so a single bad
    fetch never starves the perspective/judge of all market context.
    """
    bundle: dict = {
        "current_price": None,
        "market_cap": None,
        "recent_prices_5d": [],
        "daily_indicators": {},
        "hourly_indicators": {},
        "recent_insider_trades": [],
        "earnings": {"days_until_next": None, "days_since_last": None},
    }

    today_str = datetime.now().strftime("%Y-%m-%d")

    # Daily prices + indicators (last ~400 calendar days for full indicator history)
    try:
        start = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
        prices = get_prices(ticker, start_date=start, end_date=today_str)
        if prices:
            daily_df = prices_to_df(prices)
            if not daily_df.empty:
                bundle["current_price"] = float(daily_df["close"].iloc[-1])
                bundle["daily_indicators"] = compute_daily_indicators(daily_df, timeframe="daily")
                bundle["recent_prices_5d"] = [
                    {
                        "time": str(p.time),
                        "open": p.open,
                        "high": p.high,
                        "low": p.low,
                        "close": p.close,
                        "volume": p.volume,
                    }
                    for p in prices[-5:]
                ]
    except Exception as exc:
        logger.warning("daily price/indicator fetch failed for %s: %s", ticker, exc)

    # Hourly indicators (last 1 month of 1h bars)
    try:
        hourly_prices = get_intraday_prices(ticker, interval="1h", period="1mo")
        if hourly_prices:
            hourly_df = intraday_to_df(hourly_prices)
            if not hourly_df.empty and len(hourly_df) >= 21:
                bundle["hourly_indicators"] = compute_daily_indicators(hourly_df, timeframe="hourly")
    except Exception as exc:
        logger.warning("hourly indicator fetch failed for %s: %s", ticker, exc)

    # Market cap
    try:
        mcap = get_market_cap(ticker)
        bundle["market_cap"] = float(mcap) if mcap is not None else None
    except Exception as exc:
        logger.warning("market cap fetch failed for %s: %s", ticker, exc)

    # Insider trades (last 30 days, max 20)
    try:
        start_30 = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        trades = get_insider_trades(ticker, end_date=today_str, start_date=start_30, limit=20)
        bundle["recent_insider_trades"] = [
            t.model_dump() if hasattr(t, "model_dump") else t for t in (trades or [])
        ][:20]
    except Exception as exc:
        logger.warning("insider trades fetch failed for %s: %s", ticker, exc)

    # Earnings
    try:
        dun = days_until_next_earnings(ticker)
        bundle["earnings"]["days_until_next"] = dun
    except Exception as exc:
        logger.warning("earnings fetch failed for %s: %s", ticker, exc)

    return bundle


def build_news_researcher_facts(
    run_id: str,
    entry: TodayWatchlistEntry,
    *,
    runs_dir: str = "runs",
) -> str:
    """Write the small facts file the b_news_researcher sub-agent reads.

    Tiny by design — the news researcher only needs to know what to search
    for, not the full market data bundle. Wiki context is still injected by
    the AGENT_MANIFEST walk in build_all_stage3_facts (if a manifest entry
    is registered for b_news_researcher).
    """
    facts_dir = Path(runs_dir) / run_id / "facts"
    facts_dir.mkdir(parents=True, exist_ok=True)

    bundle = {
        "ticker": entry.ticker,
        "setup_direction": entry.direction,
        "as_of_date": datetime.now().strftime("%Y-%m-%d"),
        "setup_type": entry.setup_type,
        "wiki_context": {},
    }
    path = facts_dir / f"{_NEWS_RESEARCHER_AGENT}__{entry.ticker}.json"
    path.write_text(json.dumps(bundle, indent=2, default=str))
    logger.debug("Wrote news-researcher facts: %s", path)
    return str(path)


def merge_news_into_perspective_facts(
    run_id: str,
    *,
    runs_dir: str = "runs",
) -> dict[str, Any]:
    """Merge each ticker's news researcher output into bull/bear facts files.

    Called AFTER the news researcher sub-agents have written their outputs
    to runs/<run_id>/news/<TICKER>.json (orchestrated by .claude/skills/
    b_decide/SKILL.md Step 1.5). For each perspective facts file
    (b_bull_a/b_bull_b/b_bear_a/b_bear_b __ {TICKER}.json) this function:

      1. Loads the news researcher output for that ticker (if present)
      2. Unions news_items into the bundle's recent_news_7d (dedupe by URL)
      3. Stamps news_source = "finnhub" | "web_research" | "merged"

    Missing news files are not fatal here — the b_decide skill's Step 1.5
    verification is the gate that aborts the run if a researcher skipped
    its job. This function is forward-only: it never removes existing
    Finnhub items.

    Returns a summary dict with per-ticker merge counts.
    """
    facts_dir = Path(runs_dir) / run_id / "facts"
    news_dir = Path(runs_dir) / run_id / "news"

    summary: dict[str, Any] = {
        "run_id": run_id,
        "tickers_merged": [],
        "tickers_no_news_file": [],
        "per_ticker": {},
    }

    if not facts_dir.exists():
        logger.warning("merge_news: facts dir does not exist: %s", facts_dir)
        return summary

    # Collect tickers from existing perspective facts files
    tickers: set[str] = set()
    for agent in _PERSPECTIVE_AGENTS:
        for p in facts_dir.glob(f"{agent}__*.json"):
            t = p.stem.split("__", 1)[1]
            if t:
                tickers.add(t)

    for ticker in sorted(tickers):
        news_path = news_dir / f"{ticker}.json"
        if not news_path.exists():
            summary["tickers_no_news_file"].append(ticker)
            continue

        try:
            news_doc = json.loads(news_path.read_text())
        except Exception as exc:
            logger.warning("merge_news: failed to parse %s: %s", news_path, exc)
            summary["tickers_no_news_file"].append(ticker)
            continue

        web_items = news_doc.get("news_items", []) or []

        # Convert news researcher items to the recent_news_7d shape used by
        # bull/bear bundles. Fields: title, source, date, url, sentiment.
        web_normalized = []
        for item in web_items:
            web_normalized.append({
                "title": item.get("headline", ""),
                "source": "web_research",
                "date": item.get("date", ""),
                "url": item.get("url", ""),
                "sentiment": item.get("sentiment", "neutral"),
                "summary": item.get("summary", ""),
            })

        merged_per_ticker: dict[str, Any] = {
            "finnhub_count": 0,
            "web_count": len(web_normalized),
            "merged_count": 0,
            "news_source": "web_research",
        }

        for agent in _PERSPECTIVE_AGENTS:
            facts_path = facts_dir / f"{agent}__{ticker}.json"
            if not facts_path.exists():
                continue
            try:
                bundle = json.loads(facts_path.read_text())
            except Exception as exc:
                logger.warning("merge_news: failed to parse %s: %s", facts_path, exc)
                continue

            existing = bundle.get("recent_news_7d", []) or []
            merged_per_ticker["finnhub_count"] = len(existing)

            # Dedupe by URL — Finnhub items take precedence on collision
            seen_urls = {it.get("url", "") for it in existing if it.get("url")}
            unioned = list(existing)
            for w in web_normalized:
                u = w.get("url", "")
                if u and u in seen_urls:
                    continue
                unioned.append(w)
                if u:
                    seen_urls.add(u)

            if existing and web_normalized:
                news_source = "merged"
            elif existing:
                news_source = "finnhub"
            elif web_normalized:
                news_source = "web_research"
            else:
                news_source = "none"

            bundle["recent_news_7d"] = unioned
            bundle["news_source"] = news_source

            # Carry along the structured analyst/earnings context from the
            # news researcher so prompts can reference it without reloading
            # the news file themselves.
            bundle["analyst_consensus_web"] = news_doc.get("analyst_consensus", {})
            bundle["earnings_context_web"] = news_doc.get("earnings_context", {})

            facts_path.write_text(json.dumps(bundle, indent=2, default=str))
            merged_per_ticker["merged_count"] = len(unioned)
            merged_per_ticker["news_source"] = news_source

        summary["tickers_merged"].append(ticker)
        summary["per_ticker"][ticker] = merged_per_ticker

    logger.info(
        "merge_news: merged %d tickers, %d missing news files",
        len(summary["tickers_merged"]),
        len(summary["tickers_no_news_file"]),
    )
    return summary


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
        "direction": entry.direction,
        "setup_type": entry.setup_type,
        "watch_level": entry.watch_level,
        "invalidation_level": entry.invalidation_level,
        "catalyst_note": entry.catalyst_note,
        "conviction": entry.conviction,
        "source_reasons": entry.source_reasons,
        "recent_news_7d": _fetch_recent_news_7d(entry.ticker),
        "wiki_context": {},
    }
    bundle.update(_build_market_data_bundle(entry.ticker))
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
            "direction": entry.direction,
            "candidates": candidates_list,
            "perspectives": perspectives_stub,
            "risk_budget": risk_budget_dict,
            "market_context": "",
            "wiki_context": {},
        }
        bundle.update(_build_market_data_bundle(entry.ticker))

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
        # News researcher facts file (tiny — read by the dedicated WebSearch
        # sub-agent dispatched by .claude/skills/b_decide/SKILL.md Step 1.5).
        build_news_researcher_facts(run_id, entry, runs_dir=runs_dir)

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
