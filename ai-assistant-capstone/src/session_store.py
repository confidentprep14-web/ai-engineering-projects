"""SQLite read/write helpers for documents, eval_runs, and messages.

Split out of database.py to keep that file under the 200-line cap.
database.py owns the schema (init_db) and the `requests` table; this file
owns everything /documents, /eval, and /chat's session-history step need.
Every write is defensive: a logging failure must never take down a response
that has already been computed or streamed.
"""
import sqlite3
import sys

from src.database import connect


def log_document(db_path: str, document_id: str, filename: str, chunks_count: int) -> None:
    """Record one uploaded document. Never raises."""
    try:
        connection = connect(db_path)
        try:
            connection.execute(
                "INSERT INTO documents (id, filename, chunks_count) VALUES (?, ?, ?)",
                (document_id, filename, chunks_count),
            )
            connection.commit()
        finally:
            connection.close()
    except sqlite3.Error as db_error:
        print(f"[warning] failed to log document {document_id}: {db_error}", file=sys.stderr)


def log_eval_run(db_path: str, suite_name: str, passed: int, total: int, retrieval_hit_rate: float | None) -> None:
    """Record the outcome of one eval suite run. Never raises."""
    try:
        connection = connect(db_path)
        try:
            connection.execute(
                """
                INSERT INTO eval_runs (suite_name, passed, total, retrieval_hit_rate)
                VALUES (?, ?, ?, ?)
                """,
                (suite_name, passed, total, retrieval_hit_rate),
            )
            connection.commit()
        finally:
            connection.close()
    except sqlite3.Error as db_error:
        print(f"[warning] failed to log eval run for {suite_name}: {db_error}", file=sys.stderr)


def get_session_messages(db_path: str, session_id: str, limit: int = 20) -> list[dict]:
    """Return the last `limit` messages for a session, oldest first."""
    connection = connect(db_path)
    try:
        rows = connection.execute(
            """
            SELECT role, content FROM messages
            WHERE session_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
    finally:
        connection.close()
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


def save_message(db_path: str, session_id: str, role: str, content: str) -> None:
    """Append one message to a session's history. Never raises."""
    try:
        connection = connect(db_path)
        try:
            connection.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )
            connection.commit()
        finally:
            connection.close()
    except sqlite3.Error as db_error:
        print(f"[warning] failed to save message for session {session_id}: {db_error}", file=sys.stderr)


def count_documents(db_path: str) -> int:
    connection = connect(db_path)
    try:
        row = connection.execute("SELECT COUNT(*) AS count FROM documents").fetchone()
    finally:
        connection.close()
    return row["count"] if row else 0
