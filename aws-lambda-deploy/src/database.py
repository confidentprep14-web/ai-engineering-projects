"""SQLite request log: schema setup, per-request logging, and stats aggregation.

Every /chat call (success or failure) writes one row here. /stats reads the
whole table back to compute real p50/p95 latency and cost — no in-memory
counters that would reset on restart or be wrong across multiple workers.

On Lambda, the database file lives under /tmp — the only writable path in
the execution environment — and is wiped whenever the execution environment
is recycled. This is fine for a per-invocation request log; it is not a
substitute for durable storage if these stats need to survive cold starts.
"""
import sqlite3
import statistics
import sys


def init_db(db_path: str) -> None:
    """Create the requests table if it does not already exist."""
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                client_ip TEXT,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                latency_ms INTEGER NOT NULL,
                model TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()
    finally:
        connection.close()


def log_request(
    db_path: str,
    request_id: str,
    client_ip: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    latency_ms: int,
    model: str,
    status: str,
) -> None:
    """Persist one request's outcome. Never raises: a DB write failure must
    not take down the response that already streamed to the client."""
    try:
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                INSERT INTO requests
                    (request_id, client_ip, prompt_tokens, completion_tokens,
                     cost_usd, latency_ms, model, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    client_ip,
                    prompt_tokens,
                    completion_tokens,
                    cost_usd,
                    latency_ms,
                    model,
                    status,
                ),
            )
            connection.commit()
        finally:
            connection.close()
    except sqlite3.Error as db_error:
        print(
            f"[warning] failed to log request {request_id}: {db_error}",
            file=sys.stderr,
        )


def _percentile(sorted_values: list[int], percentile: float) -> int:
    """Nearest-rank percentile over an already-sorted list."""
    if not sorted_values:
        return 0
    rank = max(0, min(len(sorted_values) - 1, int(round(percentile * (len(sorted_values) - 1)))))
    return sorted_values[rank]


def get_stats(db_path: str) -> dict:
    """Aggregate the request log into the metrics /stats reports."""
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT latency_ms, cost_usd, status FROM requests"
        ).fetchall()
    finally:
        connection.close()

    if not rows:
        return {
            "total_requests": 0,
            "total_cost_usd": 0.0,
            "p50_latency_ms": 0,
            "p95_latency_ms": 0,
            "error_rate": 0.0,
        }

    latencies_ms = sorted(row[0] for row in rows)
    total_cost_usd = sum(row[1] for row in rows)
    error_count = sum(1 for row in rows if row[2] == "error")

    return {
        "total_requests": len(rows),
        "total_cost_usd": round(total_cost_usd, 6),
        "p50_latency_ms": int(statistics.median(latencies_ms)),
        "p95_latency_ms": _percentile(latencies_ms, 0.95),
        "error_rate": round(error_count / len(rows), 4),
    }
