"""Stage 4 journal writer — applies deterministic side effects to the wiki
after the b_journal LLM produces journal_output.json.

Side effects (idempotent):
  1. Append one bullet per closed trade to wiki/meta/lessons.md
     - Each bullet carries a hidden HTML comment marker `<!-- trade_id=N -->`
       so re-runs skip already-logged trades.
  2. Re-render wiki/meta/setup_patterns.md from closed-trade aggregation
     over the last 30 / 90 days.
  3. Re-render wiki/meta/open_positions.md from current open positions.
  4. Update the state sections of wiki/meta/budget_state.md (cash, deployed,
     open risk, scaling phase, today's P&L).  The "Rules (locked)" section
     is preserved verbatim.
  5. Bootstrap wiki pages (thesis, technicals, catalysts, trades, setup_history)
     for any ticker traded today that has no wiki/tickers/<T>/ directory.

`raw_decision` parsing (setup_type, rationale) lives in journal_facts_builder.

System B started_at is hardcoded — phase logic compares wall-clock days to it.
"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Literal
from zoneinfo import ZoneInfo

from ai_hedge.scanners.journal_facts_builder import (
    ClosedTrade,
    JournalFacts,
    OpenTrade,
)
from ai_hedge.wiki import templates
from ai_hedge.wiki.loader import parse_front_matter

logger = logging.getLogger(__name__)

PT_TZ = ZoneInfo("America/Los_Angeles")

# System B paper-trading clock origin — used for phase derivation.
# Per HANDOFF.md, the System B scaffold completed 2026-05-03; first live trade
# can occur from that date onward.
SYSTEM_B_STARTED_AT = date(2026, 5, 3)

# Pages auto-bootstrapped for a brand-new ticker on first journal pass.
_TICKER_PAGE_KINDS = ("thesis", "technicals", "catalysts", "trades", "setup_history")

# Hidden marker embedded in lesson lines for idempotent dedup.
_TRADE_ID_MARKER_RE = re.compile(r"<!--\s*trade_id\s*=\s*(\d+)\s*-->")


# ---------------------------------------------------------------------------
# Phase derivation
# ---------------------------------------------------------------------------

PhaseName = Literal["scaling_week_1_2", "scaling_week_3_4", "full", "paused"]


@dataclass(frozen=True)
class PhaseDecision:
    phase: PhaseName
    size_multiplier: float
    paused_reason: str | None  # set if phase == "paused"


def derive_phase(
    *,
    today_pt: date,
    daily_pnl_usd: float,
    weekly_pnl_usd: float,
    starting_capital_usd: float,
    daily_loss_stop_pct: float = -2.0,
    weekly_loss_stop_pct: float = -5.0,
    started_at: date = SYSTEM_B_STARTED_AT,
) -> PhaseDecision:
    """Compute current scaling phase + size multiplier.

    Phase logic (overrides apply top-down):
      - if daily P&L breaches daily stop → paused (today only)
      - elif weekly P&L breaches weekly stop → paused (system review)
      - elif days_since_start < 14 → scaling_week_1_2 (mult 0.5)
      - elif days_since_start < 28 → scaling_week_3_4 (mult 0.75)
      - else → full (mult 1.0)
    """
    if starting_capital_usd > 0:
        daily_pct = daily_pnl_usd / starting_capital_usd * 100.0
        weekly_pct = weekly_pnl_usd / starting_capital_usd * 100.0
    else:
        daily_pct = 0.0
        weekly_pct = 0.0

    if daily_pct <= daily_loss_stop_pct:
        return PhaseDecision(
            phase="paused",
            size_multiplier=0.0,
            paused_reason=f"daily loss stop ({daily_pct:.2f}% ≤ {daily_loss_stop_pct}%)",
        )
    if weekly_pct <= weekly_loss_stop_pct:
        return PhaseDecision(
            phase="paused",
            size_multiplier=0.0,
            paused_reason=f"weekly loss stop ({weekly_pct:.2f}% ≤ {weekly_loss_stop_pct}%)",
        )

    days = max(0, (today_pt - started_at).days)
    if days < 14:
        return PhaseDecision(phase="scaling_week_1_2", size_multiplier=0.5, paused_reason=None)
    if days < 28:
        return PhaseDecision(phase="scaling_week_3_4", size_multiplier=0.75, paused_reason=None)
    return PhaseDecision(phase="full", size_multiplier=1.0, paused_reason=None)


# ---------------------------------------------------------------------------
# Setup-pattern aggregation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PatternRow:
    setup_type: str
    trades: int
    wins: int
    win_rate_pct: float
    avg_pnl_usd: float
    total_pnl_usd: float


def aggregate_patterns(closed_trades: Iterable[ClosedTrade]) -> list[PatternRow]:
    """Group closed trades by setup_type and compute summary stats."""
    by_setup: dict[str, list[ClosedTrade]] = defaultdict(list)
    for t in closed_trades:
        if t.pnl is None:
            continue  # cannot aggregate without P&L
        by_setup[t.setup_type or "unknown"].append(t)

    rows: list[PatternRow] = []
    for setup, trades in sorted(by_setup.items()):
        n = len(trades)
        wins = sum(1 for t in trades if t.won)
        total = sum((t.pnl or 0.0) for t in trades)
        avg = total / n if n else 0.0
        wr = (wins / n * 100.0) if n else 0.0
        rows.append(PatternRow(
            setup_type=setup,
            trades=n,
            wins=wins,
            win_rate_pct=round(wr, 1),
            avg_pnl_usd=round(avg, 2),
            total_pnl_usd=round(total, 2),
        ))
    # Order: trade count desc, then setup_type asc for stability
    rows.sort(key=lambda r: (-r.trades, r.setup_type))
    return rows


def render_pattern_table(rows: list[PatternRow]) -> str:
    if not rows:
        return (
            "| _no data_ | — | — | — | — | — |"
        )
    lines = []
    for r in rows:
        lines.append(
            f"| {r.setup_type} | {r.trades} | {r.wins} | "
            f"{r.win_rate_pct:.1f}% | ${r.avg_pnl_usd:+,.2f} | ${r.total_pnl_usd:+,.2f} |"
        )
    return "\n".join(lines)


def render_setup_patterns_md(
    *,
    rows_30d: list[PatternRow],
    rows_90d: list[PatternRow],
    today: date,
    last_run_id: str,
    notes: str | None = None,
) -> str:
    """Render the full setup_patterns.md page (front matter + body)."""
    fm = (
        "---\n"
        "name: setup patterns\n"
        f"last_updated: {today.isoformat()}\n"
        f"last_run_id: {last_run_id}\n"
        "target_words: 400\n"
        "stale_after_days: 30\n"
        "word_count: 0\n"
        "summary: empirical win rate per setup type, last 30/90 days\n"
        "---\n\n"
    )
    notes_block = (notes.strip() if notes else "_No pattern observations yet._")
    body = (
        "# Setup Patterns\n\n"
        "## TL;DR\n\n"
        f"Refreshed by Stage 4 (b_journal) on {today.isoformat()}. "
        f"{len(rows_30d)} setup type(s) traded in the last 30 days; "
        f"{len(rows_90d)} in the last 90 days.\n\n"
        "## Last 30 days\n\n"
        "| setup_type | trades | wins | win_rate | avg_pnl | total_pnl |\n"
        "|---|---|---|---|---|---|\n"
        f"{render_pattern_table(rows_30d)}\n\n"
        "## Last 90 days\n\n"
        "| setup_type | trades | wins | win_rate | avg_pnl | total_pnl |\n"
        "|---|---|---|---|---|---|\n"
        f"{render_pattern_table(rows_90d)}\n\n"
        "## Notes\n\n"
        f"{notes_block}\n\n"
        "## Last updated\n\n"
        f"{today.isoformat()} (run `{last_run_id}`)\n"
    )
    return fm + body


# ---------------------------------------------------------------------------
# Open positions snapshot
# ---------------------------------------------------------------------------

def _unrealized_pnl(direction: str, entry: float | None, current: float | None, qty: int | None) -> float | None:
    if entry is None or current is None or qty is None:
        return None
    if direction == "long":
        return round((current - entry) * qty, 2)
    if direction == "short":
        return round((entry - current) * qty, 2)
    return None


def _unrealized_pct(direction: str, entry: float | None, current: float | None) -> float | None:
    if entry is None or current is None or not entry:
        return None
    if direction == "long":
        return round((current - entry) / entry * 100, 2)
    if direction == "short":
        return round((entry - current) / entry * 100, 2)
    return None


def render_open_positions_md(
    *,
    open_positions: list[OpenTrade],
    current_prices: dict[str, float | None],
    snapshot_at_pt: datetime,
    last_run_id: str,
) -> str:
    today = snapshot_at_pt.date()
    fm = (
        "---\n"
        "name: open positions snapshot\n"
        f"last_updated: {today.isoformat()}\n"
        f"last_run_id: {last_run_id}\n"
        "target_words: 600\n"
        "stale_after_days: 2\n"
        "word_count: 0\n"
        "summary: Structured ledger view of currently-open and pending swing trades. Refreshed nightly.\n"
        "---\n\n"
    )

    n_open = len(open_positions)
    long_count = sum(1 for p in open_positions if p.direction == "long")
    short_count = sum(1 for p in open_positions if p.direction == "short")
    tickers = sorted({p.ticker for p in open_positions})
    tickers_str = ", ".join(tickers) if tickers else "_none_"

    summary_block = (
        "## Summary\n\n"
        f"- Open positions: {n_open}\n"
        "- Pending orders: 0\n"
        f"- Net long count: {long_count}\n"
        f"- Net short count: {short_count}\n"
        f"- Tickers held: {tickers_str}\n\n"
    )

    if not open_positions:
        positions_block = "## Open positions\n\n_none_\n\n"
    else:
        rows = []
        for p in open_positions:
            current = current_prices.get(p.ticker)
            entered_dt: datetime | None
            try:
                entered_dt = datetime.fromisoformat(str(p.entered_at).replace("Z", "+00:00")) if p.entered_at else None
                if entered_dt and entered_dt.tzinfo is None:
                    entered_dt = entered_dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                entered_dt = None

            days = None
            if entered_dt is not None:
                days = max(0, (snapshot_at_pt.astimezone(timezone.utc).date() - entered_dt.date()).days)

            unreal_dollars = _unrealized_pnl(p.direction, p.entry_price, current, p.quantity)
            unreal_pct = _unrealized_pct(p.direction, p.entry_price, current)

            row = (
                f"| {p.ticker} | {p.direction} | {p.quantity} | "
                f"{_fmt_price(p.entry_price)} | {_fmt_price(current)} | "
                f"{_fmt_price(p.stop_loss)} | {_fmt_price(p.target_price)} | "
                f"{days if days is not None else '—'} | "
                f"{_fmt_signed_dollars(unreal_dollars)} | "
                f"{_fmt_signed_pct(unreal_pct)} | "
                f"{p.run_id or '—'} |"
            )
            rows.append(row)

        positions_block = (
            "## Open positions\n\n"
            "| Ticker | Dir | Qty | Entry | Current | Stop | Target | Days | Unreal $ | Unreal % | Run |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|\n"
            + "\n".join(rows) + "\n\n"
        )

    pending_block = "## Pending orders\n\n_none_\n\n"

    field_defs = (
        "## Field definitions\n\n"
        "- **Dir**: `long` or `short`.\n"
        "- **Entry**: actual fill price for open positions; limit price for pending orders.\n"
        "- **Current**: most recent traded price at snapshot time.\n"
        "- **Days**: trading days between entry and snapshot (open positions only).\n"
        "- **Unreal $/%**: unrealized P&L from entry to current price.\n"
        "- **Run**: the run_id that originated this position.\n"
    )

    header = (
        "# Open Positions — Snapshot\n\n"
        f"Snapshot taken: `{snapshot_at_pt.isoformat()}`. Refreshed nightly by Stage 4 (b_journal).\n\n"
    )

    return fm + header + summary_block + positions_block + pending_block + field_defs


def _fmt_price(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:.2f}"


def _fmt_signed_dollars(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:+,.2f}"


def _fmt_signed_pct(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:+.2f}%"


# ---------------------------------------------------------------------------
# Budget state state-section update (preserves Rules section)
# ---------------------------------------------------------------------------

def _replace_section(
    text: str,
    header: str,
    new_content: str,
    *,
    keep_blank_line_after: bool = True,
) -> str:
    """Replace the body of `## {header}` with `new_content`. Inserts the
    section just before `## Last updated` if missing.
    """
    pattern = re.compile(
        r"(##\s+" + re.escape(header) + r"\s*\n)(.*?)(?=\n##\s|\Z)",
        re.DOTALL,
    )
    replacement = (
        r"\1" + new_content.rstrip() + ("\n\n" if keep_blank_line_after else "\n")
    )
    new_text, count = pattern.subn(replacement, text, count=1)
    if count == 0:
        # Section not found; append before "## Last updated" if it exists, else at end.
        if "## Last updated" in new_text:
            new_text = new_text.replace(
                "## Last updated",
                f"## {header}\n\n{new_content.rstrip()}\n\n## Last updated",
                1,
            )
        else:
            new_text = new_text.rstrip() + f"\n\n## {header}\n\n{new_content.rstrip()}\n"
    return new_text


def update_budget_state_md(
    *,
    current_md: str,
    starting_capital_usd: float,
    cash_usd: float,
    deployed_usd: float,
    open_risk_usd: float,
    open_risk_pct: float,
    positions_open: int,
    daily_pnl_usd: float,
    weekly_pnl_usd: float,
    phase: PhaseDecision,
    today: date,
    last_run_id: str,
    vix_bucket_note: str | None = None,
) -> str:
    """Update the state sections of budget_state.md, preserving the Rules block.

    Sections rewritten: front matter (last_updated, last_run_id), TL;DR,
    Current account state, Today's status, Scaling phase, Volatility regime,
    Last updated.
    """
    text = current_md

    # --- Front matter rewrite (preserve unknown keys) -----------------------
    text = _update_front_matter(text, today=today, last_run_id=last_run_id)

    # --- TL;DR --------------------------------------------------------------
    paused_note = ""
    if phase.phase == "paused":
        paused_note = f" SYSTEM PAUSED: {phase.paused_reason}."
    tldr_body = (
        f"Account ${starting_capital_usd:,.0f} starting → cash ${cash_usd:,.2f}, "
        f"deployed ${deployed_usd:,.2f} ({_pct(deployed_usd, starting_capital_usd):.1f}%), "
        f"open risk ${open_risk_usd:,.2f} ({open_risk_pct:.2f}% of account) across "
        f"{positions_open} position(s). Phase: `{phase.phase}` (size multiplier "
        f"{phase.size_multiplier}).{paused_note}"
    )
    text = _replace_section(text, "TL;DR", tldr_body)

    # --- Current account state ---------------------------------------------
    state_table = (
        "| field | value |\n"
        "|---|---|\n"
        f"| Starting capital | ${starting_capital_usd:,.0f} |\n"
        f"| Cash on hand | ${cash_usd:,.2f} |\n"
        f"| Deployed | ${deployed_usd:,.2f} |\n"
        f"| Open risk | ${open_risk_usd:,.2f} ({open_risk_pct:.2f}% of account) |\n"
        f"| Positions open | {positions_open} |"
    )
    text = _replace_section(text, "Current account state", state_table)

    # --- Today's status -----------------------------------------------------
    paused_str = "yes" if phase.phase == "paused" else "no"
    paused_line = f"- Paused: {paused_str}"
    if phase.phase == "paused" and phase.paused_reason:
        paused_line = f"- Paused: yes — {phase.paused_reason}"
    status_body = (
        f"{paused_line}\n"
        f"- Daily P&L: {_fmt_signed_dollars(daily_pnl_usd)}\n"
        f"- Weekly P&L: {_fmt_signed_dollars(weekly_pnl_usd)}"
    )
    text = _replace_section(text, "Today's status", status_body)

    # --- Scaling phase ------------------------------------------------------
    scaling_body = (
        f"- Phase: {phase.phase}\n"
        f"- Size multiplier: {phase.size_multiplier}"
    )
    text = _replace_section(text, "Scaling phase", scaling_body)

    # --- Volatility regime --------------------------------------------------
    if vix_bucket_note is None:
        vix_body = (
            "- VIX bucket: _not measured this run_\n"
            "- Size adjustment: none (default)"
        )
    else:
        vix_body = vix_bucket_note
    text = _replace_section(text, "Volatility regime", vix_body)

    # --- Last updated -------------------------------------------------------
    text = _replace_section(
        text, "Last updated", f"{today.isoformat()} (run `{last_run_id}`)",
        keep_blank_line_after=False,
    )

    return text


def _pct(numerator: float, denominator: float) -> float:
    return (numerator / denominator * 100.0) if denominator else 0.0


def _update_front_matter(text: str, *, today: date, last_run_id: str) -> str:
    """Update last_updated + last_run_id in the YAML front matter, preserve rest."""
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    raw_fm = parts[1]
    body = parts[2]

    new_lines: list[str] = []
    saw_last_updated = False
    saw_last_run = False
    for line in raw_fm.splitlines():
        stripped = line.strip()
        if stripped.startswith("last_updated:"):
            new_lines.append(f"last_updated: {today.isoformat()}")
            saw_last_updated = True
        elif stripped.startswith("last_run_id:"):
            new_lines.append(f"last_run_id: {last_run_id}")
            saw_last_run = True
        else:
            new_lines.append(line)
    if not saw_last_updated:
        new_lines.append(f"last_updated: {today.isoformat()}")
    if not saw_last_run:
        new_lines.append(f"last_run_id: {last_run_id}")

    # Trailing newline ensures the closing `---` fence lands on its own line.
    new_fm = "\n".join(new_lines) + "\n"
    return f"---{new_fm}---{body}"


# ---------------------------------------------------------------------------
# Lessons append (idempotent via trade-id markers)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LessonInput:
    """One lesson the LLM produced (or a fallback bullet for a closed trade)."""
    trade_id: int
    line: str  # e.g. "2026-05-04 | NVDA | breakout | -$63.20 | stop trip ..."


def existing_trade_ids(lessons_md: str) -> set[int]:
    """Return the set of trade IDs already logged in lessons.md."""
    return {int(m.group(1)) for m in _TRADE_ID_MARKER_RE.finditer(lessons_md)}


def render_lesson_bullet(lesson: LessonInput) -> str:
    """Render one lesson as a markdown bullet line with the dedup marker."""
    line = lesson.line.strip()
    if line.startswith("- "):
        line = line[2:]
    return f"- {line} <!-- trade_id={lesson.trade_id} -->"


def append_lessons(
    *,
    current_md: str,
    new_lessons: list[LessonInput],
    today: date,
    last_run_id: str,
    pattern_rows_30d: list[PatternRow] | None = None,
) -> tuple[str, list[int]]:
    """Append lesson bullets under `## Lessons`, replacing the placeholder if
    present, and refresh the inline 30-day pattern table.

    Returns (new_md, ids_added).
    """
    seen = existing_trade_ids(current_md)
    to_add = [le for le in new_lessons if le.trade_id not in seen]
    ids_added = [le.trade_id for le in to_add]

    text = _update_front_matter(current_md, today=today, last_run_id=last_run_id)

    if pattern_rows_30d is not None:
        text = _replace_pattern_table_in_lessons(text, pattern_rows_30d)

    if not to_add:
        return text, ids_added

    new_block = "\n".join(render_lesson_bullet(le) for le in to_add)

    if "_No lessons yet" in text:
        text = re.sub(
            r"_No lessons yet[^\n]*_",
            new_block,
            text,
            count=1,
        )
    else:
        # Append at the end of the `## Lessons` section.
        if re.search(r"^##\s+Lessons\s*$", text, re.MULTILINE):
            text = re.sub(
                r"(##\s+Lessons\s*\n)(.*)\Z",
                lambda m: m.group(1) + (m.group(2).rstrip() + "\n\n" + new_block + "\n"),
                text,
                count=1,
                flags=re.DOTALL,
            )
        else:
            # No Lessons section — append one.
            text = text.rstrip() + "\n\n## Lessons\n\n" + new_block + "\n"

    return text, ids_added


def _replace_pattern_table_in_lessons(text: str, rows_30d: list[PatternRow]) -> str:
    """The lessons.md page has an inline patterns table refreshed by this
    writer. Replace it. Locator: heading 'Patterns (auto-generated...)'."""
    table = (
        "| Setup Type | Trades | Wins | Win Rate | Avg P&L | Total P&L |\n"
        "|---|---|---|---|---|---|\n"
        + (
            "\n".join(
                f"| {r.setup_type} | {r.trades} | {r.wins} | "
                f"{r.win_rate_pct:.1f}% | ${r.avg_pnl_usd:+,.2f} | ${r.total_pnl_usd:+,.2f} |"
                for r in rows_30d
            ) if rows_30d else "| _no data yet_ | — | — | — | — | — |"
        )
    )
    pattern = re.compile(
        r"(##\s+Patterns[^\n]*\n\n)(\|[^\n]*\n\|[^\n]*\n(?:\|[^\n]*\n)*)",
        re.MULTILINE,
    )
    if pattern.search(text):
        return pattern.sub(lambda m: m.group(1) + table + "\n", text, count=1)
    return text


# ---------------------------------------------------------------------------
# Auto-bootstrap wiki pages for new tickers
# ---------------------------------------------------------------------------

def bootstrap_ticker_wiki(
    ticker: str,
    *,
    wiki_root: Path = Path("wiki"),
    last_run_id: str = "b_journal_bootstrap",
) -> list[str]:
    """Create skeleton pages for a new ticker. Idempotent — skips existing files.

    Returns the list of relative paths actually written.
    """
    ticker = ticker.upper()
    tdir = wiki_root / "tickers" / ticker
    tdir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for kind in _TICKER_PAGE_KINDS:
        target = tdir / f"{kind}.md"
        if target.exists():
            continue
        content = templates.render(kind, ticker=ticker, last_run_id=last_run_id)
        target.write_text(content)
        written.append(str(target.relative_to(wiki_root)))
    return written


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------

@dataclass
class JournalWriteSummary:
    new_tickers_bootstrapped: list[str] = field(default_factory=list)
    pages_bootstrapped: list[str] = field(default_factory=list)
    lessons_appended_ids: list[int] = field(default_factory=list)
    lessons_skipped_ids: list[int] = field(default_factory=list)
    setup_patterns_refreshed: bool = False
    open_positions_refreshed: bool = False
    budget_state_refreshed: bool = False
    paths_written: list[str] = field(default_factory=list)


def apply_journal_writes(
    *,
    facts: JournalFacts,
    llm_output: dict[str, Any] | None,
    current_prices: dict[str, float | None] | None = None,
    weekly_pnl_usd: float | None = None,
    starting_capital_usd: float = 25_000.0,
    wiki_root: Path = Path("wiki"),
    today_pt: date | None = None,
    last_run_id: str | None = None,
) -> JournalWriteSummary:
    """Apply every Stage 4 side effect in one pass.

    `llm_output` is the parsed `journal_output.json` from the b_journal agent.
    Expected keys (all optional):
        lessons: list[{trade_id: int, line: str}]
        pattern_notes: str
    If `llm_output` is None or missing lessons, fallback bullets are generated.
    """
    today = today_pt or datetime.now(PT_TZ).date()
    last_run_id = last_run_id or facts.run_id
    summary = JournalWriteSummary()

    wiki_root.mkdir(parents=True, exist_ok=True)
    (wiki_root / "meta").mkdir(parents=True, exist_ok=True)
    (wiki_root / "tickers").mkdir(parents=True, exist_ok=True)

    # ----- 1. Bootstrap new ticker pages ------------------------------------
    for t in facts.new_tickers_today:
        pages = bootstrap_ticker_wiki(t, wiki_root=wiki_root, last_run_id=last_run_id)
        if pages:
            summary.new_tickers_bootstrapped.append(t)
            summary.pages_bootstrapped.extend(pages)

    # ----- 2. Setup patterns aggregation ------------------------------------
    rows_30d = aggregate_patterns(facts.closed_last_30d)
    rows_90d = aggregate_patterns(facts.closed_last_90d)
    notes = None
    if isinstance(llm_output, dict):
        raw_notes = llm_output.get("pattern_notes")
        if raw_notes:
            notes = str(raw_notes).strip()

    sp_path = wiki_root / "meta" / "setup_patterns.md"
    sp_md = render_setup_patterns_md(
        rows_30d=rows_30d, rows_90d=rows_90d,
        today=today, last_run_id=last_run_id, notes=notes,
    )
    sp_path.write_text(sp_md)
    summary.setup_patterns_refreshed = True
    summary.paths_written.append(str(sp_path))

    # ----- 3. Open positions snapshot ---------------------------------------
    prices = current_prices or {}
    snapshot_at_pt = datetime.now(PT_TZ)
    op_path = wiki_root / "meta" / "open_positions.md"
    op_md = render_open_positions_md(
        open_positions=facts.open_positions,
        current_prices=prices,
        snapshot_at_pt=snapshot_at_pt,
        last_run_id=last_run_id,
    )
    op_path.write_text(op_md)
    summary.open_positions_refreshed = True
    summary.paths_written.append(str(op_path))

    # ----- 4. Budget state state-sections -----------------------------------
    bs_path = wiki_root / "meta" / "budget_state.md"
    current_bs = bs_path.read_text(encoding="utf-8") if bs_path.exists() else templates.budget_state_template()
    deployed_usd = sum(
        (p.entry_price or 0.0) * (p.quantity or 0) for p in facts.open_positions
    )
    open_risk_usd = sum(
        abs((p.entry_price or 0.0) - (p.stop_loss or 0.0)) * (p.quantity or 0)
        for p in facts.open_positions
    )
    open_risk_pct = (open_risk_usd / starting_capital_usd * 100.0) if starting_capital_usd else 0.0
    cash_usd = starting_capital_usd - deployed_usd

    weekly_pnl = weekly_pnl_usd if weekly_pnl_usd is not None else _weekly_pnl_from_facts(facts, today)
    phase = derive_phase(
        today_pt=today,
        daily_pnl_usd=facts.realized_pnl_today_usd,
        weekly_pnl_usd=weekly_pnl,
        starting_capital_usd=starting_capital_usd,
    )
    new_bs = update_budget_state_md(
        current_md=current_bs,
        starting_capital_usd=starting_capital_usd,
        cash_usd=cash_usd,
        deployed_usd=deployed_usd,
        open_risk_usd=open_risk_usd,
        open_risk_pct=open_risk_pct,
        positions_open=len(facts.open_positions),
        daily_pnl_usd=facts.realized_pnl_today_usd,
        weekly_pnl_usd=weekly_pnl,
        phase=phase,
        today=today,
        last_run_id=last_run_id,
    )
    bs_path.write_text(new_bs)
    summary.budget_state_refreshed = True
    summary.paths_written.append(str(bs_path))

    # ----- 5. Lessons append ------------------------------------------------
    lessons_path = wiki_root / "meta" / "lessons.md"
    current_lessons = lessons_path.read_text(encoding="utf-8") if lessons_path.exists() else ""
    new_lessons = _build_lesson_inputs(facts, llm_output, today)

    seen_ids = existing_trade_ids(current_lessons)
    summary.lessons_skipped_ids = [le.trade_id for le in new_lessons if le.trade_id in seen_ids]

    new_lessons_md, ids_added = append_lessons(
        current_md=current_lessons,
        new_lessons=new_lessons,
        today=today,
        last_run_id=last_run_id,
        pattern_rows_30d=rows_30d,
    )
    lessons_path.write_text(new_lessons_md)
    summary.lessons_appended_ids = ids_added
    summary.paths_written.append(str(lessons_path))

    return summary


def _weekly_pnl_from_facts(facts: JournalFacts, today: date) -> float:
    """Sum of realized PnL for trades closed within the last 7 days (today inclusive)."""
    cutoff = today - timedelta(days=7)
    total = 0.0
    for t in facts.closed_last_30d:
        if not t.closed_at or t.pnl is None:
            continue
        try:
            d = datetime.fromisoformat(str(t.closed_at).replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            continue
        if d >= cutoff:
            total += t.pnl
    return round(total, 2)


def _build_lesson_inputs(
    facts: JournalFacts,
    llm_output: dict[str, Any] | None,
    today: date,
) -> list[LessonInput]:
    """Use LLM-produced lessons when available; fall back to deterministic
    one-liners that still capture trade_id, ticker, setup_type, P&L."""
    if isinstance(llm_output, dict):
        raw = llm_output.get("lessons") or []
        out: list[LessonInput] = []
        # Map closed-today trades by id for fallback enrichment.
        by_id = {t.trade_id: t for t in facts.closed_today}
        for item in raw:
            if not isinstance(item, dict):
                continue
            tid = item.get("trade_id")
            line = item.get("line") or ""
            if tid is None:
                continue
            try:
                tid_int = int(tid)
            except (TypeError, ValueError):
                continue
            line = str(line).strip()
            if not line:
                # Synthesize from facts if LLM returned an empty line.
                tr = by_id.get(tid_int)
                if tr is not None:
                    line = _fallback_line(tr, today)
                else:
                    continue
            out.append(LessonInput(trade_id=tid_int, line=line))
        if out:
            return out

    # Total fallback: synthesize a bullet from each closed_today trade.
    return [LessonInput(trade_id=t.trade_id, line=_fallback_line(t, today))
            for t in facts.closed_today]


def _fallback_line(t: ClosedTrade, today: date) -> str:
    """Deterministic lesson bullet when no LLM "why" is available."""
    pnl_str = _fmt_signed_dollars(t.pnl) if t.pnl is not None else "—"
    why = (
        "auto-generated (no LLM why available); "
        f"status {t.status}, exit {_fmt_price(t.exit_price)}, "
        f"held {t.days_held if t.days_held is not None else '?'}d"
    )
    return f"{today.isoformat()} | {t.ticker} | {t.setup_type} | {pnl_str} | {why}"


__all__ = [
    "PhaseDecision",
    "PatternRow",
    "LessonInput",
    "JournalWriteSummary",
    "SYSTEM_B_STARTED_AT",
    "derive_phase",
    "aggregate_patterns",
    "render_pattern_table",
    "render_setup_patterns_md",
    "render_open_positions_md",
    "update_budget_state_md",
    "existing_trade_ids",
    "render_lesson_bullet",
    "append_lessons",
    "bootstrap_ticker_wiki",
    "apply_journal_writes",
]
