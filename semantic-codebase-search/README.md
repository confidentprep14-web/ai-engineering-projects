# Semantic Codebase Search

Function-level semantic search over your codebase using local embeddings and FAISS.

> Part of [Path 2 — AI-Augmented Engineering](https://confidentprep.com/paths/path-2) on Confident Prep — see the full curriculum and how this project fits in.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Index your codebase
python src/main.py --index ./src

# Search semantically
python src/main.py --search "authentication middleware"

# Compare models on same query
python src/main.py --compare "error handling retry logic"
```

## How it works

1. **AST chunking** — Python files are chunked at function boundaries; other files in 30-line blocks
2. **Embedding** — Each chunk's signature + docstring is embedded with sentence-transformers
3. **FAISS** — Inner-product index with L2-normalized vectors (equivalent to cosine similarity)
4. **Incremental** — File hashes detect changes; only re-embed modified files

## Index structure

```
.index/
├── index.faiss       # FAISS binary index
├── metadata.json     # Chunk metadata (file, function, lineno)
└── file_hashes.json  # Per-file MD5 for incremental updates
```

## Commands

| Command | Description |
|---|---|
| `--index <dir>` | Index a directory (incremental by default) |
| `--reindex` | Force full re-index |
| `--search "..."` | Semantic search |
| `--compare "..."` | Compare two embedding models |
| `--top-k N` | Number of results (default: 5) |

## Running tests

```bash
pytest tests/ -v
```
