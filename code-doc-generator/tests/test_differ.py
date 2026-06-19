"""Tests for src/differ.py — unified diff generation between an
existing doc file and freshly generated content. No LLM, no mocking
needed: pure difflib logic.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from differ import show_diff  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_diff_shows_additions_when_no_existing_file():
    """Spec test 6: show_diff against a nonexistent path must diff
    against an empty string, so every non-header line in the unified
    diff is an addition (starts with '+')."""
    nonexistent_path = str(FIXTURES_DIR / "does_not_exist.md")
    generated = "# Title\n\nSome generated content.\n"

    diff = show_diff(nonexistent_path, generated)

    for line in diff.splitlines():
        if line.startswith(("---", "+++", "@@")):
            continue
        assert line.startswith("+")
