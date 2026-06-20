"""Tool plugin: ai search — semantic codebase search.

Inlines the FAISS load + sentence-transformers query-embedding + search
logic from the semantic-codebase-search project (sibling project in this
repo). Indexing itself is out of scope for this thin wrapper — this tool
only searches a pre-built index; if one isn't found it prints the
documented "No index found" message and exits 1.

Note: sentence-transformers and faiss-cpu are imported lazily, inside
run(), so `ai` with no args / other tools never pay the import cost (or
risk the known native teardown segfault — see project docs) unless
`ai search` is actually invoked.
"""

import os
import sys

TOOL_NAME = "search"
TOOL_DESCRIPTION = "Semantic codebase search — find functions by meaning, not keyword"


def add_arguments(parser) -> None:
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--index-dir", default=None, help="Override index directory from config")
    parser.add_argument("--top-k", type=int, default=5)


def run(args, config) -> None:
    index_dir = args.index_dir or config.get("index_dir", ".index")

    index_path = os.path.join(index_dir, "index.faiss")
    metadata_path = os.path.join(index_dir, "metadata.json")
    hashes_path = os.path.join(index_dir, "file_hashes.json")

    if not (os.path.exists(index_path) and os.path.exists(metadata_path) and os.path.exists(hashes_path)):
        print(f"No index found. Run: ai index --dir <path>")
        sys.exit(1)

    try:
        # Import order matters: importing sentence-transformers (torch)
        # before faiss avoids a reproducible native segfault on this
        # platform (OpenMP/library teardown conflict between torch and
        # faiss) — see GUIDE.md "Known environment gotcha".
        from sentence_transformers import SentenceTransformer
        import faiss
        import numpy as np
    except ImportError as exc:
        print(f"Missing dependency for search: {exc}. Run: pip install -r requirements.txt")
        sys.exit(1)

    index, chunks, _file_hashes = _load_index(index_dir, faiss)

    model_name = os.environ.get("EMBED_MODEL", "all-MiniLM-L6-v2")
    print(f"Loading model: {model_name}")
    model = SentenceTransformer(model_name)

    results = _search(args.query, model, index, chunks, faiss, np, top_k=args.top_k)
    _print_results_table(results)


def _load_index(index_dir: str, faiss):
    import json

    index_path = os.path.join(index_dir, "index.faiss")
    metadata_path = os.path.join(index_dir, "metadata.json")
    hashes_path = os.path.join(index_dir, "file_hashes.json")

    index = faiss.read_index(index_path)

    with open(metadata_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    try:
        with open(hashes_path, "r", encoding="utf-8") as f:
            file_hashes = json.load(f)
    except json.JSONDecodeError:
        file_hashes = {}

    return index, chunks, file_hashes


def _search(query: str, model, index, chunks: list[dict], faiss, np, top_k: int = 5) -> list[dict]:
    query_embedding = model.encode([query])
    query_embedding = np.ascontiguousarray(query_embedding, dtype=np.float32)
    faiss.normalize_L2(query_embedding)

    k = min(top_k, len(chunks)) if chunks else 0
    if k == 0:
        return []

    scores, indices = index.search(query_embedding, k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(chunks):
            continue
        chunk = chunks[idx]
        results.append(
            {
                "file": chunk["file"],
                "function_name": chunk["function_name"],
                "lineno": chunk["lineno"],
                "score": float(score),
            }
        )

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def _print_results_table(results: list[dict]) -> None:
    print(f"{'Score':<8}{'File':<45}{'Function':<25}{'Line'}")
    for result in results:
        print(f"{result['score']:<8.3f}{result['file']:<45}{result['function_name']:<25}{result['lineno']}")
