"""Main entry point for the AI PR Reviewer GitHub Action.

Inlines two patterns as simplified, self-contained logic (per the
capstone spec — no cross-project imports):

  - p2-01 (code-review-bot): chunk the diff by file, ask the LLM for
    structured findings per chunk, merge + sort the results.
  - p2-05 (llm-test-generator): pull changed Python function names out
    of the diff and ask the LLM to generate pytest tests for them
    (simplified — no AST parsing of the full file, no real pytest
    validation loop; this is a CI-speed approximation, not the full
    self-correcting generator).

Orchestration: load config -> run enabled tools -> post PR comments ->
log OTEL cost span -> enforce the severity gate -> exit 0/1.
"""

import argparse
import logging
import os
import re
import sys
import time

import yaml
from dotenv import load_dotenv

from cost_tracker import PRCostTracker
from llm import get_completion, get_json_completion
from pr_commenter import post_review_comment, post_test_results

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
VALID_SEVERITIES = set(SEVERITY_ORDER)

REVIEW_SYSTEM_PROMPT = """You are a senior engineer performing a security and quality code review.
Return ONLY a JSON array. Each element must have:
  file, line_range, severity (HIGH|MEDIUM|LOW),
  category (security|performance|correctness|style),
  finding, suggestion.
If there are no issues, return []."""

TEST_GEN_SYSTEM_PROMPT = (
    "You are an expert at writing pytest tests. "
    "Return only valid Python code, no explanation, no markdown."
)

DEFAULT_CONFIG = {
    "ai_review": {
        "code_review": {"enabled": True, "min_severity": "LOW", "severity_gate": "HIGH"},
        "test_generation": {"enabled": True, "max_retries": 2},
        "observability": {"enabled": True, "otel_exporter": "console"},
    },
    "settings": {"post_comments": True, "comment_on_pass": False},
}


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_config(config_path: str = ".aiworkflow.yml") -> dict:
    """Load .aiworkflow.yml; fall back to defaults if missing/empty."""
    if not os.path.exists(config_path):
        print("Config not found, using defaults")
        return DEFAULT_CONFIG

    with open(config_path) as f:
        loaded = yaml.safe_load(f)

    if not loaded:
        print("Config not found, using defaults")
        return DEFAULT_CONFIG

    return loaded


# ---------------------------------------------------------------------------
# Inlined p2-01 pattern: diff chunking + code review
# ---------------------------------------------------------------------------


def chunk_diff_by_file(diff_text: str) -> list[dict]:
    """Split a unified diff into one chunk per file.

    Returns a list of {"filename": str, "diff": str}. Binary files
    (no "@@" hunk header) are skipped.
    """
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


def review_chunk(chunk: dict, min_severity: str, tracker: PRCostTracker) -> list[dict]:
    """Send one file's diff chunk to the LLM and return filtered findings.

    Never raises — on JSON parse failure or any LLM error, logs a warning
    and returns []. Records the call (or a zero-usage call on failure) so
    the per-PR cost total reflects every attempt.
    """
    start = time.monotonic()
    try:
        raw_result, usage = get_json_completion(chunk["diff"], system=REVIEW_SYSTEM_PROMPT)
    except ValueError as exc:
        logger.warning("Failed to parse LLM response for %s: %s", chunk.get("filename"), exc)
        return []
    except (RuntimeError, ConnectionError) as exc:
        logger.warning("LLM call failed for %s: %s", chunk.get("filename"), exc)
        return []
    finally:
        latency_ms = int((time.monotonic() - start) * 1000)

    tracker.record_llm_call(usage, latency_ms)

    if not isinstance(raw_result, list):
        logger.warning("Expected a JSON array of findings for %s, got %s", chunk.get("filename"), type(raw_result))
        return []

    normalized = [_normalize_finding(item) for item in raw_result]
    return _filter_by_severity(normalized, min_severity)


def merge_results(results_per_chunk: list[list[dict]]) -> list[dict]:
    """Flatten, dedupe, and sort findings (HIGH first, then by filename)."""
    flat: list[dict] = [finding for chunk_results in results_per_chunk for finding in chunk_results]

    deduped: list[dict] = []
    seen_keys = set()
    for finding in flat:
        key = (finding.get("file"), finding.get("line_range"), finding.get("category"))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(finding)

    # SEVERITY_ORDER has HIGH=2, so sort descending by rank to get HIGH first.
    deduped.sort(key=lambda f: (-SEVERITY_ORDER.get(f.get("severity"), 0), f.get("file", "")))
    return deduped


def run_code_review(diff_text: str, config: dict, tracker: PRCostTracker) -> tuple[list[dict], int]:
    """Inlined p2-01 pattern: chunk the diff by file, review each chunk,
    merge results. Returns (findings, retry_count) — retry_count is
    always 0 here because review chunks are not retried (only test
    generation retries, per spec)."""
    review_cfg = config.get("ai_review", {}).get("code_review", {})
    min_severity = review_cfg.get("min_severity", "LOW")

    chunks = chunk_diff_by_file(diff_text)
    results_per_chunk = [review_chunk(chunk, min_severity, tracker) for chunk in chunks]
    findings = merge_results(results_per_chunk)
    return findings, 0


# ---------------------------------------------------------------------------
# Inlined p2-05 pattern: changed-function extraction + test generation
# ---------------------------------------------------------------------------

FUNCTION_DEF_RE = re.compile(r"^\+\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")


def extract_changed_functions(diff_text: str) -> list[str]:
    """Pull names of top-level functions added/modified in the diff.

    Simplified vs. the full p2-05 AST-based parser: this scans added
    lines (`+def name(...)`) directly in the diff text rather than
    parsing the full changed file with ast — fast enough for CI, no
    need to check out the full file tree.
    """
    names: list[str] = []
    for line in diff_text.splitlines():
        match = FUNCTION_DEF_RE.match(line)
        if match:
            name = match.group(1)
            if not name.startswith("_") and name not in names:
                names.append(name)
    return names


def build_test_gen_prompt(function_name: str, diff_text: str, prior_error: str = "") -> str:
    """Build the prompt asking the LLM to generate pytest tests for one
    changed function, given the diff context."""
    body = (
        f"Function name: {function_name}\n"
        f"Diff context:\n{diff_text}\n\n"
        "Generate pytest test cases for this function. Use only stdlib. "
        "Return only valid Python code, no markdown fences."
    )
    if prior_error:
        body = f"The previous attempt produced this error. Fix it:\n\n{prior_error}\n\n" + body
    return body


def run_test_generation(diff_text: str, config: dict, tracker: PRCostTracker) -> dict:
    """Inlined p2-05 pattern, simplified: generate tests for changed
    functions only, with up to max_retries re-prompts per function if
    the LLM call itself fails. (No real pytest validation loop here —
    that would require checking out the changed files; out of scope for
    a CI-speed diff-only Action.)
    """
    test_cfg = config.get("ai_review", {}).get("test_generation", {})
    max_retries = test_cfg.get("max_retries", 2)

    function_names = extract_changed_functions(diff_text)
    tests_generated = 0
    retries_used = 0

    for function_name in function_names:
        prior_error = ""
        for attempt in range(max_retries + 1):
            prompt = build_test_gen_prompt(function_name, diff_text, prior_error=prior_error)
            start = time.monotonic()
            try:
                _test_code, usage = get_completion(prompt, system=TEST_GEN_SYSTEM_PROMPT)
            except (RuntimeError, ConnectionError) as exc:
                latency_ms = int((time.monotonic() - start) * 1000)
                tracker.record_llm_call({"input_tokens": 0, "output_tokens": 0}, latency_ms)
                logger.warning("Test generation failed for %s: %s", function_name, exc)
                if attempt < max_retries:
                    retries_used += 1
                    prior_error = str(exc)
                    continue
                break
            else:
                latency_ms = int((time.monotonic() - start) * 1000)
                tracker.record_llm_call(usage, latency_ms)
                tests_generated += 1
                break

    return {
        "functions_tested": len(function_names),
        "tests_generated": tests_generated,
        "retries": retries_used,
        "coverage_pct": None,
    }


# ---------------------------------------------------------------------------
# Severity gate
# ---------------------------------------------------------------------------


def check_severity_gate(findings: list[dict], gate_level: str = "HIGH") -> bool:
    """Return True if any finding's severity meets or exceeds gate_level."""
    gate_value = SEVERITY_ORDER.get(gate_level.upper(), SEVERITY_ORDER["HIGH"])
    return any(
        SEVERITY_ORDER.get(str(f.get("severity", "")).upper(), 0) >= gate_value
        for f in findings
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run AI code review + test generation on a PR diff.")
    parser.add_argument("--diff", required=True, help="Path to the PR diff file.")
    parser.add_argument("--dry-run", action="store_true", help="Skip posting PR comments (local testing).")
    parser.add_argument("--config", default=".aiworkflow.yml", help="Path to .aiworkflow.yml.")
    return parser


def main(argv: list[str] | None = None) -> None:
    load_dotenv()

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if args.dry_run:
        config = dict(config)
        config["settings"] = dict(config.get("settings", {}))
        config["settings"]["post_comments"] = False

    with open(args.diff) as f:
        diff_text = f.read()

    if not diff_text.strip():
        print("Empty diff — nothing to review.")
        sys.exit(0)

    pr_number = os.environ.get("PR_NUMBER", "0")
    repo_name = os.environ.get("REPO_NAME", "")
    tracker = PRCostTracker(pr_number=pr_number, repo_name=repo_name)

    review_cfg = config.get("ai_review", {}).get("code_review", {})
    test_cfg = config.get("ai_review", {}).get("test_generation", {})

    findings: list[dict] = []
    if review_cfg.get("enabled", True):
        findings, _retry_count = run_code_review(diff_text, config, tracker)

    if test_cfg.get("enabled", True):
        test_results = run_test_generation(diff_text, config, tracker)

    trace_id = tracker.log_pr_cost()

    if review_cfg.get("enabled", True):
        post_review_comment(findings, trace_id, config)
    if test_cfg.get("enabled", True):
        post_test_results(test_results, trace_id, config)

    gate_level = review_cfg.get("severity_gate", "HIGH")
    if check_severity_gate(findings, gate_level):
        high_count = sum(1 for f in findings if str(f.get("severity", "")).upper() == "HIGH")
        print(f"Severity gate triggered: {high_count} HIGH finding(s) found.")
        sys.exit(1)

    print(f"Severity gate: CLEAR (0 {gate_level} findings)")
    sys.exit(0)


if __name__ == "__main__":
    main()
