"""Tests for src/parser.py — AST-based function metadata extraction.

No LLM involved: this is pure static analysis against the fixture files.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from parser import extract_function_metadata  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SIMPLE_MATH = str(FIXTURES_DIR / "simple_math.py")


def test_parser_extracts_exceptions_from_raise_statements():
    """Spec test 5: divide() raises ZeroDivisionError — extract_function_metadata
    must capture that in the function's `raises` list."""
    functions = extract_function_metadata(SIMPLE_MATH)
    divide_func = next(f for f in functions if f.name == "divide")

    assert "ZeroDivisionError" in divide_func.raises
