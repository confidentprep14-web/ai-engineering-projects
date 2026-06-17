# Build guide: RAG Pipeline

## What you're building and why it matters

RAG is the pattern that made LLMs useful for enterprise applications. Instead of
retraining a model on your data — expensive, slow, and stale the moment new
documents arrive — you embed your documents into a vector store and inject the
relevant pieces into the prompt at query time. Every enterprise search product,
every "chat with your docs" feature, every AI support agent uses this pattern.
The key improvement over keyword search is semantic similarity: a query about
"login problems" retrieves a chunk about "authentication failures" even though
the words don't overlap at all. p1-01's keyword retrieval cannot do this; this
project is the fix.

## The decision that matters in this build

**Score thresholding.** Without a minimum similarity score, FAISS always returns
its top-k nearest vectors, even when none of them are actually relevant — they're
just the least-bad matches in the index. A question about "climate policy" asked
against a corpus of authentication and caching docs will still get three results
back unless something stops it. The threshold is what separates a real RAG system
from a toy: below it, the pipeline says "I don't know" instead of synthesizing a
confident, wrong answer from irrelevant context. Set it too high and you get false
negatives on questions you could have answered; too low and you hallucinate. This
project starts at `SCORE_THRESHOLD=0.3` for cosine similarity with
`all-MiniLM-L6-v2` — tune it by running the same ten questions against your own
corpus and watching where genuinely relevant chunks fall.

## What will break

**Embeddings must be normalized before indexing.** `IndexFlatIP` computes raw
inner products. Without normalizing both the indexed vectors and the query vector
to unit length first, the resulting scores are not cosine similarity and the
threshold logic becomes meaningless — scores can exceed 1.0 or swing based on
vector magnitude instead of direction. Normalize with `faiss.normalize_L2()` on
both sides, every time.

**Chunking cuts mid-sentence.** The answer to a question often spans a sentence
that straddles a chunk boundary. Without overlap, you'll see the retrieved chunk
get "almost" to the answer and stop — the critical clause is sitting in the next
chunk that didn't get retrieved. 150 characters of overlap on 800-character chunks
is enough for most prose; narrower chunks need proportionally more.

**Re-embedding on every run doesn't scale.** Embedding a few sample docs feels
instant, so it's tempting to skip persistence. It stops being instant once the
corpus reaches hundreds of files. The index check in `main.py` is deliberately
simple: if `.index/index.faiss` exists and `--reindex` wasn't passed, load from
disk and skip embedding entirely.

**The FAISS index and the metadata list can drift apart.** `index.search()`
returns integer positions into the index, not document IDs. Those positions are
only meaningful if `metadata[position]` was written in the exact same order the
vectors were added in. Any reordering of one without the other silently returns
the wrong chunk for a given score.

## How to talk about this in an interview

"I built a RAG pipeline that embeds documents locally with sentence-transformers,
indexes them in FAISS using cosine similarity, and retrieves with a tunable score
threshold. The threshold is what separates this from a naive top-k lookup: below
0.3, the system returns 'I don't know' rather than fabricating an answer from
irrelevant chunks. I measured retrieval latency separately from generation latency
on every query — retrieval stayed under 10ms for a few dozen chunks, confirming
that generation, not retrieval, is the bottleneck worth optimizing first."
