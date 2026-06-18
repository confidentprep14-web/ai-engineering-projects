"""Tests for src/reviewer.py — chunking, LLM-call parsing, and merging.

The LLM is mocked in every test here (no network, no API key needed) —
these tests exercise the parsing/filtering/merging logic, not the
provider integration.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reviewer import chunk_diff_by_file, merge_results, review_chunk  # noqa: E402


def test_structured_output_parsing(mocker):
    """A mock LLM response with one HIGH security finding should come
    back from review_chunk as exactly one matching finding."""
    mock_response = [
        {
            "file": "auth.py",
            "line_range": "10-12",
            "severity": "HIGH",
            "category": "security",
            "finding": "Hardcoded password in source.",
            "suggestion": "Load the password from a secrets manager.",
        }
    ]
    mocker.patch("reviewer.get_json_completion", return_value=mock_response)

    chunk = {"filename": "auth.py", "diff": "+    password = 'hunter2'", "lines": 1}
    findings = review_chunk(chunk, min_severity="LOW")

    assert len(findings) == 1
    assert findings[0]["severity"] == "HIGH"
    assert findings[0]["category"] == "security"


def test_severity_filter(mocker):
    """When min_severity='HIGH' is requested, MEDIUM and LOW findings
    returned by the LLM must be filtered out before review_chunk returns."""
    mock_response = [
        {
            "file": "a.py",
            "line_range": "1-2",
            "severity": "HIGH",
            "category": "security",
            "finding": "High issue.",
            "suggestion": "Fix it.",
        },
        {
            "file": "a.py",
            "line_range": "3-4",
            "severity": "MEDIUM",
            "category": "performance",
            "finding": "Medium issue.",
            "suggestion": "Improve it.",
        },
        {
            "file": "a.py",
            "line_range": "5-6",
            "severity": "LOW",
            "category": "style",
            "finding": "Low issue.",
            "suggestion": "Style nit.",
        },
    ]
    mocker.patch("reviewer.get_json_completion", return_value=mock_response)

    chunk = {"filename": "a.py", "diff": "+ something", "lines": 1}
    findings = review_chunk(chunk, min_severity="HIGH")

    assert len(findings) == 1
    assert findings[0]["severity"] == "HIGH"


def test_large_diff_chunking():
    """chunk_diff_by_file must split a multi-file diff into one chunk per
    file, and no chunk's diff text may bleed in lines from another file."""
    diff_text = (
        "diff --git a/file_one.py b/file_one.py\n"
        "index 1111111..2222222 100644\n"
        "--- a/file_one.py\n"
        "+++ b/file_one.py\n"
        "@@ -1,3 +1,4 @@\n"
        " def one():\n"
        "+    return 1\n"
        "diff --git a/file_two.py b/file_two.py\n"
        "index 3333333..4444444 100644\n"
        "--- a/file_two.py\n"
        "+++ b/file_two.py\n"
        "@@ -1,3 +1,4 @@\n"
        " def two():\n"
        "+    return 2\n"
        "diff --git a/file_three.py b/file_three.py\n"
        "index 5555555..6666666 100644\n"
        "--- a/file_three.py\n"
        "+++ b/file_three.py\n"
        "@@ -1,3 +1,4 @@\n"
        " def three():\n"
        "+    return 3\n"
    )

    chunks = chunk_diff_by_file(diff_text)

    assert len(chunks) == 3
    filenames = [chunk["filename"] for chunk in chunks]
    assert filenames == ["file_one.py", "file_two.py", "file_three.py"]

    for chunk in chunks:
        other_filenames = [name for name in filenames if name != chunk["filename"]]
        for other_name in other_filenames:
            assert other_name not in chunk["diff"]


def test_merge_results_sorts_and_dedupes():
    """merge_results flattens per-chunk lists, sorts HIGH > MEDIUM > LOW
    (alphabetical by filename within a severity), and drops exact dupes."""
    results_per_chunk = [
        [
            {
                "file": "b.py",
                "line_range": "1-2",
                "severity": "LOW",
                "category": "style",
                "finding": "x",
                "suggestion": "y",
            },
            {
                "file": "a.py",
                "line_range": "1-2",
                "severity": "HIGH",
                "category": "security",
                "finding": "x",
                "suggestion": "y",
            },
        ],
        [
            {
                "file": "a.py",
                "line_range": "1-2",
                "severity": "HIGH",
                "category": "security",
                "finding": "x",
                "suggestion": "y",
            },
            {
                "file": "z.py",
                "line_range": "3-4",
                "severity": "MEDIUM",
                "category": "performance",
                "finding": "x",
                "suggestion": "y",
            },
        ],
    ]

    merged = merge_results(results_per_chunk)

    assert len(merged) == 3
    assert [item["severity"] for item in merged] == ["HIGH", "MEDIUM", "LOW"]
