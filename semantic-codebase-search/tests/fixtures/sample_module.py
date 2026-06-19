"""Sample module used as a fixture for chunker tests.

Contains 5 named top-level functions, each with a docstring, so the AST
chunker has a known, stable shape to assert against.
"""


def connect_to_database(host: str, port: int) -> object:
    """Open a connection to the database at host:port."""
    connection = object()
    return connection


def execute_query(connection, sql: str) -> list:
    """Run a SQL query against an open database connection."""
    results = []
    return results


def authenticate_user(username: str, password: str) -> bool:
    """Verify a username/password pair against stored credentials."""
    is_valid = bool(username) and bool(password)
    return is_valid


def retry_with_backoff(func, max_attempts: int = 3) -> object:
    """Call func, retrying with exponential backoff on failure."""
    attempt = 0
    while attempt < max_attempts:
        try:
            return func()
        except Exception:
            attempt += 1
    raise RuntimeError("max attempts exceeded")


def __internal_helper(value: int) -> int:
    """Dunder-style helper that should be skipped by the chunker."""
    return value * 2


def format_log_message(level: str, message: str) -> str:
    """Format a log line as '[LEVEL] message'."""
    return f"[{level.upper()}] {message}"
