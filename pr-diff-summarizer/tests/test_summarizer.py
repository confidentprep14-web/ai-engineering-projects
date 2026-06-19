"""Tests for src/summarizer.py — diff stats, test-coverage detection,
LLM-backed summary/arch-impact generation, and report formatting.

The LLM is mocked in every test here (no network, no API key needed) —
these tests exercise the parsing/post-processing/formatting logic, not
the provider integration.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from summarizer import (  # noqa: E402
    build_report,
    detect_test_changes,
    generate_arch_impact,
    generate_summary,
    parse_diff_stats,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_detect_test_changes_missing_tests():
    """no_tests.diff touches only src/auth.py — no test files present, so
    the coverage flag must be raised (True)."""
    diff_text = (FIXTURES_DIR / "no_tests.diff").read_text()

    assert detect_test_changes(diff_text) is True


def test_detect_test_changes_tests_present():
    """with_tests.diff touches src/auth.py AND tests/test_auth.py — tests
    are present, so the coverage flag must NOT be raised (False)."""
    diff_text = (FIXTURES_DIR / "with_tests.diff").read_text()

    assert detect_test_changes(diff_text) is False


def test_parse_diff_stats_counts_lines_and_files():
    """A minimal inline diff with exactly 2 added lines, 1 removed line,
    and 2 files must be parsed precisely."""
    diff_text = (
        "diff --git a/file_one.py b/file_one.py\n"
        "index 1111111..2222222 100644\n"
        "--- a/file_one.py\n"
        "+++ b/file_one.py\n"
        "@@ -1,2 +1,3 @@\n"
        " def one():\n"
        "-    return 0\n"
        "+    return 1\n"
        "diff --git a/file_two.py b/file_two.py\n"
        "index 3333333..4444444 100644\n"
        "--- a/file_two.py\n"
        "+++ b/file_two.py\n"
        "@@ -1,2 +1,3 @@\n"
        " def two():\n"
        "+    return 2\n"
    )

    stats = parse_diff_stats(diff_text)

    assert stats["files_changed"] == 2
    assert stats["lines_added"] == 2
    assert stats["lines_removed"] == 1
    assert stats["filenames"] == ["file_one.py", "file_two.py"]


def test_generate_summary_strips_raw_diff_lines(mocker):
    """If the LLM accidentally echoes a raw diff line back, generate_summary
    must strip it before returning — output must never start with + or -."""
    mock_response = (
        "This change updates the login flow to support a remember-me option.\n"
        "+    token.expires_in = 60 * 60 * 24 * 30\n"
        "The change also adds a logout helper."
    )
    mocker.patch("summarizer.get_completion", return_value=mock_response)

    diff_text = (FIXTURES_DIR / "no_tests.diff").read_text()
    summary = generate_summary(diff_text, title="Add remember-me login")

    for line in summary.splitlines():
        assert not line.startswith("+")
        assert not line.startswith("-")


def test_generate_arch_impact_docs_only_short_circuits(mocker):
    """A diff that touches only .md files must return the canned
    'No architectural changes.' string WITHOUT calling the LLM."""
    mock_completion = mocker.patch("summarizer.get_completion", return_value="x" * 5000)

    diff_text = (
        "diff --git a/README.md b/README.md\n"
        "index 1111111..2222222 100644\n"
        "--- a/README.md\n"
        "+++ b/README.md\n"
        "@@ -1,1 +1,2 @@\n"
        " # Project\n"
        "+Now with more docs.\n"
    )

    result = generate_arch_impact(diff_text)

    assert result == "No architectural changes."
    mock_completion.assert_not_called()


def test_build_report_contains_all_sections_and_flag_text():
    """build_report must render all four section headings, and the test
    coverage section must show the correct warning/success string."""
    stats = {
        "files_changed": 2,
        "lines_added": 10,
        "lines_removed": 3,
        "filenames": ["src/auth.py", "tests/test_auth.py"],
    }

    report_missing_tests = build_report(
        summary="A short plain-English summary.",
        arch_impact="A short architecture paragraph.",
        test_flag=True,
        stats=stats,
    )
    report_with_tests = build_report(
        summary="A short plain-English summary.",
        arch_impact="A short architecture paragraph.",
        test_flag=False,
        stats=stats,
    )

    for report in (report_missing_tests, report_with_tests):
        assert "Summary" in report
        assert "Architecture Impact" in report
        assert "Test Coverage Flag" in report
        assert "Diff Stats" in report

    assert "No test changes detected" in report_missing_tests
    assert "Tests modified" in report_with_tests
