"""Stage 4 journal facts builder — assembles `journal_facts.json` from Turso
and the wiki, ready for the b_journal LLM agent.

Reads:
  - Turso: today's b_swing closed trades, open positions, recent (90d) closed trades
  - Wiki: meta pages (lessons, setup_patterns, budget_state, open_positions)
          per-ticker pages (trades, setup_history) for each ticker that traded today

Writes:
  - runs/<run_id>/journal_facts.json     (the canonical facts bundle)
  - runs/<run_id>/facts/b_journal__GLOBAL.json  (mirror for inject_context)

The orchestrator dispatches one b_journal agent which reads journal_facts.json
and emits journal_output.json. journal_writer then applies side effects.

`raw_decision` is a JSON-serialized dict stored on each trade row by
ingest_decisions; we parse it to recover setup_type, rationale, conviction.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

PT_TZ = ZoneInfo("America/Los_Angeles")
B_SWING_MODE = "b_swing"
CLOSE_STATUSES = ("target_hit", "stop_hit", "expired")
OPEN_STATUSES = ("entered",)


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ClosedTrade:
    """One trade closed today (or in the lookback window)."""
    trade_id: int
    ticker: str
    direction: str               # "long" or "short"
    setup_type: str
    quantity: int
    entry_price: float | None
    exit_price: float | None
    stop_loss: float | None
    target_price: float | None
    pnl: float | None
    status: str                  # "target_hit" | "stop_hit" | "expired"
    confidence: int | None
    rationale: str
    expected_holding_days: int | None
    entered_at: str | None
    closed_at: str | None
    days_held: int | None
    won: bool                    # pnl > 0
    run_id: str | None


@dataclass
class OpenTrade:
    """One trade currently open (status='entered')."""
    trade_id: int
    ticker: str
    direction: str
    setup_type: str
    quantity: int
    entry_price: float | None
    stop_loss: float | None
    target_price: float | None
    target_price_2: float | None
    confidence: int | None
    timeframe: str | None
    entered_at: str | None
    run_id: str | None


@dataclass
class JournalFacts:
    """Top-level bundle written to journal_facts.json."""
    run_id: str
    journal_date_pt: str         # YYYY-MM-DD in PT
    generated_at_utc: str
    closed_today: list[ClosedTrade]
    open_positions: list[OpenTrade]
    closed_last_30d: list[ClosedTrade]   # for setup_patterns aggregation
    closed_last_90d: list[ClosedTrade]
    tickers_today: list[str]             # union of closed_today + open positions opened today
    new_tickers_today: list[str]         # tickers traded today with no wiki/tickers/<T>/ dir
    realized_pnl_today_usd: float
    wiki_excerpts: dict[str, Any]        # per-ticker + meta page excerpts
    wiki_context: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _today_pt_bounds(today_pt: date | None = None) -> tuple[datetime, datetime]:
    """Return [start_of_day_PT, end_of_day_PT) as UTC datetimes."""
    today = today_pt or datetime.now(PT_TZ).date()
    start_pt = datetime.combine(today, time(0, 0), tzinfo=PT_TZ)
    end_pt = start_pt + timedelta(days=1)
    return start_pt.astimezone(timezone.utc), end_pt.astimezone(timezone.utc)


def _parse_raw_decision(raw: Any) -> dict[str, Any]:
    """Parse the JSON-stringified raw_decision column. Returns {} on failure."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(str(raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _row_to_closed(row: dict[str, Any]) -> ClosedTrade:
    """Convert a Turso row → ClosedTrade dataclass."""
    rd = _parse_raw_decision(row.get("raw_decision"))
    entered = _parse_iso(row.get("entered_at"))
    closed = _parse_iso(row.get("closed_at"))
    days_held: int | None = None
    if entered and closed:
        days_held = max(0, (closed.date() - entered.date()).days)

    pnl = row.get("pnl")
    pnl_val: float | None = None
    if pnl is not None:
        try:
            pnl_val = float(pnl)
        except (TypeError, ValueError):
            pnl_val = None

    return ClosedTrade(
        trade_id=int(row.get("id", 0) or 0),
        ticker=str(row.get("ticker", "")).upper(),
        direction=str(row.get("direction", "long")),
        setup_type=str(rd.get("setup_type", "unknown")),
        quantity=int(row.get("quantity", 0) or 0),
        entry_price=_safe_float(row.get("entry_fill_price") or row.get("entry_price")),
        exit_price=_safe_float(row.get("exit_fill_price")),
        stop_loss=_safe_float(row.get("stop_loss")),
        target_price=_safe_float(row.get("target_price")),
        pnl=pnl_val,
        status=str(row.get("status", "")),
        confidence=_safe_int(row.get("confidence")),
        rationale=str(rd.get("rationale", "")),
        expected_holding_days=_safe_int(rd.get("expected_holding_days")),
        entered_at=str(row.get("entered_at") or "") or None,
        closed_at=str(row.get("closed_at") or "") or None,
        days_held=days_held,
        won=(pnl_val is not None and pnl_val > 0),
        run_id=str(row.get("run_id") or "") or None,
    )


def _row_to_open(row: dict[str, Any]) -> OpenTrade:
    rd = _parse_raw_decision(row.get("raw_decision"))
    return OpenTrade(
        trade_id=int(row.get("id", 0) or 0),
        ticker=str(row.get("ticker", "")).upper(),
        direction=str(row.get("direction", "long")),
        setup_type=str(rd.get("setup_type", "unknown")),
        quantity=int(row.get("quantity", 0) or 0),
        entry_price=_safe_float(row.get("entry_fill_price") or row.get("entry_price")),
        stop_loss=_safe_float(row.get("stop_loss")),
        target_price=_safe_float(row.get("target_price")),
        target_price_2=_safe_float(row.get("target_price_2")),
        confidence=_safe_int(row.get("confidence")),
        timeframe=str(row.get("timeframe") or "") or None,
        entered_at=str(row.get("entered_at") or "") or None,
        run_id=str(row.get("run_id") or "") or None,
    )


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Turso fetchers (filtered to mode='b_swing')
# ---------------------------------------------------------------------------

def fetch_closed_today(today_pt: date | None = None) -> list[dict[str, Any]]:
    """Closed b_swing trades whose closed_at falls within today's PT day."""
    from tracker.turso_client import _execute  # internal but stable

    start_utc, end_utc = _today_pt_bounds(today_pt)
    rows = _execute(
        "SELECT * FROM trades WHERE mode = ? AND status IN ('target_hit', 'stop_hit', 'expired') "
        "AND datetime(closed_at) >= datetime(?) AND datetime(closed_at) < datetime(?) "
        "ORDER BY closed_at ASC",
        [B_SWING_MODE, start_utc.replace(microsecond=0).isoformat(),
         end_utc.replace(microsecond=0).isoformat()],
    )
    return rows


def fetch_open_positions() -> list[dict[str, Any]]:
    """Currently open b_swing positions (status='entered')."""
    from tracker.turso_client import _execute

    return _execute(
        "SELECT * FROM trades WHERE mode = ? AND status = 'entered' ORDER BY entered_at ASC",
        [B_SWING_MODE],
    )


def fetch_closed_within(days: int) -> list[dict[str, Any]]:
    """All closed b_swing trades within the last N days (for pattern aggregation)."""
    from tracker.turso_client import _execute

    cutoff_utc = (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()
    return _execute(
        "SELECT * FROM trades WHERE mode = ? AND status IN ('target_hit', 'stop_hit', 'expired') "
        "AND datetime(closed_at) >= datetime(?) ORDER BY closed_at DESC",
        [B_SWING_MODE, cutoff_utc],
    )


# ---------------------------------------------------------------------------
# Wiki excerpts
# ---------------------------------------------------------------------------

def _read_wiki(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def collect_wiki_excerpts(
    *,
    tickers: Iterable[str],
    wiki_root: Path = Path("wiki"),
) -> dict[str, Any]:
    """Read per-ticker (trades, setup_history) and meta pages, returning a dict."""
    out: dict[str, Any] = {
        "meta": {
            "lessons": _read_wiki(wiki_root / "meta" / "lessons.md"),
            "setup_patterns": _read_wiki(wiki_root / "meta" / "setup_patterns.md"),
            "budget_state": _read_wiki(wiki_root / "meta" / "budget_state.md"),
            "open_positions": _read_wiki(wiki_root / "meta" / "open_positions.md"),
        },
        "macro": {
            "regime": _read_wiki(wiki_root / "macro" / "regime.md"),
        },
        "tickers": {},
    }
    for t in {x.upper() for x in tickers if x}:
        tdir = wiki_root / "tickers" / t
        out["tickers"][t] = {
            "trades": _read_wiki(tdir / "trades.md"),
            "setup_history": _read_wiki(tdir / "setup_history.md"),
            "thesis": _read_wiki(tdir / "thesis.md"),
        }
    return out


def detect_new_tickers(tickers: Iterable[str], wiki_root: Path = Path("wiki")) -> list[str]:
    """Tickers traded today whose wiki/tickers/<T>/ directory does not exist."""
    new: list[str] = []
    for t in sorted({x.upper() for x in tickers if x}):
        if not (wiki_root / "tickers" / t).exists():
            new.append(t)
    return new


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_journal_facts(
    run_id: str,
    *,
    today_pt: date | None = None,
    runs_dir: str = "runs",
    wiki_root: str = "wiki",
    closed_today_override: list[dict[str, Any]] | None = None,
    open_positions_override: list[dict[str, Any]] | None = None,
    closed_30d_override: list[dict[str, Any]] | None = None,
    closed_90d_override: list[dict[str, Any]] | None = None,
) -> JournalFacts:
    """Build the journal_facts bundle in memory (does not write to disk).

    Override hooks let tests / smoke runs feed mock Turso rows. When an
    override is None, the matching real fetcher is called.
    """
    today_pt = today_pt or datetime.now(PT_TZ).date()

    closed_today_rows = closed_today_override if closed_today_override is not None else fetch_closed_today(today_pt)
    open_rows = open_positions_override if open_positions_override is not None else fetch_open_positions()
    closed_30d_rows = closed_30d_override if closed_30d_override is not None else fetch_closed_within(30)
    closed_90d_rows = closed_90d_override if closed_90d_override is not None else fetch_closed_within(90)

    closed_today = [_row_to_closed(r) for r in closed_today_rows]
    open_positions = [_row_to_open(r) for r in open_rows]
    closed_30d = [_row_to_closed(r) for r in closed_30d_rows]
    closed_90d = [_row_to_closed(r) for r in closed_90d_rows]

    # Tickers traded today = closed today ∪ entered today.
    today_tickers: set[str] = {t.ticker for t in closed_today}
    start_utc, end_utc = _today_pt_bounds(today_pt)
    for op in open_positions:
        ent = _parse_iso(op.entered_at)
        if ent and start_utc <= ent < end_utc:
            today_tickers.add(op.ticker)

    tickers_today_sorted = sorted(today_tickers)
    new_tickers = detect_new_tickers(tickers_today_sorted, wiki_root=Path(wiki_root))

    realized_pnl = sum((t.pnl or 0.0) for t in closed_today)

    wiki_excerpts = collect_wiki_excerpts(tickers=tickers_today_sorted, wiki_root=Path(wiki_root))

    return JournalFacts(
        run_id=run_id,
        journal_date_pt=today_pt.isoformat(),
        generated_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        closed_today=closed_today,
        open_positions=open_positions,
        closed_last_30d=closed_30d,
        closed_last_90d=closed_90d,
        tickers_today=tickers_today_sorted,
        new_tickers_today=new_tickers,
        realized_pnl_today_usd=round(realized_pnl, 2),
        wiki_excerpts=wiki_excerpts,
    )


def write_journal_facts(
    facts: JournalFacts,
    *,
    runs_dir: str = "runs",
) -> dict[str, str]:
    """Serialize the bundle to runs/<run_id>/journal_facts.json (canonical)
    and runs/<run_id>/facts/b_journal__GLOBAL.json (inject_context mirror).

    Returns {"journal_facts": "<path>", "global_facts": "<path>"}.
    """
    run_dir = Path(runs_dir) / facts.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    payload = _dataclass_to_plain(facts)

    canonical = run_dir / "journal_facts.json"
    canonical.write_text(json.dumps(payload, indent=2, default=str))

    facts_dir = run_dir / "facts"
    facts_dir.mkdir(parents=True, exist_ok=True)
    global_facts = facts_dir / "b_journal__GLOBAL.json"
    # The mirror file gets a `wiki_context` key that inject_context will overwrite.
    payload_global = dict(payload)
    payload_global.setdefault("wiki_context", {})
    payload_global["ticker"] = "GLOBAL"
    global_facts.write_text(json.dumps(payload_global, indent=2, default=str))

    return {"journal_facts": str(canonical), "global_facts": str(global_facts)}


def _dataclass_to_plain(obj: Any) -> Any:
    """Recursively convert dataclasses → dict (json-friendly)."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _dataclass_to_plain(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_dataclass_to_plain(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _dataclass_to_plain(v) for k, v in obj.items()}
    return obj


__all__ = [
    "ClosedTrade",
    "OpenTrade",
    "JournalFacts",
    "build_journal_facts",
    "write_journal_facts",
    "fetch_closed_today",
    "fetch_open_positions",
    "fetch_closed_within",
    "collect_wiki_excerpts",
    "detect_new_tickers",
]
