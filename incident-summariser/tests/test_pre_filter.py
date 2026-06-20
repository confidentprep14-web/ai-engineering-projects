"""Tests for src/pre_filter.py — streaming regex pre-filter and reduction stats.

No LLM call involved: this module is pure file/string logic.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pre_filter import calculate_reduction_pct, stream_filter_errors  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_pre_filter_extracts_error_lines_only(tmp_path):
    """Spec test 1: a 10-line log with 7 INFO, 2 ERROR, 1 WARN must yield
    exactly 3 filtered lines and report 10 total lines."""
    content = (
        "INFO starting up\n"
        "INFO request received\n"
        "ERROR failed to connect to db\n"
        "INFO retrying\n"
        "INFO retry succeeded\n"
        "WARN connection pool nearly full\n"
        "INFO request handled\n"
        "INFO request handled\n"
        "ERROR timeout waiting for upstream\n"
        "INFO shutting down\n"
    )
    log_file = tmp_path / "ten_lines.log"
    log_file.write_text(content)

    filtered_lines, total_lines = stream_filter_errors(str(log_file))

    assert total_lines == 10
    assert len(filtered_lines) == 3


def test_token_reduction_is_measurable_on_1000_line_log():
    """Spec test 2: on the 1000-line app.log fixture (mostly INFO lines),
    the pre-filter must reduce line count by more than 50%."""
    filtered_lines, total_lines = stream_filter_errors(str(FIXTURES_DIR / "app.log"))

    reduction_pct = calculate_reduction_pct(total_lines, len(filtered_lines))

    assert total_lines == 1000
    assert reduction_pct > 50.0


def test_stack_trace_lines_included_after_error(tmp_path):
    """Spec test 6: indented/'at '-prefixed lines following an ERROR line
    must be captured as part of the stack trace; subsequent non-indented
    INFO lines must not be."""
    content = "ERROR something failed\n  at module.py:42\n  at main.py:10\nINFO next line\n"
    log_file = tmp_path / "stack_trace.log"
    log_file.write_text(content)

    filtered_lines, total_lines = stream_filter_errors(str(log_file))

    assert total_lines == 4
    assert "  at module.py:42" in filtered_lines
    assert "  at main.py:10" in filtered_lines
    assert not any("INFO next line" in line for line in filtered_lines)


def test_empty_file_returns_empty_list_and_zero_total(tmp_path):
    log_file = tmp_path / "empty.log"
    log_file.write_text("")

    filtered_lines, total_lines = stream_filter_errors(str(log_file))

    assert filtered_lines == []
    assert total_lines == 0


def test_calculate_reduction_pct_handles_zero_total():
    assert calculate_reduction_pct(0, 0) == 0.0


def test_calculate_reduction_pct_rounds_to_one_decimal():
    assert calculate_reduction_pct(1000, 58) == 94.2
