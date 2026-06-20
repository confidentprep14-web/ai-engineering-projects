"""Core agent loop: NL -> SQL -> validate -> execute -> interpret.

nl_to_sql and interpret_results are the only functions here that call the
LLM (via get_completion); they're mocked at that boundary in unit tests.
retry_on_error wires the self-correction loop: a validation error or a
runtime SQL error gets fed back into the next nl_to_sql call as
prior_error, up to max_retries attempts.
"""

import sqlite3

from llm import get_completion
from sql_validator import extract_sql_from_response, parse_and_validate

NL_TO_SQL_SYSTEM_PROMPT = (
    "You are a SQLite expert. Given a database schema and a user question, "
    "generate a single SELECT statement that answers the question. Return "
    "ONLY the SQL query, no explanation."
)

INTERPRET_SYSTEM_PROMPT = (
    "You are a data analyst. Explain these SQL query results in plain "
    "English, in 2-3 sentences. Focus on the answer to the question, not "
    "the data format."
)


def nl_to_sql(question: str, schema_str: str, prior_error: str = "") -> str:
    """Ask the LLM to translate a natural-language question into SQL.

    Returns the raw LLM response (may contain markdown fences) — callers
    must run extract_sql_from_response before validating/executing.
    """
    user_prompt = f"Schema:\n{schema_str}\n\nQuestion: {question}"
    if prior_error:
        user_prompt = (
            f"The previous SQL produced this error: {prior_error}\n"
            f"Generate a corrected SQL query.\n\n{user_prompt}"
        )

    return get_completion(user_prompt, system=NL_TO_SQL_SYSTEM_PROMPT)


def execute_safe(sql: str, db_path: str) -> tuple[list[dict], list[str]]:
    """Execute a validated SELECT statement and return (rows, column_names).

    Raises RuntimeError on any runtime SQL error — the caller (retry_on_error)
    treats this as a recoverable failure and retries with the error injected.
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
        except sqlite3.Error as e:
            raise RuntimeError(str(e)) from e

        column_names = [description[0] for description in cursor.description]
        raw_rows = cursor.fetchall()
        rows = [dict(zip(column_names, row)) for row in raw_rows]
        return rows, column_names
    finally:
        conn.close()


def retry_on_error(
    question: str, schema_str: str, db_path: str, max_retries: int = 2
) -> tuple[list[dict], list[str], str, int]:
    """Run the NL -> SQL -> validate -> execute loop with self-correction.

    Returns (rows, column_names, sql_used, attempts) on success.
    Raises RuntimeError if no valid, executable SQL is produced within
    max_retries attempts.
    """
    prior_error = ""
    last_sql = ""

    for attempt in range(1, max_retries + 1):
        raw_response = nl_to_sql(question, schema_str, prior_error=prior_error)
        sql = extract_sql_from_response(raw_response)
        last_sql = sql

        validation = parse_and_validate(sql)
        if not validation.is_valid:
            prior_error = validation.error
            if attempt < max_retries:
                print(f"Retry {attempt}/{max_retries}: {prior_error}")
            continue

        try:
            rows, column_names = execute_safe(sql, db_path)
            return rows, column_names, sql, attempt
        except RuntimeError as e:
            prior_error = str(e)
            if attempt < max_retries:
                print(f"Retry {attempt}/{max_retries}: {prior_error}")
            continue

    raise RuntimeError(
        f"Could not generate valid SQL after {max_retries} attempts. "
        f"Last SQL tried: {last_sql!r}. Last error: {prior_error}"
    )


def interpret_results(question: str, rows: list[dict], column_names: list[str]) -> str:
    """Explain query results in plain English, or short-circuit on empty results."""
    if not rows:
        return "No results found."

    preview_rows = rows[:5]
    formatted = "\n".join(
        ", ".join(f"{col}={row[col]}" for col in column_names) for row in preview_rows
    )
    user_prompt = f"Question: {question}\nResults (first 5 rows):\n{formatted}"

    return get_completion(user_prompt, system=INTERPRET_SYSTEM_PROMPT)
