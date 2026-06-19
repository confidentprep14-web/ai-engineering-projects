"""Supporting (non-spec-mandated) coverage for embedder.py.

The spec's 6 authoritative test cases live in test_chunker.py (4) and
test_indexer.py (2). This file adds a couple of extra checks for the
embedder module itself, which the spec's test list does not separately
enumerate but which embed_functions's documented edge cases call for.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
import pytest

from chunker import ast_chunk_python
from embedder import embed_functions, load_model

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_MODULE = str(FIXTURES_DIR / "sample_module.py")


@pytest.fixture(scope="module")
def embedding_model():
    return load_model("all-MiniLM-L6-v2")


def test_embed_functions_returns_correct_shape(embedding_model):
    chunks = ast_chunk_python(SAMPLE_MODULE)

    embedded_chunks, embeddings = embed_functions(chunks, embedding_model)

    assert embedded_chunks == chunks
    assert embeddings.shape == (len(chunks), 384)
    assert embeddings.dtype == np.float32


def test_embed_functions_handles_empty_chunks(embedding_model):
    embedded_chunks, embeddings = embed_functions([], embedding_model)

    assert embedded_chunks == []
    assert embeddings is None
