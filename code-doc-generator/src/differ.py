"""Unified diff display between an existing doc file and freshly
generated content. Uses difflib so it handles files of any size
without truncation — no custom size limits needed.
"""

import difflib
import os

from rich.console import Console

console = Console()


def show_diff(existing_path: str, generated: str) -> str:
    """Return a unified diff between existing_path's contents and
    generated. If existing_path doesn't exist, diff against an empty
    string so every line in the result is an addition."""
    if os.path.exists(existing_path):
        with open(existing_path) as f:
            existing_text = f.read()
    else:
        existing_text = ""

    diff_lines = difflib.unified_diff(
        existing_text.splitlines(keepends=True),
        generated.splitlines(keepends=True),
        fromfile=existing_path,
        tofile="generated",
    )
    return "".join(diff_lines)


def print_diff(diff: str) -> None:
    """Print diff with rich coloring: additions green, removals red.
    An empty diff prints a no-changes message instead."""
    if not diff:
        console.print("No changes — generated docs match existing file.")
        return

    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            console.print(line, style="green")
        elif line.startswith("-") and not line.startswith("---"):
            console.print(line, style="red")
        else:
            console.print(line)
