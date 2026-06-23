# Document Chat

A CLI tool that loads a PDF or text file and answers questions about it,
with streaming output and exact source citations for every answer.

> Part of [Path 1 — AI Engineering Fundamentals](https://confidentprep.com/paths/path-1) on Confident Prep — see the full curriculum and how this project fits in.

## Setup

```bash
cd p1-01-document-chat
cp .env.example .env
# Edit .env: set LLM_PROVIDER and LLM_API_KEY
# To run free with no API key: set LLM_PROVIDER=ollama and install Ollama
pip install -r requirements.txt
```

## Run

```bash
# Single question
python src/main.py sample_docs/test.txt --question "What is the main topic?"

# Interactive mode
python src/main.py my_document.pdf
```

Expected output:
```
Loaded 12 pages from my_document.pdf
Created 47 chunks (size=1000, overlap=200)

Ask a question (or 'quit'):
> What does section 3 say about authentication?

Answer:
Section 3 describes token-based authentication using JWTs [Chunk 14, chars 13800–14799].
Tokens expire after 24 hours and must be refreshed via the /auth/refresh endpoint [Chunk 15, chars 14600–15599].

⏱  First token: 312ms | Total: 1840ms
```

## Tests

```bash
pytest tests/ -v
```

Tests verify chunking overlap, chunk count, error handling, and keyword retrieval.
No API key required to run tests.

## What to try next

- Replace keyword retrieval with embeddings (see p1-03-rag-pipeline)
- Add a `--top-k` flag to control how many chunks are retrieved
- Try different chunk sizes and see how answer quality changes
