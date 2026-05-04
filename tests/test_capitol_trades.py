"""Live-network tests for ai_hedge/data/capitol_trades.py.

These tests hit capitoltrades.com. They require internet access.
If the site is unreachable, test_is_capitol_trades_reachable skips
(and only that test). All other tests fail hard on network errors —
do not add spurious skips to hide real breakage.
"""
import time
from datetime import date, timedelta

import pytest

from ai_hedge.data.capitol_trades import (
    CongressionalTrade,
    _cache,
    get_politicians_who_bought,
    get_recent_trades,
    get_recent_trades_for_ticker,
    get_top_performing_politicians,
    is_capitol_trades_reachable,
)


# ---------------------------------------------------------------------------
# 1. Reachability
# ---------------------------------------------------------------------------

def test_is_capitol_trades_reachable():
    """HEAD request to capitoltrades.com returns 2xx."""
    reachable = is_capitol_trades_reachable(timeout_sec=10.0)
    if not reachable:
        time.sleep(5)
        reachable = is_capitol_trades_reachable(timeout_sec=10.0)
    if not reachable:
        pytest.skip("Capitol Trades appears to be down; skipping reachability test")
    assert reachable


# ---------------------------------------------------------------------------
# 2. Global trades — sane list
# ---------------------------------------------------------------------------

def test_get_recent_trades_returns_sane_list():
    """get_recent_trades returns a non-empty list with well-formed CongressionalTrade objects."""
    trades = get_recent_trades(days_back=30, max_pages=2)
    assert isinstance(trades, list), "must return a list"
    assert len(trades) > 0, "Congress is always trading something; expected > 0 trades"

    sixty_days_ago = date.today() - timedelta(days=60)
    for t in trades:
        assert isinstance(t, CongressionalTrade), f"expected CongressionalTrade, got {type(t)}"
        assert t.ticker, "ticker must be non-empty"
        assert t.politician_name, "politician_name must be non-empty"
        assert t.transaction_date >= sixty_days_ago, (
            f"transaction_date {t.transaction_date} is older than 60 days for {t.ticker}"
        )


# ---------------------------------------------------------------------------
# 3. Direction filter
# ---------------------------------------------------------------------------

def test_get_recent_trades_filter_buys_only():
    """get_recent_trades(direction='buy') returns only buy trades."""
    trades = get_recent_trades(direction="buy", max_pages=1)
    assert isinstance(trades, list), "must return a list"
    for t in trades:
        assert t.direction == "buy", (
            f"expected direction='buy', got {t.direction!r} for {t.ticker} / {t.politician_name}"
        )


# ---------------------------------------------------------------------------
# 4. Per-ticker — AAPL
# ---------------------------------------------------------------------------

def test_get_recent_trades_for_ticker_aapl():
    """get_recent_trades_for_ticker('AAPL', days_back=180) returns AAPL-only trades."""
    trades = get_recent_trades_for_ticker("AAPL", days_back=180)
    assert isinstance(trades, list), "must return a list"
    assert len(trades) >= 1, (
        "AAPL is one of the most-traded names by Congress; expected at least 1 trade in 180 days"
    )
    for t in trades:
        assert t.ticker == "AAPL", f"expected ticker='AAPL', got {t.ticker!r}"


# ---------------------------------------------------------------------------
# 5. Politicians who bought
# ---------------------------------------------------------------------------

def test_get_politicians_who_bought_aapl():
    """get_politicians_who_bought('AAPL') returns a list of dicts with expected keys."""
    politicians = get_politicians_who_bought("AAPL", days_back=180)
    assert isinstance(politicians, list), "must return a list"
    for p in politicians:
        assert isinstance(p, dict), "each item must be a dict"
        assert "politician_name" in p, "missing 'politician_name' key"
        assert "count" in p, "missing 'count' key"
        assert p["count"] >= 1, "count must be at least 1"


# ---------------------------------------------------------------------------
# 6. Top-performing politicians — either works or raises NotImplementedError
# ---------------------------------------------------------------------------

def test_get_top_performing_politicians_either_works_or_raises_not_implemented():
    """get_top_performing_politicians either returns data or raises NotImplementedError."""
    try:
        result = get_top_performing_politicians(top_n=5)
        assert isinstance(result, list), "if it returns, must be a list"
        assert len(result) <= 5, f"expected at most 5 results, got {len(result)}"
    except NotImplementedError:
        pass  # expected — Capitol Trades does not publish track-record data


# ---------------------------------------------------------------------------
# 7. Cache hit — second call is faster
# ---------------------------------------------------------------------------

def test_cache_hit():
    """Second call to get_recent_trades(max_pages=1) is served from cache (much faster)."""
    # Clear any existing cache entry to ensure first call is a real fetch
    cache_key = "ct:recent_all:30:1"
    if cache_key in _cache:
        del _cache[cache_key]

    t0 = time.monotonic()
    trades1 = get_recent_trades(days_back=30, max_pages=1)
    t1 = time.monotonic()
    first_call_ms = (t1 - t0) * 1000

    t2 = time.monotonic()
    trades2 = get_recent_trades(days_back=30, max_pages=1)
    t3 = time.monotonic()
    second_call_ms = (t3 - t2) * 1000

    assert second_call_ms < first_call_ms / 5, (
        f"cache hit ({second_call_ms:.1f}ms) should be much faster than "
        f"network call ({first_call_ms:.1f}ms)"
    )
    assert len(trades1) == len(trades2), "cached result must match original"


# ---------------------------------------------------------------------------
# 8. Unknown ticker returns empty list, not raises
# ---------------------------------------------------------------------------

def test_unknown_ticker_returns_empty_not_raises():
    """get_recent_trades_for_ticker with a bogus ticker returns [] and does not raise."""
    result = get_recent_trades_for_ticker("ZZZNOTAREALCOMPANY")
    assert result == [], f"expected [], got {result!r}"
