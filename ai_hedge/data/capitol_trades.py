"""Capitol Trades scraper — congressional stock-trade disclosures.

Used by System B's Stage 1 scanner to find tickers where US politicians
have recently bought. Free, polite, cached. Falls back gracefully on
scraping failures (logs warning, returns empty list).

No API key required. Source: capitoltrades.com.

TODO: migrate from in-memory TTL cache to SQLite cache once cache.py
exposes a generic cache_get/cache_set interface (currently domain-typed).

═══════════════════════════════════════════════════════════════════
PHASE 2 FINDINGS — what's scrapable and what's not
═══════════════════════════════════════════════════════════════════

robots.txt (checked 2026-05-03):
    User-Agent: *
    Allow: /
    Disallow: /_next/data/*          ← __NEXT_DATA__ endpoint is off-limits

Scraping is allowed for /trades, /issuers, /politicians.

Capitol Trades is a Next.js app with React Server Components (RSC).
Pages arrive as fully-rendered HTML containing RSC payload blobs:

    <script>self.__next_f.push([1,"...JSON string..."])</script>

The JSON string is a React component tree. The trade table data is
embedded as a JSON array in the field  "data":[{...trade objects...}].

Trades listing format:
    URL:  https://www.capitoltrades.com/trades?page=N
    Sort: default is -pubDate (newest publication/disclosure date first)
    The ?txDate=last30days URL filter returns data:[] (empty) because it
    filters on the *transaction* date, which may not be disclosed yet
    (STOCK Act allows 30-45 day delay). Using ?page=N without a date
    filter and stopping when pubDate < cutoff is the reliable approach.
    ~12-15 trades per page, 35,000+ total trades across ~2,900 pages.

Per-ticker (per-issuer) page format:
    URL:  https://www.capitoltrades.com/issuers/{issuer_id}?page=N
    Each issuer has a numeric ID (e.g. AAPL = 429789, MSFT = 433382).
    IDs are embedded in the trade JSON and the issuers filter sidebar.
    Per-issuer pages scope results to one ticker — ~15 trades/page.
    For AAPL: 279 total trades, 19 pages.

Issuer ID discovery:
    The trades page RSC payload includes an "issuers" sidebar listing
    ~15 popular issuers with their numeric IDs. Any trade in the data
    also carries _issuerId in its issuer sub-object.  The module
    accumulates a ticker→issuerId map at runtime (_ticker_id_cache).
    For tickers absent from that cache, the function falls back to
    paginating global trades and filtering client-side.

Trade value field:
    The "value" field is a numeric USD estimate.  Capitol Trades maps
    the STOCK Act size bucket to a midpoint:
        8,000  → "$1K–$15K"   (midpoint of 1,001–15,000)
       32,500  → "$15K–$50K"  (midpoint of 15,001–50,000)
    This module reverse-maps numeric value → TradeSizeBucket.

Politician track-record / alpha-vs-SPY data:
    NOT scrapable. Capitol Trades politician pages show trade history
    and basic stats (count, date range) but publish no performance
    metrics (alpha, win rate, return vs SPY). get_top_performing_politicians()
    raises NotImplementedError — see that function's docstring.

Asset type:
    Not a direct field in the trade JSON. Derived from issuer.sector
    (null for ETFs/funds) and issuer.issuerName keywords.

JS-rendering status:
    No headless browser needed. The RSC payload in <script> tags
    contains the full trade data. Plain requests.get() works.
═══════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal, Sequence

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.capitoltrades.com"
_VERSION = "0.1.1"
_USER_AGENT = (
    f"ai-hedge-fund/{_VERSION} "
    "(research; +https://github.com/NamanVinayak/claude-code-swing-scanner)"
)
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

TradeDirection = Literal["buy", "sell", "exchange"]
TradeSizeBucket = Literal[
    "1K-15K",
    "15K-50K",
    "50K-100K",
    "100K-250K",
    "250K-500K",
    "500K-1M",
    "1M-5M",
    "5M-25M",
    "25M-50M",
    "50M+",
]


@dataclass(frozen=True)
class CongressionalTrade:
    """One politician's disclosed stock trade."""
    ticker: str
    politician_name: str
    politician_id: str | None
    chamber: Literal["house", "senate"] | None
    party: Literal["democrat", "republican", "independent"] | None
    direction: TradeDirection
    size_bucket: TradeSizeBucket | None
    transaction_date: date
    disclosure_date: date
    asset_type: str
    issuer_name: str | None
    source_url: str


# ---------------------------------------------------------------------------
# Module-level TTL cache
# Structure: { key: (data, fetched_at_unix) }
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[Any, float]] = {}

# Accumulated ticker → issuer_id mapping (populated as trades are parsed)
_ticker_id_cache: dict[str, int] = {}


def _cache_get(key: str, ttl: int) -> Any | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    data, fetched_at = entry
    if (time.time() - fetched_at) > ttl:
        return None
    return data


def _cache_set(key: str, data: Any) -> None:
    _cache[key] = (data, time.time())


# ---------------------------------------------------------------------------
# Internal: RSC payload parsing
# ---------------------------------------------------------------------------

_RSC_RE = re.compile(r'self\.__next_f\.push\(\[1,(.*?)\]\)', re.DOTALL)


def _extract_rsc_data(html: str) -> tuple[list[dict], int, int]:
    """Parse RSC payload from HTML.

    Returns (trades, total_count, total_pages).
    Each trade is the raw dict from Capitol Trades JSON.
    """
    import json

    trades: list[dict] = []
    total_count = 0
    total_pages = 0

    for m in _RSC_RE.finditer(html):
        raw = m.group(1)
        try:
            decoded = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(decoded, str):
            continue

        # Extract trade array using bracket matching (avoids fragile regex on nested JSON)
        data_idx = decoded.find('"data":[{')
        if data_idx >= 0 and not trades:
            arr_start = data_idx + 7  # points at '['
            depth = 0
            arr_end = arr_start
            for i in range(arr_start, len(decoded)):
                ch = decoded[i]
                if ch == '[':
                    depth += 1
                elif ch == ']':
                    depth -= 1
                    if depth == 0:
                        arr_end = i + 1
                        break
            try:
                candidate = json.loads(decoded[arr_start:arr_end])
                if (
                    isinstance(candidate, list)
                    and candidate
                    and isinstance(candidate[0], dict)
                    and ('issuer' in candidate[0] or '_politicianId' in candidate[0])
                ):
                    trades = candidate
                    _ingest_issuer_ids(candidate)
            except (json.JSONDecodeError, IndexError):
                pass

        # Extract pagination — search the decoded string
        count_m = re.search(r'"totalCount":(\d+)', decoded)
        pages_m = re.search(r'"totalPages":(\d+)', decoded)
        if count_m and not total_count:
            total_count = int(count_m.group(1))
        if pages_m and not total_pages:
            total_pages = int(pages_m.group(1))

        # Extract issuers filter list (for ticker→issuerID lookup)
        _ingest_issuers_sidebar(decoded)

    return trades, total_count, total_pages


def _ingest_issuer_ids(trades: list[dict]) -> None:
    """Populate _ticker_id_cache from parsed trade objects."""
    for trade in trades:
        issuer = trade.get("issuer") or {}
        raw_ticker = issuer.get("issuerTicker", "")
        issuer_id = issuer.get("_issuerId")
        if raw_ticker and issuer_id:
            clean = raw_ticker.split(":")[0].strip().upper()
            if clean:
                _ticker_id_cache[clean] = issuer_id


def _ingest_issuers_sidebar(decoded: str) -> None:
    """Parse the issuers dropdown filter list from RSC payload."""
    import json

    sidebar_idx = decoded.find('"issuers":[{')
    if sidebar_idx < 0:
        return
    arr_start = sidebar_idx + 10  # points at '['
    depth = 0
    arr_end = arr_start
    for i in range(arr_start, len(decoded)):
        ch = decoded[i]
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                arr_end = i + 1
                break
    try:
        issuer_list = json.loads(decoded[arr_start:arr_end])
        for item in issuer_list:
            raw_ticker = item.get("issuerTicker", "")
            issuer_id = item.get("_issuerId")
            if raw_ticker and issuer_id:
                clean = raw_ticker.split(":")[0].strip().upper()
                if clean:
                    _ticker_id_cache[clean] = issuer_id
    except (json.JSONDecodeError, IndexError, TypeError):
        pass


# ---------------------------------------------------------------------------
# Internal: value → size bucket
# ---------------------------------------------------------------------------

def _value_to_size_bucket(value: int | float | None) -> TradeSizeBucket | None:
    """Map Capitol Trades numeric value estimate to TradeSizeBucket.

    Capitol Trades converts the STOCK Act disclosure bucket to a USD midpoint:
        8,000  → "1K-15K"   32,500 → "15K-50K"   75,000 → "50K-100K"
    """
    if not value or value <= 0:
        return None
    if value <= 15_000:
        return "1K-15K"
    if value <= 50_000:
        return "15K-50K"
    if value <= 100_000:
        return "50K-100K"
    if value <= 250_000:
        return "100K-250K"
    if value <= 500_000:
        return "250K-500K"
    if value <= 1_000_000:
        return "500K-1M"
    if value <= 5_000_000:
        return "1M-5M"
    if value <= 25_000_000:
        return "5M-25M"
    if value <= 50_000_000:
        return "25M-50M"
    return "50M+"


# ---------------------------------------------------------------------------
# Internal: asset type heuristic
# ---------------------------------------------------------------------------

def _guess_asset_type(issuer_name: str, sector: str | None) -> str:
    name_up = issuer_name.upper()
    if sector is None:
        if "ETF" in name_up or "INDEX FUND" in name_up:
            return "etf"
        if any(k in name_up for k in ("FUND", "TRUST", "TREASURY", "BILL", "NOTE", "BOND")):
            return "bond_or_fund"
        return "etf_or_fund"
    return "stock"


# ---------------------------------------------------------------------------
# Internal: parse one trade dict → CongressionalTrade
# ---------------------------------------------------------------------------

def _parse_trade(raw: dict) -> CongressionalTrade | None:
    """Convert raw Capitol Trades JSON trade object to CongressionalTrade.

    Returns None if the trade is missing essential fields.
    """
    try:
        issuer = raw.get("issuer") or {}
        pol = raw.get("politician") or {}

        raw_ticker = issuer.get("issuerTicker", "")
        ticker = raw_ticker.split(":")[0].strip().upper()
        if not ticker:
            return None

        tx_type = (raw.get("txType") or "").lower()
        if tx_type == "buy":
            direction: TradeDirection = "buy"
        elif tx_type == "sell":
            direction = "sell"
        elif tx_type in ("exchange", "swap"):
            direction = "exchange"
        else:
            logger.debug("Unknown txType %r for trade %s", tx_type, raw.get("_txId"))
            direction = "buy"

        tx_date_raw = raw.get("txDate", "")
        pub_date_raw = raw.get("pubDate", "")[:10]
        if not tx_date_raw or not pub_date_raw:
            return None

        try:
            tx_date = date.fromisoformat(tx_date_raw)
            pub_date = date.fromisoformat(pub_date_raw)
        except ValueError:
            return None

        first = pol.get("firstName", "")
        last = pol.get("lastName", "")
        politician_name = f"{first} {last}".strip() or "Unknown"
        politician_id: str | None = raw.get("_politicianId")

        chamber_raw = (raw.get("chamber") or "").lower()
        chamber: Literal["house", "senate"] | None
        if chamber_raw == "senate":
            chamber = "senate"
        elif chamber_raw == "house":
            chamber = "house"
        else:
            chamber = None

        party_raw = (pol.get("party") or "").lower()
        party: Literal["democrat", "republican", "independent"] | None
        if party_raw in ("democrat", "republican", "independent"):
            party = party_raw  # type: ignore[assignment]
        else:
            party = None

        value = raw.get("value")
        size_bucket = _value_to_size_bucket(value)
        if value is not None and size_bucket is None:
            logger.debug("Unknown size bucket value %r for trade %s", value, raw.get("_txId"))

        issuer_name = issuer.get("issuerName") or None
        asset_type = _guess_asset_type(issuer_name or "", issuer.get("sector"))

        tx_id = raw.get("_txId")
        source_url = (
            f"{_BASE_URL}/trades/{tx_id}" if tx_id else
            f"{_BASE_URL}/politicians/{politician_id}" if politician_id else
            _BASE_URL
        )

        return CongressionalTrade(
            ticker=ticker,
            politician_name=politician_name,
            politician_id=politician_id,
            chamber=chamber,
            party=party,
            direction=direction,
            size_bucket=size_bucket,
            transaction_date=tx_date,
            disclosure_date=pub_date,
            asset_type=asset_type,
            issuer_name=issuer_name,
            source_url=source_url,
        )
    except Exception as exc:
        logger.debug("Failed to parse trade %s: %s", raw.get("_txId"), exc)
        return None


# ---------------------------------------------------------------------------
# Internal: HTTP fetch with retry
# ---------------------------------------------------------------------------

def _fetch_page(url: str, timeout: int = 20) -> str | None:
    """GET a page; returns HTML text or None on hard failure."""
    for attempt in range(2):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            if attempt == 0:
                logger.warning("Capitol Trades fetch failed (%s), retrying in 2s: %s", url, exc)
                time.sleep(2)
            else:
                logger.error("Capitol Trades fetch failed on retry (%s): %s", url, exc)
    return None


def _paginate(
    base_url: str,
    *,
    stop_before: date | None = None,
    max_pages: int = 20,
) -> list[CongressionalTrade]:
    """Paginate base_url, collect trades, stop when pubDate falls below stop_before.

    Sleeps 1s between pages. Stops early on 2 consecutive failures.
    """
    all_trades: list[CongressionalTrade] = []
    consecutive_failures = 0

    for page in range(1, max_pages + 1):
        sep = "&" if "?" in base_url else "?"
        url = f"{base_url}{sep}page={page}"
        logger.info("Fetching Capitol Trades page %d: %s", page, url)

        html = _fetch_page(url)
        if html is None:
            consecutive_failures += 1
            if consecutive_failures >= 2:
                logger.warning("2 consecutive failures; stopping Capitol Trades pagination")
                break
            continue
        consecutive_failures = 0

        raw_trades, _, _ = _extract_rsc_data(html)
        if not raw_trades:
            logger.info("No trades on page %d, stopping", page)
            break

        page_trades: list[CongressionalTrade] = []
        oldest_pub: date | None = None
        for raw in raw_trades:
            trade = _parse_trade(raw)
            if trade is None:
                continue
            if oldest_pub is None or trade.disclosure_date < oldest_pub:
                oldest_pub = trade.disclosure_date
            page_trades.append(trade)

        all_trades.extend(page_trades)

        # Stop if the oldest trade on this page predates our cutoff
        if stop_before and oldest_pub and oldest_pub < stop_before:
            logger.info(
                "Oldest pubDate %s < cutoff %s; done paginating", oldest_pub, stop_before
            )
            break

        if page < max_pages:
            time.sleep(1.0)

    return all_trades


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def get_recent_trades(
    *,
    days_back: int = 30,
    direction: TradeDirection | None = None,
    chamber: Literal["house", "senate"] | None = None,
    cache_ttl_sec: int = 3600,
    max_pages: int = 20,
) -> list[CongressionalTrade]:
    """Fetch all congressional trades disclosed in the last N days.

    Filters apply post-fetch on the parsed CongressionalTrade objects
    UNLESS the upstream URL supports the filter natively (in which case
    use the URL filter — fewer requests).

    `max_pages` caps pagination to avoid runaway loops if the site changes.

    Caches the FULL fetch result (pre-filter) for cache_ttl_sec. Default
    1 hour — congressional disclosures don't change minute-to-minute.

    On scraping failure: logs WARNING with details, returns []. Does not
    raise. Stage 1 must not crash because Capitol Trades had a bad day.
    """
    cache_key = f"ct:recent_all:{days_back}:{max_pages}"
    cached = _cache_get(cache_key, cache_ttl_sec)
    if cached is not None:
        logger.info("cache hit: get_recent_trades(days_back=%d)", days_back)
        all_trades: list[CongressionalTrade] = cached
    else:
        logger.info("cache miss: get_recent_trades(days_back=%d, max_pages=%d)", days_back, max_pages)
        cutoff = date.today() - timedelta(days=days_back)
        try:
            all_trades = _paginate(
                f"{_BASE_URL}/trades",
                stop_before=cutoff,
                max_pages=max_pages,
            )
        except Exception as exc:
            logger.warning("get_recent_trades hard failure: %s", exc)
            return []

        if not all_trades:
            # Don't cache empty results — might be a transient outage
            return []

        # Filter to the requested window before caching
        all_trades = [t for t in all_trades if t.disclosure_date >= cutoff]
        _cache_set(cache_key, all_trades)

    # Apply optional post-cache filters
    result = all_trades
    if direction is not None:
        result = [t for t in result if t.direction == direction]
    if chamber is not None:
        result = [t for t in result if t.chamber == chamber]
    return result


def get_recent_trades_for_ticker(
    ticker: str,
    *,
    days_back: int = 30,
    direction: TradeDirection | None = None,
    cache_ttl_sec: int = 3600,
) -> list[CongressionalTrade]:
    """Fetch all congressional trades for one ticker in the last N days.

    Prefer this over `get_recent_trades` when you only care about one ticker —
    Capitol Trades has per-ticker pages (e.g. /issuers/429789 for AAPL) that are
    cheaper to fetch than paginating the global list.

    On scraping failure: returns []. Does not raise.
    """
    sym = ticker.strip().upper()
    cache_key = f"ct:ticker:{sym}:{days_back}"
    cached = _cache_get(cache_key, cache_ttl_sec)
    if cached is not None:
        logger.info("cache hit: get_recent_trades_for_ticker(%s, days_back=%d)", sym, days_back)
        result: list[CongressionalTrade] = cached
        if direction is not None:
            result = [t for t in result if t.direction == direction]
        return result

    logger.info("cache miss: get_recent_trades_for_ticker(%s, days_back=%d)", sym, days_back)

    cutoff = date.today() - timedelta(days=days_back)

    # Try to get issuer ID for efficient per-issuer pagination
    if sym not in _ticker_id_cache:
        # Warm the cache from a global-trades first page
        _warm_ticker_id_cache()

    issuer_id = _ticker_id_cache.get(sym)

    try:
        if issuer_id:
            logger.info("Using per-issuer page %d for %s", issuer_id, sym)
            # Calculate how many pages we need for the requested days_back
            # ~15 trades per page; estimate generously
            estimated_pages = max(5, days_back // 2)
            all_trades = _paginate(
                f"{_BASE_URL}/issuers/{issuer_id}",
                stop_before=cutoff,
                max_pages=estimated_pages,
            )
        else:
            logger.info("No issuer ID for %s; using global trades fallback", sym)
            # Fall back to global trades — this is slower for large days_back
            all_trades = get_recent_trades(days_back=days_back, cache_ttl_sec=cache_ttl_sec)

        ticker_trades = [t for t in all_trades if t.ticker == sym and t.disclosure_date >= cutoff]
        _cache_set(cache_key, ticker_trades)

    except Exception as exc:
        logger.warning("get_recent_trades_for_ticker(%s) hard failure: %s", sym, exc)
        return []

    if direction is not None:
        ticker_trades = [t for t in ticker_trades if t.direction == direction]
    return ticker_trades


def _warm_ticker_id_cache() -> None:
    """Fetch page 1 of global trades to populate _ticker_id_cache."""
    url = f"{_BASE_URL}/trades?page=1"
    html = _fetch_page(url)
    if html:
        _extract_rsc_data(html)


def get_politicians_who_bought(
    ticker: str,
    *,
    days_back: int = 30,
) -> list[dict]:
    """Convenience: list of unique politicians who BOUGHT this ticker recently.

    Each dict: {politician_name, politician_id, chamber, party, count, latest_date}.
    Sorted by latest_date descending. Returns [] on failure.
    """
    trades = get_recent_trades_for_ticker(ticker, days_back=days_back, direction="buy")
    if not trades:
        return []

    pol_map: dict[str, dict] = {}
    for t in trades:
        pid = t.politician_id or t.politician_name
        if pid not in pol_map:
            pol_map[pid] = {
                "politician_name": t.politician_name,
                "politician_id": t.politician_id,
                "chamber": t.chamber,
                "party": t.party,
                "count": 0,
                "latest_date": t.disclosure_date,
            }
        pol_map[pid]["count"] += 1
        if t.disclosure_date > pol_map[pid]["latest_date"]:
            pol_map[pid]["latest_date"] = t.disclosure_date

    result = sorted(pol_map.values(), key=lambda d: d["latest_date"], reverse=True)
    return result


def get_top_performing_politicians(
    top_n: int = 10,
    *,
    cache_ttl_sec: int = 86400,
) -> list[dict]:
    """List politicians with the strongest historical alpha vs SPY.

    Each dict: {politician_id, politician_name, chamber, party, alpha_vs_spy_pct,
    win_rate_pct, total_trades, source_url}.

    If Capitol Trades does not expose a track-record/alpha metric publicly,
    this function MUST raise NotImplementedError with a clear message
    pointing at the relevant doc comment. Do not return fake data.

    ── Why NotImplementedError ──────────────────────────────────────────
    Capitol Trades politician pages (e.g. /politicians/W000805) show:
      • list of trades with txDate / pubDate / ticker / txType / value
      • basic stats: countTrades, dateFirstTraded, dateLastTraded, sector

    They do NOT publish:
      • alpha vs SPY or any benchmark
      • annualised return
      • win rate (% of trades that were profitable)
      • portfolio-level performance metrics

    All track-record research cited in the Lopez-Lira / AlphaAgents work
    is based on independent back-testing against actual stock prices, not
    data vended by Capitol Trades. To implement this function, wire it
    to a back-tester that joins Capitol Trades trade data (available via
    get_recent_trades) with yfinance price data. That computation lives
    above this data-access layer — not here.
    ─────────────────────────────────────────────────────────────────────
    """
    raise NotImplementedError(
        "Capitol Trades does not publish alpha-vs-SPY or win-rate data for politicians. "
        "Implement a back-tester that joins get_recent_trades() with yfinance price data "
        "to compute performance metrics. See the module docstring PHASE 2 FINDINGS section "
        "and the get_top_performing_politicians() docstring for details."
    )


def is_capitol_trades_reachable(*, timeout_sec: float = 5.0) -> bool:
    """Health check: HEAD request to capitoltrades.com homepage.

    Used by Stage 1 to detect outages before relying on this data source.
    Returns True if 2xx, False on any error (including timeout).
    """
    try:
        resp = requests.head(_BASE_URL, headers=_HEADERS, timeout=timeout_sec)
        return resp.status_code < 300
    except Exception:
        return False
