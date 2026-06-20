"""Tests for src/copilot.py — confidence gating and citation-formatted answers.

build_answer_with_citations is the only function in this project that makes
a real LLM call; get_completion is mocked here (the established exception:
unit tests mock the LLM boundary, the real CLI path calls a live provider).
handle_below_threshold and format_citations are pure logic and need no mock.
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from chunker import ChunkMetadata  # noqa: E402
from copilot import (  # noqa: E402
    build_answer_with_citations,
    format_citations,
    handle_below_threshold,
)


def _meta(doc_title: str, section_heading: str) -> ChunkMetadata:
    return ChunkMetadata(
        doc_title=doc_title,
        section_heading=section_heading,
        last_modified=1700000000.0,
        source_file=f"/fixtures/docs/{doc_title}.md",
        chunk_index=0,
        char_count=42,
    )


def test_handle_below_threshold_returns_dont_know_message():
    """Spec test 3: below-threshold score returns a message containing
    "don't have enough information" and the original query text."""
    result = handle_below_threshold(
        query="What is the airspeed velocity?", top_score=0.3, threshold=0.5
    )

    assert result is not None
    assert "don't have enough information" in result
    assert "What is the airspeed velocity?" in result


def test_handle_below_threshold_returns_none_when_above_threshold():
    result = handle_below_threshold(query="How do I reset my password?", top_score=0.8, threshold=0.5)

    assert result is None


def test_build_answer_with_citations_contains_citation_format():
    """Spec test 4: mocked get_completion response with a citation; assert
    the returned answer contains a [..>..] bracket pair and the cited
    doc_title."""
    chunks = [
        {"text": "Set DATABASE_URL in your .env file.", "metadata": _meta("setup_guide", "Database Configuration")},
        {"text": "Use a Bearer token in the Authorization header.", "metadata": _meta("api_reference", "Authentication")},
    ]
    mocked_response = (
        "To configure the database, set DATABASE_URL in your .env file. "
        "[setup_guide > Database Configuration]"
    )

    with patch("copilot.get_completion", return_value=mocked_response):
        answer = build_answer_with_citations("How do I configure the database?", chunks)

    assert "[" in answer and ">" in answer
    assert "setup_guide" in answer


def test_format_citations_deduplicates_preserving_order():
    chunks = [
        {"text": "a", "metadata": _meta("setup_guide", "Installation")},
        {"text": "b", "metadata": _meta("setup_guide", "Installation")},
        {"text": "c", "metadata": _meta("api_reference", "Authentication")},
    ]

    citations = format_citations(chunks)

    assert citations == ["setup_guide > Installation", "api_reference > Authentication"]
