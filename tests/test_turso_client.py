"""Tests for the Turso tracker client.

History note (2026-05-07): the original tests in this file mocked
`get_connection()` — a legacy local-SQLite proxy that the current cloud
client does not use. Every public function (`get_all_trades`,
`insert_trade`, `update_trade`, `log_fill`, `create_all_tables`) talks to
Turso directly via HTTP through `_execute`, `_execute_batch`,
`_insert_and_get_id`, or `requests.post`. The mocks were silently ignored
and tests inserted real rows into production Turso (e.g. NVDA at $850
under run_id "run-3"). These tests have been rewritten to intercept the
actual HTTP-layer helpers so they can no longer leak.
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Test doubles for the HTTP-layer helpers
# ---------------------------------------------------------------------------

class FakeExecute:
    """Drop-in replacement for tracker.turso_client._execute.

    Records every (sql, params) call and returns a canned row set per
    matched SQL prefix. Tests can inspect `self.calls` afterwards to
    verify SQL shape and parameter binding.
    """

    def __init__(self, prefix_to_rows: dict[str, list[dict[str, Any]]] | None = None):
        self.calls: list[tuple[str, list[Any] | None]] = []
        self.prefix_to_rows = prefix_to_rows or {}

    def __call__(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        self.calls.append((sql, list(params) if params else None))
        normalized = " ".join(sql.lower().split())
        for prefix, rows in self.prefix_to_rows.items():
            if normalized.startswith(prefix.lower()):
                return rows
        return []


class FakeInsertAndGetId:
    """Drop-in replacement for tracker.turso_client._insert_and_get_id.

    Records every (sql, params) call and returns canned rowids in order.
    """

    def __init__(self, returns: list[int]):
        self.calls: list[tuple[str, list[Any]]] = []
        self._returns = list(returns)

    def __call__(self, sql: str, params: list[Any]) -> int:
        self.calls.append((sql, list(params)))
        if not self._returns:
            raise AssertionError("FakeInsertAndGetId called more times than expected")
        return self._returns.pop(0)


class FakeRequestsResponse:
    def __init__(self, json_payload: dict, status: int = 200):
        self._json = json_payload
        self.status_code = status

    def json(self) -> dict:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeRequestsPost:
    """Captures HTTP body sent to Turso's pipeline endpoint without making
    an actual network call. Used only for `create_all_tables` (which calls
    `requests.post` directly rather than going through `_execute`)."""

    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        # Hrana's pipeline replies with a list of per-statement results.
        results = []
        for stmt_req in (json or {}).get("requests", []):
            if stmt_req.get("type") == "execute":
                results.append({
                    "type": "ok",
                    "response": {"result": {"cols": [], "rows": []}},
                })
            elif stmt_req.get("type") == "close":
                results.append({"type": "ok"})
        return FakeRequestsResponse({"results": results})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_create_all_tables_emits_required_schema(monkeypatch):
    """`create_all_tables` should send a single HTTP request whose body contains
    CREATE TABLE statements for trades, daily_summary, fills, pending_decisions —
    and the trades schema must include the `last_checked_at` column the simulator
    relies on for idempotent fills."""
    from tracker import turso_client

    # Provide fake credentials so _creds() inside create_all_tables doesn't crash
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://fake.test")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "fake-token")

    fake_post = FakeRequestsPost()
    monkeypatch.setattr(turso_client.requests, "post", fake_post)

    turso_client.create_all_tables()

    assert len(fake_post.calls) == 1, "create_all_tables should make exactly one HTTP call"
    body = fake_post.calls[0]["json"]
    sqls = "\n".join(
        req["stmt"]["sql"]
        for req in body["requests"]
        if req.get("type") == "execute"
    )
    assert "CREATE TABLE IF NOT EXISTS trades" in sqls
    assert "last_checked_at TEXT" in sqls
    assert "decision_made_at TEXT" in sqls          # added 2026-05-07
    assert "entry_valid_until TEXT" in sqls         # added 2026-05-07
    assert "CREATE TABLE IF NOT EXISTS daily_summary" in sqls
    assert "CREATE TABLE IF NOT EXISTS fills" in sqls
    assert "CREATE TABLE IF NOT EXISTS pending_decisions" in sqls


def test_trade_queries_filter_by_status(monkeypatch):
    """get_all_trades / get_open_positions / get_pending_trades should hit
    `_execute` with the right SQL filter (or no filter for "all"), and pass
    statuses as bound parameters — never as string concatenation."""
    from tracker import turso_client

    canned_rows = {
        "select * from trades order by created_at desc": [
            {"id": 1, "ticker": "AAPL", "status": "entered"},
            {"id": 2, "ticker": "MSFT", "status": "pending"},
        ],
        "select * from trades where status = ? order by created_at desc": [
            {"id": 1, "ticker": "AAPL", "status": "entered"},
        ],
    }
    fake_execute = FakeExecute(prefix_to_rows=canned_rows)
    monkeypatch.setattr(turso_client, "_execute", fake_execute)

    # All trades (no status filter)
    fake_execute.prefix_to_rows = {"select * from trades order by": [
        {"id": 1, "ticker": "AAPL", "status": "entered"},
        {"id": 2, "ticker": "MSFT", "status": "pending"},
    ]}
    all_trades = turso_client.get_all_trades()
    assert [t["ticker"] for t in all_trades] == ["AAPL", "MSFT"]

    # Open positions (status='entered')
    fake_execute.prefix_to_rows = {"select * from trades where status = ?": [
        {"id": 1, "ticker": "AAPL", "status": "entered"},
    ]}
    open_positions = turso_client.get_open_positions()
    assert [t["ticker"] for t in open_positions] == ["AAPL"]
    open_call = fake_execute.calls[-1]
    assert open_call[1] == ["entered"], f"status must be a bound param, got: {open_call}"

    # Pending trades (status='pending')
    fake_execute.prefix_to_rows = {"select * from trades where status = ?": [
        {"id": 2, "ticker": "MSFT", "status": "pending"},
    ]}
    pending_trades = turso_client.get_pending_trades()
    assert [t["ticker"] for t in pending_trades] == ["MSFT"]
    pending_call = fake_execute.calls[-1]
    assert pending_call[1] == ["pending"], f"status must be a bound param, got: {pending_call}"


def test_insert_update_and_log_fill_use_parameterized_sql(monkeypatch):
    """insert_trade, update_trade, and log_fill must all use parameterized SQL
    (`?` placeholders + a separate args list) rather than string concatenation.
    A regression here would expose us to SQL-injection-style bugs.

    Also asserts that this test itself is hermetic — it must NEVER reach real
    Turso. Earlier versions of this test mocked `get_connection`, which the
    current cloud client doesn't use, and silently leaked NVDA rows into the
    production database.
    """
    from tracker import turso_client

    fake_insert = FakeInsertAndGetId(returns=[42, 99])
    fake_execute = FakeExecute()
    monkeypatch.setattr(turso_client, "_insert_and_get_id", fake_insert)
    monkeypatch.setattr(turso_client, "_execute", fake_execute)

    # 1. insert_trade goes through _insert_and_get_id with parameterized SQL
    trade_id = turso_client.insert_trade({
        "run_id": "run-3",
        "mode": "swing",
        "ticker": "NVDA",
        "direction": "long",
        "quantity": 1,
        "entry_price": 850.0,
    })
    assert trade_id == 42
    assert len(fake_insert.calls) == 1
    insert_sql, insert_params = fake_insert.calls[0]
    assert insert_sql.startswith("INSERT INTO trades")
    assert insert_sql.count("?") == len(insert_params), \
        "every value must be a placeholder; counts must match"
    # No literal value should appear in the SQL itself
    assert "NVDA" not in insert_sql
    assert "850" not in insert_sql

    # 2. update_trade goes through _execute with parameterized SET clause
    turso_client.update_trade(42, status="entered", entry_fill_price=851.0)
    assert len(fake_execute.calls) == 1
    update_sql, update_params = fake_execute.calls[0]
    assert update_sql == "UPDATE trades SET status = ?, entry_fill_price = ? WHERE id = ?"
    assert update_params == ["entered", 851.0, 42]

    # 3. log_fill goes through _insert_and_get_id with parameterized SQL
    fill_id = turso_client.log_fill(
        trade_id=42,
        event_type="entry_filled",
        price=851.0,
        bar_timestamp="2026-04-29T13:00:00",
        reason="entry crossed",
    )
    assert fill_id == 99
    assert len(fake_insert.calls) == 2
    fill_sql, fill_params = fake_insert.calls[1]
    assert fill_sql.startswith("INSERT INTO fills")
    assert fill_sql.count("?") == len(fill_params)
    assert "entry_filled" not in fill_sql
    assert fill_params[1] == "entry_filled"
