"""Metadata-aware chunking for Markdown and PDF documentation.

The key difference from basic RAG chunking: every chunk keeps the section
heading it came from, plus the source file's last-modified time, so answers
can cite "[doc_title > section_heading]" and the index can detect staleness.
"""

import os
import re
from dataclasses import dataclass

MAX_CHUNK_CHARS = int(os.environ.get("MAX_CHUNK_CHARS", "2000"))

_HEADING_RE = re.compile(r"^#{1,3}\s+(.*)$")
_ALL_CAPS_HEADING_RE = re.compile(r"^[A-Z0-9][A-Z0-9 \-_/]{2,59}$")


@dataclass
class ChunkMetadata:
    doc_title: str  # Filename without extension
    section_heading: str  # Nearest heading above this chunk
    last_modified: float  # os.path.getmtime() value
    source_file: str  # Absolute file path
    chunk_index: int  # Position within document
    char_count: int  # Length of chunk text


def _doc_title(filepath: str) -> str:
    base = os.path.basename(filepath)
    return os.path.splitext(base)[0]


def _split_oversized(text: str, max_chars: int) -> list[str]:
    """Split text into paragraph-bounded pieces no longer than max_chars."""
    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split("\n\n")
    pieces: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) > max_chars and current:
            pieces.append(current.strip())
            current = paragraph
        else:
            current = candidate
    if current.strip():
        pieces.append(current.strip())
    return pieces or [text]


def markdown_chunk_by_section(filepath: str) -> list[tuple[str, ChunkMetadata]]:
    """Split a Markdown file into one chunk per H1/H2/H3 section.

    A file with no headings produces a single chunk whose section_heading
    equals the document title (filename without extension).
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.splitlines()

    doc_title = _doc_title(filepath)
    last_modified = os.path.getmtime(filepath)
    abs_path = os.path.abspath(filepath)

    sections: list[tuple[str, list[str]]] = []
    current_heading = doc_title
    current_lines: list[str] = []
    seen_heading = False

    for line in lines:
        match = _HEADING_RE.match(line)
        if match:
            if current_lines or seen_heading:
                sections.append((current_heading, current_lines))
            current_heading = match.group(1).strip()
            current_lines = []
            seen_heading = True
        else:
            current_lines.append(line)

    if current_lines or not sections:
        sections.append((current_heading, current_lines))

    chunks: list[tuple[str, ChunkMetadata]] = []
    chunk_index = 0
    for heading, body_lines in sections:
        text = "\n".join(body_lines).strip()
        if not text:
            continue
        for piece in _split_oversized(text, MAX_CHUNK_CHARS):
            meta = ChunkMetadata(
                doc_title=doc_title,
                section_heading=heading,
                last_modified=last_modified,
                source_file=abs_path,
                chunk_index=chunk_index,
                char_count=len(piece),
            )
            chunks.append((piece, meta))
            chunk_index += 1

    return chunks


def _detect_pdf_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if len(stripped) < 60 and stripped.isupper():
        return True
    return bool(_ALL_CAPS_HEADING_RE.match(stripped))


def pdf_chunk_with_heading_detection(filepath: str) -> list[tuple[str, ChunkMetadata]]:
    """Extract text from a PDF and group it under heuristically detected headings.

    Headings are detected as ALL CAPS lines, or short lines (<60 chars)
    followed by a blank line. Falls back to "Page N" when no heading is
    found for a page. Returns [] for PDFs with no extractable text or that
    are encrypted.
    """
    import pdfplumber

    doc_title = _doc_title(filepath)
    last_modified = os.path.getmtime(filepath)
    abs_path = os.path.abspath(filepath)

    try:
        pdf = pdfplumber.open(filepath)
    except Exception as exc:
        print(f"Warning: could not open PDF {filepath}: {exc}")
        return []

    chunks: list[tuple[str, ChunkMetadata]] = []
    chunk_index = 0

    try:
        if getattr(pdf, "is_encrypted", False):
            print(f"Warning: {filepath} is encrypted; skipping.")
            return []

        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if not text.strip():
                continue

            lines = text.splitlines()
            current_heading = f"Page {page_num}"
            current_lines: list[str] = []
            sections: list[tuple[str, list[str]]] = []

            for i, line in enumerate(lines):
                next_blank = i + 1 < len(lines) and not lines[i + 1].strip()
                if _detect_pdf_heading(line) and (line.strip().isupper() or next_blank):
                    if current_lines:
                        sections.append((current_heading, current_lines))
                    current_heading = line.strip()
                    current_lines = []
                else:
                    current_lines.append(line)
            if current_lines:
                sections.append((current_heading, current_lines))

            for heading, body_lines in sections:
                body_text = "\n".join(body_lines).strip()
                if not body_text:
                    continue
                for piece in _split_oversized(body_text, MAX_CHUNK_CHARS):
                    meta = ChunkMetadata(
                        doc_title=doc_title,
                        section_heading=heading,
                        last_modified=last_modified,
                        source_file=abs_path,
                        chunk_index=chunk_index,
                        char_count=len(piece),
                    )
                    chunks.append((piece, meta))
                    chunk_index += 1
    finally:
        pdf.close()

    if not chunks:
        print(f"Warning: no extractable text found in {filepath}")
    return chunks


def attach_metadata(text: str, meta: ChunkMetadata) -> dict:
    """Wrap chunk text and metadata into the standard chunk dict shape."""
    return {"text": text, "metadata": meta}
