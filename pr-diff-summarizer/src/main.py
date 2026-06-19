"""CLI entry point — reads a diff, parses stats, detects test coverage,
generates an audience-aware summary and architecture impact paragraph,
then prints a combined markdown report.
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from summarizer import (
    build_report,
    detect_test_changes,
    generate_arch_impact,
    generate_summary,
    parse_diff_stats,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize a git diff for both technical and non-technical readers.")
    parser.add_argument("--diff", help="Path to a diff file. If omitted, reads from stdin.")
    parser.add_argument("--title", default="", help="Optional PR title to include in the summary prompt.")
    parser.add_argument(
        "--comments",
        help="Optional path to a plain-text file of reviewer comments, appended to the summary prompt.",
    )
    return parser


def read_diff_text(diff_path: str | None) -> str:
    if diff_path:
        with open(diff_path) as f:
            return f.read()
    return sys.stdin.read()


def read_comments_text(comments_path: str | None) -> str:
    """Read the optional reviewer-comments file. Missing files warn and
    continue (do not crash)."""
    if not comments_path:
        return ""
    if not os.path.exists(comments_path):
        print(f"Warning: comments file not found: {comments_path}. Continuing without comments.")
        return ""
    with open(comments_path) as f:
        return f.read()


def main() -> int:
    load_dotenv()

    parser = build_arg_parser()
    args = parser.parse_args()

    diff_text = read_diff_text(args.diff)

    if not diff_text.strip():
        print("No changes detected in diff.")
        return 0

    stats = parse_diff_stats(diff_text)
    print(
        f"Diff stats | files_changed={stats['files_changed']} "
        f"lines_added={stats['lines_added']} lines_removed={stats['lines_removed']}"
    )

    test_flag = detect_test_changes(diff_text)
    comments_text = read_comments_text(args.comments)

    summary = generate_summary(diff_text, title=args.title, stats=stats)
    arch_impact = generate_arch_impact(diff_text, stats=stats)

    report = build_report(
        summary=summary,
        arch_impact=arch_impact,
        test_flag=test_flag,
        stats=stats,
        comments_text=comments_text,
    )
    print(report)

    print(
        f"Summary generated | files_changed={stats['files_changed']} "
        f"lines_added={stats['lines_added']} lines_removed={stats['lines_removed']} "
        f"test_flag={test_flag}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
