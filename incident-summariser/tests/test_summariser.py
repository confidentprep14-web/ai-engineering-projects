"""Tests for src/summariser.py — prompt construction and report parsing.

get_json_completion is mocked here (the established exception: unit tests
mock the LLM boundary; the real CLI path calls a live provider).
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from correlator import TimestampedLine  # noqa: E402
from summariser import (  # noqa: E402
    build_incident_prompt,
    parse_incident_report,
)

VALID_REPORT = {
    "timeline": [{"timestamp": "2024-01-01T10:00:02", "event": "DB connection refused"}],
    "root_cause": {
        "hypothesis": "Database replica became unreachable",
        "confidence": 0.85,
        "evidence": ["ERROR Connection refused by replica db-replica-2"],
    },
    "action_items": [{"priority": "HIGH", "description": "Restart replica db-replica-2"}],
}


def test_structured_output_has_required_keys():
    """Spec test 3: parse_incident_report must return a dict with
    timeline/root_cause/action_items, and confidence must be a float in
    [0, 1]."""
    with patch("summariser.get_json_completion", return_value=VALID_REPORT):
        report = parse_incident_report("irrelevant raw text — mocked")

    assert set(["timeline", "root_cause", "action_items"]).issubset(report.keys())
    confidence = report["root_cause"]["confidence"]
    assert isinstance(confidence, float)
    assert 0.0 <= confidence <= 1.0


def test_confidence_is_clamped_to_0_1_range():
    """Spec test 4: a confidence of 1.5 from the LLM must be clamped to 1.0."""
    bad_report = {
        "timeline": [],
        "root_cause": {"hypothesis": "Overconfident model", "confidence": 1.5, "evidence": []},
        "action_items": [],
    }
    with patch("summariser.get_json_completion", return_value=bad_report):
        report = parse_incident_report("irrelevant raw text — mocked")

    assert report["root_cause"]["confidence"] == 1.0


def test_confidence_is_clamped_when_negative():
    bad_report = {
        "timeline": [],
        "root_cause": {"hypothesis": "Underconfident model", "confidence": -0.4, "evidence": []},
        "action_items": [],
    }
    with patch("summariser.get_json_completion", return_value=bad_report):
        report = parse_incident_report("irrelevant raw text — mocked")

    assert report["root_cause"]["confidence"] == 0.0


def test_missing_keys_returns_minimal_report():
    incomplete = {"some_other_key": "oops"}
    with patch("summariser.get_json_completion", return_value=incomplete):
        report = parse_incident_report("irrelevant raw text — mocked")

    assert report["root_cause"]["hypothesis"] == "Unable to determine"
    assert report["root_cause"]["confidence"] == 0.0
    assert report["timeline"] == []
    assert report["action_items"] == []


def test_json_parse_failure_returns_minimal_report():
    with patch("summariser.get_json_completion", side_effect=ValueError("bad json: ```not json```")):
        report = parse_incident_report("not valid json")

    assert report["root_cause"]["hypothesis"] == "Unable to determine"
    assert report["root_cause"]["confidence"] == 0.0
    assert report["timeline"] == []
    assert report["action_items"] == []


def test_build_incident_prompt_formats_timestamped_lines():
    lines = [
        TimestampedLine(raw="ERROR boom", timestamp="2024-01-01T10:00:02", service="auth", lineno=1),
    ]
    prompt = build_incident_prompt(lines, ["auth"])

    assert "[auth]" in prompt
    assert "2024-01-01T10:00:02" in prompt
    assert "ERROR boom" in prompt
    assert "auth" in prompt


def test_build_incident_prompt_formats_plain_strings():
    prompt = build_incident_prompt(["ERROR boom no timestamp"], ["app"])

    assert "ERROR boom no timestamp" in prompt
    assert "app" in prompt
