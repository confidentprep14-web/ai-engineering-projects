import os
import time

import faiss
from sentence_transformers import SentenceTransformer

from embedder import embed_query
from indexer import search
from llm import get_completion

RAG_SYSTEM_PROMPT = (
    "You are a precise assistant that answers questions using only the supplied context. "
    "Cite the source of every claim using the [Source: ..., Chunk N, Score: ...] tags given "
    'to you. If the context is insufficient to answer, say "Not found in documents."'
)

NO_CONTEXT_PROMPT_TEMPLATE = (
    "There is no relevant context available for this question — none of the indexed "
    "documents scored above the similarity threshold.\n\n"
    "Question: {query}\n\n"
    'Respond with exactly: "I don\'t know — no relevant context was found in the documents."'
)


def build_rag_prompt(query: str, retrieved_chunks: list[dict]) -> str:
    if not retrieved_chunks:
        return NO_CONTEXT_PROMPT_TEMPLATE.format(query=query)

    context_blocks = [
        f"[Source: {chunk['source']}, Chunk {chunk['chunk_index']}, Score: {chunk['score']:.2f}]\n{chunk['text']}\n"
        for chunk in retrieved_chunks
    ]
    context = "\n".join(context_blocks)
    return (
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Answer using only the context above. Cite sources inline as "
        "[Source: filename, Chunk N, Score: X.XX]."
    )


def answer_with_rag(query: str, index: faiss.Index, metadata: list[dict], model: SentenceTransformer) -> dict:
    retrieval_start = time.perf_counter()
    query_embedding = embed_query(query, model)
    top_k = int(os.environ.get("TOP_K", 3))
    score_threshold = float(os.environ.get("SCORE_THRESHOLD", 0.3))
    retrieved_chunks = search(query_embedding, index, metadata, top_k, score_threshold)
    retrieval_ms = (time.perf_counter() - retrieval_start) * 1000

    prompt = build_rag_prompt(query, retrieved_chunks)

    generation_start = time.perf_counter()
    answer_text = get_completion(prompt, system=RAG_SYSTEM_PROMPT)
    generation_ms = (time.perf_counter() - generation_start) * 1000

    return {
        "answer": answer_text,
        "sources": retrieved_chunks,
        "retrieval_ms": retrieval_ms,
        "generation_ms": generation_ms,
        "chunks_retrieved": len(retrieved_chunks),
    }


def answer_without_rag(query: str) -> dict:
    generation_start = time.perf_counter()
    answer_text = get_completion(query)
    generation_ms = (time.perf_counter() - generation_start) * 1000
    return {"answer": answer_text, "generation_ms": generation_ms}
