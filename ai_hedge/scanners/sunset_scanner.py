"""Stage 1 Sunset Scanner — System B's signal-first, direction-aware funnel.

Runs late afternoon Pacific (after market close). Pulls TradingView signal
screens FIRST (the union of unique tickers that hit any signal IS the candidate
pool — no upfront market-cap-rank cap), enriches with Capitol Trades disclosures,
then applies per-ticker sanity filters via a single batch metadata lookup.

Direction-aware: long signals (strong_buy, breakout_up, trending_up, oversold)
and short signals (strong_sell, breakout_down, trending_down, overbought) are
tracked separately. Capitol buys go into long reasons (politicians buying =
bullish). A candidate must clear `min_reasons_to_advance` in a SINGLE direction;
having reasons in BOTH directions is treated as "conflicted" and dropped.

Pure-Python — no LLM calls in this module.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from ai_hedge.data.capitol_trades import get_recent_trades
from ai_hedge.data.tradingview import find_signals, lookup_metadata

logger = logging.getLogger(__name__)

_PT = ZoneInfo("America/Los_Angeles")


# --- Direction taxonomy ----------------------------------------------------
# RSI < 30 = oversold = bullish (long); RSI > 70 = overbought = bearish (short).

LONG_SIGNALS: set[str] = {"strong_buy", "breakout_up", "trending_up", "oversold"}
SHORT_SIGNALS: set[str] = {"strong_sell", "breakout_down", "trending_down", "overbought"}


# --- Public types -----------------------------------------------------------

@dataclass(frozen=True)
class ScanConfig:
    # Per-ticker sanity filters (applied AFTER signal-pool union, via batch metadata)
    min_price: float = 5.0
    min_avg_volume: int = 500_000
    min_market_cap_usd: float = 1_000_000_000

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
    signals_max_per_kind: int = 400

    # Which directions to scan for. Default both on. Setting to ("long",) skips
    # short signal kinds entirely (and vice versa).
    directions_enabled: tuple[str, ...] = ("long", "short")

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
    long_reasons: list[str] = field(default_factory=list)
    short_reasons: list[str] = field(default_factory=list)
    direction: Literal["long", "short"] | None = None
    # Back-compat: downstream (premarket_reviewer.py) reads `reasons`. Populated
    # with whichever directional list met the advancement threshold.
    reasons: list[str] = field(default_factory=list)
    capitol_buys_30d: int = 0
    capitol_buys_politicians: list[str] = field(default_factory=list)

    @property
    def score(self) -> int:
        """Number of distinct reason codes in the advancing direction."""
        return len(self.reasons)


@dataclass
class ScanResult:
    run_id: str
    scan_timestamp_pt: str  # ISO-8601 with PT offset
    config: ScanConfig
    universe_size: int  # unique tickers with any signal hit (pre-sanity-filter)
    candidates: list[Candidate]
    signal_counts: dict[str, int]  # raw counts per signal kind + capitol_buys + telemetry
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
        1. For each enabled signal kind, pull tradingview.find_signals().
           Tag each ticker's reason into long_reasons or short_reasons depending
           on the signal kind's direction. Union of all hits = candidate pool.
        2. If config.capitol_trades_enabled: pull capitol_trades.get_recent_trades(direction='buy')
           and add capitol_buys_2plus / capitol_buys_5plus to long_reasons for any
           pool ticker.
        3. Batch metadata lookup for the entire pool in ONE scanner POST.
        4. Per-ticker sanity filter: min_price, min_avg_volume, min_market_cap_usd.
        5. Direction resolution:
             - reasons in BOTH directions → drop as "conflicted"
             - 1 reason in single direction → drop as "directional singleton"
             - long_reasons >= min_reasons_to_advance → advance as direction="long"
             - short_reasons >= min_reasons_to_advance → advance as direction="short"
        6. Rank by (-score, -market_cap), truncate to max_candidates.

    On any single source failure (e.g., Capitol Trades site down), log a warning
    and continue with degraded data — record the error in result.errors.

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

    # Step 1: Pull signal hits and partition by direction
    long_reasons_map: dict[str, list[str]] = {}
    short_reasons_map: dict[str, list[str]] = {}
    signal_hits_total = 0
    long_enabled = "long" in config.directions_enabled
    short_enabled = "short" in config.directions_enabled

    for signal in config.signals:
        is_long = signal in LONG_SIGNALS
        is_short = signal in SHORT_SIGNALS
        if is_long and not long_enabled:
            signal_counts[f"tv_{signal}"] = 0
            continue
        if is_short and not short_enabled:
            signal_counts[f"tv_{signal}"] = 0
            continue
        if not (is_long or is_short):
            logger.warning("Signal %s not classified as long or short — skipping", signal)
            signal_counts[f"tv_{signal}"] = 0
            continue

        logger.info("Scanning signal: %s (%s)", signal, "long" if is_long else "short")
        try:
            hits = find_signals(signal, max_results=config.signals_max_per_kind)
        except Exception as exc:
            err = f"find_signals({signal!r}) failed: {exc}"
            logger.warning(err)
            errors.append(err)
            signal_counts[f"tv_{signal}"] = 0
            continue

        target_map = long_reasons_map if is_long else short_reasons_map
        reason = f"tv_{signal}"
        kind_count = 0
        for entry in hits:
            sym = (entry.get("symbol") or "").upper().strip()
            if not sym:
                continue
            signal_hits_total += 1
            bucket = target_map.setdefault(sym, [])
            if reason not in bucket:
                bucket.append(reason)
            kind_count += 1
        signal_counts[f"tv_{signal}"] = kind_count

    # Step 2: Capitol Trades enrichment (long-side only — buys are bullish)
    capitol_pool_ticker_count = 0
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
            ticker_pol_ids: dict[str, set[str]] = {}
            ticker_pol_names: dict[str, list[str]] = {}
            ticker_pol_names_seen: dict[str, set[str]] = {}
            for trade in buy_trades:
                sym = trade.ticker.upper()
                # Namespace name-fallback keys so they never collide with real politician IDs
                if trade.politician_id:
                    pid = f"id:{trade.politician_id}"
                else:
                    pid = f"name:{trade.politician_name.lower().strip()}"
                if sym not in ticker_pol_ids:
                    ticker_pol_ids[sym] = set()
                    ticker_pol_names[sym] = []
                    ticker_pol_names_seen[sym] = set()
                ticker_pol_ids[sym].add(pid)
                if trade.politician_name not in ticker_pol_names_seen[sym]:
                    ticker_pol_names[sym].append(trade.politician_name)
                    ticker_pol_names_seen[sym].add(trade.politician_name)

            pool_tickers_now = set(long_reasons_map.keys()) | set(short_reasons_map.keys())
            capitol_meta: dict[str, tuple[int, list[str]]] = {}
            for sym, pol_ids in ticker_pol_ids.items():
                if sym not in pool_tickers_now:
                    continue
                n = len(pol_ids)
                capitol_meta[sym] = (n, ticker_pol_names.get(sym, []))
                if n >= 2:
                    bucket = long_reasons_map.setdefault(sym, [])
                    if "capitol_buys_2plus" not in bucket:
                        bucket.append("capitol_buys_2plus")
                if n >= 5:
                    bucket = long_reasons_map.setdefault(sym, [])
                    if "capitol_buys_5plus" not in bucket:
                        bucket.append("capitol_buys_5plus")
            capitol_pool_ticker_count = len(capitol_meta)
            signal_counts["capitol_buys"] = capitol_pool_ticker_count
            logger.info(
                "Capitol Trades: %d pool tickers had congressional buys",
                capitol_pool_ticker_count,
            )
        except Exception as exc:
            err = f"Capitol Trades fetch failed: {exc}"
            logger.warning(err)
            errors.append(err)
            capitol_meta = {}
    else:
        capitol_meta = {}

    # Step 3: Pool union + batch metadata lookup
    pool_tickers = sorted(set(long_reasons_map.keys()) | set(short_reasons_map.keys()))
    unique_tickers_with_any_signal = len(pool_tickers)

    metadata: dict[str, dict] = {}
    if pool_tickers:
        logger.info("Batch metadata lookup for %d pool tickers", len(pool_tickers))
        try:
            metadata = lookup_metadata(pool_tickers)
        except Exception as exc:
            err = f"lookup_metadata failed: {exc}"
            logger.warning(err)
            errors.append(err)
            metadata = {}

    # Step 4: Sanity filter + Step 5: direction resolution
    dropped_min_price = 0
    dropped_min_volume = 0
    dropped_min_market_cap = 0
    dropped_no_metadata = 0
    conflicted_drops = 0
    directional_singletons_long = 0
    directional_singletons_short = 0
    below_threshold_drops = 0

    candidates_built: list[Candidate] = []

    for sym in pool_tickers:
        meta = metadata.get(sym)
        if meta is None:
            dropped_no_metadata += 1
            continue

        last_close = meta.get("last_close")
        market_cap = meta.get("market_cap")
        avg_vol = meta.get("avg_volume_10d")

        if last_close is None or float(last_close) < config.min_price:
            dropped_min_price += 1
            continue
        if market_cap is None or float(market_cap) < config.min_market_cap_usd:
            dropped_min_market_cap += 1
            continue
        if avg_vol is None or float(avg_vol) < config.min_avg_volume:
            dropped_min_volume += 1
            continue

        long_r = list(long_reasons_map.get(sym, []))
        short_r = list(short_reasons_map.get(sym, []))
        long_n = len(long_r)
        short_n = len(short_r)

        if long_n > 0 and short_n > 0:
            conflicted_drops += 1
            continue
        if long_n + short_n == 1:
            if long_n == 1:
                directional_singletons_long += 1
            else:
                directional_singletons_short += 1
            continue

        direction: Literal["long", "short"] | None = None
        chosen_reasons: list[str] = []
        if long_n >= config.min_reasons_to_advance:
            direction = "long"
            chosen_reasons = long_r
        elif short_n >= config.min_reasons_to_advance:
            direction = "short"
            chosen_reasons = short_r
        else:
            below_threshold_drops += 1
            continue

        cap_n, cap_pols = capitol_meta.get(sym, (0, []))
        vol_raw = meta.get("volume")
        chg_raw = meta.get("change_pct")
        candidates_built.append(
            Candidate(
                ticker=sym,
                exchange=str(meta.get("exchange") or ""),
                last_close=float(last_close),
                market_cap_usd=float(market_cap) if market_cap is not None else None,
                volume=int(vol_raw) if vol_raw is not None else None,
                change_pct_today=float(chg_raw) if chg_raw is not None else None,
                long_reasons=long_r,
                short_reasons=short_r,
                direction=direction,
                reasons=chosen_reasons,
                capitol_buys_30d=cap_n,
                capitol_buys_politicians=cap_pols,
            )
        )

    # Step 6: Sort + truncate
    candidates_built.sort(key=lambda c: (-c.score, -(c.market_cap_usd or 0.0)))
    candidates = candidates_built[: config.max_candidates]

    # Telemetry
    signal_counts["signal_hits_total"] = signal_hits_total
    signal_counts["unique_tickers_with_any_signal"] = unique_tickers_with_any_signal
    signal_counts["dropped_min_price"] = dropped_min_price
    signal_counts["dropped_min_volume"] = dropped_min_volume
    signal_counts["dropped_min_market_cap"] = dropped_min_market_cap
    signal_counts["dropped_no_metadata"] = dropped_no_metadata
    signal_counts["conflicted_drops"] = conflicted_drops
    signal_counts["directional_singletons_long"] = directional_singletons_long
    signal_counts["directional_singletons_short"] = directional_singletons_short
    signal_counts["below_threshold_drops"] = below_threshold_drops

    elapsed = time.monotonic() - t_start
    logger.info(
        "Scan complete: pool=%d, candidates=%d (long=%d, short=%d), elapsed=%.1fs, errors=%d",
        unique_tickers_with_any_signal,
        len(candidates),
        sum(1 for c in candidates if c.direction == "long"),
        sum(1 for c in candidates if c.direction == "short"),
        elapsed,
        len(errors),
    )

    return ScanResult(
        run_id=run_id,
        scan_timestamp_pt=scan_timestamp_pt,
        config=config,
        universe_size=unique_tickers_with_any_signal,
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
        "direction": c.direction,
        "reasons": c.reasons,
        "long_reasons": c.long_reasons,
        "short_reasons": c.short_reasons,
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
            "signals": list(result.config.signals),
            "signals_max_per_kind": result.config.signals_max_per_kind,
            "directions_enabled": list(result.config.directions_enabled),
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
