"""String templates for wiki page types.

Each template is rendered at bootstrap time (and as a fallback when the
curator must create a fresh page on a brand-new ticker). The curator
otherwise produces page contents directly — these templates are NOT a
strict layout the curator must mimic, just a sane skeleton.

Word-budget metadata lives in the YAML front-matter so the linter and
compactor can enforce it without re-reading this module.

System A (Phase 1) page types: thesis, technicals, catalysts, trades, regime.
System B additions: setup_history (per-ticker), scanner_state (macro),
  setup_patterns (meta), budget_state (meta).
"""

from __future__ import annotations

from datetime import date


def _front_matter(
    *,
    name: str,
    target_words: int,
    stale_after_days: int,
    last_updated: str | None = None,
    last_run_id: str = "bootstrap",
    summary: str = "",
) -> str:
    last = last_updated or date.today().isoformat()
    return (
        "---\n"
        f"name: {name}\n"
        f"last_updated: {last}\n"
        f"last_run_id: {last_run_id}\n"
        f"target_words: {target_words}\n"
        f"stale_after_days: {stale_after_days}\n"
        f"word_count: 0\n"
        f"summary: {summary}\n"
        "---\n\n"
    )


def thesis_template(ticker: str, *, last_run_id: str = "bootstrap") -> str:
    return _front_matter(
        name=f"{ticker} thesis",
        target_words=500,
        stale_after_days=30,
        last_run_id=last_run_id,
        summary="durable bull/bear story",
    ) + (
        f"# {ticker} — Thesis\n\n"
        "## TL;DR\n\n"
        "_Bootstrap placeholder. Fill in after first run._\n\n"
        "## Bull case\n\n"
        "- _pending_\n\n"
        "## Bear case\n\n"
        "- _pending_\n\n"
        "## What would change my mind\n\n"
        "- _pending_\n\n"
        "## Last updated\n\n"
        "_pending_\n"
    )


def technicals_template(ticker: str, *, last_run_id: str = "bootstrap") -> str:
    return _front_matter(
        name=f"{ticker} technicals",
        target_words=350,
        stale_after_days=7,
        last_run_id=last_run_id,
        summary="current chart state",
    ) + (
        f"# {ticker} — Technicals\n\n"
        "## TL;DR\n\n"
        "_Bootstrap placeholder._\n\n"
        "## Multi-timeframe state\n\n"
        "_pending_\n\n"
        "## Key levels\n\n"
        "| level | value |\n"
        "|---|---|\n"
        "| support | _pending_ |\n"
        "| resistance | _pending_ |\n"
        "| entry zone | _pending_ |\n"
        "| invalidation | _pending_ |\n\n"
        "## Setup type\n\n"
        "_pending_\n\n"
        "## Last updated\n\n"
        "_pending_\n"
    )


def catalysts_template(ticker: str, *, last_run_id: str = "bootstrap") -> str:
    return _front_matter(
        name=f"{ticker} catalysts",
        target_words=400,
        stale_after_days=14,
        last_run_id=last_run_id,
        summary="upcoming events + recent news",
    ) + (
        f"# {ticker} — Catalysts\n\n"
        "## TL;DR\n\n"
        "_Bootstrap placeholder._\n\n"
        "## Upcoming events\n\n"
        "- _pending_\n\n"
        "## Recent news synthesis\n\n"
        "- _pending_\n\n"
        "## Insider activity\n\n"
        "_pending_\n\n"
        "## Analyst consensus\n\n"
        "_pending_\n\n"
        "## Last updated\n\n"
        "_pending_\n"
    )


def trades_template(ticker: str, *, last_run_id: str = "bootstrap") -> str:
    return _front_matter(
        name=f"{ticker} trades",
        target_words=800,
        stale_after_days=60,
        last_run_id=last_run_id,
        summary="trade journal for this ticker",
    ) + (
        f"# {ticker} — Trades\n\n"
        "## TL;DR\n\n"
        "_No trades yet._\n\n"
        "## Open positions\n\n"
        "_none_\n\n"
        "## Closed — last 30 days\n\n"
        "_none_\n\n"
        "## Closed — older, rolled by month\n\n"
        "_none_\n\n"
        "## Closed — older than 6 months\n\n"
        "_none_\n\n"
        "## Lifetime stats\n\n"
        "_none_\n"
    )


def regime_template(*, last_run_id: str = "bootstrap") -> str:
    return _front_matter(
        name="macro regime",
        target_words=400,
        stale_after_days=14,
        last_run_id=last_run_id,
        summary="current macro regime",
    ) + (
        "# Macro Regime\n\n"
        "## TL;DR\n\n"
        "_Bootstrap placeholder._\n\n"
        "## Fed posture\n\n"
        "_pending_\n\n"
        "## Rate trajectory & inflation\n\n"
        "_pending_\n\n"
        "## Geopolitical / regulatory\n\n"
        "_pending_\n\n"
        "## Risk-off triggers to watch\n\n"
        "- _pending_\n\n"
        "## Last updated\n\n"
        "_pending_\n"
    )


def setup_history_template(ticker: str, *, last_run_id: str = "bootstrap") -> str:
    return _front_matter(
        name=f"{ticker} setup history",
        target_words=600,
        stale_after_days=14,
        last_run_id=last_run_id,
        summary="rolling log of setups detected and their outcomes",
    ) + (
        f"# {ticker} — Setup History\n\n"
        "## TL;DR\n\n"
        "_Bootstrap placeholder. Fill in after first scanner run detects this ticker._\n\n"
        "## Setups detected\n\n"
        "| date | setup_type | screener_signals | watch_level | outcome |\n"
        "|---|---|---|---|---|\n"
        "| _pending_ | _pending_ | _pending_ | _pending_ | _pending_ |\n\n"
        "## Personality notes\n\n"
        "_No observations yet._\n\n"
        "## Last updated\n\n"
        "_pending_\n"
    )


def scanner_state_template(*, last_run_id: str = "bootstrap") -> str:
    return _front_matter(
        name="scanner state",
        target_words=500,
        stale_after_days=3,
        last_run_id=last_run_id,
        summary="current market breadth + signal density across the universe",
    ) + (
        "# Scanner State\n\n"
        "## TL;DR\n\n"
        "_Bootstrap placeholder. Populated by Stage 1 (Sunset Scanner) on first run._\n\n"
        "## Sector breadth\n\n"
        "_pending_\n\n"
        "## Signal density\n\n"
        "_pending_\n\n"
        "## Anomalies\n\n"
        "_pending_\n\n"
        "## Last updated\n\n"
        "_pending_\n"
    )


def setup_patterns_template(*, last_run_id: str = "bootstrap") -> str:
    return _front_matter(
        name="setup patterns",
        target_words=400,
        stale_after_days=30,
        last_run_id=last_run_id,
        summary="empirical win rate per setup type, last 30/90 days",
    ) + (
        "# Setup Patterns\n\n"
        "## TL;DR\n\n"
        "_Bootstrap placeholder. Populated by Stage 4 (Journal) compactor on Sundays._\n\n"
        "## Last 30 days\n\n"
        "| setup_type | trades | wins | win_rate | avg_pnl | total_pnl |\n"
        "|---|---|---|---|---|---|\n"
        "| _no data_ | — | — | — | — | — |\n\n"
        "## Last 90 days\n\n"
        "| setup_type | trades | wins | win_rate | avg_pnl | total_pnl |\n"
        "|---|---|---|---|---|---|\n"
        "| _no data_ | — | — | — | — | — |\n\n"
        "## Notes\n\n"
        "_No pattern observations yet._\n\n"
        "## Last updated\n\n"
        "_pending_\n"
    )


def budget_state_template(*, last_run_id: str = "bootstrap") -> str:
    return _front_matter(
        name="budget state",
        target_words=800,
        stale_after_days=2,
        last_run_id=last_run_id,
        summary="live capital state and the rules that guard it",
    ) + (
        "# Budget State\n\n"
        "## TL;DR\n\n"
        "Starting capital $25,000. No trades executed yet. System in scaling week 1–2 "
        "(half-size). All rules active.\n\n"
        "## Rules (locked)\n\n"
        "- Risk per trade max:       1.0% of account\n"
        "- Total open risk cap:      4.0% of account\n"
        "- Max simultaneous positions: 5\n"
        "- Max % deployed:           60% (40% cash floor)\n"
        "- Single-position cap:      15% of account\n"
        "- Daily loss stop:          -2% account → pause for the day\n"
        "- Weekly loss stop:         -5% account → system review\n"
        "- Scaling: half-size weeks 1–2, three-quarter weeks 3–4, full from month 2\n"
        "- Volatility: VIX > 25 → cut size 50%; VIX > 30 → no new entries\n\n"
        "## Current account state\n\n"
        "| field | value |\n"
        "|---|---|\n"
        "| Starting capital | $25,000 |\n"
        "| Cash on hand | $25,000 |\n"
        "| Deployed | $0 |\n"
        "| Open risk | $0 (0.0% of account) |\n"
        "| Positions open | 0 |\n\n"
        "## Today's status\n\n"
        "- Paused: no\n"
        "- Daily P&L: $0\n"
        "- Weekly P&L: $0\n\n"
        "## Scaling phase\n\n"
        "- Phase: scaling_week_1_2\n"
        "- Size multiplier: 0.5\n\n"
        "## Volatility regime\n\n"
        "- VIX bucket: _pending (check at run time)_\n"
        "- Size adjustment: none (default)\n\n"
        "## Last updated\n\n"
        "_pending_\n"
    )


# No-ticker page types: regime + System B macro/meta additions.
_NO_TICKER_TYPES = frozenset({"regime", "scanner_state", "setup_patterns", "budget_state"})

PAGE_TEMPLATES = {
    "thesis": thesis_template,
    "technicals": technicals_template,
    "catalysts": catalysts_template,
    "trades": trades_template,
    "regime": regime_template,
    # System B additions
    "setup_history": setup_history_template,
    "scanner_state": scanner_state_template,
    "setup_patterns": setup_patterns_template,
    "budget_state": budget_state_template,
}


def render(page_kind: str, ticker: str | None = None, *, last_run_id: str = "bootstrap") -> str:
    """Render a fresh skeleton for a wiki page type.

    No-ticker types (regime, scanner_state, setup_patterns, budget_state) do
    not require a ticker argument. All other types are per-ticker.
    """
    if page_kind not in PAGE_TEMPLATES:
        raise ValueError(f"unknown page_kind: {page_kind}")
    fn = PAGE_TEMPLATES[page_kind]
    if page_kind in _NO_TICKER_TYPES:
        return fn(last_run_id=last_run_id)
    if not ticker:
        raise ValueError(f"page_kind={page_kind} requires ticker")
    return fn(ticker, last_run_id=last_run_id)
