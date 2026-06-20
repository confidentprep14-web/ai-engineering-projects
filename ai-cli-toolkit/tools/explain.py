"""Tool plugin: ai explain — PR diff summarizer.

Inlines the diff-stats parsing, test-coverage detection, and two LLM
calls (plain-English summary + architecture impact) from the
pr-diff-summarizer project (sibling project in this repo). Self-contained.
"""

import os
import re
import sys

from src.llm import get_completion

TOOL_NAME = "explain"
TOOL_DESCRIPTION = "PR summarizer — plain-English summary, architecture impact, and test coverage flag"

TEST_PATTERNS = ["test_", "_test.py", "/tests/"]
DIFF_HEADER_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")


def add_arguments(parser) -> None:
    parser.add_argument("--diff", help="Path to diff file (reads stdin if omitted)")
    parser.add_argument("--title", default="", help="PR title (optional)")
    parser.add_argument("--comments", help="Path to reviewer comments file (optional)")


def run(args, config) -> None:
    diff_text = _read_diff_text(args.diff)
    if not diff_text.strip():
        print("No changes detected in diff.")
        return

    stats = _parse_diff_stats(diff_text)
    print(
        f"Diff stats | files_changed={stats['files_changed']} "
        f"lines_added={stats['lines_added']} lines_removed={stats['lines_removed']}"
    )

    test_flag = _detect_test_changes(diff_text)
    comments_text = _read_comments_text(args.comments)

    try:
        summary = _generate_summary(diff_text, title=args.title, stats=stats)
        arch_impact = _generate_arch_impact(diff_text, stats=stats)
    except (RuntimeError, ConnectionError) as exc:
        print(f"LLM call failed: {exc}")
        return

    report = _build_report(
        summary=summary,
        arch_impact=arch_impact,
        test_flag=test_flag,
        stats=stats,
        comments_text=comments_text,
    )
    print(report)


def _read_diff_text(diff_path: str | None) -> str:
    if diff_path:
        with open(diff_path) as f:
            return f.read()
    return sys.stdin.read()


def _read_comments_text(comments_path: str | None) -> str:
    if not comments_path:
        return ""
    if not os.path.exists(comments_path):
        print(f"Warning: comments file not found: {comments_path}. Continuing without comments.")
        return ""
    with open(comments_path) as f:
        return f.read()


def _extract_filenames(diff_text: str) -> list[str]:
    filenames = []
    for line in diff_text.splitlines():
        match = DIFF_HEADER_RE.match(line)
        if match:
            filenames.append(match.group(2))
    return filenames


def _parse_diff_stats(diff_text: str) -> dict:
    filenames = _extract_filenames(diff_text)

    lines_added = 0
    lines_removed = 0
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            lines_added += 1
        elif line.startswith("-"):
            lines_removed += 1

    return {
        "files_changed": len(filenames),
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "filenames": filenames,
    }


def _detect_test_changes(diff_text: str) -> bool:
    """True when NO test files are present (coverage flag raised)."""
    filenames = _extract_filenames(diff_text)
    has_tests = any(any(pattern in filename for pattern in TEST_PATTERNS) for filename in filenames)
    return not has_tests


def _strip_raw_diff_lines(text: str) -> str:
    kept_lines = [line for line in text.splitlines() if not line.startswith("+") and not line.startswith("-")]
    return "\n".join(kept_lines).strip()


def _truncate_to_word_limit(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " [...]"


def _is_docs_only(filenames: list[str]) -> bool:
    return bool(filenames) and all(filename.endswith(".md") for filename in filenames)


def _generate_summary(diff_text: str, title: str = "", stats: dict = None) -> str:
    max_words = int(os.environ.get("SUMMARY_MAX_WORDS", "150"))
    stats = stats if stats is not None else _parse_diff_stats(diff_text)

    system = (
        "You are a technical writer translating a code change for a non-technical audience.\n"
        "Write in plain English. Do not include code, variable names, or file paths.\n"
        f"Keep the summary under {max_words} words."
    )

    context_lines = [
        f"PR title: {title}" if title else "PR title: (none provided)",
        f"Files changed: {stats['files_changed']}",
        f"Lines added: {stats['lines_added']}",
        f"Lines removed: {stats['lines_removed']}",
    ]
    prompt = "\n".join(context_lines) + "\n\nDiff:\n" + diff_text

    raw_response = get_completion(prompt, system)
    cleaned_response = _strip_raw_diff_lines(raw_response)
    return _truncate_to_word_limit(cleaned_response, max_words)


def _generate_arch_impact(diff_text: str, stats: dict = None) -> str:
    max_words = int(os.environ.get("ARCH_MAX_WORDS", "100"))
    stats = stats if stats is not None else _parse_diff_stats(diff_text)

    if _is_docs_only(stats["filenames"]):
        return "No architectural changes."

    system = (
        "You are a software architect reviewing a pull request for system design impact.\n"
        "Describe module boundaries, data flow changes, and any new dependencies introduced.\n"
        f"One paragraph, under {max_words} words."
    )

    context_lines = [
        f"Files changed: {stats['files_changed']} ({', '.join(stats['filenames'])})",
        f"Lines added: {stats['lines_added']}",
        f"Lines removed: {stats['lines_removed']}",
    ]
    prompt = "\n".join(context_lines) + "\n\nDiff:\n" + diff_text

    raw_response = get_completion(prompt, system)
    cleaned_response = _strip_raw_diff_lines(raw_response)
    return _truncate_to_word_limit(cleaned_response, max_words)


def _build_report(summary: str, arch_impact: str, test_flag: bool, stats: dict, comments_text: str = "") -> str:
    flag_text = "No test changes detected" if test_flag else "Tests modified"

    sections = [
        "## Summary",
        "",
        summary,
        "",
        "## Architecture Impact",
        "",
        arch_impact,
        "",
        "## Test Coverage Flag",
        "",
        flag_text,
        "",
        "## Diff Stats",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Files changed | {stats['files_changed']} |",
        f"| Lines added | {stats['lines_added']} |",
        f"| Lines removed | {stats['lines_removed']} |",
    ]

    if comments_text:
        sections += ["", "## Reviewer Comments", "", comments_text]

    return "\n".join(sections)
