"""CLI entry point: --index, --search, --compare, --reindex."""

import argparse
import os
import sys
import time

import numpy as np
from dotenv import load_dotenv

from chunker import ast_chunk_python, file_hash, heuristic_chunk
from embedder import embed_functions, load_model
from indexer import build_index, get_changed_files, load_index, save_index, search

PYTHON_EXTENSION = ".py"
SKIP_DIR_NAMES = {".venv", "venv", ".git", "__pycache__", ".index", ".pytest_cache"}


def _walk_indexable_files(directory: str) -> list[str]:
    """Return all file paths under directory, skipping noise directories."""
    filepaths = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES]
        for name in files:
            filepaths.append(os.path.join(root, name))
    return filepaths


def _chunk_file(filepath: str) -> list[dict]:
    if filepath.endswith(PYTHON_EXTENSION):
        return ast_chunk_python(filepath)
    return heuristic_chunk(filepath)


def _load_existing_state(index_dir: str, force_reindex: bool) -> tuple:
    """Return (existing_index, existing_chunks, existing_hashes), or empty state.

    Empty state is used on --reindex or when no index exists yet.
    """
    if force_reindex:
        return None, [], {}
    try:
        return load_index(index_dir)
    except FileNotFoundError:
        return None, [], {}


def _keep_unchanged_chunks(existing_index, existing_chunks: list[dict], changed_files: list[str]) -> tuple:
    """Pull metadata + already-computed vectors for chunks whose file did not change.

    Reusing these vectors (via FAISS's reconstruct) instead of re-embedding is
    what makes incremental indexing actually skip work, not just skip files in
    the printed message.
    """
    if existing_index is None or not existing_chunks:
        return [], None

    kept_positions = [i for i, c in enumerate(existing_chunks) if c["file"] not in changed_files]
    if not kept_positions:
        return [], None

    kept_chunks = [existing_chunks[i] for i in kept_positions]
    kept_vectors = np.vstack([existing_index.reconstruct(i) for i in kept_positions]).astype(np.float32)
    return kept_chunks, kept_vectors


def run_index(directory: str, index_dir: str, model_name: str, force_reindex: bool) -> None:
    """Index a directory: incremental by default, full rebuild if force_reindex."""
    start_time = time.time()

    all_files = _walk_indexable_files(directory)
    if not all_files:
        print(f"No indexable files found in {directory}.")
        sys.exit(0)

    existing_index, existing_chunks, existing_hashes = _load_existing_state(index_dir, force_reindex)

    if force_reindex:
        changed_files, unchanged_files = all_files, []
    else:
        changed_files, unchanged_files = get_changed_files(directory, existing_hashes)

    print(f"Skipped {len(unchanged_files)} files (unchanged)")

    new_chunks: list[dict] = []
    for filepath in changed_files:
        new_chunks.extend(_chunk_file(filepath))

    kept_chunks, kept_vectors = _keep_unchanged_chunks(existing_index, existing_chunks, changed_files)

    if not new_chunks and not kept_chunks:
        print("Nothing new to index.")
        sys.exit(0)

    if new_chunks:
        model = load_model(model_name)
        new_chunks, new_embeddings = embed_functions(new_chunks, model)
    else:
        new_embeddings = None

    all_chunks = kept_chunks + new_chunks
    if kept_vectors is not None and new_embeddings is not None:
        embeddings = np.vstack([kept_vectors, new_embeddings])
    else:
        embeddings = new_embeddings if new_embeddings is not None else kept_vectors

    index = build_index(all_chunks, embeddings)

    new_hashes = dict(existing_hashes)
    for filepath in changed_files:
        new_hashes[filepath] = file_hash(filepath)

    save_index(index, all_chunks, new_hashes, index_dir)

    elapsed = time.time() - start_time
    indexed_files = {c["file"] for c in all_chunks}
    print(f"Indexed {len(all_chunks)} functions from {len(indexed_files)} files | latency={elapsed:.1f}s")


def _print_results_table(results: list[dict]) -> None:
    print(f"{'Score':<8}{'File':<45}{'Function':<25}{'Line'}")
    for result in results:
        print(f"{result['score']:<8.3f}{result['file']:<45}{result['function_name']:<25}{result['lineno']}")


def run_search(query: str, index_dir: str, model_name: str, top_k: int, min_score: float) -> None:
    """Load the index, embed the query, search, and print a results table."""
    start_time = time.time()

    index, chunks, _file_hashes = load_index(index_dir)
    model = load_model(model_name)
    results = search(query, model, index, chunks, top_k=top_k)
    results = [r for r in results if r["score"] >= min_score]

    elapsed_ms = (time.time() - start_time) * 1000
    if results:
        print(f"Search completed in {elapsed_ms:.0f}ms | top score={results[0]['score']:.3f}")
    else:
        print(f"Search completed in {elapsed_ms:.0f}ms | no results above threshold")

    _print_results_table(results)


def run_compare(query: str, index_dir: str, embed_model_name: str, compare_model_name: str, top_k: int) -> None:
    """Run the query against EMBED_MODEL and COMPARE_MODEL, print side by side."""
    index, chunks, _file_hashes = load_index(index_dir)

    primary_model = load_model(embed_model_name)
    primary_results = search(query, primary_model, index, chunks, top_k=top_k)

    compare_model = load_model(compare_model_name)
    compare_results = search(query, compare_model, index, chunks, top_k=top_k)

    print("=" * 70)
    print(f"PRIMARY MODEL: {embed_model_name}")
    print("=" * 70)
    _print_results_table(primary_results)

    print()
    print("=" * 70)
    print(f"COMPARE MODEL: {compare_model_name}")
    print("=" * 70)
    _print_results_table(compare_results)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Semantic search over a codebase, at function granularity.")
    parser.add_argument("--index", dest="index_dir_arg", default=None, help="Index this directory")
    parser.add_argument("--reindex", action="store_true", help="Force full reindex (ignore existing hashes)")
    parser.add_argument("--search", dest="search_query", default=None, help="Search query")
    parser.add_argument("--compare", dest="compare_query", default=None, help="Compare EMBED_MODEL vs COMPARE_MODEL")
    parser.add_argument("--top-k", type=int, default=None, help="Number of results to return")
    args = parser.parse_args()

    index_dir = os.environ.get("INDEX_DIR", ".index")
    embed_model_name = os.environ.get("EMBED_MODEL", "all-MiniLM-L6-v2")
    compare_model_name = os.environ.get("COMPARE_MODEL", "all-MiniLM-L6-v2")
    top_k = args.top_k if args.top_k is not None else int(os.environ.get("TOP_K", 5))
    min_score = float(os.environ.get("MIN_SCORE", 0.0))

    try:
        if args.index_dir_arg:
            run_index(args.index_dir_arg, index_dir, embed_model_name, args.reindex)

        if args.search_query:
            run_search(args.search_query, index_dir, embed_model_name, top_k, min_score)

        if args.compare_query:
            run_compare(args.compare_query, index_dir, embed_model_name, compare_model_name, top_k)

        if not (args.index_dir_arg or args.search_query or args.compare_query):
            parser.print_help()
    except FileNotFoundError as known_failure:
        print(f"Error: {known_failure}")
        sys.exit(1)
    except OSError as model_failure:
        print("Model download failed. Check network.")
        sys.exit(1)


if __name__ == "__main__":
    main()
