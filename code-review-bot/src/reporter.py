"""Render review findings — as a colored table (stdout) or a JSON file."""

import json
import os

from rich.console import Console
from rich.table import Table

SEVERITY_STYLE = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "default"}


def _truncate(text: str, max_len: int = 60) -> str:
    text = str(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def print_table(findings: list[dict]) -> None:
    """Print findings as a rich table — HIGH rows red, MEDIUM yellow,
    LOW default color."""
    console = Console()
    table = Table(show_header=True, header_style="bold")
    table.add_column("Severity")
    table.add_column("File")
    table.add_column("Lines")
    table.add_column("Category")
    table.add_column("Finding")
    table.add_column("Suggestion")

    for finding in findings:
        severity = finding.get("severity", "LOW")
        style = SEVERITY_STYLE.get(severity, "default")
        table.add_row(
            severity,
            str(finding.get("file", "")),
            str(finding.get("line_range", "")),
            str(finding.get("category", "")),
            _truncate(finding.get("finding", "")),
            _truncate(finding.get("suggestion", "")),
            style=style,
        )

    console.print(table)


def save_json(findings: list[dict], output_path: str) -> None:
    """Write findings to a JSON file, creating the parent directory if
    needed, and print a confirmation line."""
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    with open(output_path, "w") as f:
        json.dump(findings, f, indent=2)

    print(f"Saved {len(findings)} findings to {output_path}")


def count_by_severity(findings: list[dict]) -> dict:
    """Return {"HIGH": int, "MEDIUM": int, "LOW": int}, defaulting any
    missing severity to 0."""
    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for finding in findings:
        severity = finding.get("severity", "LOW")
        if severity in counts:
            counts[severity] += 1
    return counts
