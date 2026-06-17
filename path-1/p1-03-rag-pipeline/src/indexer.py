import json
import os

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from embedder import embed_texts

INDEX_FILE_NAME = "index.faiss"
METADATA_FILE_NAME = "metadata.json"


def chunk_text(text: str, source: str, chunk_size: int, overlap: int) -> list[dict]:
    if overlap >= chunk_size:
        raise ValueError(f"overlap ({overlap}) must be less than chunk_size ({chunk_size})")

    step = chunk_size - overlap
    chunks = []
    char_start = 0
    chunk_index = 0
    while char_start < len(text):
        char_end = min(char_start + chunk_size, len(text))
        chunks.append({"text": text[char_start:char_end], "source": source, "chunk_index": chunk_index})
        if char_end == len(text):
            break
        char_start += step
        chunk_index += 1
    return chunks


def build_index(
    doc_dir: str, index_dir: str, model: SentenceTransformer, chunk_size: int = 800, overlap: int = 150
) -> tuple[faiss.Index, list[dict]]:
    document_paths = [
        os.path.join(doc_dir, file_name)
        for file_name in sorted(os.listdir(doc_dir))
        if file_name.endswith((".txt", ".md"))
    ]
    if not document_paths:
        raise ValueError(f"No .txt or .md files found in {doc_dir}")

    chunk_metadata = []
    for document_path in document_paths:
        with open(document_path, "r", encoding="utf-8") as document_file:
            document_text = document_file.read()
        chunk_metadata.extend(chunk_text(document_text, os.path.basename(document_path), chunk_size, overlap))

    chunk_embeddings = embed_texts([chunk["text"] for chunk in chunk_metadata], model)
    faiss.normalize_L2(chunk_embeddings)

    chunk_index = faiss.IndexFlatIP(chunk_embeddings.shape[1])
    chunk_index.add(chunk_embeddings)

    os.makedirs(index_dir, exist_ok=True)
    faiss.write_index(chunk_index, os.path.join(index_dir, INDEX_FILE_NAME))
    with open(os.path.join(index_dir, METADATA_FILE_NAME), "w", encoding="utf-8") as metadata_file:
        json.dump(chunk_metadata, metadata_file)

    print(f"Indexed {len(chunk_metadata)} chunks from {len(document_paths)} files")
    return chunk_index, chunk_metadata


def load_index(index_dir: str) -> tuple[faiss.Index, list[dict]]:
    index_path = os.path.join(index_dir, INDEX_FILE_NAME)
    metadata_path = os.path.join(index_dir, METADATA_FILE_NAME)
    if not os.path.isfile(index_path) or not os.path.isfile(metadata_path):
        raise FileNotFoundError(f"No index found at {index_dir} — run with --index first")

    chunk_index = faiss.read_index(index_path)
    with open(metadata_path, "r", encoding="utf-8") as metadata_file:
        chunk_metadata = json.load(metadata_file)
    return chunk_index, chunk_metadata


def search(
    query_embedding: np.ndarray,
    index: faiss.Index,
    metadata: list[dict],
    top_k: int,
    score_threshold: float,
) -> list[dict]:
    normalized_query = query_embedding.copy().astype(np.float32)
    faiss.normalize_L2(normalized_query)

    similarity_scores, chunk_positions = index.search(normalized_query, top_k)

    retrieved_chunks = []
    for score, position in zip(similarity_scores[0], chunk_positions[0]):
        if position == -1 or score < score_threshold:
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
