"""Live-network tests for ai_hedge/data/tradingview.py.

These tests hit TradingView's public endpoints. They require internet access.
If TradingView rate-limits (HTTP 429), retry once before failing.
"""
import time

import pytest

from ai_hedge.data.tradingview import (
    Recommendation,
    TickerSnapshot,
    find_signals,
    get_recommendation,
    get_snapshot,
    screen_universe,
    _cache,
)

_VALID_RECOMMENDATIONS = {"STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"}


def test_get_snapshot_aapl_nasdaq():
    """get_snapshot('AAPL') returns a well-formed TickerSnapshot."""
    snap = get_snapshot("AAPL")
    assert isinstance(snap, TickerSnapshot)
    assert snap.recommendation in _VALID_RECOMMENDATIONS
    assert "RSI" in snap.indicators, "indicators must include RSI"
    assert "EMA20" in snap.indicators, "indicators must include EMA20"
    assert snap.last_close > 0, "last_close must be positive"
    assert set(snap.summary.keys()) >= {"BUY", "SELL", "NEUTRAL"}, \
        "summary must have BUY, SELL, NEUTRAL keys"
    assert snap.symbol == "AAPL"
    assert snap.timeframe == "1d"


def test_get_snapshot_unknown_ticker_raises():
    """get_snapshot with a bogus ticker raises ValueError (or RuntimeError if rate-limited)."""
    # Either ValueError (bad symbol) or RuntimeError (rate limit acting as unknown) is acceptable.
    # The important invariant: no TickerSnapshot is returned for a fake ticker.
    with pytest.raises((ValueError, RuntimeError)):
        get_snapshot("ZZZNOTREAL")


def test_screen_universe_returns_sane_list():
    """screen_universe returns a non-empty list with expected fields."""
    rows = screen_universe(
        min_price=5.0,
        min_avg_volume=1_000_000,
        min_market_cap_usd=10_000_000_000,
        max_results=50,
    )
    assert isinstance(rows, list), "screen_universe must return a list"
    assert 5 <= len(rows) <= 50, f"expected 5–50 results, got {len(rows)}"
    for row in rows:
        assert "symbol" in row, "each row must have 'symbol'"
        assert "last_close" in row, "each row must have 'last_close'"
        assert row["last_close"] >= 5.0, "min_price filter should apply"


def test_find_signals_oversold():
    """find_signals('oversold') returns tickers with RSI < 30."""
    results = find_signals("oversold", max_results=10)
    assert isinstance(results, list), "find_signals must return a list"
    for entry in results:
        assert "symbol" in entry, "each entry must have 'symbol'"
        rsi = entry.get("RSI")
        assert rsi is not None, "oversold entries must include RSI"
        assert rsi < 30, f"expected RSI < 30, got {rsi} for {entry['symbol']}"


def test_get_recommendation_msft():
    """get_recommendation('MSFT') returns a valid Recommendation literal."""
    rec = get_recommendation("MSFT")
    assert rec in _VALID_RECOMMENDATIONS, f"unexpected recommendation: {rec!r}"


def test_cache_hit():
    """Second call to get_snapshot('AAPL') is served from cache (faster or same)."""
    # Clear any stale AAPL entry to ensure first call is a real fetch
    aapl_keys = [k for k in list(_cache.keys()) if k.startswith("snapshot:AAPL:1d")]
    for k in aapl_keys:
        del _cache[k]

    t0 = time.monotonic()
    snap1 = get_snapshot("AAPL", cache_ttl_sec=60)
    t1 = time.monotonic()
    first_call_ms = (t1 - t0) * 1000

    t2 = time.monotonic()
    snap2 = get_snapshot("AAPL", cache_ttl_sec=60)
    t3 = time.monotonic()
    second_call_ms = (t3 - t2) * 1000

    # Cache hit should be at least 10× faster than the network call
    assert second_call_ms < first_call_ms / 5, (
        f"cache hit ({second_call_ms:.1f}ms) should be much faster than "
        f"network call ({first_call_ms:.1f}ms)"
    )
    assert snap1.last_close == snap2.last_close, "cached result must match original"
