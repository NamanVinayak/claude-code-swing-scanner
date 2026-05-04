"""TradingView Python wrapper — screener + indicator helpers.

Used by System B's Stage 1 (Sunset Scanner) for mechanical universe screening
without LLM calls. Sits below any agent layer.

All functions are pure-data: they fetch from TradingView's public endpoints
(via the `tradingview-ta` library, which under the hood scrapes the same data
TradingView's web screener uses), cache results in a module-level in-memory
TTL store (same pattern as ai_hedge/data/cache.py), and return plain Python
types (lists/dicts).

No API key required. No TradingView Pro account required.

Cache note: Uses a module-level in-memory TTL dict (not the shared SQLite
Cache singleton) because the Cache class in cache.py has domain-specific
typed stores and no generic key-value API. The TTL logic is identical.
TODO: migrate to SQLite cache once Cache gains a generic store.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Sequence

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

Timeframe = Literal["1m", "5m", "15m", "1h", "4h", "1d", "1W", "1M"]
Recommendation = Literal["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"]
SignalKind = Literal[
    "strong_buy",
    "strong_sell",
    "oversold",       # RSI < 30
    "overbought",     # RSI > 70
    "breakout_up",    # price >= BB.upper on above-avg volume (20-day proxy)
    "breakout_down",  # price <= BB.lower on above-avg volume
    "trending_up",    # EMA20 > EMA50 > EMA200, price > EMA20
    "trending_down",  # EMA20 < EMA50 < EMA200, price < EMA20
]


@dataclass(frozen=True)
class TickerSnapshot:
    """One ticker's current technical state on a given timeframe."""
    symbol: str
    exchange: str       # NASDAQ, NYSE, etc.
    timeframe: Timeframe
    recommendation: Recommendation
    indicators: dict[str, float]   # RSI, MACD.macd, MACD.signal, EMA20, etc.
    summary: dict[str, int]        # {"BUY": N, "SELL": N, "NEUTRAL": N}
    last_close: float
    fetched_at: str     # ISO-8601 UTC


# ---------------------------------------------------------------------------
# Internal: TradingView interval mapping
# ---------------------------------------------------------------------------

_TV_INTERVAL: dict[str, str] = {
    "1m":  "1m",
    "5m":  "5m",
    "15m": "15m",
    "1h":  "1h",
    "4h":  "4h",
    "1d":  "1d",
    "1W":  "1W",
    "1M":  "1M",
}

# Suffix appended to column names in scanner API for non-daily timeframes
_TV_INTERVAL_SUFFIX: dict[str, str] = {
    "1m":  "|1",
    "5m":  "|5",
    "15m": "|15",
    "1h":  "|60",
    "4h":  "|240",
    "1d":  "",
    "1W":  "|1W",
    "1M":  "|1M",
}

_SCANNER_URL = "https://scanner.tradingview.com/{screener}/scan"
# Browser-like headers required to avoid 429 rate limiting on the public scanner endpoint.
# The tradingview_ta default "tradingview_ta/3.3.0" UA gets throttled aggressively per-IP.
_SCANNER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
}

# ---------------------------------------------------------------------------
# Internal: module-level TTL cache
# ---------------------------------------------------------------------------
# Structure: { key: (data, fetched_at_unix) }
_cache: dict[str, tuple[Any, float]] = {}


def _cache_get(key: str, ttl: int) -> Any | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    data, fetched_at = entry
    if (time.time() - fetched_at) > ttl:
        return None
    return data


def _cache_set(key: str, data: Any) -> None:
    _cache[key] = (data, time.time())


# ---------------------------------------------------------------------------
# Internal: network helpers
# ---------------------------------------------------------------------------

def _tv_interval_obj(timeframe: Timeframe):
    """Return the tradingview_ta Interval constant for a Timeframe string."""
    from tradingview_ta import Interval as _Interval  # lazy import
    _map = {
        "1m":  _Interval.INTERVAL_1_MINUTE,
        "5m":  _Interval.INTERVAL_5_MINUTES,
        "15m": _Interval.INTERVAL_15_MINUTES,
        "1h":  _Interval.INTERVAL_1_HOUR,
        "4h":  _Interval.INTERVAL_4_HOURS,
        "1d":  _Interval.INTERVAL_1_DAY,
        "1W":  _Interval.INTERVAL_1_WEEK,
        "1M":  _Interval.INTERVAL_1_MONTH,
    }
    return _map[timeframe]


def _fetch_analysis(symbol: str, exchange: str, timeframe: Timeframe):
    """Fetch one ticker's full Analysis via the scanner POST API.

    Uses the same HTTP endpoint as screen_universe/find_signals (more reliable
    than TA_Handler for sequential requests). Calls tradingview_ta.calculate
    internally to compute the BUY/SELL/NEUTRAL counts and recommendation.

    Raises Exception if the ticker is not found or HTTP error.
    """
    from tradingview_ta.main import TradingView, calculate  # lazy import

    interval_str = _TV_INTERVAL[timeframe]
    exchange_symbol = f"{exchange}:{symbol}"
    payload = TradingView.data([exchange_symbol], interval_str, TradingView.indicators)
    url = _SCANNER_URL.format(screener="america")
    resp = requests.post(url, json=payload, headers=_SCANNER_HEADERS, timeout=15)

    if resp.status_code == 429:
        raise Exception(f"Can't access TradingView's API. HTTP status code: 429.")
    resp.raise_for_status()

    result = resp.json()
    data_rows = result.get("data") or []
    if not data_rows:
        raise Exception(f"No data returned for {exchange_symbol}")

    row = data_rows[0]
    indicators_dict: dict[str, float | None] = {}
    for idx, key in enumerate(TradingView.indicators):
        indicators_dict[key] = row["d"][idx] if idx < len(row["d"]) else None

    analysis = calculate(
        indicators=indicators_dict,
        indicators_key=TradingView.indicators,
        screener="america",
        symbol=symbol,
        exchange=exchange,
        interval=interval_str,
    )
    if analysis is None:
        raise Exception(f"calculate() returned None for {exchange_symbol} — likely None indicators")
    return analysis


def _scanner_post(screener: str, payload: dict, timeout: int = 15) -> dict:
    """POST to TradingView scanner; raises RuntimeError on failure."""
    url = _SCANNER_URL.format(screener=screener)
    resp = requests.post(url, json=payload, headers=_SCANNER_HEADERS, timeout=timeout)
    resp.raise_for_status()
    result = resp.json()
    if result is None or "data" not in result:
        raise RuntimeError(f"Unexpected scanner response: {resp.text[:200]}")
    return result


def _scanner_post_with_retry(screener: str, payload: dict) -> dict:
    """One retry with 1-second backoff on any failure."""
    try:
        return _scanner_post(screener, payload)
    except Exception as e:
        logger.warning("TradingView scanner request failed (%s), retrying in 1s", e)
        time.sleep(1)
        try:
            return _scanner_post(screener, payload)
        except Exception as e2:
            logger.error("TradingView scanner request failed on retry: %s", e2)
            raise RuntimeError(f"TradingView scanner unavailable: {e2}") from e2


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Internal: map Recommendation.All float → Recommendation literal
# ---------------------------------------------------------------------------

def _rec_float_to_literal(val: float | None) -> Recommendation:
    if val is None:
        return "NEUTRAL"
    if val >= 0.5:
        return "STRONG_BUY"
    if val > 0.1:
        return "BUY"
    if val >= -0.1:
        return "NEUTRAL"
    if val > -0.5:
        return "SELL"
    return "STRONG_SELL"


def _rec_str_to_literal(val: str | None) -> Recommendation:
    mapping = {
        "STRONG_BUY": "STRONG_BUY",
        "BUY": "BUY",
        "NEUTRAL": "NEUTRAL",
        "SELL": "SELL",
        "STRONG_SELL": "STRONG_SELL",
    }
    return mapping.get((val or "").upper(), "NEUTRAL")


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def get_snapshot(
    symbol: str,
    *,
    timeframe: Timeframe = "1d",
    exchange: str | None = None,
    cache_ttl_sec: int = 300,
) -> TickerSnapshot:
    """Fetch one ticker's TA snapshot.

    If `exchange` is None, autodetect by trying NASDAQ first, then NYSE.
    Caches in the module-level TTL store for `cache_ttl_sec` seconds.
    Raises ValueError on unknown ticker. Raises RuntimeError on network failure
    after one retry.
    """
    sym = symbol.upper()
    cache_key = f"snapshot:{sym}:{timeframe}"
    cached = _cache_get(cache_key, cache_ttl_sec)
    if cached is not None:
        return TickerSnapshot(**cached)

    logger.info("cache miss: get_snapshot(%s, timeframe=%s)", sym, timeframe)

    exchanges_to_try = [exchange] if exchange else ["NASDAQ", "NYSE"]
    analysis = None
    last_exc: Exception | None = None
    last_was_rate_limit = False

    for exch in exchanges_to_try:
        try:
            analysis = _fetch_analysis(sym, exch, timeframe)
            used_exchange = exch
            break
        except Exception as e:
            last_exc = e
            last_was_rate_limit = "429" in str(e)
            logger.warning("get_snapshot: %s on %s failed (%s), trying next exchange", sym, exch, e)
            sleep_secs = 5.0 if last_was_rate_limit else 0.3
            time.sleep(sleep_secs)

    if analysis is None:
        if last_was_rate_limit:
            raise RuntimeError(f"TradingView rate limited fetching {sym}") from last_exc
        raise ValueError(f"unknown ticker or no data: {sym}") from last_exc

    rec_str = analysis.summary.get("RECOMMENDATION", "NEUTRAL")
    recommendation = _rec_str_to_literal(rec_str)

    snap = TickerSnapshot(
        symbol=sym,
        exchange=used_exchange,
        timeframe=timeframe,
        recommendation=recommendation,
        indicators=dict(analysis.indicators),
        summary={
            "BUY": analysis.summary.get("BUY", 0),
            "SELL": analysis.summary.get("SELL", 0),
            "NEUTRAL": analysis.summary.get("NEUTRAL", 0),
        },
        last_close=float(analysis.indicators.get("close", 0.0)),
        fetched_at=_utc_now_iso(),
    )
    _cache_set(cache_key, {
        "symbol": snap.symbol,
        "exchange": snap.exchange,
        "timeframe": snap.timeframe,
        "recommendation": snap.recommendation,
        "indicators": snap.indicators,
        "summary": snap.summary,
        "last_close": snap.last_close,
        "fetched_at": snap.fetched_at,
    })
    return snap


def screen_universe(
    *,
    market: Literal["america"] = "america",
    exchanges: Sequence[str] = ("NASDAQ", "NYSE"),
    min_price: float | None = 5.0,
    max_price: float | None = None,
    min_avg_volume: int | None = 500_000,
    min_market_cap_usd: float | None = 1_000_000_000,
    max_results: int = 200,
    cache_ttl_sec: int = 60,
) -> list[dict]:
    """Mechanical universe screen.

    Returns a list of dicts, one per ticker passing all filters. Each dict has
    at minimum: symbol, exchange, last_close, volume, market_cap, change_pct.

    Filters with None are not applied. `max_results` truncates the return;
    no scoring or ordering guarantee — caller must sort.

    Caches in the module-level TTL store for `cache_ttl_sec` seconds keyed on
    the full filter signature.
    """
    cache_key = (
        f"screen:{market}:{','.join(sorted(exchanges))}:"
        f"minp={min_price}:maxp={max_price}:minvol={min_avg_volume}:"
        f"mincap={min_market_cap_usd}:max={max_results}"
    )
    cached = _cache_get(cache_key, cache_ttl_sec)
    if cached is not None:
        return cached

    logger.info("cache miss: screen_universe(market=%s, max=%d)", market, max_results)

    filters: list[dict] = []

    if exchanges:
        filters.append({"left": "exchange", "operation": "in_range", "right": list(exchanges)})
    if min_price is not None:
        filters.append({"left": "close", "operation": "greater", "right": min_price})
    if max_price is not None:
        filters.append({"left": "close", "operation": "less", "right": max_price})
    if min_avg_volume is not None:
        filters.append({"left": "average_volume_10d_calc", "operation": "greater", "right": min_avg_volume})
    if min_market_cap_usd is not None:
        filters.append({"left": "market_cap_basic", "operation": "greater", "right": min_market_cap_usd})

    columns = ["name", "close", "volume", "change", "market_cap_basic", "average_volume_10d_calc", "exchange"]

    payload = {
        "filter": filters,
        "columns": columns,
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        "range": [0, max_results],
        "options": {"lang": "en"},
    }

    result = _scanner_post_with_retry(market, payload)
    rows = result.get("data") or []

    output = []
    for row in rows:
        s = row.get("s", "")
        parts = s.split(":") if ":" in s else [None, s]
        d = row.get("d", [])
        if len(d) < len(columns):
            continue
        output.append({
            "symbol":       d[0],
            "last_close":   d[1],
            "volume":       d[2],
            "change_pct":   d[3],
            "market_cap":   d[4],
            "avg_volume_10d": d[5],
            "exchange":     d[6],
        })

    _cache_set(cache_key, output)
    return output


def find_signals(
    signal: SignalKind,
    *,
    market: Literal["america"] = "america",
    exchanges: Sequence[str] = ("NASDAQ", "NYSE"),
    timeframe: Timeframe = "1d",
    max_results: int = 50,
    cache_ttl_sec: int = 60,
) -> list[dict]:
    """Find tickers currently showing a named signal.

    Returns a list of dicts. Each dict has at minimum: symbol, exchange,
    last_close, and the signal-specific metric.

    Signal → filter mapping:
      strong_buy:    direct screener filter — Recommend.All >= 0.5 (STRONG_BUY threshold)
      strong_sell:   direct screener filter — Recommend.All <= -0.5
      oversold:      direct screener filter — RSI <= 30
      overbought:    direct screener filter — RSI >= 70
      breakout_up:   direct screener filter — close >= BB.upper (20-day upper band proxy),
                     then post-hoc: volume > avg_volume_10d * 1.2
      breakout_down: direct screener filter — close <= BB.lower (20-day lower band proxy),
                     then post-hoc: volume > avg_volume_10d * 1.2
      trending_up:   fetch EMA20/EMA50/EMA200/close columns, post-hoc client-side filter:
                     EMA20 > EMA50 > EMA200 AND close > EMA20
      trending_down: fetch EMA20/EMA50/EMA200/close columns, post-hoc:
                     EMA20 < EMA50 < EMA200 AND close < EMA20
    """
    sfx = _TV_INTERVAL_SUFFIX[timeframe]
    cache_key = f"signals:{signal}:{market}:{','.join(sorted(exchanges))}:{timeframe}:{max_results}"
    cached = _cache_get(cache_key, cache_ttl_sec)
    if cached is not None:
        return cached

    logger.info("cache miss: find_signals(signal=%s, timeframe=%s)", signal, timeframe)

    exch_filter = {"left": "exchange", "operation": "in_range", "right": list(exchanges)} if exchanges else None

    def _base_filters() -> list[dict]:
        return [exch_filter] if exch_filter else []

    def _col(name: str) -> str:
        return name + sfx

    if signal == "strong_buy":
        filters = _base_filters() + [
            {"left": _col("Recommend.All"), "operation": "greater", "right": 0.5},
        ]
        columns = ["name", _col("close"), _col("Recommend.All"), "exchange"]
        sort_col = _col("Recommend.All")
        sort_order = "desc"
        result_builder = lambda sym, exch, d: {
            "symbol":          d[0],
            "last_close":      d[1],
            "recommend_all":   d[2],
            "exchange":        exch,
        }

    elif signal == "strong_sell":
        filters = _base_filters() + [
            {"left": _col("Recommend.All"), "operation": "less", "right": -0.5},
        ]
        columns = ["name", _col("close"), _col("Recommend.All"), "exchange"]
        sort_col = _col("Recommend.All")
        sort_order = "asc"
        result_builder = lambda sym, exch, d: {
            "symbol":          d[0],
            "last_close":      d[1],
            "recommend_all":   d[2],
            "exchange":        exch,
        }

    elif signal == "oversold":
        filters = _base_filters() + [
            {"left": _col("RSI"), "operation": "less", "right": 30},
        ]
        columns = ["name", _col("close"), _col("RSI"), "exchange"]
        sort_col = _col("RSI")
        sort_order = "asc"
        result_builder = lambda sym, exch, d: {
            "symbol":     d[0],
            "last_close": d[1],
            "RSI":        d[2],
            "exchange":   exch,
        }

    elif signal == "overbought":
        filters = _base_filters() + [
            {"left": _col("RSI"), "operation": "greater", "right": 70},
        ]
        columns = ["name", _col("close"), _col("RSI"), "exchange"]
        sort_col = _col("RSI")
        sort_order = "desc"
        result_builder = lambda sym, exch, d: {
            "symbol":     d[0],
            "last_close": d[1],
            "RSI":        d[2],
            "exchange":   exch,
        }

    elif signal == "breakout_up":
        # close >= BB.upper (price broke above the 20-period upper Bollinger Band)
        # post-hoc: volume > avg_volume_10d * 1.2
        filters = _base_filters() + [
            {"left": _col("close"), "operation": "greater_equal", "right": 0},  # placeholder
        ]
        columns = ["name", _col("close"), _col("BB.upper"), _col("volume"), "average_volume_10d_calc", "exchange"]
        sort_col = _col("close")
        sort_order = "desc"
        # We'll apply the BB.upper and volume comparisons post-hoc
        def result_builder(sym, exch, d):
            close_val = d[1]
            bb_upper = d[2]
            vol = d[3]
            avg_vol = d[4]
            if bb_upper is None or avg_vol is None:
                return None
            if close_val < bb_upper:  # price must be at/above upper band
                return None
            if vol < avg_vol * 1.2:   # volume must be above average
                return None
            return {
                "symbol":     d[0],
                "last_close": close_val,
                "BB_upper":   bb_upper,
                "volume":     vol,
                "avg_vol_10d": avg_vol,
                "exchange":   exch,
            }
        # Remove placeholder filter and add real filter indirectly via post-hoc
        filters = _base_filters()

    elif signal == "breakout_down":
        # close <= BB.lower on above-avg volume
        filters = _base_filters()
        columns = ["name", _col("close"), _col("BB.lower"), _col("volume"), "average_volume_10d_calc", "exchange"]
        sort_col = _col("close")
        sort_order = "asc"
        def result_builder(sym, exch, d):
            close_val = d[1]
            bb_lower = d[2]
            vol = d[3]
            avg_vol = d[4]
            if bb_lower is None or avg_vol is None:
                return None
            if close_val > bb_lower:
                return None
            if vol < avg_vol * 1.2:
                return None
            return {
                "symbol":     d[0],
                "last_close": close_val,
                "BB_lower":   bb_lower,
                "volume":     vol,
                "avg_vol_10d": avg_vol,
                "exchange":   exch,
            }

    elif signal == "trending_up":
        # EMA20 > EMA50 > EMA200, close > EMA20 — all client-side
        filters = _base_filters()
        columns = ["name", _col("close"), _col("EMA20"), _col("EMA50"), _col("EMA200"), "exchange"]
        sort_col = _col("close")
        sort_order = "desc"
        def result_builder(sym, exch, d):
            close_val = d[1]
            ema20 = d[2]
            ema50 = d[3]
            ema200 = d[4]
            if any(v is None for v in [close_val, ema20, ema50, ema200]):
                return None
            if not (ema20 > ema50 > ema200 and close_val > ema20):
                return None
            return {
                "symbol":     d[0],
                "last_close": close_val,
                "EMA20":      ema20,
                "EMA50":      ema50,
                "EMA200":     ema200,
                "exchange":   exch,
            }

    elif signal == "trending_down":
        filters = _base_filters()
        columns = ["name", _col("close"), _col("EMA20"), _col("EMA50"), _col("EMA200"), "exchange"]
        sort_col = _col("close")
        sort_order = "asc"
        def result_builder(sym, exch, d):
            close_val = d[1]
            ema20 = d[2]
            ema50 = d[3]
            ema200 = d[4]
            if any(v is None for v in [close_val, ema20, ema50, ema200]):
                return None
            if not (ema20 < ema50 < ema200 and close_val < ema20):
                return None
            return {
                "symbol":     d[0],
                "last_close": close_val,
                "EMA20":      ema20,
                "EMA50":      ema50,
                "EMA200":     ema200,
                "exchange":   exch,
            }

    else:
        raise ValueError(f"Unknown signal kind: {signal!r}")

    # For post-hoc signals (breakout, trending) we fetch a larger batch to compensate
    # for client-side filtering reducing the count.
    is_posthoc = signal in ("breakout_up", "breakout_down", "trending_up", "trending_down")
    fetch_limit = max_results * 5 if is_posthoc else max_results

    payload = {
        "filter": filters,
        "columns": columns,
        "sort": {"sortBy": sort_col, "sortOrder": sort_order},
        "range": [0, min(fetch_limit, 500)],
        "options": {"lang": "en"},
    }

    result = _scanner_post_with_retry(market, payload)
    rows = result.get("data") or []

    output = []
    for row in rows:
        s = row.get("s", "")
        parts = s.split(":") if ":" in s else [None, s]
        exch = parts[0] if len(parts) == 2 else ""
        d = row.get("d", [])
        if len(d) < len(columns):
            continue
        entry = result_builder(s, exch, d)
        if entry is not None:
            output.append(entry)
        if len(output) >= max_results:
            break

    _cache_set(cache_key, output)
    return output


def get_recommendation(symbol: str, *, timeframe: Timeframe = "1d") -> Recommendation:
    """Convenience: just the TA recommendation for one ticker. Uses get_snapshot."""
    snap = get_snapshot(symbol, timeframe=timeframe)
    return snap.recommendation


def lookup_metadata(
    symbols: list[str],
    *,
    market: Literal["america"] = "america",
    cache_ttl_sec: int = 60,
) -> dict[str, dict]:
    """Batch-fetch last_close, volume, change_pct, market_cap, avg_volume_10d, exchange
    for many tickers in ONE scanner POST.

    Returns dict keyed by upper-cased symbol → row dict. Row dicts have None values
    dropped (so callers should use .get() and not assume keys are present).

    Symbols not found in the scanner response are simply absent from the returned
    dict — caller must handle missing keys.
    """
    if not symbols:
        return {}

    syms = sorted({s.upper().strip() for s in symbols if s and s.strip()})
    if not syms:
        return {}

    cache_key = f"meta:{market}:{','.join(syms)}"
    cached = _cache_get(cache_key, cache_ttl_sec)
    if cached is not None:
        return cached

    logger.info("cache miss: lookup_metadata(%d symbols)", len(syms))

    columns = ["name", "close", "volume", "change", "market_cap_basic", "average_volume_10d_calc", "exchange"]
    payload = {
        "filter": [
            {"left": "name", "operation": "in_range", "right": syms},
        ],
        "columns": columns,
        "range": [0, len(syms)],
        "options": {"lang": "en"},
    }

    result = _scanner_post_with_retry(market, payload)
    rows = result.get("data") or []

    output: dict[str, dict] = {}
    for row in rows:
        d = row.get("d", [])
        if len(d) < len(columns):
            continue
        sym = d[0]
        if not sym:
            continue
        sym = str(sym).upper()
        entry_full = {
            "symbol":          sym,
            "last_close":      d[1],
            "volume":          d[2],
            "change_pct":      d[3],
            "market_cap":      d[4],
            "avg_volume_10d":  d[5],
            "exchange":        d[6],
        }
        entry = {k: v for k, v in entry_full.items() if v is not None}
        output[sym] = entry

    _cache_set(cache_key, output)
    return output
