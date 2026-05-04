"""Per-stage wiki reading manifest for System B (four-stage pipeline).

Each entry says: for this pipeline stage, what pages does it read, and in
what mode (`tldr` = only the TL;DR section; `full` = entire page).

Pages are referenced as a (category, basename, mode) triple. Per-ticker
pages use category `"ticker"`; macro pages use `"macro"`; meta pages use
`"meta"`.

The injector walks this manifest and assembles a `wiki_context` dict per
(stage, ticker) which gets merged into the existing facts bundle.

System B stages: b_scanner, b_premarket, b_bull_a, b_bull_b, b_bear_a,
  b_bear_b, b_judge, b_journal.
"""

from __future__ import annotations

# (category, basename, mode)
#  category: "ticker" (one per analysis ticker), "macro", "meta"
#  basename: filename without .md
#  mode: "tldr" or "full"
AGENT_MANIFEST: dict[str, list[tuple[str, str, str]]] = {
    # Stage 1 — Sunset Scanner. Mostly mechanical; the LLM synthesizer at
    # the end reads market-wide context to write a paragraph for the watchlist.
    "b_scanner": [
        ("macro", "regime", "full"),
        ("macro", "scanner_state", "full"),
        ("meta", "setup_patterns", "full"),
    ],

    # Stage 2 — Pre-market Reviewer. Per-ticker mini-agents (one per candidate)
    # check whether yesterday's setup is still valid given overnight news.
    "b_premarket": [
        ("ticker", "setup_history", "tldr"),
        ("ticker", "recent", "tldr"),  # `recent.md` is inherited from System A's templates
        ("macro", "regime", "tldr"),
    ],

    # Stage 3 — Adversarial Decision: 2 bull + 2 bear agents per surviving candidate.
    # All four read the same per-ticker context; they differ only in adversarial framing
    # via their prompt (not via what they read).
    "b_bull_a": [
        ("ticker", "thesis", "full"),
        ("ticker", "catalysts", "full"),
        ("ticker", "technicals", "full"),
    ],
    "b_bull_b": [
        ("ticker", "thesis", "full"),
        ("ticker", "catalysts", "full"),
        ("ticker", "technicals", "full"),
    ],
    "b_bear_a": [
        ("ticker", "thesis", "full"),
        ("ticker", "catalysts", "full"),
        ("ticker", "technicals", "full"),
    ],
    "b_bear_b": [
        ("ticker", "thesis", "full"),
        ("ticker", "catalysts", "full"),
        ("ticker", "technicals", "full"),
    ],

    # Stage 3 — Judge. Reads the four perspectives + the global discipline pages.
    # The judge is the gate that enforces capital allocation rules.
    "b_judge": [
        ("ticker", "thesis", "tldr"),
        ("ticker", "trades", "full"),
        ("meta", "lessons", "full"),
        ("meta", "setup_patterns", "full"),
        ("meta", "budget_state", "full"),
        ("meta", "open_positions", "full"),
    ],

    # Stage 4 — End-of-Day Journal. Reads everything for today's tickers and
    # writes lessons + updates per-ticker pages + updates budget_state.
    "b_journal": [
        ("ticker", "trades", "full"),
        ("ticker", "setup_history", "full"),
        ("meta", "lessons", "full"),
        ("meta", "setup_patterns", "full"),
        ("meta", "budget_state", "full"),
        ("meta", "open_positions", "full"),
    ],
}


def pages_for(agent: str) -> list[tuple[str, str, str]]:
    """Return the manifest entries for an agent (empty list if not listed)."""
    return AGENT_MANIFEST.get(agent, [])


def agents_with_wiki_context() -> list[str]:
    """Names of agents whose prompts must mention `wiki_context`."""
    return list(AGENT_MANIFEST.keys())
