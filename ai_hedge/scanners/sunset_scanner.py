"""Stage 1 Sunset Scanner — System B's universe → candidates funnel.

Runs late afternoon Pacific (after market close). Combines TradingView
signal screens with Capitol Trades disclosures. Pure-Python — no LLM
calls in this module. The orchestrator (Desktop Scheduled Task) is
responsible for dispatching the synthesizer agent that turns the diagnostic
output into `wiki/macro/scanner_state.md` content.

All public functions are pure-data and idempotent (within their cache TTL).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from zoneinfo import ZoneInfo

from ai_hedge.data.capitol_trades import get_recent_trades
from ai_hedge.data.tradingview import find_signals, screen_universe

logger = logging.getLogger(__name__)

_PT = ZoneInfo("America/Los_Angeles")


# --- Public types -----------------------------------------------------------

@dataclass(frozen=True)
class ScanConfig:
    # Universe filters
    min_price: float = 5.0
    min_avg_volume: int = 500_000
    min_market_cap_usd: float = 1_000_000_000
    max_universe_size: int = 500  # cap the base universe pull from TradingView

    # Signal universe (which find_signals kinds to query)
    signals: tuple[str, ...] = (
        "strong_buy",
        "strong_sell",
        "oversold",
        "overbought",
        "breakout_up",
        "breakout_down",
        "trending_up",
        "trending_down",
    )
    signals_max_per_kind: int = 50

    # Capitol Trades filters
    capitol_trades_enabled: bool = True
    capitol_trades_days_back: int = 30
    capitol_trades_max_pages: int = 10

    # Scoring + output
    min_reasons_to_advance: int = 2
    max_candidates: int = 40


@dataclass
class Candidate:
    ticker: str
    exchange: str
    last_close: float
    market_cap_usd: float | None
    volume: int | None
    change_pct_today: float | None
    reasons: list[str] = field(default_factory=list)
    tradingview_recommendation: str | None = None
    capitol_buys_30d: int = 0  # how many distinct politicians bought in last 30d
    capitol_buys_politicians: list[str] = field(default_factory=list)

    @property
    def score(self) -> int:
        """Number of distinct reason codes."""
        return len(self.reasons)


@dataclass
class ScanResult:
    run_id: str
    scan_timestamp_pt: str  # ISO-8601 with PT offset
    config: ScanConfig
    universe_size: int
    candidates: list[Candidate]
    signal_counts: dict[str, int]  # raw counts per signal kind + capitol_buys
    errors: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0


# --- Public functions -------------------------------------------------------

def run_sunset_scan(
    config: ScanConfig | None = None,
    *,
    run_id: str | None = None,
) -> ScanResult:
    """Run the Stage 1 scan end-to-end and return the result.

    Steps (in order):
        1. Pull base universe from tradingview.screen_universe()
        2. For each signal kind, pull tradingview.find_signals() and tag candidates
        3. If config.capitol_trades_enabled: pull capitol_trades.get_recent_trades(direction='buy')
           and tag candidates with capitol_buys_30d count + politician names
        4. Filter to candidates with reasons >= config.min_reasons_to_advance
        5. Rank by (-reason_count, -market_cap)
        6. Truncate to config.max_candidates

    On any single source failure (e.g., Capitol Trades site down), log a warning
    and continue with degraded data — record the error in result.errors.

    If run_id is None, generate one as `datetime.now().strftime("%Y%m%d_%H%M%S")`.

    Does NOT write any files. The runner (write_scan_outputs) handles I/O.
    """
    if config is None:
        config = ScanConfig()
    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    t_start = time.monotonic()
    errors: list[str] = []
    signal_counts: dict[str, int] = {}

    scan_timestamp_pt = datetime.now(timezone.utc).astimezone(_PT).isoformat(timespec="seconds")

    # Step 1: Pull base universe
    logger.info("Stage 1: pulling base universe (max=%d)", config.max_universe_size)
    try:
        universe_rows = screen_universe(
            min_price=config.min_price,
            min_avg_volume=config.min_avg_volume,
            min_market_cap_usd=config.min_market_cap_usd,
            max_results=config.max_universe_size,
        )
    except Exception as exc:
        err = f"screen_universe failed: {exc}"
        logger.warning(err)
        errors.append(err)
        universe_rows = []

    # Authoritative source of last_close, market_cap_usd, exchange
    universe: dict[str, dict] = {}
    for row in universe_rows:
        sym = (row.get("symbol") or "").upper().strip()
        if sym:
            universe[sym] = row
    logger.info("Universe: %d tickers", len(universe))

    # candidates_map accumulates reason codes per ticker (only in-universe tickers)
    candidates_map: dict[str, Candidate] = {}

    def _get_or_create(ticker: str) -> Candidate | None:
        if ticker not in universe:
            return None
        if ticker not in candidates_map:
            row = universe[ticker]
            mc = row.get("market_cap")
            vol = row.get("volume")
            chg = row.get("change_pct")
            candidates_map[ticker] = Candidate(
                ticker=ticker,
                exchange=str(row.get("exchange") or ""),
                last_close=float(row.get("last_close") or 0.0),
                market_cap_usd=float(mc) if mc is not None else None,
                volume=int(vol) if vol is not None else None,
                change_pct_today=float(chg) if chg is not None else None,
            )
        return candidates_map[ticker]

    # Step 2: Tag candidates via TradingView signal screens
    total_skipped = 0
    for signal in config.signals:
        logger.info("Scanning signal: %s", signal)
        try:
            hits = find_signals(signal, max_results=config.signals_max_per_kind)
        except Exception as exc:
            err = f"find_signals({signal!r}) failed: {exc}"
            logger.warning(err)
            errors.append(err)
            signal_counts[f"tv_{signal}"] = 0
            continue

        in_uni = 0
        skipped = 0
        reason = f"tv_{signal}"
        for entry in hits:
            sym = (entry.get("symbol") or "").upper().strip()
            if not sym:
                continue
            c = _get_or_create(sym)
            if c is None:
                skipped += 1
                total_skipped += 1
                continue
            if reason not in c.reasons:
                c.reasons.append(reason)
            # Capture TradingView TA recommendation from the directional signals
            if signal == "strong_buy" and c.tradingview_recommendation is None:
                c.tradingview_recommendation = "STRONG_BUY"
            elif signal == "strong_sell" and c.tradingview_recommendation is None:
                c.tradingview_recommendation = "STRONG_SELL"
            in_uni += 1

        signal_counts[f"tv_{signal}"] = in_uni
        if skipped:
            logger.debug("%s: %d hits not in universe (skipped)", signal, skipped)

    signal_counts["skipped_not_in_universe"] = total_skipped

    # Step 3: Tag candidates via Capitol Trades congressional buys
    if config.capitol_trades_enabled:
        logger.info(
            "Fetching Capitol Trades buys (days_back=%d, max_pages=%d)",
            config.capitol_trades_days_back,
            config.capitol_trades_max_pages,
        )
        try:
            buy_trades = get_recent_trades(
                direction="buy",
                days_back=config.capitol_trades_days_back,
                max_pages=config.capitol_trades_max_pages,
            )
            # Group by ticker: distinct politician IDs and unique politician names
            ticker_pol_ids: dict[str, set[str]] = {}
            ticker_pol_names: dict[str, list[str]] = {}
            for trade in buy_trades:
                sym = trade.ticker.upper()
                pid = trade.politician_id or trade.politician_name
                if sym not in ticker_pol_ids:
                    ticker_pol_ids[sym] = set()
                    ticker_pol_names[sym] = []
                ticker_pol_ids[sym].add(pid)
                if trade.politician_name not in ticker_pol_names[sym]:
                    ticker_pol_names[sym].append(trade.politician_name)

            capitol_in_uni = 0
            for sym, pol_ids in ticker_pol_ids.items():
                n = len(pol_ids)
                c = _get_or_create(sym)
                if c is None:
                    continue
                capitol_in_uni += 1
                c.capitol_buys_30d = n
                c.capitol_buys_politicians = ticker_pol_names.get(sym, [])
                # Two distinct tiers: 2+ is a signal; 5+ is a high-conviction bonus reason
                if n >= 2 and "capitol_buys_2plus" not in c.reasons:
                    c.reasons.append("capitol_buys_2plus")
                if n >= 5 and "capitol_buys_5plus" not in c.reasons:
                    c.reasons.append("capitol_buys_5plus")

            signal_counts["capitol_buys"] = capitol_in_uni
            logger.info(
                "Capitol Trades: %d tickers in universe had congressional buys",
                capitol_in_uni,
            )
        except Exception as exc:
            err = f"Capitol Trades fetch failed: {exc}"
            logger.warning(err)
            errors.append(err)

    # Step 4: Filter to min_reasons_to_advance
    advanced = [c for c in candidates_map.values() if c.score >= config.min_reasons_to_advance]

    # Step 5: Sort by (-score, -market_cap_usd); stable sort, larger market cap breaks ties
    advanced.sort(key=lambda c: (-c.score, -(c.market_cap_usd or 0.0)))

    # Step 6: Truncate
    candidates = advanced[: config.max_candidates]

    elapsed = time.monotonic() - t_start
    logger.info(
        "Scan complete: universe=%d, candidates=%d, elapsed=%.1fs, errors=%d",
        len(universe),
        len(candidates),
        elapsed,
        len(errors),
    )

    return ScanResult(
        run_id=run_id,
        scan_timestamp_pt=scan_timestamp_pt,
        config=config,
        universe_size=len(universe),
        candidates=candidates,
        signal_counts=signal_counts,
        errors=errors,
        elapsed_seconds=elapsed,
    )


def _candidate_to_dict(c: Candidate) -> dict:
    return {
        "ticker": c.ticker,
        "exchange": c.exchange,
        "last_close": c.last_close,
        "market_cap_usd": c.market_cap_usd,
        "volume": c.volume,
        "change_pct_today": c.change_pct_today,
        "score": c.score,
        "reasons": c.reasons,
        "tradingview_recommendation": c.tradingview_recommendation,
        "capitol_buys_30d": c.capitol_buys_30d,
        "capitol_buys_politicians": c.capitol_buys_politicians,
    }


def write_scan_outputs(result: ScanResult, runs_dir: str = "runs") -> dict[str, str]:
    """Write tomorrow_watchlist.json and scanner_diagnostic.json to runs/<run_id>/.

    Returns dict of paths written. Creates the run dir if needed.
    """
    import json

    run_dir = Path(runs_dir) / result.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    watchlist_path = run_dir / "tomorrow_watchlist.json"
    watchlist = {
        "run_id": result.run_id,
        "scan_timestamp_pt": result.scan_timestamp_pt,
        "universe_size": result.universe_size,
        "candidate_count": len(result.candidates),
        "candidates": [_candidate_to_dict(c) for c in result.candidates],
    }
    watchlist_path.write_text(json.dumps(watchlist, indent=2, default=str))

    diagnostic_path = run_dir / "scanner_diagnostic.json"
    diagnostic = {
        "run_id": result.run_id,
        "scan_timestamp_pt": result.scan_timestamp_pt,
        "universe_size": result.universe_size,
        "candidate_count": len(result.candidates),
        "signal_counts": result.signal_counts,
        "errors": result.errors,
        "elapsed_seconds": result.elapsed_seconds,
        "config": {
            "min_price": result.config.min_price,
            "min_avg_volume": result.config.min_avg_volume,
            "min_market_cap_usd": result.config.min_market_cap_usd,
            "max_universe_size": result.config.max_universe_size,
            "signals": list(result.config.signals),
            "signals_max_per_kind": result.config.signals_max_per_kind,
            "capitol_trades_enabled": result.config.capitol_trades_enabled,
            "capitol_trades_days_back": result.config.capitol_trades_days_back,
            "capitol_trades_max_pages": result.config.capitol_trades_max_pages,
            "min_reasons_to_advance": result.config.min_reasons_to_advance,
            "max_candidates": result.config.max_candidates,
        },
    }
    diagnostic_path.write_text(json.dumps(diagnostic, indent=2, default=str))

    return {
        "tomorrow_watchlist": str(watchlist_path),
        "scanner_diagnostic": str(diagnostic_path),
    }
