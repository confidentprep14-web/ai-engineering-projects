"""Tests for src/schema_inspector.py — real sqlite3 introspection.

No mocking: these create a real temp SQLite file with the e-commerce
schema and run introspect_db / format_schema_for_prompt against it.
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from schema_inspector import format_schema_for_prompt, introspect_db  # noqa: E402

SCHEMA_SQL = """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    country TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL,
    stock_quantity INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    total_amount REAL NOT NULL,
    status TEXT NOT NULL,
    ordered_at TEXT NOT NULL
);
"""


def _make_temp_db() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
    return path


def test_introspect_db_returns_three_tables():
    """Spec test 5: a fresh e-commerce-schema db introspects to 3 tables
    with the expected names."""
    db_path = _make_temp_db()
    try:
        schema = introspect_db(db_path)

        assert len(schema["tables"]) == 3
        table_names = {t["name"] for t in schema["tables"]}
        assert table_names == {"customers", "products", "orders"}
    finally:
        os.remove(db_path)


def test_introspect_db_raises_file_not_found_for_missing_db():
    result_path = "/tmp/this_db_does_not_exist_sql_agent_test.db"
    if os.path.exists(result_path):
        os.remove(result_path)

    try:
        introspect_db(result_path)
        assert False, "expected FileNotFoundError"
    except FileNotFoundError as e:
        assert "init_db.py" in str(e)


def test_introspect_db_captures_foreign_keys():
    db_path = _make_temp_db()
    try:
        schema = introspect_db(db_path)
        orders_table = next(t for t in schema["tables"] if t["name"] == "orders")

        fk_columns = {fk["column"] for fk in orders_table["foreign_keys"]}
        assert fk_columns == {"customer_id", "product_id"}
    finally:
        os.remove(db_path)


def test_format_schema_for_prompt_includes_table_and_column_names():
    db_path = _make_temp_db()
    try:
        schema = introspect_db(db_path)
        formatted = format_schema_for_prompt(schema)

        assert "customers" in formatted
        assert "products" in formatted
        assert "orders" in formatted
        assert "FK→customers.id" in formatted or "FK→customers" in formatted
    finally:
        os.remove(db_path)
