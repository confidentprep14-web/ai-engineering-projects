"""FAISS index build/save/load/search plus mtime-based freshness tracking.

Freshness uses file mtimes, not content hashes — mtime is cheap to read and
sufficient to detect that a doc changed since the last index run. On any
mismatch we re-chunk and re-embed that file's content and rebuild the whole
index (simplest correct approach for a docs-sized corpus).
"""

import json
import os

import faiss
import numpy as np

from chunker import ChunkMetadata, markdown_chunk_by_section, pdf_chunk_with_heading_detection

INDEX_FILE_NAME = "index.faiss"
METADATA_FILE_NAME = "metadata.json"
MTIMES_FILE_NAME = "file_mtimes.json"


def _embed(texts: list[str], model) -> np.ndarray:
    embeddings = model.encode(texts, convert_to_numpy=True)
    return np.asarray(embeddings, dtype=np.float32)


def build_with_metadata(chunks: list[dict], model) -> tuple:
    """Embed every chunk's text, normalize, and build an IndexFlatIP.

    Returns (faiss_index, embeddings, chunks) — chunks is passed through
    unchanged so callers can zip it with search results by position.
    """
    texts = [chunk["text"] for chunk in chunks]
    embeddings = _embed(texts, model)
    faiss.normalize_L2(embeddings)

    index = faiss.IndexFlatIP(embeddings.shape[1])
    if len(chunks) > 0:
        index.add(embeddings)

    return index, embeddings, chunks


def _metadata_to_dict(meta: ChunkMetadata) -> dict:
    return {
        "doc_title": meta.doc_title,
        "section_heading": meta.section_heading,
        "last_modified": meta.last_modified,
        "source_file": meta.source_file,
        "chunk_index": meta.chunk_index,
        "char_count": meta.char_count,
    }


def _dict_to_metadata(d: dict) -> ChunkMetadata:
    return ChunkMetadata(
        doc_title=d["doc_title"],
        section_heading=d["section_heading"],
        last_modified=d["last_modified"],
        source_file=d["source_file"],
        chunk_index=d["chunk_index"],
        char_count=d["char_count"],
    )


def save_index(index, chunks: list[dict], file_mtimes: dict, index_dir: str) -> None:
    """Write index.faiss, metadata.json (chunks without the FAISS array), and file_mtimes.json."""
    os.makedirs(index_dir, exist_ok=True)

    faiss.write_index(index, os.path.join(index_dir, INDEX_FILE_NAME))

    serializable_chunks = [
        {"text": chunk["text"], "metadata": _metadata_to_dict(chunk["metadata"])} for chunk in chunks
    ]
    with open(os.path.join(index_dir, METADATA_FILE_NAME), "w", encoding="utf-8") as f:
        json.dump(serializable_chunks, f)

    with open(os.path.join(index_dir, MTIMES_FILE_NAME), "w", encoding="utf-8") as f:
        json.dump(file_mtimes, f)


def load_index(index_dir: str) -> tuple:
    """Load (index, chunks, file_mtimes) from index_dir.

    Raises FileNotFoundError if any of the three expected files is missing.
    """
    index_path = os.path.join(index_dir, INDEX_FILE_NAME)
    metadata_path = os.path.join(index_dir, METADATA_FILE_NAME)
    mtimes_path = os.path.join(index_dir, MTIMES_FILE_NAME)

    if not all(os.path.isfile(p) for p in (index_path, metadata_path, mtimes_path)):
        raise FileNotFoundError("Run --index first")

    index = faiss.read_index(index_path)
    with open(metadata_path, "r", encoding="utf-8") as f:
        raw_chunks = json.load(f)
    chunks = [{"text": c["text"], "metadata": _dict_to_metadata(c["metadata"])} for c in raw_chunks]
    with open(mtimes_path, "r", encoding="utf-8") as f:
        file_mtimes = json.load(f)

    return index, chunks, file_mtimes


def search_with_metadata(query: str, model, index, chunks: list[dict], top_k: int = 5) -> list[dict]:
    """Embed query, search the FAISS index, and return results sorted by score descending."""
    if index.ntotal == 0:
        return []

    query_embedding = _embed([query], model)
    faiss.normalize_L2(query_embedding)

    scores, positions = index.search(query_embedding, min(top_k, index.ntotal))

    results = []
    for score, position in zip(scores[0], positions[0]):
        if position == -1:
            continue
        chunk = chunks[position]
        results.append({"text": chunk["text"], "metadata": chunk["metadata"], "score": float(score)})

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def _chunk_file(filepath: str) -> list[dict]:
    if filepath.endswith(".md"):
        pairs = markdown_chunk_by_section(filepath)
    elif filepath.endswith(".pdf"):
        pairs = pdf_chunk_with_heading_detection(filepath)
    else:
        return []
    return [{"text": text, "metadata": meta} for text, meta in pairs]


def _walk_docs(docs_dir: str) -> list[str]:
    matches = []
    for root, _dirs, files in os.walk(docs_dir):
        for name in sorted(files):
            if name.endswith((".md", ".pdf")):
                matches.append(os.path.abspath(os.path.join(root, name)))
    return sorted(matches)


def check_freshness_and_reindex(index_dir: str, docs_dir: str, model) -> bool:
    """Compare stored mtimes to current file mtimes; rebuild the index if any differ.

    Returns True if a re-index was needed and performed, False if every
    file's mtime already matches what's stored. On first run (no
    file_mtimes.json yet) every file is treated as stale.
    """
    mtimes_path = os.path.join(index_dir, MTIMES_FILE_NAME)
    stored_mtimes: dict = {}
    if os.path.isfile(mtimes_path):
        with open(mtimes_path, "r", encoding="utf-8") as f:
            stored_mtimes = json.load(f)

    current_files = _walk_docs(docs_dir)
    stale_files = []
    for filepath in current_files:
        current_mtime = os.path.getmtime(filepath)
        if stored_mtimes.get(filepath) != current_mtime:
            stale_files.append(filepath)

    if not stale_files:
        return False

    for filepath in stale_files:
        print(f"Stale index detected: {os.path.basename(filepath)} changed. Re-indexing.")

    all_chunks: list[dict] = []
    for filepath in current_files:
        all_chunks.extend(_chunk_file(filepath))

    new_mtimes = {filepath: os.path.getmtime(filepath) for filepath in current_files}

    index, _embeddings, chunks = build_with_metadata(all_chunks, model)
    save_index(index, chunks, new_mtimes, index_dir)

    return True
