# RAG Pipeline

Embeds a folder of documents into a persistent FAISS index and answers questions by
retrieving semantically relevant chunks, with score-threshold filtering and an A/B
mode that puts RAG and no-RAG answers side by side.

## What this is

A retrieval-augmented generation pipeline: documents are split into overlapping
chunks, embedded locally with `sentence-transformers`, and stored in a FAISS
`IndexFlatIP` index for cosine-similarity search. At query time the top-k chunks
above a similarity threshold are injected into the LLM prompt with source citations.
If no chunk clears the threshold, the pipeline returns "I don't know" instead of
asking the LLM to guess. The index is built once and persisted to `.index/` —
subsequent runs load it from disk instead of re-embedding everything.

## Setup

```bash
cd p1-03-rag-pipeline
cp .env.example .env
# Edit .env: set LLM_PROVIDER and LLM_API_KEY
pip install -r requirements.txt
# First run downloads the embedding model (~90MB) — cached after that
```

## Run

```bash
# Step 1: Build the index
python src/main.py --index sample_docs/

# Step 2: Ask a question
python src/main.py --query "How does refresh token rotation work?"

# Step 3: Compare RAG vs no-RAG
python src/main.py --ab "What is the recovery point objective for the database?"

# Force a rebuild of the index
python src/main.py --index sample_docs/ --reindex

# Interactive mode (loads the existing index, loops on questions)
python src/main.py
```

Expected output:
```
Indexed 21 chunks from 3 files

Retrieved 3 chunks (scores: 0.81, 0.74, 0.61)

Answer:
Refresh tokens are rotated on every use: each call to /auth/refresh invalidates
the old refresh token and issues a new one [Source: doc1.txt, Chunk 1, Score: 0.81].

⏱  Retrieval: 8ms (top score: 0.81) | Generation: 1840ms
```

## Tests

```bash
pytest tests/ -v
```

Seven tests verify chunk overlap, embedding shape, FAISS search above and below
the score threshold, prompt construction for the no-context case, and the
`FileNotFoundError` raised when no index exists yet. Embedding tests use a real
`sentence-transformers` model (downloaded once, cached after). No LLM calls are
made in the test suite.

## What to try next

- Add PDF support using the loader pattern from p1-01-document-chat
- Swap `EMBEDDING_MODEL` for a larger model (e.g. `all-mpnet-base-v2`) and compare retrieval scores
- Index a few hundred more documents and watch how retrieval latency scales
