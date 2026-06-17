def chunk_document(pages: list[dict], chunk_size: int, overlap: int) -> list[dict]:
    if overlap >= chunk_size:
        raise ValueError(f"overlap ({overlap}) must be less than chunk_size ({chunk_size})")

    source = pages[0]["source"] if pages else ""
    full_text = "".join(page["text"] for page in pages)

    step = chunk_size - overlap
    chunks = []
    char_start = 0
    chunk_index = 0
    while char_start < len(full_text):
        char_end = min(char_start + chunk_size, len(full_text))
        chunks.append(
            {
                "chunk_index": chunk_index,
                "text": full_text[char_start:char_end],
                "source": source,
                "char_start": char_start,
                "char_end": char_end,
            }
        )
        if char_end == len(full_text):
            break
        char_start += step
        chunk_index += 1
    return chunks


def retrieve_top_chunks(query: str, chunks: list[dict], top_k: int) -> list[dict]:
    query_words = query.lower().split()

    scored_chunks = []
    for chunk in chunks:
        chunk_text_lower = chunk["text"].lower()
        score = sum(chunk_text_lower.count(word) for word in query_words)
        scored_chunks.append((score, chunk))

    if all(score == 0 for score, _ in scored_chunks):
        return chunks[:top_k]

    scored_chunks.sort(key=lambda pair: pair[0], reverse=True)
    return [chunk for _, chunk in scored_chunks[:top_k]]
