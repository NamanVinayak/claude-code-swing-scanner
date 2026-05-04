"""Stage 2 Pre-market Reviewer — mechanical filter + facts builder.

Runs ~5:30 AM Pacific each weekday. Reads Stage 1's tomorrow_watchlist.json,
drops candidates that have stopped being tradeable overnight, and builds
per-ticker facts bundles for the LLM mini-agents that come next.

No LLM calls in this module. The orchestrator dispatches the b_premarket
mini-agents (one per survivor) and the b_premarket_synthesizer (one) using
the prompt files this task delivers.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import yfinance as yf

from ai_hedge.data.earnings_calendar import days_until_next_earnings

logger = logging.getLogger(__name__)

_PT = ZoneInfo("America/Los_Angeles")
_ET = ZoneInfo("America/New_York")


# --- Public types -----------------------------------------------------------

DropReason = Literal[
    "gap_up_exhausted",        # LONG: overnight gap > +5% — already moved past watch
    "gap_down_setup_broken",   # LONG: overnight gap < -5% — bull setup broken
    "gap_up_setup_broken",     # SHORT: overnight gap > +5% — bear thesis steamrolled
    "gap_down_exhausted",      # SHORT: overnight gap < -5% — breakdown already played out
    "premarket_volume_vacuum", # premarket volume < 50% of 10d avg premarket — no interest
    "earnings_just_reported",  # earnings reported in last 12h — thesis stale
    "earnings_blackout_3d",    # earnings within next 3 days — overnight gap risk too high for swing
    "stage1_too_old",          # tomorrow_watchlist.json older than 24h
    "data_unavailable",        # could not fetch fresh data (handled gracefully, not an error)
]


@dataclass(frozen=True)
class PreMarketSnapshot:
    ticker: str
    last_regular_close: float       # yesterday's close
    premarket_last: float | None    # latest premarket price, None if unavailable
    overnight_gap_pct: float | None # (premarket_last / last_regular_close) - 1, in percent
    premarket_volume: int | None
    avg_premarket_volume_10d: float | None
    fetched_at: str                 # ISO-8601


@dataclass
class FilterDecision:
    ticker: str
    keep: bool
    drop_reasons: list[DropReason] = field(default_factory=list)
    snapshot: PreMarketSnapshot | None = None
    earnings_recent_days: float | None = None  # how many days ago earnings reported (negative = future)


@dataclass
class PreMarketReviewResult:
    run_id: str
    review_timestamp_pt: str
    source_run_id: str               # the run_id of the Stage 1 watchlist consumed
    source_path: str                 # the JSON path consumed
    candidates_in: int
    survivors: list[str]             # ticker symbols that passed all filters
    decisions: list[FilterDecision]  # one entry per input candidate (whether kept or dropped)
    errors: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0


# --- Public functions --------------------------------------------------------

def load_latest_stage1_watchlist(runs_dir: str = "runs") -> tuple[str, dict]:
    """Find the most recent runs/*/tomorrow_watchlist.json and return (run_id, parsed_dict).

    Sorts run dirs by modification time descending. Skips dirs without
    tomorrow_watchlist.json. Raises FileNotFoundError if none found.
    """
    runs_path = Path(runs_dir)
    if not runs_path.exists():
        raise FileNotFoundError(f"Runs directory not found: {runs_path}")

    found: list[tuple[float, str, Path]] = []
    for run_dir in runs_path.iterdir():
        if not run_dir.is_dir():
            continue
        watchlist_file = run_dir / "tomorrow_watchlist.json"
        if watchlist_file.exists():
            found.append((watchlist_file.stat().st_mtime, run_dir.name, watchlist_file))

    if not found:
        raise FileNotFoundError(f"No tomorrow_watchlist.json found under {runs_dir}/")

    found.sort(key=lambda x: x[0], reverse=True)
    _, run_id, watchlist_path = found[0]

    data = json.loads(watchlist_path.read_text())
    return run_id, data


def _compute_avg_premarket_volume_10d(df) -> float | None:
    """Compute average daily premarket volume (4:00–9:30 AM ET) over last 10 trading days."""
    try:
        import pandas as pd

        if df is None or df.empty:
            return None
        if df.index.tz is None:
            return None

        df_et = df.copy()
        df_et.index = df_et.index.tz_convert(_ET)

        pm_mask = (
            (df_et.index.time >= pd.Timestamp("04:00").time()) &
            (df_et.index.time < pd.Timestamp("09:30").time())
        )
        pm_df = df_et[pm_mask].copy()

        if pm_df.empty:
            return None

        pm_df["_date"] = pm_df.index.date
        daily_vols = pm_df.groupby("_date")["Volume"].sum()

        last_10 = daily_vols.iloc[-10:]
        if last_10.empty:
            return None

        return float(last_10.mean())
    except Exception as exc:
        logger.debug("avg premarket volume computation failed: %s", exc)
        return None


def _get_last_regular_close(df) -> float | None:
    """Extract the most recent regular-session close (9:30 AM – 4:00 PM ET) from a 1m bar df."""
    try:
        import pandas as pd

        if df is None or df.empty:
            return None
        if df.index.tz is None:
            return float(df["Close"].iloc[-1])

        df_et = df.copy()
        df_et.index = df_et.index.tz_convert(_ET)

        regular_mask = (
            (df_et.index.time >= pd.Timestamp("09:30").time()) &
            (df_et.index.time <= pd.Timestamp("16:00").time())
        )
        reg_df = df_et[regular_mask]

        if reg_df.empty:
            return float(df["Close"].iloc[-1])

        return float(reg_df["Close"].iloc[-1])
    except Exception:
        return None


def _get_today_premarket_data(df) -> tuple[float | None, int | None]:
    """Extract today's premarket last price and total volume from a 1m bar df."""
    try:
        import pandas as pd

        if df is None or df.empty:
            return None, None
        if df.index.tz is None:
            return None, None

        df_et = df.copy()
        df_et.index = df_et.index.tz_convert(_ET)

        today = datetime.now(_ET).date()
        today_mask = df_et.index.date == today
        today_df = df_et[today_mask]

        pm_mask = (
            (today_df.index.time >= pd.Timestamp("04:00").time()) &
            (today_df.index.time < pd.Timestamp("09:30").time())
        )
        pm_today = today_df[pm_mask]

        if pm_today.empty:
            return None, None

        premarket_last = float(pm_today["Close"].iloc[-1])
        premarket_volume = int(pm_today["Volume"].sum())
        return premarket_last, premarket_volume
    except Exception:
        return None, None


def fetch_premarket_snapshot(ticker: str) -> PreMarketSnapshot:
    """Fetch latest premarket price + volume for one ticker.

    Uses yfinance's intraday API with prepost=True. If pre-market data is
    not available (weekend, halted, etc.), populates premarket_last=None
    and overnight_gap_pct=None — the caller treats this as 'data_unavailable'
    and uses a soft-keep policy (don't drop solely on missing premarket data).

    Single retry on network failure, then return a snapshot with last_regular_close
    populated and the rest None.
    """
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _empty = PreMarketSnapshot(
        ticker=ticker,
        last_regular_close=0.0,
        premarket_last=None,
        overnight_gap_pct=None,
        premarket_volume=None,
        avg_premarket_volume_10d=None,
        fetched_at=fetched_at,
    )

    df = None
    for attempt in range(2):
        try:
            t = yf.Ticker(ticker)
            df = t.history(period="5d", interval="1m", prepost=True)
            if df is not None and not df.empty:
                break
        except Exception as exc:
            if attempt == 0:
                logger.warning("premarket fetch for %s failed (attempt 1), retrying: %s", ticker, exc)
            else:
                logger.error("premarket fetch for %s failed on retry: %s", ticker, exc)
                return _empty

    if df is None or df.empty:
        return _empty

    last_regular_close = _get_last_regular_close(df) or 0.0
    premarket_last, premarket_volume = _get_today_premarket_data(df)
    avg_premarket_volume_10d = _compute_avg_premarket_volume_10d(df)

    overnight_gap_pct = None
    if premarket_last is not None and last_regular_close > 0:
        overnight_gap_pct = (premarket_last / last_regular_close - 1.0) * 100.0

    return PreMarketSnapshot(
        ticker=ticker,
        last_regular_close=last_regular_close,
        premarket_last=premarket_last,
        overnight_gap_pct=overnight_gap_pct,
        premarket_volume=premarket_volume,
        avg_premarket_volume_10d=avg_premarket_volume_10d,
        fetched_at=fetched_at,
    )


def _get_days_since_last_earnings(ticker: str) -> float | None:
    """Return calendar days since most recent past earnings, or None if unavailable."""
    try:
        t = yf.Ticker(ticker)
        earnings_dates = t.earnings_dates
        if earnings_dates is None or earnings_dates.empty:
            return None

        now_utc = datetime.now(timezone.utc)
        past_mask = earnings_dates.index < now_utc
        past_dates = earnings_dates.index[past_mask]

        if len(past_dates) == 0:
            return None

        most_recent = past_dates.max()
        delta = now_utc - most_recent.to_pydatetime()
        return delta.total_seconds() / 3600.0 / 24.0
    except Exception as exc:
        logger.debug("earnings dates fetch failed for %s: %s", ticker, exc)
        return None


def evaluate_candidate(
    ticker: str,
    *,
    gap_threshold_pct: float = 5.0,
    volume_floor_ratio: float = 0.5,
    earnings_recency_hours: float = 12.0,
    snapshot: PreMarketSnapshot | None = None,
    earnings_recent_days: float | None = None,
    earnings_upcoming_days: float | None = None,
    direction: Literal["long", "short"] = "long",
) -> FilterDecision:
    """Apply the pre-filter to one ticker. Pure function once data is fetched.

    If snapshot is None, fetches it via fetch_premarket_snapshot().
    earnings_recent_days: days since last earnings; None means unavailable (skip filter).

    Returns FilterDecision with keep=False if any drop reason fires.
    Multiple drop reasons can stack (informational).

    Special case: if data is fully unavailable, keep=True with drop_reasons=['data_unavailable'].
    Rationale: don't drop names solely because we couldn't fetch — let Stage 3 handle them.
    Better to over-include here than under-include.
    """
    if snapshot is None:
        snapshot = fetch_premarket_snapshot(ticker)

    drop_reasons: list[DropReason] = []

    # Soft-keep when premarket data is completely absent
    if snapshot.premarket_last is None:
        drop_reasons.append("data_unavailable")
        return FilterDecision(
            ticker=ticker,
            keep=True,
            drop_reasons=drop_reasons,
            snapshot=snapshot,
            earnings_recent_days=earnings_recent_days,
        )

    # Gap filter — direction-aware. Only fires when we have actual premarket data.
    if snapshot.overnight_gap_pct is not None:
        if direction == "short":
            # Bearish thesis: gap UP breaks the thesis; gap DOWN means breakdown already played out.
            if snapshot.overnight_gap_pct > gap_threshold_pct:
                drop_reasons.append("gap_up_setup_broken")
            elif snapshot.overnight_gap_pct < -gap_threshold_pct:
                drop_reasons.append("gap_down_exhausted")
        else:
            # Bullish thesis (default): gap UP means breakout already played out; gap DOWN breaks it.
            if snapshot.overnight_gap_pct > gap_threshold_pct:
                drop_reasons.append("gap_up_exhausted")
            elif snapshot.overnight_gap_pct < -gap_threshold_pct:
                drop_reasons.append("gap_down_setup_broken")

    # Volume vacuum — only fires when both values are available
    if (
        snapshot.premarket_volume is not None
        and snapshot.avg_premarket_volume_10d is not None
        and snapshot.avg_premarket_volume_10d > 0
    ):
        ratio = snapshot.premarket_volume / snapshot.avg_premarket_volume_10d
        if ratio < volume_floor_ratio:
            drop_reasons.append("premarket_volume_vacuum")

    # Earnings recency — only fires when recent earnings are confirmed
    if earnings_recent_days is not None:
        threshold_days = earnings_recency_hours / 24.0
        if 0.0 <= earnings_recent_days <= threshold_days:
            drop_reasons.append("earnings_just_reported")

    # Forward earnings blackout — drop if earnings coming up in next 3 days.
    # Swing trades typically take 2-20 days to play out; an overnight earnings
    # gap can blow up the thesis regardless of technicals.
    if earnings_upcoming_days is not None and earnings_upcoming_days <= 3:
        drop_reasons.append("earnings_blackout_3d")

    keep = len(drop_reasons) == 0
    return FilterDecision(
        ticker=ticker,
        keep=keep,
        drop_reasons=drop_reasons,
        snapshot=snapshot,
        earnings_recent_days=earnings_recent_days,
    )


def review_premarket(
    *,
    source_path: str | None = None,
    run_id: str | None = None,
    gap_threshold_pct: float = 5.0,
    volume_floor_ratio: float = 0.5,
    earnings_recency_hours: float = 12.0,
    max_age_hours: float = 24.0,
) -> PreMarketReviewResult:
    """End-to-end Stage 2 review.

    1. Load the source watchlist (or auto-discover latest)
    2. For each candidate ticker, fetch premarket snapshot + earnings recency
    3. Apply filters; produce FilterDecision per candidate
    4. Survivors = decisions where keep=True
    5. Return the result; does NOT write files (write_review_outputs handles I/O)
    """
    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    review_timestamp_pt = datetime.now(timezone.utc).astimezone(_PT).isoformat(timespec="seconds")
    t_start = time.monotonic()
    errors: list[str] = []

    # Step 1: Load watchlist
    source_run_id = ""
    watchlist_data: dict = {}

    if source_path is not None:
        try:
            watchlist_data = json.loads(Path(source_path).read_text())
            source_run_id = watchlist_data.get("run_id", "")
        except Exception as exc:
            errors.append(f"Failed to load watchlist from {source_path}: {exc}")
            return PreMarketReviewResult(
                run_id=run_id,
                review_timestamp_pt=review_timestamp_pt,
                source_run_id="",
                source_path=source_path,
                candidates_in=0,
                survivors=[],
                decisions=[],
                errors=errors,
                elapsed_seconds=time.monotonic() - t_start,
            )
    else:
        try:
            source_run_id, watchlist_data = load_latest_stage1_watchlist()
            source_path = str(Path("runs") / source_run_id / "tomorrow_watchlist.json")
        except FileNotFoundError as exc:
            errors.append(str(exc))
            return PreMarketReviewResult(
                run_id=run_id,
                review_timestamp_pt=review_timestamp_pt,
                source_run_id="",
                source_path="",
                candidates_in=0,
                survivors=[],
                decisions=[],
                errors=errors,
                elapsed_seconds=time.monotonic() - t_start,
            )

    # Step 2: Check Stage 1 staleness
    scan_timestamp_str = watchlist_data.get("scan_timestamp_pt", "")
    if scan_timestamp_str:
        try:
            scan_ts = datetime.fromisoformat(scan_timestamp_str)
            if scan_ts.tzinfo is None:
                scan_ts = scan_ts.replace(tzinfo=timezone.utc)
            now_utc = datetime.now(timezone.utc)
            age_hours = (now_utc - scan_ts.astimezone(timezone.utc)).total_seconds() / 3600.0
            if age_hours > max_age_hours:
                logger.warning(
                    "Stage 1 watchlist is %.1fh old (max %.1fh) — dropping all candidates with stage1_too_old",
                    age_hours, max_age_hours,
                )
                candidates_raw = watchlist_data.get("candidates", [])
                decisions = [
                    FilterDecision(ticker=c["ticker"], keep=False, drop_reasons=["stage1_too_old"])
                    for c in candidates_raw
                    if c.get("ticker")
                ]
                return PreMarketReviewResult(
                    run_id=run_id,
                    review_timestamp_pt=review_timestamp_pt,
                    source_run_id=source_run_id,
                    source_path=source_path or "",
                    candidates_in=len(candidates_raw),
                    survivors=[],
                    decisions=decisions,
                    errors=errors,
                    elapsed_seconds=time.monotonic() - t_start,
                )
        except Exception as exc:
            logger.warning("Could not parse scan_timestamp_pt %r: %s", scan_timestamp_str, exc)

    # Step 3: Evaluate each candidate
    candidates_raw = watchlist_data.get("candidates", [])
    decisions: list[FilterDecision] = []

    for cand in candidates_raw:
        ticker = cand.get("ticker", "")
        if not ticker:
            continue

        direction_raw = str(cand.get("direction", "long")).lower()
        direction: Literal["long", "short"] = "short" if direction_raw == "short" else "long"

        try:
            snap = fetch_premarket_snapshot(ticker)
        except Exception as exc:
            err = f"fetch_premarket_snapshot failed for {ticker}: {exc}"
            logger.error(err)
            errors.append(err)
            snap = PreMarketSnapshot(
                ticker=ticker,
                last_regular_close=0.0,
                premarket_last=None,
                overnight_gap_pct=None,
                premarket_volume=None,
                avg_premarket_volume_10d=None,
                fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )

        days_since = None
        try:
            days_since = _get_days_since_last_earnings(ticker)
        except Exception as exc:
            logger.warning("earnings recency fetch failed for %s: %s", ticker, exc)

        upcoming = None
        try:
            upcoming = days_until_next_earnings(ticker)
        except Exception as exc:
            logger.warning("upcoming earnings fetch failed for %s: %s", ticker, exc)

        try:
            decision = evaluate_candidate(
                ticker,
                gap_threshold_pct=gap_threshold_pct,
                volume_floor_ratio=volume_floor_ratio,
                earnings_recency_hours=earnings_recency_hours,
                snapshot=snap,
                earnings_recent_days=days_since,
                earnings_upcoming_days=upcoming,
                direction=direction,
            )
            decisions.append(decision)

            status = "KEEP" if decision.keep else "DROP"
            gap_str = (
                f"{decision.snapshot.overnight_gap_pct:+.2f}%"
                if (decision.snapshot and decision.snapshot.overnight_gap_pct is not None)
                else "n/a"
            )
            logger.info("%s: %s | gap=%s | reasons=%s", ticker, status, gap_str, decision.drop_reasons)

        except Exception as exc:
            err = f"evaluate_candidate failed for {ticker}: {exc}"
            logger.error(err)
            errors.append(err)
            decisions.append(FilterDecision(
                ticker=ticker,
                keep=True,
                drop_reasons=["data_unavailable"],
            ))

    survivors = [d.ticker for d in decisions if d.keep]

    return PreMarketReviewResult(
        run_id=run_id,
        review_timestamp_pt=review_timestamp_pt,
        source_run_id=source_run_id,
        source_path=source_path or "",
        candidates_in=len(candidates_raw),
        survivors=survivors,
        decisions=decisions,
        errors=errors,
        elapsed_seconds=time.monotonic() - t_start,
    )


def _build_facts_bundle(
    candidate_data: dict,
    decision: FilterDecision,
    watchlist_data: dict,
) -> dict:
    """Build the per-ticker facts bundle for a surviving candidate."""
    ticker = decision.ticker
    snap = decision.snapshot

    premarket_block: dict = {}
    if snap is not None:
        vol_ratio = None
        if (
            snap.premarket_volume is not None
            and snap.avg_premarket_volume_10d is not None
            and snap.avg_premarket_volume_10d > 0
        ):
            vol_ratio = round(snap.premarket_volume / snap.avg_premarket_volume_10d, 3)

        premarket_block = {
            "last_price": snap.premarket_last,
            "overnight_gap_pct": (
                round(snap.overnight_gap_pct, 4) if snap.overnight_gap_pct is not None else None
            ),
            "volume": snap.premarket_volume,
            "avg_volume_10d": (
                round(snap.avg_premarket_volume_10d, 0) if snap.avg_premarket_volume_10d is not None else None
            ),
            "volume_ratio": vol_ratio,
        }

    days_since = decision.earnings_recent_days
    days_until = None
    try:
        days_until = days_until_next_earnings(ticker)
    except Exception:
        pass

    last_close = (
        snap.last_regular_close
        if (snap is not None and snap.last_regular_close > 0)
        else float(candidate_data.get("last_close", 0.0))
    )

    return {
        "ticker": ticker,
        "exchange": candidate_data.get("exchange", ""),
        "direction": candidate_data.get("direction", "long"),
        "stage1_score": candidate_data.get("score", 0),
        "stage1_reasons": candidate_data.get("reasons", []),
        "last_regular_close": last_close,
        "premarket": premarket_block,
        "earnings": {
            "days_since_last": round(days_since, 2) if days_since is not None else None,
            "days_until_next": days_until,
        },
        "scanner_universe": {
            "size": watchlist_data.get("universe_size", 0),
            "scan_timestamp_pt": watchlist_data.get("scan_timestamp_pt", ""),
        },
        "wiki_context": {},
    }


def write_review_outputs(
    result: PreMarketReviewResult,
    *,
    runs_dir: str = "runs",
) -> dict[str, str]:
    """Write Stage 2 outputs to runs/<run_id>/.

    Files written:
      - runs/<run_id>/premarket_filtered.json         (the full PreMarketReviewResult, JSON-serialized)
      - runs/<run_id>/facts/b_premarket__<TICKER>.json  (one per survivor — facts bundle)

    After writing facts files, calls ai_hedge.wiki.inject.inject_context(run_id, survivors, mode='b_premarket')
    to merge wiki context into each facts file.

    Returns dict of paths written.
    """
    from ai_hedge.wiki.inject import inject_context

    run_dir = Path(runs_dir) / result.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    paths_written: dict[str, str] = {}

    # Write premarket_filtered.json
    filtered_path = run_dir / "premarket_filtered.json"

    def _snap_to_dict(s: PreMarketSnapshot) -> dict:
        return {
            "ticker": s.ticker,
            "last_regular_close": s.last_regular_close,
            "premarket_last": s.premarket_last,
            "overnight_gap_pct": s.overnight_gap_pct,
            "premarket_volume": s.premarket_volume,
            "avg_premarket_volume_10d": s.avg_premarket_volume_10d,
            "fetched_at": s.fetched_at,
        }

    def _decision_to_dict(d: FilterDecision) -> dict:
        return {
            "ticker": d.ticker,
            "keep": d.keep,
            "drop_reasons": list(d.drop_reasons),
            "earnings_recent_days": d.earnings_recent_days,
            "snapshot": _snap_to_dict(d.snapshot) if d.snapshot is not None else None,
        }

    filtered_data = {
        "run_id": result.run_id,
        "review_timestamp_pt": result.review_timestamp_pt,
        "source_run_id": result.source_run_id,
        "source_path": result.source_path,
        "candidates_in": result.candidates_in,
        "survivors": result.survivors,
        "decisions": [_decision_to_dict(d) for d in result.decisions],
        "errors": result.errors,
        "elapsed_seconds": result.elapsed_seconds,
    }
    filtered_path.write_text(json.dumps(filtered_data, indent=2, default=str))
    paths_written["premarket_filtered"] = str(filtered_path)

    # Load source watchlist for candidate metadata
    source_watchlist: dict = {}
    try:
        source_watchlist = json.loads(Path(result.source_path).read_text())
    except Exception as exc:
        logger.warning("Could not load source watchlist for facts building: %s", exc)

    candidate_map: dict[str, dict] = {
        c["ticker"]: c
        for c in source_watchlist.get("candidates", [])
        if "ticker" in c
    }

    # Write per-survivor facts files
    facts_dir = run_dir / "facts"
    facts_dir.mkdir(exist_ok=True)

    decision_map = {d.ticker: d for d in result.decisions}

    for ticker in result.survivors:
        decision = decision_map.get(ticker)
        if decision is None:
            continue

        candidate_data = candidate_map.get(ticker, {})
        bundle = _build_facts_bundle(candidate_data, decision, source_watchlist)

        facts_path = facts_dir / f"b_premarket__{ticker.upper()}.json"
        facts_path.write_text(json.dumps(bundle, indent=2, default=str))
        paths_written[f"facts__{ticker}"] = str(facts_path)
        logger.info("Wrote facts bundle: %s", facts_path)

    # Run wiki injection (requires files at runs/<run_id>/facts/ relative to CWD)
    if result.survivors:
        try:
            inject_result = inject_context(result.run_id, result.survivors, mode="b_premarket")
            logger.info("Wiki injection: %s", inject_result)
        except Exception as exc:
            logger.warning("Wiki injection failed: %s", exc)

    return paths_written
