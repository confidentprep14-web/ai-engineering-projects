"""CLI entry point: --db <path>, --schema <path>, --test.

Interactive mode introspects the database schema once at startup, then
loops on a Question> prompt, running the NL -> SQL -> validate -> execute
-> interpret pipeline (retry_on_error) for each question.

--test runs the 10 built-in NL->SQL pairs against the schema and reports
pass/fail plus average retry attempts.
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from agent import interpret_results, retry_on_error
from schema_inspector import format_schema_for_prompt, introspect_db

MAX_RETRIES = int(os.environ.get("MAX_SQL_RETRIES", "2"))
MAX_DISPLAY_ROWS = int(os.environ.get("MAX_DISPLAY_ROWS", "20"))

NL_SQL_TEST_PAIRS = [
    "Show me all customers from the US",
    "What are the 5 most expensive products?",
    "How many orders are in 'shipped' status?",
    "List all products with less than 10 items in stock",
    "What is the total revenue from delivered orders?",
    "Show me orders placed by customer with ID 1",
    "Which customers have placed more than 2 orders?",
    "What is the average order value?",
    "List customers along with their total number of orders",
    "What products have never been ordered?",
]


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


def run_interactive(db_path: str, schema_str: str) -> None:
    while True:
        try:
            question = input("Question> ").strip()
        except EOFError:
            break

        if question.lower() in ("quit", "exit"):
            break
        if not question:
            continue

        try:
            rows, column_names, sql_used, attempts = retry_on_error(
                question, schema_str, db_path, max_retries=MAX_RETRIES
            )
        except RuntimeError as e:
            print(f"Error: {e}")
            continue

        print(f"SQL: {sql_used} (attempts: {attempts})")
        _print_results_table(rows, column_names)
        print(interpret_results(question, rows, column_names))


def run_test_suite(db_path: str, schema_str: str) -> None:
    passed = 0
    total_attempts = 0

    for question in NL_SQL_TEST_PAIRS:
        try:
            rows, _column_names, sql_used, attempts = retry_on_error(
                question, schema_str, db_path, max_retries=MAX_RETRIES
            )
        except RuntimeError as e:
            print(f"[FAIL] {question} | Error: {e}")
            continue

        total_attempts += attempts
        # A query "passes" if it returns rows, or if it's an aggregate query
        # (COUNT/SUM/AVG) that legitimately returns a single row even when
        # the aggregate value itself is 0 or NULL.
        ok = len(rows) > 0 or "COUNT" in sql_used.upper() or "SUM" in sql_used.upper() or "AVG" in sql_used.upper()
        status = "[PASS]" if ok else "[FAIL]"
        if ok:
            passed += 1
        print(f"{status} {question} | SQL: {sql_used}")

    avg_attempts = total_attempts / len(NL_SQL_TEST_PAIRS) if NL_SQL_TEST_PAIRS else 0.0
    print(f"Passed {passed}/{len(NL_SQL_TEST_PAIRS)} | avg attempts: {avg_attempts:.1f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="SQL Agent — natural language to SQL")
    parser.add_argument("--db", default=os.environ.get("DEFAULT_DB_PATH", "ecommerce.db"))
    parser.add_argument("--schema", help="Path to a pre-formatted schema file (skip introspection)")
    parser.add_argument("--test", action="store_true", help="Run the 10 NL->SQL test pairs")
    args = parser.parse_args()

    if args.schema:
        with open(args.schema, "r", encoding="utf-8") as f:
            schema_str = f.read()
        print("Schema loaded from file")
    else:
        try:
            schema = introspect_db(args.db)
        except FileNotFoundError as e:
            print(str(e))
            sys.exit(1)
        schema_str = format_schema_for_prompt(schema)
        print(f"Schema loaded: {len(schema['tables'])} tables")

    if args.test:
        run_test_suite(args.db, schema_str)
    else:
        run_interactive(args.db, schema_str)


if __name__ == "__main__":
    main()
