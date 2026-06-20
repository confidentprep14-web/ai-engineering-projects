"""Tests for src/chunker.py — markdown section chunking and metadata attachment.

These tests exercise real chunking logic against real fixture files on disk.
No mocking is needed: markdown_chunk_by_section is pure file/string logic
with no LLM or network calls.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from chunker import markdown_chunk_by_section  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "docs"


def test_markdown_chunk_by_section_attaches_metadata_to_every_chunk():
    """Spec test 1: setup_guide.md has 3 headings -> 3+ chunks, every chunk's
    metadata has non-empty doc_title, section_heading, and a positive
    last_modified float."""
    chunks = markdown_chunk_by_section(str(FIXTURES_DIR / "setup_guide.md"))

    assert len(chunks) >= 3
    for _text, meta in chunks:
        assert meta.doc_title
        assert meta.section_heading
        assert isinstance(meta.last_modified, float)
        assert meta.last_modified > 0


def test_markdown_chunk_by_section_no_headings_returns_one_chunk(tmp_path):
    """Spec test 5: a markdown file with 3 paragraphs and no headings
    produces exactly 1 chunk, and section_heading falls back to doc_title."""
    no_headings_file = tmp_path / "no_headings.md"
    no_headings_file.write_text(
        "This is the first paragraph with some general information.\n\n"
        "This is the second paragraph that continues the discussion.\n\n"
        "This is the third paragraph that wraps up the document.\n"
    )

    chunks = markdown_chunk_by_section(str(no_headings_file))

    assert len(chunks) == 1
    text, meta = chunks[0]
    assert meta.section_heading == meta.doc_title == "no_headings"
    assert "first paragraph" in text
