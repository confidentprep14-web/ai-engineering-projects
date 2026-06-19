# Build Guide — Semantic Codebase Search

## Step 1 — AST chunking

Use Python's `ast` module to walk function definitions:

```python
import ast

tree = ast.parse(source)
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        # node.name, node.lineno, node.end_lineno
        docstring = ast.get_docstring(node) or ""
        first_line = source_lines[node.lineno - 1]
        text = f"{first_line}\n{docstring}"
```

The key insight: embed the **signature + docstring**, not the full body. The docstring describes intent; the signature describes interface. Together they're what a programmer searches for. The body is implementation detail.

## Step 2 — Incremental indexing

Hash each file with MD5:

```python
import hashlib

def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()
```

Store `{filepath: hash}` as JSON. On next run, compare. Only chunk + embed files whose hash changed.

## Step 3 — FAISS with cosine similarity

For cosine similarity with FAISS's `IndexFlatIP`:

```python
import faiss
import numpy as np

embeddings = model.encode(texts)
faiss.normalize_L2(embeddings)  # convert to unit vectors
index = faiss.IndexFlatIP(embeddings.shape[1])
index.add(embeddings)
```

For search, normalize the query vector the same way before calling `index.search`.

## Step 4 — Model comparison

Run the same query twice with different models. The difference in rankings reveals:
- Code-tuned models rank syntactic matches higher
- General models rank semantic/intent matches higher

For the `--compare` output, show both ranked lists and highlight rank position changes.

## Debugging tips

- If search returns nonsense, print the chunk texts being embedded — you may be embedding empty strings
- If FAISS index fails to load, check that `metadata.json` and `index.faiss` have the same number of entries
- The heuristic chunker is intentionally simple; for production you'd use tree-sitter for JS/TS

## How to talk about this in an interview

**"Why function-level chunking instead of file-level?"**
> File-level embedding loses signal — a 500-line file has many unrelated functions. Function-level gives you precise retrieval: you get the exact function that answers the query, not the whole file you have to scan.

**"How does incremental indexing work?"**
> I hash each file with MD5. On re-run I compare current hashes to stored hashes. Only changed or new files get re-embedded. This keeps re-indexing fast enough to run as a pre-commit hook.

**"What's the score difference between models?"**
> Code-tuned models (like CodeBERT) are better at matching identifier names and API patterns. General models are better at matching intent described in comments and docstrings. The `--compare` mode makes this concrete for any query.
