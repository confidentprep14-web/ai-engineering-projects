"""Tests for src/indexer.py — FAISS index build/load/search and freshness checks.

These tests exercise real embedding + FAISS logic (sentence-transformers is
fully local, no API key needed). check_freshness_and_reindex's model
argument is only ever passed through to build_with_metadata/embedding calls
internally, so a real lightweight model is used directly rather than mocked
where practical; spec test 2 explicitly says "model mocked" so we follow
that for the freshness test specifically.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from chunker import ChunkMetadata, markdown_chunk_by_section  # noqa: E402
from indexer import (  # noqa: E402
    build_with_metadata,
    check_freshness_and_reindex,
    load_index,
    save_index,
    search_with_metadata,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "docs"


@pytest.fixture
def real_model():
    """Load the real, small sentence-transformers model once per test."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("all-MiniLM-L6-v2")


def _meta(doc_title: str, section_heading: str, source_file: str) -> ChunkMetadata:
    return ChunkMetadata(
        doc_title=doc_title,
        section_heading=section_heading,
        last_modified=1700000000.0,
        source_file=source_file,
        chunk_index=0,
        char_count=10,
    )


def test_check_freshness_and_reindex_detects_changed_file(tmp_path, capsys):
    """Spec test 2: a stale stored mtime for setup_guide.md should trigger
    re-index (True) and print "Stale index detected"."""
    index_dir = tmp_path / ".index"
    index_dir.mkdir()
    docs_dir = FIXTURES_DIR

    setup_guide_path = str((docs_dir / "setup_guide.md").resolve())
    fake_old_mtime = 1.0  # far older than the real fixture file's mtime
    (index_dir / "file_mtimes.json").write_text(json.dumps({setup_guide_path: fake_old_mtime}))

    mock_model = MagicMock()
    mock_model.encode.return_value = np.zeros((1, 384), dtype=np.float32)

    was_reindexed = check_freshness_and_reindex(str(index_dir), str(docs_dir), mock_model)

    captured = capsys.readouterr()
    assert was_reindexed is True
    assert "Stale index detected" in captured.out


def test_check_freshness_and_reindex_returns_false_when_current(tmp_path):
    """When stored mtimes already match every file on disk, no re-index happens."""
    index_dir = tmp_path / ".index"
    index_dir.mkdir()
    docs_dir = FIXTURES_DIR

    current_mtimes = {
        str((docs_dir / f.name).resolve()): f.stat().st_mtime for f in docs_dir.glob("*.md")
    }
    (index_dir / "file_mtimes.json").write_text(json.dumps(current_mtimes))

    mock_model = MagicMock()

    was_reindexed = check_freshness_and_reindex(str(index_dir), str(docs_dir), mock_model)

    assert was_reindexed is False
    mock_model.encode.assert_not_called()


def test_search_with_metadata_returns_results_above_threshold(real_model):
    """Spec test 6: build a small in-memory index from 2 chunks; search for
    a query semantically matching chunk 1; assert top result has
    score > 0.0 and a metadata key with section_heading."""
    chunks = [
        {
            "text": "To configure the database, set DATABASE_URL in your .env file.",
            "metadata": _meta("setup_guide", "Database Configuration", "/fixtures/setup_guide.md"),
        },
        {
            "text": "All API calls require a Bearer token in the Authorization header.",
            "metadata": _meta("api_reference", "Authentication", "/fixtures/api_reference.md"),
        },
    ]

    index, _embeddings, chunks = build_with_metadata(chunks, real_model)

    results = search_with_metadata("How do I set up the database connection?", real_model, index, chunks, top_k=2)

    assert len(results) > 0
    top_result = results[0]
    assert top_result["score"] > 0.0
    assert "metadata" in top_result
    assert top_result["metadata"].section_heading == "Database Configuration"


def test_save_and_load_index_round_trip(tmp_path, real_model):
    chunks = [
        {
            "text": "Reset your password from the Settings page.",
            "metadata": _meta("setup_guide", "Account Settings", "/fixtures/setup_guide.md"),
        }
    ]
    index, _embeddings, chunks = build_with_metadata(chunks, real_model)
    index_dir = str(tmp_path / ".index")
    file_mtimes = {"/fixtures/setup_guide.md": 1700000000.0}

    save_index(index, chunks, file_mtimes, index_dir)
    loaded_index, loaded_chunks, loaded_mtimes = load_index(index_dir)

    assert loaded_index.ntotal == 1
    assert loaded_chunks[0]["metadata"].section_heading == "Account Settings"
    assert loaded_mtimes == file_mtimes


def test_load_index_missing_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_index(str(tmp_path / "nonexistent"))
