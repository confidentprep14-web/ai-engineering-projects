"""Incident report generation: prompt construction and response parsing.

build_incident_prompt() formats pre-filtered, timestamp-correlated log
lines into a single prompt. parse_incident_report() calls the LLM boundary
(get_json_completion) and validates/repairs the response so a malformed
or partial LLM reply never crashes the CLI — it degrades to a minimal
"Unable to determine" report instead.
"""

from correlator import TimestampedLine
from llm import get_json_completion

SYSTEM_PROMPT = """You are an SRE analyzing logs to produce an incident report.
Return ONLY valid JSON with this schema:
{
  "timeline": [{"timestamp": "...", "event": "..."}],
  "root_cause": {"hypothesis": "...", "confidence": 0.0-1.0, "evidence": []},
  "action_items": [{"priority": "HIGH|MEDIUM|LOW", "description": "..."}]
}"""

_MINIMAL_REPORT = {
    "timeline": [],
    "root_cause": {"hypothesis": "Unable to determine", "confidence": 0.0, "evidence": []},
    "action_items": [],
}


def _format_line(line: "TimestampedLine | str") -> str:
    if isinstance(line, TimestampedLine):
        if line.timestamp:
            return f"[{line.service}] {line.timestamp} {line.raw}"
        return f"[{line.service}] {line.raw}"
    return str(line)


def build_incident_prompt(lines: list, service_names: list[str]) -> str:
    """Format filtered log lines and service names into an LLM prompt."""
    formatted_lines = "\n".join(_format_line(line) for line in lines)
    services = ", ".join(service_names)

    return (
        f"Services involved: {services}\n\n"
        f"Log lines (pre-filtered for errors/warnings/stack traces):\n"
        f"{formatted_lines}\n\n"
        "Analyze these logs and return ONLY valid JSON matching the schema "
        "in the system prompt: a timeline of key events, a root cause "
        "hypothesis with a confidence score between 0.0 and 1.0 and "
        "supporting evidence, and a prioritized list of action items."
    )


def _minimal_report() -> dict:
    return {
        "timeline": [],
        "root_cause": {"hypothesis": "Unable to determine", "confidence": 0.0, "evidence": []},
        "action_items": [],
    }


def parse_incident_report(raw_response: str) -> dict:
    """Parse and validate an incident report from the LLM.

    raw_response is the prompt sent to get_json_completion (the function
    itself performs the LLM call + JSON parsing); this function validates
    and repairs the structured result. Falls back to a minimal report if
    the LLM call/JSON parse fails or required keys are missing.
    """
    try:
        parsed = get_json_completion(raw_response, system=SYSTEM_PROMPT)
    except ValueError:
        return _minimal_report()

    if not isinstance(parsed, dict):
        return _minimal_report()

    if not all(key in parsed for key in ("timeline", "root_cause", "action_items")):
        return _minimal_report()

    root_cause = parsed.get("root_cause")
    if not isinstance(root_cause, dict) or "confidence" not in root_cause or "hypothesis" not in root_cause:
        return _minimal_report()

    try:
        confidence = float(root_cause["confidence"])
    except (TypeError, ValueError):
        return _minimal_report()

    confidence = max(0.0, min(1.0, confidence))

    action_items = parsed.get("action_items") or []
    validated_action_items = []
    for item in action_items:
        if isinstance(item, dict) and "priority" in item and "description" in item:
            validated_action_items.append(item)

    return {
        "timeline": parsed.get("timeline") or [],
        "root_cause": {
            "hypothesis": root_cause.get("hypothesis", "Unable to determine"),
            "confidence": confidence,
            "evidence": root_cause.get("evidence") or [],
        },
        "action_items": validated_action_items,
    }


def summarise_logs(lines: list, service_names: list[str]) -> dict:
    """Orchestrate the full pipeline for a set of pre-filtered lines:
    build the prompt, call the LLM, and return the validated report."""
    prompt = build_incident_prompt(lines, service_names)
    return parse_incident_report(prompt)
