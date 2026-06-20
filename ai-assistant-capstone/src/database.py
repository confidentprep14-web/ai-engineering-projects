"""SQLite schema + request log + metrics aggregation.

Owns the `requests` table (per spec) and schema creation for all four
tables — the other three tables' read/write helpers live in
session_store.py to keep this file under the 200-line cap; schema stays
centralized here so init_db() is the single source of truth for the DDL.

/metrics reads the requests table back to compute real p50/p95 latency,
cost, retrieval hit rate, and tool use rate — no in-memory counters that
would reset on restart or be wrong across multiple workers. Every write is
defensive: a logging failure must never take down a response that has
already been computed or streamed.
"""
import sqlite3
import statistics
import sys


def connect(db_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: str) -> None:
    """Create all tables if they do not already exist.

    Three tables per spec (requests, documents, eval_runs), plus one extra
    `messages` table to hold the multi-turn session history that /chat's
    "load last 20 messages for this session_id" step depends on.
    """
    connection = connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                latency_ms INTEGER NOT NULL,
                retrieval_hit INTEGER NOT NULL DEFAULT 0,
                tool_used INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                chunks_count INTEGER NOT NULL,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS eval_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                suite_name TEXT NOT NULL,
                passed INTEGER NOT NULL,
                total INTEGER NOT NULL,
                retrieval_hit_rate REAL,
                run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()
    finally:
        connection.close()


def log_request(
    db_path: str,
    session_id: str | None,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    latency_ms: int,
    retrieval_hit: bool,
    tool_used: bool,
    status: str,
) -> None:
    """Persist one /chat request's outcome. Never raises."""
    try:
        connection = connect(db_path)
        try:
            connection.execute(
                """
                INSERT INTO requests
                    (session_id, prompt_tokens, completion_tokens, cost_usd,
                     latency_ms, retrieval_hit, tool_used, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    prompt_tokens,
                    completion_tokens,
                    cost_usd,
                    latency_ms,
                    int(retrieval_hit),
                    int(tool_used),
                    status,
                ),
            )
            connection.commit()
        finally:
            connection.close()
    except sqlite3.Error as db_error:
        print(f"[warning] failed to log request: {db_error}", file=sys.stderr)


def _percentile(sorted_values: list[int], percentile: float) -> int:
    """Nearest-rank percentile over an already-sorted list."""
    if not sorted_values:
        return 0
    rank = max(0, min(len(sorted_values) - 1, int(round(percentile * (len(sorted_values) - 1)))))
    return sorted_values[rank]


def get_metrics(db_path: str) -> dict:
    """Aggregate the requests table into the metrics /metrics reports."""
    connection = connect(db_path)
    try:
        rows = connection.execute(
            "SELECT latency_ms, cost_usd, status, retrieval_hit, tool_used FROM requests"
        ).fetchall()
    finally:
        connection.close()

    if not rows:
        return {
            "total_requests": 0,
            "total_cost_usd": 0.0,
            "p50_latency_ms": 0,
            "p95_latency_ms": 0,
            "retrieval_hit_rate": 0.0,
            "tool_use_rate": 0.0,
            "error_rate": 0.0,
        }

    latencies_ms = sorted(row["latency_ms"] for row in rows)
    total_cost_usd = sum(row["cost_usd"] for row in rows)
    error_count = sum(1 for row in rows if row["status"] == "error")
    retrieval_hit_count = sum(1 for row in rows if row["retrieval_hit"])
    tool_used_count = sum(1 for row in rows if row["tool_used"])

    return {
        "total_requests": len(rows),
        "total_cost_usd": round(total_cost_usd, 6),
        "p50_latency_ms": int(statistics.median(latencies_ms)),
        "p95_latency_ms": _percentile(latencies_ms, 0.95),
        "retrieval_hit_rate": round(retrieval_hit_count / len(rows), 4),
        "tool_use_rate": round(tool_used_count / len(rows), 4),
        "error_rate": round(error_count / len(rows), 4),
    }
