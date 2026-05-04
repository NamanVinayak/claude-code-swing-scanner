"""Wiki layer tests for System B (four-stage pipeline).

These tests verify:
1. AGENT_MANIFEST has exactly the 8 expected System B stage keys.
2. The 4 new page templates render with valid front-matter and required sections.
3. budget_state template contains all 9 locked rule lines.
4. inject_context() accepts b_* mode names (not blocked by the Phase 1 gate).
5. Bootstrapped pages exist and have parseable front-matter.
6. Bootstrap script is idempotent (second run does not modify files).
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WIKI_ROOT = _PROJECT_ROOT / "wiki"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _has_valid_front_matter(content: str) -> bool:
    """True if the content starts with a --- ... --- YAML block."""
    parts = content.split("---", 2)
    return len(parts) >= 3 and "last_updated" in parts[1]


def _has_section(content: str, heading: str) -> bool:
    """True if '## <heading>' appears in content (case-insensitive)."""
    return f"## {heading}" in content or f"## {heading.lower()}" in content.lower()


# ---------------------------------------------------------------------------
# 1. Manifest has exactly the 8 System B stage keys
# ---------------------------------------------------------------------------

def test_manifest_has_all_b_stages():
    from ai_hedge.wiki.manifest import AGENT_MANIFEST

    expected = {
        "b_scanner", "b_premarket",
        "b_bull_a", "b_bull_b",
        "b_bear_a", "b_bear_b",
        "b_judge", "b_journal",
    }
    assert set(AGENT_MANIFEST.keys()) == expected, (
        f"Unexpected manifest keys. Got: {sorted(AGENT_MANIFEST.keys())}"
    )


# ---------------------------------------------------------------------------
# 2. New templates render with valid front-matter and required sections
# ---------------------------------------------------------------------------

def test_render_new_templates():
    from ai_hedge.wiki.templates import render

    # setup_history is per-ticker
    sh = render("setup_history", ticker="TEST")
    assert _has_valid_front_matter(sh), "setup_history missing front-matter"
    assert _has_section(sh, "TL;DR"), "setup_history missing ## TL;DR"
    assert _has_section(sh, "Setups detected"), "setup_history missing ## Setups detected"
    assert _has_section(sh, "Personality notes"), "setup_history missing ## Personality notes"

    # scanner_state is macro-level (no ticker)
    ss = render("scanner_state")
    assert _has_valid_front_matter(ss), "scanner_state missing front-matter"
    assert _has_section(ss, "TL;DR"), "scanner_state missing ## TL;DR"
    assert _has_section(ss, "Sector breadth"), "scanner_state missing ## Sector breadth"
    assert _has_section(ss, "Signal density"), "scanner_state missing ## Signal density"
    assert _has_section(ss, "Anomalies"), "scanner_state missing ## Anomalies"

    # setup_patterns is meta-level (no ticker)
    sp = render("setup_patterns")
    assert _has_valid_front_matter(sp), "setup_patterns missing front-matter"
    assert _has_section(sp, "TL;DR"), "setup_patterns missing ## TL;DR"
    assert _has_section(sp, "Last 30 days"), "setup_patterns missing ## Last 30 days"
    assert _has_section(sp, "Last 90 days"), "setup_patterns missing ## Last 90 days"

    # budget_state is meta-level (no ticker)
    bs = render("budget_state")
    assert _has_valid_front_matter(bs), "budget_state missing front-matter"
    assert _has_section(bs, "TL;DR"), "budget_state missing ## TL;DR"
    assert _has_section(bs, "Rules (locked)"), "budget_state missing ## Rules (locked)"
    assert _has_section(bs, "Current account state"), "budget_state missing ## Current account state"


def test_render_setup_history_requires_ticker():
    from ai_hedge.wiki.templates import render
    with pytest.raises(ValueError, match="requires ticker"):
        render("setup_history")


def test_render_no_ticker_types_do_not_need_ticker():
    from ai_hedge.wiki.templates import render
    # These must not raise even without ticker
    for kind in ("scanner_state", "setup_patterns", "budget_state", "regime"):
        content = render(kind)
        assert content, f"render('{kind}') returned empty string"


# ---------------------------------------------------------------------------
# 3. budget_state template contains all 9 locked rule lines
# ---------------------------------------------------------------------------

_LOCKED_RULES = [
    "Risk per trade max:",
    "Total open risk cap:",
    "Max simultaneous positions:",
    "Max % deployed:",
    "Single-position cap:",
    "Daily loss stop:",
    "Weekly loss stop:",
    "Scaling: half-size weeks 1",
    "Volatility: VIX > 25",
]


def test_budget_state_has_locked_rules():
    from ai_hedge.wiki.templates import render

    content = render("budget_state")
    for rule in _LOCKED_RULES:
        assert rule in content, (
            f"budget_state template missing locked rule line: '{rule}'"
        )


# ---------------------------------------------------------------------------
# 4. inject_context() accepts System B mode names
# ---------------------------------------------------------------------------

def test_inject_accepts_system_b_modes():
    """b_scanner mode must not be rejected by the Phase 1 mode gate.

    The facts dir won't exist, so we expect the 'facts dir missing' reason —
    NOT 'mode=b_scanner not supported in Phase 1'.
    """
    import os
    original_dir = os.getcwd()
    os.chdir(_PROJECT_ROOT)
    try:
        from ai_hedge.wiki.inject import inject_context
        result = inject_context(run_id="nonexistent_run_xyz", tickers=["AAPL"], mode="b_scanner")
        assert result.get("skipped") is True, f"Expected skipped=True, got: {result}"
        assert result.get("reason") == "facts dir missing", (
            f"Expected 'facts dir missing' but got reason: {result.get('reason')!r}\n"
            "This means the b_* mode gate is blocking System B stages."
        )
    finally:
        os.chdir(original_dir)


def test_inject_still_rejects_unknown_modes():
    """Modes that are neither 'swing' nor 'b_*' must still be rejected."""
    import os
    original_dir = os.getcwd()
    os.chdir(_PROJECT_ROOT)
    try:
        from ai_hedge.wiki.inject import inject_context
        result = inject_context(run_id="nonexistent", tickers=["AAPL"], mode="daytrade")
        assert result.get("skipped") is True
        assert "not supported" in result.get("reason", ""), (
            f"Expected 'not supported' reason for unknown mode, got: {result.get('reason')!r}"
        )
    finally:
        os.chdir(original_dir)


# ---------------------------------------------------------------------------
# 5. Bootstrapped pages exist and have parseable front-matter
# ---------------------------------------------------------------------------

_EXPECTED_BOOTSTRAP_PAGES = [
    "macro/regime.md",
    "macro/scanner_state.md",
    "meta/budget_state.md",
    "meta/lessons.md",
    "meta/setup_patterns.md",
    "meta/open_positions.md",
]


def test_bootstrapped_pages_exist_and_parse():
    import os
    original_dir = os.getcwd()
    os.chdir(_PROJECT_ROOT)
    try:
        from ai_hedge.wiki.loader import parse_front_matter
        for rel in _EXPECTED_BOOTSTRAP_PAGES:
            p = _WIKI_ROOT / rel
            assert p.exists(), f"Bootstrap page missing: wiki/{rel}"
            fm = parse_front_matter(p)
            assert "last_updated" in fm, (
                f"wiki/{rel} has no 'last_updated' in front-matter. Got: {fm}"
            )
            assert "name" in fm, (
                f"wiki/{rel} has no 'name' in front-matter. Got: {fm}"
            )
    finally:
        os.chdir(original_dir)


# ---------------------------------------------------------------------------
# 6. Bootstrap script is idempotent (second run does not modify files)
# ---------------------------------------------------------------------------

def test_bootstrap_script_is_idempotent():
    """Running the bootstrap script twice must not change any file content."""
    bootstrap_script = _PROJECT_ROOT / "scripts" / "wiki_bootstrap_system_b.py"
    assert bootstrap_script.exists(), "bootstrap script not found"

    python = _PROJECT_ROOT / ".venv" / "bin" / "python"

    # Capture hashes before second run
    hashes_before = {rel: _sha256(_WIKI_ROOT / rel) for rel in _EXPECTED_BOOTSTRAP_PAGES}

    # Run bootstrap again (no --force — should skip all existing files)
    result = subprocess.run(
        [str(python), str(bootstrap_script)],
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Bootstrap script failed:\n{result.stderr}"

    # Verify no file content changed
    for rel in _EXPECTED_BOOTSTRAP_PAGES:
        before = hashes_before[rel]
        after = _sha256(_WIKI_ROOT / rel)
        assert before == after, (
            f"wiki/{rel} was modified on second run — bootstrap is NOT idempotent"
        )

    # Verify stdout says 'skipped' for each page, not 'wrote'
    assert "skipped" in result.stdout, (
        f"Expected 'skipped' in bootstrap output on second run.\nGot:\n{result.stdout}"
    )
