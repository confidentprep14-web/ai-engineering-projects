"""Diff chunking, per-chunk LLM review, and result merging.

chunk_diff_by_file splits a raw unified diff into one chunk per file.
review_chunk sends one chunk to the LLM and returns structured findings.
merge_results flattens + sorts + dedupes findings across all chunks.
"""

import logging

from llm import get_json_completion

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
VALID_SEVERITIES = set(SEVERITY_ORDER)

SYSTEM_PROMPT = """You are a senior engineer performing a security and quality code review.
Return ONLY a JSON array. Each element must have:
  file, line_range, severity (HIGH|MEDIUM|LOW),
  category (security|performance|correctness|style),
  finding, suggestion.
If there are no issues, return []."""


def chunk_diff_by_file(diff_text: str) -> list[dict]:
    """Split a unified diff into one chunk per file.

    Returns a list of {"filename": str, "diff": str, "lines": int}.
    Binary file entries (no "@@" hunk header) are skipped with a log
    message. An empty diff returns [].
    """
    if not diff_text.strip():
        return []

    chunks: list[dict] = []
    # Re-attach the "diff --git" marker so each chunk is a complete,
    # self-contained diff snippet for that file.
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

        line_count = _count_changed_lines(file_diff)
        chunks.append({"filename": filename, "diff": file_diff, "lines": line_count})

    return chunks


def _extract_filename(diff_piece: str) -> str | None:
    """Pull the file path out of a 'a/path b/path' header line."""
    header_line = diff_piece.splitlines()[0] if diff_piece.splitlines() else ""
    parts = header_line.split()
    if len(parts) < 2:
        return None
    b_path = parts[1]
    if b_path.startswith("b/"):
        b_path = b_path[2:]
    return b_path


def _count_changed_lines(file_diff: str) -> int:
    """Count added/removed lines only — context lines don't count."""
    count = 0
    for line in file_diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+") or line.startswith("-"):
            count += 1
    return count


def review_chunk(chunk: dict, min_severity: str = "LOW") -> list[dict]:
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
        # llm.py raises immediately on a missing API key or unreachable
        # Ollama host (per spec) — review_chunk must never propagate
        # exceptions to its caller, so we log and degrade to no findings.
        logger.warning("LLM call failed for %s: %s", chunk.get("filename"), exc)
        return []

    if not isinstance(raw_result, list):
        logger.warning("Expected a JSON array of findings for %s, got %s", chunk.get("filename"), type(raw_result))
        return []

    normalized = [_normalize_finding(item) for item in raw_result]
    return _filter_by_severity(normalized, min_severity)


def _normalize_finding(finding: dict) -> dict:
    """Uppercase severity and fall back to MEDIUM if it's not one of the
    three allowed values."""
    normalized = dict(finding)
    severity = str(normalized.get("severity", "")).upper()
    if severity not in VALID_SEVERITIES:
        severity = "MEDIUM"
    normalized["severity"] = severity
    return normalized


def _filter_by_severity(findings: list[dict], min_severity: str) -> list[dict]:
    min_rank = SEVERITY_ORDER.get(min_severity.upper(), SEVERITY_ORDER["LOW"])
    return [f for f in findings if SEVERITY_ORDER.get(f["severity"], SEVERITY_ORDER["LOW"]) <= min_rank]


def merge_results(results_per_chunk: list[list[dict]]) -> list[dict]:
    """Flatten per-chunk finding lists into one sorted, deduplicated list.

    Sort order: HIGH first, then MEDIUM, then LOW; within the same
    severity, alphabetical by filename. Exact duplicates (same file +
    line_range + category) are dropped.
    """
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
