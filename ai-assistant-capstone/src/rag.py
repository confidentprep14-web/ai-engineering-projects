"""RAG pipeline: load/create a FAISS index, add documents, retrieve chunks.

Same chunking and retrieval approach as the standalone rag-pipeline project,
adapted for an API that adds one document at a time (instead of building the
whole index up front from a directory) and persists the index to disk after
every add so a warm Lambda invocation can reuse it.

Known limitation (see GUIDE.md): Lambda's /tmp does not survive a cold
start, so the FAISS index must be rebuilt by re-uploading documents after
one. load_or_create_index() handles a missing index by creating an empty one
rather than raising, so /chat with use_rag=true never crashes — it just
returns zero chunks and the caller falls back to retrieval_hit=False.
"""
import json
import os
import uuid

import faiss
import numpy as np
import pdfplumber
from sentence_transformers import SentenceTransformer

INDEX_FILE_NAME = "index.faiss"
METADATA_FILE_NAME = "metadata.json"
CHUNK_SIZE_CHARS = 800
CHUNK_OVERLAP_CHARS = 150
EMBEDDING_DIM_FALLBACK = 384  # all-MiniLM-L6-v2 output dimension


def load_or_create_index(index_path: str) -> tuple[faiss.Index, list[dict]]:
    """Load a persisted FAISS index + metadata, or create an empty one.

    Never raises on a missing/corrupt index — RAG degrades to "no chunks"
    rather than taking down /chat or /documents.
    """
    index_file = os.path.join(index_path, INDEX_FILE_NAME)
    metadata_file = os.path.join(index_path, METADATA_FILE_NAME)

    if os.path.isfile(index_file) and os.path.isfile(metadata_file):
        try:
            index = faiss.read_index(index_file)
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            return index, metadata
        except Exception as load_error:
            print(f"[warning] failed to load index at {index_path}: {load_error} — starting fresh")

    os.makedirs(index_path, exist_ok=True)
    return faiss.IndexFlatIP(EMBEDDING_DIM_FALLBACK), []


def _persist_index(index: faiss.Index, metadata: list[dict], index_path: str) -> None:
    os.makedirs(index_path, exist_ok=True)
    faiss.write_index(index, os.path.join(index_path, INDEX_FILE_NAME))
    with open(os.path.join(index_path, METADATA_FILE_NAME), "w", encoding="utf-8") as f:
        json.dump(metadata, f)


def _extract_text(file_path: str) -> str:
    if file_path.lower().endswith(".pdf"):
        with pdfplumber.open(file_path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def _chunk_text(text: str, source: str) -> list[dict]:
    step = CHUNK_SIZE_CHARS - CHUNK_OVERLAP_CHARS
    chunks = []
    char_start = 0
    chunk_index = 0
    while char_start < len(text):
        char_end = min(char_start + CHUNK_SIZE_CHARS, len(text))
        chunk_text = text[char_start:char_end].strip()
        if chunk_text:
            chunks.append({"text": chunk_text, "source": source, "chunk_index": chunk_index})
            chunk_index += 1
        if char_end == len(text):
            break
        char_start += step
    return chunks


def add_document(
    file_path: str,
    index: faiss.Index,
    metadata: list[dict],
    model: SentenceTransformer,
    index_path: str,
) -> tuple[int, str, faiss.Index]:
    """Chunk, embed, and add one document to the FAISS index. Persists to disk.

    Returns (chunks_added, document_id, index). The index is returned because
    when the placeholder index from an empty load_or_create_index() doesn't
    match the real embedding dimension, this function must rebuild it as a
    *new* faiss.Index object — callers must rebind their reference to this
    return value or they'll keep writing to the discarded placeholder.
    """
    source_name = os.path.basename(file_path)
    document_text = _extract_text(file_path)
    new_chunks = _chunk_text(document_text, source_name)

    if not new_chunks:
        return 0, str(uuid.uuid4()), index

    chunk_embeddings = model.encode([c["text"] for c in new_chunks], convert_to_numpy=True).astype(np.float32)
    faiss.normalize_L2(chunk_embeddings)

    if index.ntotal == 0 and index.d != chunk_embeddings.shape[1]:
        index = faiss.IndexFlatIP(chunk_embeddings.shape[1])

    index.add(chunk_embeddings)
    metadata.extend(new_chunks)
    _persist_index(index, metadata, index_path)

    return len(new_chunks), str(uuid.uuid4()), index


def retrieve(
    query: str,
    index: faiss.Index,
    metadata: list[dict],
    model: SentenceTransformer,
    top_k: int = 3,
    threshold: float = 0.3,
) -> list[dict]:
    """Return up to top_k chunks scoring above threshold for the query."""
    if index.ntotal == 0 or not metadata:
        return []

    query_embedding = model.encode([query], convert_to_numpy=True).astype(np.float32)
    faiss.normalize_L2(query_embedding)

    similarity_scores, chunk_positions = index.search(query_embedding, min(top_k, index.ntotal))

    retrieved_chunks = []
    for score, position in zip(similarity_scores[0], chunk_positions[0]):
        if position == -1 or position >= len(metadata) or score < threshold:
            continue
        chunk_record = metadata[position]
        retrieved_chunks.append(
            {
                "text": chunk_record["text"],
                "source": chunk_record["source"],
                "chunk_index": chunk_record["chunk_index"],
                "score": float(score),
            }
        )
    return retrieved_chunks


def format_rag_context(chunks: list[dict]) -> str:
    """Format retrieved chunks for system prompt injection."""
    if not chunks:
        return ""
    blocks = [
        f"[Source: {chunk['source']}, Chunk {chunk['chunk_index']}, Score: {chunk['score']:.2f}]\n{chunk['text']}"
        for chunk in chunks
    ]
    return "Relevant context from uploaded documents:\n\n" + "\n\n".join(blocks)
