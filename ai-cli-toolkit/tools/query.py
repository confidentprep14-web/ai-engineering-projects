"""Tool plugin: ai query — natural language to SQL over a SQLite database.

Inlines schema introspection, the sqlglot-based SQL validator, and the
NL -> SQL -> validate -> execute -> interpret retry loop from the
sql-agent project (sibling project in this repo). Self-contained.
"""

import os
import sqlite3
import sys

from src.llm import get_completion

TOOL_NAME = "query"
TOOL_DESCRIPTION = "Natural language to SQL — ask questions about a SQLite database"

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

MAX_DISPLAY_ROWS = 20


def add_arguments(parser) -> None:
    parser.add_argument("--question", required=True, help="Natural language question")
    parser.add_argument("--db", default=None, help="SQLite database path (override config)")


def run(args, config) -> None:
    db_path = args.db or config.get("db_path", "ecommerce.db")
    max_retries = int(os.environ.get("MAX_SQL_RETRIES", config.get("max_retries", 3)))

    if not os.path.isfile(db_path):
        print(f"Database not found: {db_path}. Check .aiworkflow.yml db_path.")
        sys.exit(1)

    schema = _introspect_db(db_path)
    schema_str = _format_schema_for_prompt(schema)
    print(f"Schema loaded: {len(schema['tables'])} tables")

    try:
        rows, column_names, sql_used, attempts = _retry_on_error(
            args.question, schema_str, db_path, max_retries=max_retries
        )
    except RuntimeError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    print(f"SQL: {sql_used} (attempts: {attempts})")
    _print_results_table(rows, column_names)
    print(_interpret_results(args.question, rows, column_names))


def _introspect_db(db_path: str) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        tables = []
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        table_names = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]

        for table_name in table_names:
            cursor.execute(f"PRAGMA table_info('{table_name}')")
            columns = [
                {"name": row[1], "type": row[2], "nullable": not row[3], "pk": bool(row[5])}
                for row in cursor.fetchall()
            ]

            cursor.execute(f"PRAGMA foreign_key_list('{table_name}')")
            foreign_keys = [
                {"column": row[3], "references_table": row[2], "references_column": row[4]}
                for row in cursor.fetchall()
            ]

            tables.append({"name": table_name, "columns": columns, "foreign_keys": foreign_keys})

        return {"tables": tables}
    finally:
        conn.close()


def _format_schema_for_prompt(schema: dict) -> str:
    lines = ["Tables:", ""]

    for table in schema["tables"]:
        fk_by_column = {fk["column"]: fk for fk in table["foreign_keys"]}

        col_parts = []
        for col in table["columns"]:
            part = f"{col['name']} {col['type']}"
            if col["pk"]:
                part += " PK"
            fk = fk_by_column.get(col["name"])
            if fk:
                part += f" FK→{fk['references_table']}.{fk['references_column']}"
            col_parts.append(part)

        lines.append(f"{table['name']} ({', '.join(col_parts)})")

    return "\n".join(lines)


def _nl_to_sql(question: str, schema_str: str, prior_error: str = "") -> str:
    user_prompt = f"Schema:\n{schema_str}\n\nQuestion: {question}"
    if prior_error:
        user_prompt = (
            f"The previous SQL produced this error: {prior_error}\n"
            f"Generate a corrected SQL query.\n\n{user_prompt}"
        )
    return get_completion(user_prompt, system=NL_TO_SQL_SYSTEM_PROMPT)


def _extract_sql_from_response(response: str) -> str:
    text = response.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    text = text.split(";")[0].strip()
    return text


def _parse_and_validate(sql: str) -> tuple[bool, str | None]:
    """Returns (is_valid, error). Uses sqlglot's AST — not regex — to
    confirm the statement is a single SELECT."""
    import sqlglot
    import sqlglot.errors

    try:
        parsed = sqlglot.parse_one(sql)
    except sqlglot.errors.ParseError as e:
        return False, f"SQL parse error: {e}"

    stmt_type = type(parsed).__name__
    if stmt_type != "Select":
        return False, f"Only SELECT queries are allowed. Got: {stmt_type}."

    return True, None


def _execute_safe(sql: str, db_path: str) -> tuple[list[dict], list[str]]:
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


def _retry_on_error(
    question: str, schema_str: str, db_path: str, max_retries: int = 3
) -> tuple[list[dict], list[str], str, int]:
    prior_error = ""
    last_sql = ""

    for attempt in range(1, max_retries + 1):
        raw_response = _nl_to_sql(question, schema_str, prior_error=prior_error)
        sql = _extract_sql_from_response(raw_response)
        last_sql = sql

        is_valid, error = _parse_and_validate(sql)
        if not is_valid:
            prior_error = error
            if attempt < max_retries:
                print(f"Retry {attempt}/{max_retries}: {prior_error}")
            continue

        try:
            rows, column_names = _execute_safe(sql, db_path)
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


def _interpret_results(question: str, rows: list[dict], column_names: list[str]) -> str:
    if not rows:
        return "No results found."

    preview_rows = rows[:5]
    formatted = "\n".join(
        ", ".join(f"{col}={row[col]}" for col in column_names) for row in preview_rows
    )
    user_prompt = f"Question: {question}\nResults (first 5 rows):\n{formatted}"

    return get_completion(user_prompt, system=INTERPRET_SYSTEM_PROMPT)


def _print_results_table(rows: list[dict], column_names: list[str]) -> None:
    if not rows:
        print("(no rows)")
        return

    display_rows = rows[:MAX_DISPLAY_ROWS]
    header = " | ".join(column_names)
    print(header)
    print("-" * len(header))
    for row in display_rows:
        print(" | ".join(str(row[col]) for col in column_names))
    if len(rows) > MAX_DISPLAY_ROWS:
        print(f"... ({len(rows) - MAX_DISPLAY_ROWS} more rows)")
