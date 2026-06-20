"""CLI entry point: --index <dir>, --ask "...", --rebuild.

Stores the indexed docs directory alongside the FAISS index (.index/docs_dir.txt)
so --ask can re-run the freshness check without the caller having to repeat
which directory was indexed.
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from chunker import markdown_chunk_by_section, pdf_chunk_with_heading_detection
from copilot import build_answer_with_citations, format_citations, handle_below_threshold
from indexer import build_with_metadata, check_freshness_and_reindex, load_index, save_index
from indexer import search_with_metadata

INDEX_DIR = os.environ.get("INDEX_DIR", ".index")
TOP_K = int(os.environ.get("TOP_K", "5"))
CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.5"))
EMBED_MODEL = os.environ.get("EMBED_MODEL", "all-MiniLM-L6-v2")
DOCS_DIR_FILE = "docs_dir.txt"

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def _walk_docs(docs_dir: str) -> list[str]:
    matches = []
    for root, _dirs, files in os.walk(docs_dir):
        for name in sorted(files):
            if name.endswith((".md", ".pdf")):
                matches.append(os.path.abspath(os.path.join(root, name)))
    return sorted(matches)


def _chunk_file(filepath: str) -> list[dict]:
    if filepath.endswith(".md"):
        pairs = markdown_chunk_by_section(filepath)
    elif filepath.endswith(".pdf"):
        pairs = pdf_chunk_with_heading_detection(filepath)
    else:
        return []
    return [{"text": text, "metadata": meta} for text, meta in pairs]


def _save_docs_dir(docs_dir: str) -> None:
    os.makedirs(INDEX_DIR, exist_ok=True)
    with open(os.path.join(INDEX_DIR, DOCS_DIR_FILE), "w", encoding="utf-8") as f:
        f.write(os.path.abspath(docs_dir))


def _load_docs_dir() -> str | None:
    path = os.path.join(INDEX_DIR, DOCS_DIR_FILE)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def cmd_index(docs_dir: str, rebuild: bool) -> None:
    files = _walk_docs(docs_dir)
    if not files:
        print(f"No .md or .pdf files found in {docs_dir}.")
        return

    mtimes_path = os.path.join(INDEX_DIR, "file_mtimes.json")
    stored_mtimes: dict = {}
    if os.path.isfile(mtimes_path) and not rebuild:
        with open(mtimes_path, "r", encoding="utf-8") as f:
            stored_mtimes = json.load(f)

    new_or_changed = sum(1 for f in files if stored_mtimes.get(f) != os.path.getmtime(f))
    unchanged = len(files) - new_or_changed

    model = _get_model()

    if rebuild:
        all_chunks: list[dict] = []
        for filepath in files:
            all_chunks.extend(_chunk_file(filepath))
        new_mtimes = {filepath: os.path.getmtime(filepath) for filepath in files}
        index, _embeddings, chunks = build_with_metadata(all_chunks, model)
        save_index(index, chunks, new_mtimes, INDEX_DIR)
    else:
        check_freshness_and_reindex(INDEX_DIR, docs_dir, model)

    _save_docs_dir(docs_dir)
    _index, chunks, _mtimes = load_index(INDEX_DIR)
    print(f"Indexed {len(chunks)} chunks from {len(files)} files ({new_or_changed} new, {unchanged} unchanged)")


def cmd_ask(query: str) -> None:
    try:
        load_index(INDEX_DIR)
    except FileNotFoundError as exc:
        print(str(exc))
        sys.exit(1)

    model = _get_model()

    docs_dir = _load_docs_dir()
    if docs_dir and os.path.isdir(docs_dir):
        check_freshness_and_reindex(INDEX_DIR, docs_dir, model)

    index, chunks, _mtimes = load_index(INDEX_DIR)
    results = search_with_metadata(query, model, index, chunks, top_k=TOP_K)
    top_score = results[0]["score"] if results else 0.0

    below = handle_below_threshold(query, top_score, CONFIDENCE_THRESHOLD)
    if below is not None:
        print(below)
        return

    answer = build_answer_with_citations(query, results)
    print(answer)
    print("\nSources:")
    for citation in format_citations(results):
        print(f"  {citation}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Docs Copilot — RAG documentation assistant")
    parser.add_argument("--index", metavar="DIR", help="Index a documentation directory")
    parser.add_argument("--ask", metavar="QUESTION", help="Ask a question against the index")
    parser.add_argument("--rebuild", action="store_true", help="Force full re-index, ignoring mtimes")
    args = parser.parse_args()

    if args.index:
        cmd_index(args.index, rebuild=args.rebuild)
    elif args.ask:
        cmd_ask(args.ask)
    elif args.rebuild:
        docs_dir = _load_docs_dir()
        if not docs_dir:
            print("No previously indexed directory found. Run --index <dir> first.")
            sys.exit(1)
        cmd_index(docs_dir, rebuild=True)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
