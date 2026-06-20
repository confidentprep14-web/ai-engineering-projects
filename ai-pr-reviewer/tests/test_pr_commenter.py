"""Tests for pr_commenter.py: markdown formatting and dry-run posting."""

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from pr_commenter import (  # noqa: E402
    format_review_comment,
    format_test_results_comment,
    post_comment,
)


# ---------------------------------------------------------------------------
# Test 2 — PR comment formatter produces valid markdown
# ---------------------------------------------------------------------------


def test_format_review_comment_produces_valid_markdown():
    findings = [
        {
            "severity": "HIGH",
            "file": "auth.py",
            "line_range": "12-15",
            "category": "security",
            "finding": "Hardcoded password",
            "suggestion": "Use env var",
        },
        {
            "severity": "LOW",
            "file": "utils.py",
            "line_range": "3-3",
            "category": "style",
            "finding": "Missing docstring",
            "suggestion": "Add docstring",
        },
    ]
    trace_id = "a1b2c3d4"

    result = format_review_comment(findings, trace_id)

    assert result.startswith("## AI Code Review")

    high_row = next(line for line in result.splitlines() if "auth.py" in line)
    assert "🔴" in high_row

    assert trace_id in result
    assert "1 HIGH, 0 MEDIUM, 1 LOW findings" in result


# ---------------------------------------------------------------------------
# Test 5 — Dry-run skips posting but logs body
# ---------------------------------------------------------------------------


def test_post_comment_dry_run_skips_posting_and_logs_body(capsys):
    body = "## AI Code Review\n\nsome findings"

    result = post_comment(
        body,
        pr_number=1,
        repo_name="owner/repo",
        github_token="",
        post_comments=False,
    )

    assert result == "dry-run"

    captured = capsys.readouterr()
    assert body in captured.out


# ---------------------------------------------------------------------------
# Test 6 — Test results comment format
# ---------------------------------------------------------------------------


def test_format_test_results_comment():
    results = {
        "functions_tested": 3,
        "tests_generated": 8,
        "retries": 1,
        "coverage_pct": 72.0,
    }
    trace_id = "deadbeef"

    result = format_test_results_comment(results, trace_id)

    assert "Functions analyzed" in result
    assert "Tests generated" in result
    assert "Retries" in result
    assert trace_id in result
