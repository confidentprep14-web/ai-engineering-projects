"""Tests for src/sql_validator.py — AST-based SQL safety validation.

No LLM calls involved; sqlglot parsing is real and exercised directly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sql_validator import parse_and_validate  # noqa: E402


def test_blocks_insert():
    """Spec test 1: INSERT must be rejected, with the statement type surfaced."""
    result = parse_and_validate(
        "INSERT INTO customers VALUES (1, 'Alice', 'a@b.com', 'US', '2024-01-01')"
    )

    assert result.is_valid is False
    # sqlglot's AST node name is "Insert" (not "INSERT"); compare
    # case-insensitively per the spec's intent of "INSERT" appearing
    # somewhere in the error or statement_type.
    assert "insert" in (result.error or "").lower() or "insert" in (result.statement_type or "").lower()


def test_blocks_update():
    """Spec test 2: UPDATE must be rejected."""
    result = parse_and_validate("UPDATE customers SET name='Bob' WHERE id=1")

    assert result.is_valid is False


def test_blocks_delete():
    result = parse_and_validate("DELETE FROM customers WHERE id=1")

    assert result.is_valid is False


def test_blocks_drop():
    result = parse_and_validate("DROP TABLE customers")

    assert result.is_valid is False


def test_allows_select_with_join():
    """Spec test 3: a multi-table SELECT with JOIN/GROUP BY is allowed."""
    result = parse_and_validate(
        "SELECT c.name, COUNT(o.id) FROM customers c LEFT JOIN orders o "
        "ON c.id = o.customer_id GROUP BY c.id"
    )

    assert result.is_valid is True
    assert result.statement_type == "SELECT"


def test_does_not_flag_drop_table_as_a_string_literal():
    """The whole point of AST validation over regex: a string literal that
    contains the words "DROP TABLE" must not trip up SELECT validation."""
    result = parse_and_validate(
        "SELECT * FROM customers WHERE name = 'DROP TABLE'"
    )

    assert result.is_valid is True
    assert result.statement_type == "SELECT"


def test_parse_error_on_malformed_sql():
    result = parse_and_validate("SELEC * FORM customers")

    # sqlglot's default dialect is permissive; this is primarily a guard
    # against a crash — either an explicit parse error or a non-SELECT type
    # is an acceptable failure mode for malformed input.
    assert result.is_valid is False
