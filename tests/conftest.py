"""Shared pytest fixtures for System B tests."""
import time
import pytest


@pytest.fixture(autouse=True)
def _tradingview_rate_limit_delay(request):
    """Pause between tests to avoid TradingView 429 rate limits.

    TradingView's public scanner throttles rapid sequential requests.
    A short pre-test sleep ensures each test gets a fresh quota window.
    """
    if "tradingview" in request.fspath.basename:
        time.sleep(5.0)
    yield
