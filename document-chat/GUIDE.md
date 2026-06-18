# Build guide: Document Chat

## What you're building and why it matters

LLMs have a fixed context window — the total amount of text they can process in one call.
GPT-4o has 128k tokens; Claude 3 Haiku has 200k. Sounds large, but a 200-page PDF is
roughly 150k tokens. Even if it fits today, you pay for every token on every question.
Chunking — splitting the document and retrieving only the relevant pieces — solves both
the size problem and the cost problem. This is the foundation under every production
document AI system, including enterprise search, legal document review, and coding copilots.

## The decision that matters in this build

**Overlap size.** Naive chunking splits the document at exact character boundaries.
A sentence that straddles a boundary gets split, and the answer to a question that
depends on that sentence will be wrong. Overlap makes sure both adjacent chunks
contain the boundary sentence. Too little overlap and you miss cross-boundary answers.
Too much and retrieval returns near-duplicate content. Start with 20% of chunk_size
(so 200 chars for 1000-char chunks) and adjust by looking at whether answers miss
context that was "right there" in the document.

## What will break

**Keyword retrieval is too naive for similar words.** If the document says "authentication"
and the question asks about "login", the score will be zero even though they mean the same
thing. This is the exact problem embeddings solve in p1-03. Feel this limitation here — it
will make the RAG upgrade meaningful.

**Long PDF pages produce one giant chunk.** Some PDFs have 5000-character pages.
Your chunker will split them correctly, but the character positions in citations will be
relative to the concatenated document, not the original page. Track this and make sure
your citation output makes sense to someone reading the original document.

**Streaming + `print(end="")` buffering.** On some terminals, output appears in batches
instead of token by token. Add `flush=True` to every streaming print call.

## How to talk about this in an interview

"I built a document Q&A system that chunks PDFs with configurable overlap to handle
documents larger than the LLM context window. I measured time-to-first-token on every
call and found that chunk retrieval added under 5ms of latency — the LLM generation
was always the bottleneck. I also learned that keyword retrieval breaks down for
paraphrase queries, which led me directly to building a vector retrieval system next."
