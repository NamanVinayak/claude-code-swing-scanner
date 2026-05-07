import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import logging
from datetime import datetime, time, timedelta, timezone
import pytz
import yfinance as yf
import pandas as pd
from tracker.turso_client import (
    get_pending_trades,
    get_open_positions,
    update_trade,
    log_fill,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

NY_TZ = pytz.timezone('America/New_York')
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)

def is_market_hours(dt: datetime) -> bool:
    ny_dt = dt.astimezone(NY_TZ)
    return MARKET_OPEN <= ny_dt.time() <= MARKET_CLOSE


# ---------------------------------------------------------------------------
# Time-discipline helpers
#
# History: prior to 2026-05-07, freshly-inserted trades whose `last_checked_at`
# was NULL fell back to `start_of_today` (NY midnight) as the bar-scan floor.
# That meant the simulator processed bars from 9:30 AM ET market open even
# when the trade was actually inserted hours later, producing impossible
# retroactive fills. The helpers below replace that fallback with a floor
# anchored to `decision_made_at` (when the agent finished deciding), and add
# an expiry pass that respects the judge's per-trade `entry_valid_until`.
# ---------------------------------------------------------------------------

ORDER_LIVE_BUFFER_SECONDS = 60  # broker-side delay between agent decision and order being live


def _floor_for_fresh_trade(trade: dict, fallback_start_of_today: datetime) -> datetime:
    """For a freshly-inserted trade with no last_checked_at yet, the simulator
    must NOT process bars from before the agent's decision was finalized.
    Floor = decision_made_at + ORDER_LIVE_BUFFER_SECONDS.
    Fallback to start_of_today only if decision_made_at is missing or unparsable
    (legacy rows from before this fix shipped)."""
    decision_str = trade.get('decision_made_at')
    if not decision_str:
        return fallback_start_of_today
    try:
        decision_dt = pd.to_datetime(decision_str).to_pydatetime()
    except Exception:
        return fallback_start_of_today
    if decision_dt.tzinfo is None:
        decision_dt = decision_dt.replace(tzinfo=timezone.utc)
    return decision_dt + timedelta(seconds=ORDER_LIVE_BUFFER_SECONDS)


def _safety_cap_expiry(trade: dict) -> datetime:
    """Default expiry when judge set entry_valid_until = null (or it failed to parse):
    16:00 ET on the day the decision was made. Mirrors how a real broker handles a
    plain day-order. Falls back to created_at, then now() if neither is available."""
    decision_str = trade.get('decision_made_at') or trade.get('created_at')
    if decision_str:
        try:
            base = pd.to_datetime(decision_str).to_pydatetime()
        except Exception:
            base = datetime.now(timezone.utc)
    else:
        base = datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    base_ny = base.astimezone(NY_TZ)
    market_close_ny = base_ny.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_close_ny.astimezone(timezone.utc)


def run_simulator(dry_run: bool = False):
    pending = get_pending_trades()
    opened = get_open_positions()
    
    trades = pending + opened
    if not trades:
        print("Checked 0 positions: 0 entries filled, 0 stops hit, 0 targets hit, 0 unchanged")
        return

    tickers = list(set(t['ticker'] for t in trades))
    
    # Download 1m data for today
    logger.info(f"Fetching 1-minute bars for {len(tickers)} tickers: {tickers}")
    try:
        data = yf.download(
            tickers, 
            period="1d", 
            interval="1m", 
            auto_adjust=True, 
            group_by="ticker",
            progress=False
        )
    except Exception as e:
        logger.error(f"Failed to fetch data from yfinance: {e}")
        print(f"Checked {len(trades)} positions: 0 entries filled, 0 stops hit, 0 targets hit, {len(trades)} unchanged")
        return
        
    if data.empty:
        logger.warning("No data returned from yfinance.")
        print(f"Checked {len(trades)} positions: 0 entries filled, 0 stops hit, 0 targets hit, {len(trades)} unchanged")
        return
        
    entries_filled = 0
    stops_hit = 0
    targets_hit = 0
    unchanged = 0
    expired_count = 0

    now_ny = datetime.now(NY_TZ)
    start_of_today = now_ny.replace(hour=0, minute=0, second=0, microsecond=0)

    for t in trades:
        trade_id = t['id']
        ticker = t['ticker']
        direction = t['direction']
        entry_price = t['entry_price']
        status = t['status']
        stop_loss = t.get('stop_loss')
        target_price = t.get('target_price')
        target_price_2 = t.get('target_price_2')
        qty = t['quantity']
        
        last_checked_str = t.get('last_checked_at')
        if last_checked_str:
            try:
                last_checked = pd.to_datetime(last_checked_str).to_pydatetime()
            except Exception:
                last_checked = _floor_for_fresh_trade(t, start_of_today)
        else:
            last_checked = _floor_for_fresh_trade(t, start_of_today)

        # Ensure last_checked is tz-aware for comparison
        if last_checked.tzinfo is None:
            last_checked = last_checked.replace(tzinfo=timezone.utc)

        # Expiry pass — applies only to still-pending trades.
        # If the entry-validity window has closed without a fill, mark the
        # order expired BEFORE walking any bars. The judge set entry_valid_until
        # per-trade; null falls back to end-of-decision-day at 16:00 ET.
        if status == 'pending':
            now_utc = datetime.now(timezone.utc)
            expiry_str = t.get('entry_valid_until')
            if expiry_str:
                try:
                    expiry_dt = pd.to_datetime(expiry_str).to_pydatetime()
                except Exception:
                    expiry_dt = _safety_cap_expiry(t)
            else:
                expiry_dt = _safety_cap_expiry(t)

            if expiry_dt.tzinfo is None:
                expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)

            if now_utc > expiry_dt:
                expired_count += 1
                if not dry_run:
                    update_trade(
                        trade_id,
                        status='expired',
                        closed_at=expiry_dt.isoformat(),
                        exit_fill_price=None,
                        pnl=None,
                    )
                    # log_fill requires non-null price; use 0.0 sentinel.
                    # event_type='expired' is the discriminator.
                    log_fill(trade_id, "expired", 0.0, expiry_dt.isoformat(), "entry window closed without fill")
                logger.info(f"  EXPIRED: {direction.upper()} {qty} {ticker} @ entry {entry_price} (window closed at {expiry_dt.isoformat()})")
                continue  # skip bar loop entirely

        try:
            # Handle multi-index columns from yfinance
            if len(tickers) == 1:
                # If only one ticker, yf may not return multi-level columns if group_by is ignored in some versions
                if isinstance(data.columns, pd.MultiIndex):
                    df = data[ticker].dropna(how='all')
                else:
                    df = data.dropna(how='all')
            else:
                if isinstance(data.columns, pd.MultiIndex) and ticker in data.columns.levels[0]:
                    df = data[ticker].dropna(how='all')
                else:
                    logger.warning(f"No data found in yfinance response for {ticker}")
                    unchanged += 1
                    continue
        except Exception as e:
            logger.error(f"Error extracting data for {ticker}: {e}")
            unchanged += 1
            continue
            
        if df.empty:
            logger.warning(f"Data empty for {ticker}")
            unchanged += 1
            continue

        initial_status = status
        latest_bar_time = None
        has_fill = False
        
        for idx, row in df.iterrows():
            # If idx is just integer, we can't use it as datetime. (unlikely with yfinance)
            try:
                bar_time = idx.to_pydatetime()
            except AttributeError:
                continue

            if bar_time.tzinfo is None:
                bar_time = NY_TZ.localize(bar_time)
                
            if bar_time <= last_checked:
                continue
                
            if not is_market_hours(bar_time):
                continue
                
            latest_bar_time = bar_time
            try:
                low = float(row['Low'])
                high = float(row['High'])
            except KeyError:
                continue
                
            bar_timestamp_str = bar_time.isoformat()
            
            # 1. Check entries for pending (with entry tolerance band)
            if status == 'pending':
                tolerance_pct = t.get('entry_tolerance_pct') or 1.0
                if direction == 'long':
                    entry_max = entry_price * (1 + tolerance_pct / 100.0)
                    if low <= entry_max:
                        fill_price = max(low, entry_price)  # ideal or worse-within-tolerance
                        status = 'entered'
                        has_fill = True
                        entries_filled += 1
                        if not dry_run:
                            update_trade(trade_id, status='entered', entered_at=bar_timestamp_str, entry_fill_price=fill_price)
                            reason = "long entry hit" if fill_price <= entry_price else f"long entry filled within tolerance ({tolerance_pct}%)"
                            log_fill(trade_id, "entry_filled", fill_price, bar_timestamp_str, reason)
                elif direction == 'short':
                    entry_min = entry_price * (1 - tolerance_pct / 100.0)
                    if high >= entry_min:
                        fill_price = min(high, entry_price)  # ideal or worse-within-tolerance
                        status = 'entered'
                        has_fill = True
                        entries_filled += 1
                        if not dry_run:
                            update_trade(trade_id, status='entered', entered_at=bar_timestamp_str, entry_fill_price=fill_price)
                            reason = "short entry hit" if fill_price >= entry_price else f"short entry filled within tolerance ({tolerance_pct}%)"
                            log_fill(trade_id, "entry_filled", fill_price, bar_timestamp_str, reason)

            # 2. Check stops/targets for entered
            if status == 'entered':
                if direction == 'long':
                    if stop_loss is not None and low <= stop_loss:
                        status = 'stop_hit'
                        has_fill = True
                        stops_hit += 1
                        if not dry_run:
                            pnl = (stop_loss - entry_price) * qty
                            update_trade(trade_id, status='stop_hit', closed_at=bar_timestamp_str, exit_fill_price=stop_loss, pnl=pnl)
                            log_fill(trade_id, "stop_hit", stop_loss, bar_timestamp_str, "long stop loss hit")
                        break
                    elif target_price is not None and high >= target_price:
                        if target_price_2 is not None:
                            has_fill = True
                            if not dry_run:
                                update_trade(trade_id, stop_loss=entry_price, target_price=target_price_2, target_price_2=None)
                                log_fill(trade_id, "target_hit", target_price, bar_timestamp_str, "long target 1 hit, trailing stop to entry")
                            stop_loss = entry_price
                            target_price = target_price_2
                            target_price_2 = None
                        else:
                            status = 'target_hit'
                            has_fill = True
                            targets_hit += 1
                            if not dry_run:
                                pnl = (target_price - entry_price) * qty
                                update_trade(trade_id, status='target_hit', closed_at=bar_timestamp_str, exit_fill_price=target_price, pnl=pnl)
                                log_fill(trade_id, "target_hit", target_price, bar_timestamp_str, "long target hit")
                            break
                            
                elif direction == 'short':
                    if stop_loss is not None and high >= stop_loss:
                        status = 'stop_hit'
                        has_fill = True
                        stops_hit += 1
                        if not dry_run:
                            pnl = (entry_price - stop_loss) * qty
                            update_trade(trade_id, status='stop_hit', closed_at=bar_timestamp_str, exit_fill_price=stop_loss, pnl=pnl)
                            log_fill(trade_id, "stop_hit", stop_loss, bar_timestamp_str, "short stop loss hit")
                        break
                    elif target_price is not None and low <= target_price:
                        if target_price_2 is not None:
                            has_fill = True
                            if not dry_run:
                                update_trade(trade_id, stop_loss=entry_price, target_price=target_price_2, target_price_2=None)
                                log_fill(trade_id, "target_hit", target_price, bar_timestamp_str, "short target 1 hit, trailing stop to entry")
                            stop_loss = entry_price
                            target_price = target_price_2
                            target_price_2 = None
                        else:
                            status = 'target_hit'
                            has_fill = True
                            targets_hit += 1
                            if not dry_run:
                                pnl = (entry_price - target_price) * qty
                                update_trade(trade_id, status='target_hit', closed_at=bar_timestamp_str, exit_fill_price=target_price, pnl=pnl)
                                log_fill(trade_id, "target_hit", target_price, bar_timestamp_str, "short target hit")
                            break

        if not has_fill:
            unchanged += 1
            
        if latest_bar_time is not None and not dry_run:
            update_trade(trade_id, last_checked_at=latest_bar_time.isoformat())

    print(f"Checked {len(trades)} positions: {entries_filled} entries filled, {stops_hit} stops hit, {targets_hit} targets hit, {expired_count} expired, {unchanged} unchanged")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous Fill Engine Simulator")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without writing to Turso")
    args = parser.parse_args()
    
    run_simulator(dry_run=args.dry_run)
