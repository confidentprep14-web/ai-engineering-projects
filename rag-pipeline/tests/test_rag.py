import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import faiss
import numpy as np
import pytest

from embedder import embed_query, embed_texts, load_embedding_model
from indexer import chunk_text, load_index, search
from rag import build_rag_prompt


@pytest.fixture(scope="module")
def embedding_model():
    return load_embedding_model()


def _build_faiss_index(texts: list[str], model) -> tuple[faiss.Index, list[dict]]:
    chunk_embeddings = embed_texts(texts, model)
    faiss.normalize_L2(chunk_embeddings)
    flat_index = faiss.IndexFlatIP(chunk_embeddings.shape[1])
    flat_index.add(chunk_embeddings)
    chunk_metadata = [{"text": text, "source": "test.txt", "chunk_index": i} for i, text in enumerate(texts)]
    return flat_index, chunk_metadata


def test_chunk_text_produces_overlap():
    chunks = chunk_text("A" * 2000, "test.txt", chunk_size=500, overlap=100)

    assert chunks[0]["text"][-100:] == chunks[1]["text"][:100]
    assert chunks[1]["text"][-100:] == chunks[2]["text"][:100]


def test_chunk_text_rejects_overlap_not_smaller_than_chunk_size():
    with pytest.raises(ValueError):
        chunk_text("some text", "test.txt", chunk_size=100, overlap=100)


def test_embed_texts_returns_correct_shape(embedding_model):
    embedding_matrix = embed_texts(["alpha", "beta", "gamma"], embedding_model)

    assert embedding_matrix.shape == (3, 384)
    assert embedding_matrix.dtype == np.float32


def test_search_returns_empty_list_below_threshold(embedding_model):
    flat_index, chunk_metadata = _build_faiss_index(
        ["cats are small domestic animals", "rockets launch into orbit"], embedding_model
    )
    query_embedding = embed_query("a completely unrelated query about tax law", embedding_model)

    retrieved_chunks = search(query_embedding, flat_index, chunk_metadata, top_k=2, score_threshold=0.99)

    assert retrieved_chunks == []


def test_search_returns_results_above_threshold(embedding_model):
    flat_index, chunk_metadata = _build_faiss_index(
        ["the cat sat on the mat", "rockets launch into orbit from the launch pad"], embedding_model
    )
    query_embedding = embed_query("the cat sat on the mat", embedding_model)

    retrieved_chunks = search(query_embedding, flat_index, chunk_metadata, top_k=2, score_threshold=0.1)

    assert len(retrieved_chunks) >= 1
    assert retrieved_chunks[0]["score"] >= 0.1
    assert retrieved_chunks[0]["text"] == "the cat sat on the mat"


def test_build_rag_prompt_handles_empty_chunks():
    prompt_text = build_rag_prompt("What is X?", [])

    assert "don't know" in prompt_text.lower() or "no relevant context" in prompt_text.lower()


def test_load_index_raises_file_not_found_when_missing():
    with pytest.raises(FileNotFoundError):
        load_index("/nonexistent/path/for/rag/index")
