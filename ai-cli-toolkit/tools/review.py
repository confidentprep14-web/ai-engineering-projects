"""Tool plugin: ai review — code review over a git diff.

Inlines the chunking + per-chunk LLM review + merge + report logic from
the code-review-bot project (sibling project in this repo). Self-contained:
no sys.path import from another project directory.
"""

import json
import logging
import os
import sys

from src.llm import get_json_completion

TOOL_NAME = "review"
TOOL_DESCRIPTION = "Code review — finds security, performance, correctness, and style issues in a git diff"

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
VALID_SEVERITIES = set(SEVERITY_ORDER)

SYSTEM_PROMPT = """You are a senior engineer performing a security and quality code review.
Return ONLY a JSON array. Each element must have:
  file, line_range, severity (HIGH|MEDIUM|LOW),
  category (security|performance|correctness|style),
  finding, suggestion.
If there are no issues, return []."""


def add_arguments(parser) -> None:
    parser.add_argument("--diff", help="Path to diff file (reads stdin if omitted)")
    parser.add_argument("--min-severity", choices=["HIGH", "MEDIUM", "LOW"], default=None)
    parser.add_argument("--output", choices=["table", "json"], default=None)
    parser.add_argument("--json-out", default="review_output.json", help="Path for JSON output")


def run(args, config) -> None:
    min_severity = args.min_severity or config.get("min_severity", "LOW")
    output_format = args.output or config.get("default_output", "table")

    diff_text = _read_diff_text(args.diff)
    if not diff_text.strip():
        print("No changes found in diff.")
        return

    chunks = _chunk_diff_by_file(diff_text)
    if not chunks:
        print("No changes found in diff.")
        return

    results_per_chunk = [_review_chunk(chunk, min_severity=min_severity) for chunk in chunks]
    findings = _merge_results(results_per_chunk)

    counts = _count_by_severity(findings)
    print(f"Found {len(findings)} findings ({counts['HIGH']} HIGH, {counts['MEDIUM']} MEDIUM, {counts['LOW']} LOW)")

    if output_format == "json":
        _save_json(findings, args.json_out)
    else:
        _print_table(findings)


def _read_diff_text(diff_path: str | None) -> str:
    if diff_path:
        with open(diff_path) as f:
            return f.read()
    return sys.stdin.read()


def _chunk_diff_by_file(diff_text: str) -> list[dict]:
    """Split a unified diff into one chunk per file."""
    if not diff_text.strip():
        return []

    chunks: list[dict] = []
    raw_pieces = diff_text.split("diff --git ")
    for piece in raw_pieces:
        if not piece.strip():
            continue
        file_diff = "diff --git " + piece
        filename = _extract_filename(piece)
        if filename is None:
            continue

        if "@@" not in file_diff:
            logger.warning("Skipping binary file: %s", filename)
            continue

        chunks.append({"filename": filename, "diff": file_diff})

    return chunks


def _extract_filename(diff_piece: str) -> str | None:
    header_line = diff_piece.splitlines()[0] if diff_piece.splitlines() else ""
    parts = header_line.split()
    if len(parts) < 2:
        return None
    b_path = parts[1]
    if b_path.startswith("b/"):
        b_path = b_path[2:]
    return b_path


def _review_chunk(chunk: dict, min_severity: str = "LOW") -> list[dict]:
    """Send one file's diff chunk to the LLM and return filtered findings.

    Never raises — on JSON parse failure or any LLM error, logs a warning
    and returns [].
    """
    try:
        raw_result = get_json_completion(chunk["diff"], system=SYSTEM_PROMPT)
    except ValueError as exc:
        logger.warning("Failed to parse LLM response for %s: %s", chunk.get("filename"), exc)
        return []
    except (RuntimeError, ConnectionError) as exc:
        logger.warning("LLM call failed for %s: %s", chunk.get("filename"), exc)
        print(f"LLM call failed: {exc}")
        return []

    if not isinstance(raw_result, list):
        logger.warning("Expected a JSON array of findings for %s", chunk.get("filename"))
        return []

    normalized = [_normalize_finding(item) for item in raw_result]
    return _filter_by_severity(normalized, min_severity)


def _normalize_finding(finding: dict) -> dict:
    normalized = dict(finding)
    severity = str(normalized.get("severity", "")).upper()
    if severity not in VALID_SEVERITIES:
        severity = "MEDIUM"
    normalized["severity"] = severity
    return normalized


def _filter_by_severity(findings: list[dict], min_severity: str) -> list[dict]:
    min_rank = SEVERITY_ORDER.get(min_severity.upper(), SEVERITY_ORDER["LOW"])
    return [f for f in findings if SEVERITY_ORDER.get(f["severity"], SEVERITY_ORDER["LOW"]) <= min_rank]


def _merge_results(results_per_chunk: list[list[dict]]) -> list[dict]:
    flat: list[dict] = [finding for chunk_results in results_per_chunk for finding in chunk_results]

    deduped: list[dict] = []
    seen_keys = set()
    for finding in flat:
        key = (finding.get("file"), finding.get("line_range"), finding.get("category"))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(finding)

    deduped.sort(key=lambda f: (SEVERITY_ORDER.get(f.get("severity"), SEVERITY_ORDER["LOW"]), f.get("file", "")))
    return deduped


def _count_by_severity(findings: list[dict]) -> dict:
    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for finding in findings:
        severity = finding.get("severity", "LOW")
        if severity in counts:
            counts[severity] += 1
    return counts


def _truncate(text, max_len: int = 60) -> str:
    text = str(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _print_table(findings: list[dict]) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        for f in findings:
            print(f"[{f.get('severity')}] {f.get('file')}:{f.get('line_range')} {f.get('category')} - {f.get('finding')}")
        return

    severity_style = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "default"}
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
        style = severity_style.get(severity, "default")
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


def _save_json(findings: list[dict], output_path: str) -> None:
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    with open(output_path, "w") as f:
        json.dump(findings, f, indent=2)

    print(f"Saved {len(findings)} findings to {output_path}")
