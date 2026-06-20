"""Tests for src/validator.py — running generated test code through real
pytest and reporting back pass/fail + parsed output. No LLM involved:
this module's job is ground-truth validation of code that already exists.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest  # noqa: E402
from validator import (  # noqa: E402
    filter_passing_tests,
    parse_pytest_output,
    print_coverage_summary,
    run_pytest_on_generated,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SIMPLE_MATH = str(FIXTURES_DIR / "simple_math.py")


def test_validator_detects_syntax_error():
    """Spec test 1: intentionally broken Python must be reported as a
    syntax error, not silently swallowed or misreported as a test failure."""
    broken_code = "def test_foo(:\n    pass"

    result = run_pytest_on_generated(broken_code, SIMPLE_MATH, "foo")

    assert result["passed"] is False
    assert "SyntaxError" in result["error"]


def test_filter_passing_tests_keeps_only_passing():
    """Spec test 3: a combined test file with one passing and one failing
    test must come out of filter_passing_tests with only the passer."""
    combined = f"""
import sys
sys.path.insert(0, {str(FIXTURES_DIR)!r})
from simple_math import add

def test_add_passes():
    assert add(2, 3) == 5

def test_add_fails():
    assert add(2, 3) == 999
"""

    result = filter_passing_tests(combined, SIMPLE_MATH)

    assert "test_add_passes" in result
    assert "test_add_fails" not in result


def test_coverage_summary_shows_branch_count(capsys):
    """Spec test 4: print_coverage_summary on the simple_math fixture with
    a real passing test file must print a percentage in its output."""
    pytest.importorskip("pytest_cov")

    real_test_file = str(FIXTURES_DIR / "tmp_test_simple_math_for_coverage.py")
    with open(real_test_file, "w") as f:
        f.write(
            f"""
import sys
sys.path.insert(0, {str(FIXTURES_DIR)!r})
from simple_math import add, subtract, divide

def test_add():
    assert add(2, 3) == 5

def test_subtract():
    assert subtract(5, 2) == 3

def test_divide():
    assert divide(10, 2) == 5

def test_divide_by_zero():
    try:
        divide(1, 0)
    except ZeroDivisionError:
        pass
"""
        )

    try:
        print_coverage_summary(SIMPLE_MATH, real_test_file)
        captured = capsys.readouterr()
        assert "%" in captured.out
        import re

        assert re.search(r"\d+%", captured.out)
    finally:
        Path(real_test_file).unlink(missing_ok=True)


def test_parse_pytest_output_summary_line():
    output = "===== 2 passed, 1 failed in 0.12s ====="
    result = parse_pytest_output(output)
    assert result["passed"] == 2
    assert result["failed"] == 1


def test_parse_pytest_output_no_tests_ran():
    output = "no tests ran in 0.01s"
    result = parse_pytest_output(output)
    assert result == {"total": 0, "passed": 0, "failed": 0, "errors": 1}
