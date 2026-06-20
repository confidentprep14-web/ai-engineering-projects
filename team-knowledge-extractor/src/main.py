"""CLI entry point — extract decisions from a folder of GitHub issue
JSON / ADR markdown files, search the local knowledge store by keyword +
recency, list everything stored, or export the full store to JSON.
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from extractor import extract_decision, load_adr_markdown, load_github_issue_json
from store import KnowledgeStore


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract and search structured decisions from GitHub issues and ADRs."
    )
    parser.add_argument("--extract", metavar="DIR", help="Process all .json/.md files in DIR.")
    parser.add_argument("--search", metavar="QUERY", help="Search the knowledge store.")
    parser.add_argument("--show", action="store_true", help="List all stored decisions.")
    parser.add_argument("--export", metavar="PATH", help="Export the full store to PATH.")
    return parser


def _run_extract(directory: str, store: KnowledgeStore) -> int:
    if not os.path.isdir(directory):
        print(f"Not a directory: {directory}")
        return 1

    files = sorted(os.listdir(directory))
    target_files = [f for f in files if f.endswith(".json") or f.endswith(".md")]

    extracted_count = 0
    for filename in target_files:
        filepath = os.path.join(directory, filename)
        try:
            if filename.endswith(".json"):
                raw_content = load_github_issue_json(filepath)
                source_type = "github_issue"
            else:
                raw_content = load_adr_markdown(filepath)
                source_type = "adr"

            decision = extract_decision(raw_content, source_type, filename)
            store.save(decision)
            extracted_count += 1
        except ValueError as exc:
            print(f"Skipping {filename}: {exc}")

    print(f"Extracted {extracted_count} decisions from {len(target_files)} files")
    return 0


def _run_search(query: str, store: KnowledgeStore) -> int:
    if not store.list_all():
        print("No decisions found. Run --extract first.")
        return 0

    top_k = int(os.environ.get("SEARCH_TOP_K", "5"))
    results = store.search_keyword_recency(query, top_k=top_k)

    print(f"{'Rank':<6}{'Date':<12}{'Decision':<50}{'Author':<15}Tags")
    for rank, decision in enumerate(results, start=1):
        decision_text = decision.decision[:47] + "..." if len(decision.decision) > 50 else decision.decision
        tags = ", ".join(decision.tags)
        print(f"{rank:<6}{decision.date:<12}{decision_text:<50}{decision.author:<15}{tags}")
    return 0


def _run_show(store: KnowledgeStore) -> int:
    decisions = store.list_all()
    if not decisions:
        print("No decisions found. Run --extract first.")
        return 0

    print(f"{'Date':<12}{'Decision':<50}{'Author':<15}Source")
    for decision in decisions:
        decision_text = decision.decision[:47] + "..." if len(decision.decision) > 50 else decision.decision
        print(f"{decision.date:<12}{decision_text:<50}{decision.author:<15}{decision.source_file}")
    return 0


def run(args: argparse.Namespace) -> int:
    load_dotenv()
    store = KnowledgeStore()

    if args.extract:
        return _run_extract(args.extract, store)
    if args.search is not None:
        return _run_search(args.search, store)
    if args.show:
        return _run_show(store)
    if args.export:
        store.export_json(args.export)
        print(f"Exported store to {args.export}")
        return 0

    print("No action given. Use --extract, --search, --show, or --export.")
    return 1


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
