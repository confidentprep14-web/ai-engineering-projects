"""Tests for src/extractor.py — loaders and LLM-backed extraction.

get_json_completion is mocked here (the established exception: unit tests
mock the LLM boundary; the real CLI path calls a live provider). The two
loader tests (ADR markdown parsing) are pure string logic and need no mock.
"""

import re
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from extractor import (  # noqa: E402
    extract_decision,
    load_adr_markdown,
    load_github_issue_json,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

VALID_EXTRACTION = {
    "decision": "Switch to PostgreSQL for JSONB support",
    "rationale": "PostgreSQL offers native JSONB columns with GIN indexing and we already run it elsewhere.",
    "author": "octocat",
    "tags": ["database", "postgresql", "jsonb"],
    "date": "2024-01-15",
}


def test_extraction_returns_decision_with_all_required_fields():
    """Spec test 3: mocked LLM extraction must populate decision, rationale,
    author, tags, date, source_file, and id must match ^[0-9a-f]{12}$."""
    raw_content = load_github_issue_json(str(FIXTURES_DIR / "issues" / "issue_42.json"))

    with patch("extractor.get_json_completion", return_value=VALID_EXTRACTION):
        decision = extract_decision(raw_content, "github_issue", "issue_42.json")

    assert decision.decision
    assert decision.rationale
    assert decision.author
    assert decision.tags
    assert decision.date
    assert decision.source_file == "issue_42.json"
    assert re.match(r"^[0-9a-f]{12}$", decision.id)


def test_adr_loader_extracts_title_and_date():
    """Spec test 6: load_adr_markdown on 0001-use-postgres.md must extract
    title 'Use PostgreSQL' and date '2024-03-10' from the heading/Date line."""
    result = load_adr_markdown(str(FIXTURES_DIR / "adrs" / "0001-use-postgres.md"))

    assert result["title"] == "Use PostgreSQL"
    assert result["date"] == "2024-03-10"
    assert "PostgreSQL" in result["content"]


def test_load_github_issue_json_returns_expected_keys():
    result = load_github_issue_json(str(FIXTURES_DIR / "issues" / "issue_42.json"))

    assert result["number"] == 42
    assert "PostgreSQL" in result["title"]
    assert result["closed_at"] == "2024-01-15T10:00:00Z"
    assert len(result["comments"]) == 2


def test_load_github_issue_json_missing_keys_get_defaults():
    missing_keys_path = FIXTURES_DIR / "issues" / "_missing_keys.json"
    missing_keys_path.write_text('{"number": 1}')
    try:
        result = load_github_issue_json(str(missing_keys_path))
    finally:
        missing_keys_path.unlink()

    assert result["title"] == ""
    assert result["body"] == ""
    assert result["comments"] == []
    assert result["closed_at"] == ""


def test_load_github_issue_json_invalid_json_raises_value_error():
    bad_path = FIXTURES_DIR / "issues" / "_invalid.json"
    bad_path.write_text("{not valid json")
    try:
        try:
            load_github_issue_json(str(bad_path))
            assert False, "expected ValueError"
        except ValueError as exc:
            assert str(bad_path) in str(exc)
    finally:
        bad_path.unlink()


def test_adr_loader_no_title_falls_back_to_filename():
    no_title_path = FIXTURES_DIR / "adrs" / "_no_title.md"
    no_title_path.write_text("Just some content with no heading.\n")
    try:
        result = load_adr_markdown(str(no_title_path))
    finally:
        no_title_path.unlink()

    assert result["title"] == "_no_title.md"
    assert result["date"] is None


def test_extract_decision_null_decision_falls_back_to_title():
    """Edge case from spec: LLM returns null for decision -> use raw title."""
    raw_content = load_github_issue_json(str(FIXTURES_DIR / "issues" / "issue_42.json"))
    extraction_with_null = {**VALID_EXTRACTION, "decision": None}

    with patch("extractor.get_json_completion", return_value=extraction_with_null):
        decision = extract_decision(raw_content, "github_issue", "issue_42.json")

    assert decision.decision == raw_content["title"]
