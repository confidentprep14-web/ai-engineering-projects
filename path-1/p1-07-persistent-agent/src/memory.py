"""SQLite-backed persistent memory: conversation history and extracted facts.

Two tables: `messages` (full conversation log per session) and `facts`
(deduplicated key/value facts with a confidence score). Both survive process
restarts because they live on disk, not in a dict that resets on exit.
"""

import os
import sqlite3
import time

CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_FACTS_TABLE = """
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_key TEXT NOT NULL,
    fact_value TEXT NOT NULL,
    confidence REAL NOT NULL,
    source_message_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(fact_key)
);
"""


class MemoryStore:
    """Owns the SQLite connection and all reads/writes to conversation memory."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        parent_dir = os.path.dirname(os.path.abspath(db_path))
        if parent_dir and not os.path.isdir(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        self.connection = sqlite3.connect(db_path)
        self.connection.execute(CREATE_MESSAGES_TABLE)
        self.connection.execute(CREATE_FACTS_TABLE)
        self.connection.commit()

    def _execute_with_retry(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Run a write statement, retrying once if SQLite reports the file is locked."""
        try:
            cursor = self.connection.execute(sql, params)
            self.connection.commit()
            return cursor
        except sqlite3.OperationalError as lock_error:
            if "locked" not in str(lock_error).lower():
                raise
            time.sleep(0.2)
            try:
                cursor = self.connection.execute(sql, params)
                self.connection.commit()
                return cursor
            except sqlite3.OperationalError as retry_error:
                raise sqlite3.OperationalError(
                    f"Database at {self.db_path} is locked after retry: {retry_error}"
                ) from retry_error

    def save_message(self, session_id: str, role: str, content: str) -> int:
        """Insert one conversation turn and return its rowid."""
        cursor = self._execute_with_retry(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        return cursor.lastrowid

    def load_recent_messages(self, session_id: str, limit: int) -> list[dict]:
        """Return the most recent `limit` messages for a session, oldest first."""
        rows = self.connection.execute(
            """
            SELECT role, content FROM (
                SELECT role, content, created_at, id
                FROM messages
                WHERE session_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            ) ORDER BY created_at ASC, id ASC
            """,
            (session_id, limit),
        ).fetchall()
        return [{"role": role, "content": content} for role, content in rows]

    def save_fact(self, key: str, value: str, confidence: float, source_id: int = None) -> None:
        """Insert or replace a fact so each fact_key holds exactly one current value."""
        self._execute_with_retry(
            """
            INSERT OR REPLACE INTO facts (fact_key, fact_value, confidence, source_message_id)
            VALUES (?, ?, ?, ?)
            """,
            (key, value, confidence, source_id),
        )

    def load_all_facts(self) -> list[dict]:
        """Return every stored fact as {"key", "value", "confidence"} dicts."""
        rows = self.connection.execute(
            "SELECT fact_key, fact_value, confidence FROM facts ORDER BY confidence DESC"
        ).fetchall()
        return [{"key": key, "value": value, "confidence": confidence} for key, value, confidence in rows]

    def load_top_facts(self, limit: int) -> list[dict]:
        """Return the highest-confidence facts, capped at `limit`."""
        rows = self.connection.execute(
            "SELECT fact_key, fact_value, confidence FROM facts ORDER BY confidence DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [{"key": key, "value": value, "confidence": confidence} for key, value, confidence in rows]

    def clear_all(self) -> None:
        """Wipe every stored message and fact."""
        self.connection.execute("DELETE FROM messages")
        self.connection.execute("DELETE FROM facts")
        self.connection.commit()

    def get_message_count(self) -> int:
        return self.connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    def get_fact_count(self) -> int:
        return self.connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0]

    def close(self) -> None:
        self.connection.close()
