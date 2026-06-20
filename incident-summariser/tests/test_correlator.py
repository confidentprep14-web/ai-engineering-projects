"""Tests for src/correlator.py — timestamp parsing and multi-service merge.

Pure logic, no LLM call involved.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from correlator import merge_multi_service_logs, parse_timestamp  # noqa: E402


def test_multi_service_merge_sorts_by_timestamp():
    """Spec test 5: lines from two services must be merged into one list
    sorted by timestamp, regardless of input order."""
    lines_a = ["2024-01-01 10:00:05 ERROR something broke in service A"]
    lines_b = ["2024-01-01 10:00:02 ERROR something broke in service B"]

    merged = merge_multi_service_logs(
        ["auth.log", "db.log"],
        [lines_a, lines_b],
    )

    timestamps = [item.timestamp for item in merged]
    index_a = next(i for i, item in enumerate(merged) if item.service == "auth")
    index_b = next(i for i, item in enumerate(merged) if item.service == "db")

    assert index_b < index_a
    assert timestamps == sorted(timestamps)


def test_merge_tags_lines_with_service_name_from_filename():
    merged = merge_multi_service_logs(
        ["/var/log/auth.log"],
        [["2024-01-01 10:00:00 ERROR boom"]],
    )

    assert merged[0].service == "auth"


def test_merge_puts_lines_without_timestamp_at_end():
    merged = merge_multi_service_logs(
        ["app.log"],
        [["no timestamp here", "2024-01-01 10:00:00 ERROR boom"]],
    )

    assert merged[-1].timestamp is None
    assert merged[-1].raw == "no timestamp here"


def test_parse_timestamp_iso_format():
    assert parse_timestamp("2024-01-01T10:00:05 ERROR boom") == "2024-01-01T10:00:05"


def test_parse_timestamp_apache_format():
    assert parse_timestamp('10.0.0.1 - - [01/Jan/2024:10:00:05 +0000] "GET /"') == "01/Jan/2024:10:00:05"


def test_parse_timestamp_unix_epoch():
    assert parse_timestamp("1704103205.123 ERROR boom") == "1704103205.123"


def test_parse_timestamp_returns_none_when_no_match():
    assert parse_timestamp("no timestamp in this line") is None
