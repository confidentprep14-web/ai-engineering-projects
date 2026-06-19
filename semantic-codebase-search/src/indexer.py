"""FAISS index build/save/load/search and incremental file-hash tracking."""

import json
import os

import faiss
import numpy as np

from chunker import file_hash


def build_index(chunks: list[dict], embeddings) -> faiss.Index:
    """Build a cosine-similarity FAISS index (IndexFlatIP over L2-normalized vectors)."""
    embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)
    faiss.normalize_L2(embeddings)

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    return index


def save_index(index: faiss.Index, chunks: list[dict], file_hashes: dict, index_dir: str) -> None:
    """Persist the FAISS index, chunk metadata, and file hashes to index_dir."""
    os.makedirs(index_dir, exist_ok=True)

    faiss.write_index(index, os.path.join(index_dir, "index.faiss"))

    with open(os.path.join(index_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2)

    with open(os.path.join(index_dir, "file_hashes.json"), "w", encoding="utf-8") as f:
        json.dump(file_hashes, f, indent=2)


def load_index(index_dir: str) -> tuple[faiss.Index, list[dict], dict]:
    """Load the FAISS index, chunk metadata, and file hashes from index_dir.

    Raises FileNotFoundError("Run --index first") if any expected file is
    missing.
    """
    index_path = os.path.join(index_dir, "index.faiss")
    metadata_path = os.path.join(index_dir, "metadata.json")
    hashes_path = os.path.join(index_dir, "file_hashes.json")

    if not (os.path.exists(index_path) and os.path.exists(metadata_path) and os.path.exists(hashes_path)):
        raise FileNotFoundError("Run --index first")

    index = faiss.read_index(index_path)

    with open(metadata_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    try:
        with open(hashes_path, "r", encoding="utf-8") as f:
            file_hashes = json.load(f)
    except json.JSONDecodeError:
        print(f"Warning: {hashes_path} is corrupted; treating as no hashes.")
        file_hashes = {}

    return index, chunks, file_hashes


def search(query: str, model, index: faiss.Index, chunks: list[dict], top_k: int = 5) -> list[dict]:
    """Embed query, search the FAISS index, and map hits back to chunk metadata.

    Returns results sorted by score descending, each
    {"file", "function_name", "lineno", "score", "text"}.
    """
    query_embedding = model.encode([query])
    query_embedding = np.ascontiguousarray(query_embedding, dtype=np.float32)
    faiss.normalize_L2(query_embedding)

    k = min(top_k, len(chunks)) if chunks else 0
    if k == 0:
        return []

    scores, indices = index.search(query_embedding, k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(chunks):
            continue
        chunk = chunks[idx]
        results.append(
            {
                "file": chunk["file"],
                "function_name": chunk["function_name"],
                "lineno": chunk["lineno"],
                "score": float(score),
                "text": chunk["text"],
            }
        )

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def get_changed_files(directory: str, file_hashes: dict) -> tuple[list[str], list[str]]:
    """Walk directory and split files into changed (or new) vs. unchanged.

    Compares each file's current MD5 to the stored hash in file_hashes.
    New files (no stored hash) count as changed.
    """
    changed_files = []
    unchanged_files = []

    for root, _dirs, files in os.walk(directory):
        for name in files:
            filepath = os.path.join(root, name)
            try:
                current_hash = file_hash(filepath)
            except (FileNotFoundError, OSError):
                continue

            stored_hash = file_hashes.get(filepath)
            if stored_hash == current_hash:
                unchanged_files.append(filepath)
            else:
                changed_files.append(filepath)

    return changed_files, unchanged_files
