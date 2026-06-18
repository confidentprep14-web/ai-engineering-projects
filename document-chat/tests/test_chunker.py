import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from chunker import chunk_document, retrieve_top_chunks
from loader import load_document


def _make_pages(text: str, source: str = "test.txt") -> list[dict]:
    return [{"page": 1, "text": text, "source": source}]


def test_overlap_produces_shared_text():
    text = "a" * 3000
    chunks = chunk_document(_make_pages(text), chunk_size=1000, overlap=200)

    assert chunks[0]["text"][-200:] == chunks[1]["text"][:200]


def test_chunk_count_is_correct():
    text = "b" * 2500
    chunks = chunk_document(_make_pages(text), chunk_size=1000, overlap=200)

    assert len(chunks) == 3
    assert (chunks[0]["char_start"], chunks[0]["char_end"]) == (0, 1000)
    assert (chunks[1]["char_start"], chunks[1]["char_end"]) == (800, 1800)
    assert (chunks[2]["char_start"], chunks[2]["char_end"]) == (1600, 2500)


def test_overlap_exceeding_chunk_size_raises():
    with pytest.raises(ValueError):
        chunk_document(_make_pages("some text"), chunk_size=500, overlap=500)


def test_keyword_retrieval_returns_best_match():
    chunks = [
        {"chunk_index": i, "text": "irrelevant filler text", "source": "t", "char_start": 0, "char_end": 0}
        for i in range(5)
    ]
    chunks[2]["text"] = "neural network " * 3

    retrieved = retrieve_top_chunks("neural network", chunks, top_k=2)

    assert retrieved[0]["chunk_index"] == 2


def test_txt_loader_returns_page_dict():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp_file:
        tmp_file.write("hello world")
        tmp_path = tmp_file.name

    result = load_document(tmp_path)

    assert isinstance(result, list)
    assert set(result[0].keys()) >= {"page", "text", "source"}
