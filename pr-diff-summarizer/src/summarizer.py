"""Diff parsing, test-coverage detection, and audience-aware LLM
generation: a plain-English summary, an architecture impact paragraph,
and a markdown report that combines both with a test coverage flag.
"""

import os
import re

from llm import get_completion

TEST_PATTERNS = ["test_", "_test.py", "/tests/"]

DIFF_HEADER_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")


def _extract_filenames(diff_text: str) -> list[str]:
    """Pull filenames out of `diff --git a/<path> b/<path>` headers, in
    the order they appear in the diff."""
    filenames = []
    for line in diff_text.splitlines():
        match = DIFF_HEADER_RE.match(line)
        if match:
            filenames.append(match.group(2))
    return filenames


def parse_diff_stats(diff_text: str) -> dict:
    """Count added/removed lines and changed files in a unified diff.

    Lines starting with `+++`/`---` (file headers) are not counted as
    added/removed content. Binary files still count toward
    files_changed but contribute 0 added/removed lines.
    """
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


def detect_test_changes(diff_text: str) -> bool:
    """Return True when NO test files are present in the diff (coverage
    flag raised). Return False when at least one test file is touched.

    A test file is any filename matching test_*.py, *_test.py, or any
    path containing a /tests/ directory segment.
    """
    filenames = _extract_filenames(diff_text)
    has_tests = any(any(pattern in filename for pattern in TEST_PATTERNS) for filename in filenames)
    return not has_tests


def _strip_raw_diff_lines(text: str) -> str:
    """Drop any line that starts with + or - (raw diff noise the model
    sometimes echoes back), so output is always safe for a non-technical
    audience."""
    kept_lines = [line for line in text.splitlines() if not line.startswith("+") and not line.startswith("-")]
    return "\n".join(kept_lines).strip()


def _truncate_to_word_limit(text: str, max_words: int) -> str:
    """Truncate text to at most max_words words, appending a trailing
    `[...]` marker when truncation happens."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " [...]"


def _is_docs_only(filenames: list[str]) -> bool:
    """True when every changed file is a Markdown (.md) file."""
    return bool(filenames) and all(filename.endswith(".md") for filename in filenames)


def generate_summary(diff_text: str, title: str = "", stats: dict = None) -> str:
    """Generate a plain-English summary paragraph for a non-technical
    audience (product manager / engineering manager), capped at
    SUMMARY_MAX_WORDS words (default 150)."""
    max_words = int(os.environ.get("SUMMARY_MAX_WORDS", "150"))
    stats = stats if stats is not None else parse_diff_stats(diff_text)

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
    if stats["lines_added"] == 0 and stats["lines_removed"] == 0 and stats["files_changed"] > 0:
        context_lines.append("Note: this diff appears to contain binary changes only.")

    prompt = "\n".join(context_lines) + "\n\nDiff:\n" + diff_text

    raw_response = get_completion(prompt, system)
    cleaned_response = _strip_raw_diff_lines(raw_response)
    return _truncate_to_word_limit(cleaned_response, max_words)


def generate_arch_impact(diff_text: str, stats: dict = None) -> str:
    """Generate a one-paragraph architecture impact summary describing
    affected modules and system-level properties, capped at
    ARCH_MAX_WORDS words (default 100).

    Documentation-only diffs (every changed file ends in .md) return the
    canned string "No architectural changes." without calling the LLM.
    """
    max_words = int(os.environ.get("ARCH_MAX_WORDS", "100"))
    stats = stats if stats is not None else parse_diff_stats(diff_text)

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
    if stats["lines_added"] == 0 and stats["lines_removed"] == 0 and stats["files_changed"] > 0:
        context_lines.append("Note: this diff appears to contain binary changes only.")

    prompt = "\n".join(context_lines) + "\n\nDiff:\n" + diff_text

    raw_response = get_completion(prompt, system)
    cleaned_response = _strip_raw_diff_lines(raw_response)
    return _truncate_to_word_limit(cleaned_response, max_words)


def build_report(summary: str, arch_impact: str, test_flag: bool, stats: dict, comments_text: str = "") -> str:
    """Compose the final markdown report: Summary, Architecture Impact,
    Test Coverage Flag, and Diff Stats sections."""
    flag_text = "⚠️ No test changes detected" if test_flag else "✅ Tests modified"

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
