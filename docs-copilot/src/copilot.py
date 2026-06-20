"""Answer generation with mandatory section-level citations.

handle_below_threshold runs BEFORE any LLM call: if the top retrieval score
is below the configured confidence threshold, we return an "I don't know"
message and skip the LLM entirely. This avoids hallucinating an answer to a
question the docs don't actually cover, and it saves a paid API call.
"""

from chunker import ChunkMetadata
from llm import get_completion

SYSTEM_PROMPT = (
    "You are a helpful documentation assistant. Answer the question using "
    "ONLY the provided context. After each statement cite the source using "
    "format [source_name > section]. If the context doesn't contain the "
    "answer, say 'I don't know.'"
)


def _citation_label(meta: ChunkMetadata) -> str:
    return f"{meta.doc_title} > {meta.section_heading}"


def build_answer_with_citations(query: str, retrieved_chunks: list[dict]) -> str:
    """Call the LLM with retrieved context and return an answer that cites sources.

    Builds a context block of "[Source: doc_title > section_heading]\\ntext"
    per chunk, then ensures every cited doc_title's bracketed citation is
    present in [doc_title > section_heading] format in the final answer.
    """
    context_parts = []
    for chunk in retrieved_chunks:
        meta: ChunkMetadata = chunk["metadata"]
        context_parts.append(f"[Source: {_citation_label(meta)}]\n{chunk['text']}")
    context = "\n\n".join(context_parts)

    user_prompt = f"Context:\n{context}\n\nQuestion: {query}"

    answer = get_completion(user_prompt, system=SYSTEM_PROMPT)

    # Post-process: if the model didn't cite in the exact bracket format,
    # append the available citations so the answer is never uncited.
    has_bracket_citation = "[" in answer and ">" in answer and "]" in answer
    if not has_bracket_citation and retrieved_chunks:
        citations = format_citations(retrieved_chunks)
        citation_suffix = " ".join(f"[{c}]" for c in citations)
        answer = f"{answer.strip()} {citation_suffix}"

    return answer


def handle_below_threshold(query: str, top_score: float, threshold: float) -> str | None:
    """Return an "I don't know" message if top_score is below threshold.

    Returns None when retrieval confidence is acceptable, signalling the
    caller to proceed to the LLM call.
    """
    if top_score < threshold:
        return f"I don't have enough information to answer '{query}'. The documentation may not cover this topic."
    return None


def format_citations(chunks: list[dict]) -> list[str]:
    """Return deduplicated "{doc_title} > {section_heading}" strings, order preserved."""
    seen: set[str] = set()
    citations: list[str] = []
    for chunk in chunks:
        meta: ChunkMetadata = chunk["metadata"]
        label = _citation_label(meta)
        if label not in seen:
            seen.add(label)
            citations.append(label)
    return citations
