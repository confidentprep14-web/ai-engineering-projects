"""CLI entry point — reads a diff, reviews it chunk by chunk, reports
findings as a table or JSON file, and exits 1 if any HIGH finding exists
(so it can gate CI).
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from reporter import count_by_severity, print_table, save_json
from reviewer import chunk_diff_by_file, merge_results, review_chunk

DEFAULT_JSON_OUTPUT_PATH = "review_output.json"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review a git diff and report structured findings.")
    parser.add_argument("--diff", help="Path to a diff file. If omitted, reads from stdin.")
    parser.add_argument(
        "--min-severity",
        choices=["HIGH", "MEDIUM", "LOW"],
        default="LOW",
        help="Minimum severity to include in the report (default: LOW).",
    )
    parser.add_argument(
        "--output",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table).",
    )
    parser.add_argument(
        "--json-out",
        default=DEFAULT_JSON_OUTPUT_PATH,
        help=f"Path for JSON output when --output json is used (default: {DEFAULT_JSON_OUTPUT_PATH}).",
    )
    return parser


def read_diff_text(diff_path: str | None) -> str:
    if diff_path:
        with open(diff_path) as f:
            return f.read()
    return sys.stdin.read()


def main() -> int:
    load_dotenv()

    parser = build_arg_parser()
    args = parser.parse_args()

    diff_text = read_diff_text(args.diff)

    if not diff_text.strip():
        print("No changes found in diff.")
        return 0

    chunks = chunk_diff_by_file(diff_text)

    if not chunks:
        print("No changes found in diff.")
        return 0

    results_per_chunk = [review_chunk(chunk, min_severity=args.min_severity) for chunk in chunks]
    findings = merge_results(results_per_chunk)

    counts = count_by_severity(findings)
    summary_line = f"Found {len(findings)} findings ({counts['HIGH']} HIGH, {counts['MEDIUM']} MEDIUM, {counts['LOW']} LOW)"
    print(summary_line)

    if args.output == "json":
        save_json(findings, args.json_out)
    else:
        print_table(findings)

    return 1 if counts["HIGH"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
