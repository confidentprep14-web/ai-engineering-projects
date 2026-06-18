"""Tests for src/reporter.py — severity counting and JSON output."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reporter import count_by_severity, save_json  # noqa: E402


def test_count_by_severity():
    """2 HIGH, 1 MEDIUM, 0 LOW findings must produce the matching counts,
    with the missing LOW key defaulting to 0."""
    findings = [
        {"severity": "HIGH"},
        {"severity": "HIGH"},
        {"severity": "MEDIUM"},
    ]

    counts = count_by_severity(findings)

    assert counts == {"HIGH": 2, "MEDIUM": 1, "LOW": 0}


def test_save_json_roundtrip(tmp_path):
    """save_json must write valid JSON that round-trips exactly, including
    severity values."""
    findings = [
        {
            "file": "a.py",
            "line_range": "1-2",
            "severity": "HIGH",
            "category": "security",
            "finding": "x",
            "suggestion": "y",
        },
        {
            "file": "b.py",
            "line_range": "3-4",
            "severity": "LOW",
            "category": "style",
            "finding": "x2",
            "suggestion": "y2",
        },
    ]
    output_path = tmp_path / "results.json"

    save_json(findings, str(output_path))

    with open(output_path) as f:
        loaded = json.load(f)

    assert len(loaded) == 2
    assert loaded[0]["severity"] == "HIGH"
    assert loaded[1]["severity"] == "LOW"
