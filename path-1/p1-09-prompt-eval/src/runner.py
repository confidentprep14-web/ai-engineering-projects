"""Test suite runner: loads YAML suites, fills prompt templates, calls the
LLM under test, and scores each response with the judge on every dimension.
"""
import time

import yaml

from src import judge as judge_module
from src import llm


def load_suite(yaml_path: str) -> dict:
    """Load and parse a YAML test suite file.

    Raises a clear, file-and-line-aware error on malformed YAML instead of
    letting a raw yaml.YAMLError traceback reach the user.
    """
    try:
        with open(yaml_path, "r") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse YAML suite '{yaml_path}': {exc}") from exc
    except FileNotFoundError as exc:
        raise ValueError(f"Test suite file not found: {yaml_path}") from exc


def run_test_case(test_case: dict, prompt_template: str, dimensions: list) -> dict:
    """Run one test case: fill the prompt, call the LLM, score every dimension.

    Returns a dict with the response, per-dimension scores, overall pass/fail,
    and latency in milliseconds. If the LLM call itself fails, the test case
    is marked failed with the error captured in "response" rather than
    raising and aborting the whole suite.
    """
    if "{input}" not in prompt_template:
        raise ValueError(
            "Prompt template is missing the required '{input}' placeholder"
        )

    filled_prompt = prompt_template.format(
        input=test_case["input"], context=test_case.get("context", "")
    )

    start = time.monotonic()
    try:
        response = llm.get_completion(filled_prompt)
    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "id": test_case["id"],
            "input": test_case["input"],
            "response": f"ERROR: {exc}",
            "scores": {},
            "passed": False,
            "latency_ms": latency_ms,
        }
    latency_ms = int((time.monotonic() - start) * 1000)

    scores = {}
    for dimension in dimensions:
        scores[dimension["name"]] = judge_module.score_response(
            response, test_case["input"], test_case.get("context", ""), dimension
        )

    passed = all(s["passed"] for s in scores.values()) if scores else False

    return {
        "id": test_case["id"],
        "input": test_case["input"],
        "response": response,
        "scores": scores,
        "passed": passed,
        "latency_ms": latency_ms,
    }


def run_suite(suite: dict, prompt_template: str) -> dict:
    """Run every test case in a suite and aggregate pass/fail summary stats."""
    dimensions = suite.get("scoring_dimensions", [])
    results = [
        run_test_case(tc, prompt_template, dimensions) for tc in suite["test_cases"]
    ]

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    pass_rate = round(passed / total, 4) if total else 0.0

    return {
        "suite_name": suite.get("suite_name", ""),
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": pass_rate,
        },
    }
