"""Markdown formatting for the final incident report."""


def format_markdown_report(report: dict, service_names: list[str], reduction_stats: dict) -> str:
    """Render a parsed incident report dict as a markdown document.

    reduction_stats is {"total": int, "filtered": int, "reduction_pct": float}.
    """
    lines = ["# Incident Report", ""]

    lines.append("## Services Involved")
    for service in service_names:
        lines.append(f"- {service}")
    lines.append("")

    lines.append("## Pre-filter Stats")
    lines.append("| Total lines | Filtered lines | Reduction % |")
    lines.append("|---|---|---|")
    lines.append(
        f"| {reduction_stats.get('total', 0)} | {reduction_stats.get('filtered', 0)} "
        f"| {reduction_stats.get('reduction_pct', 0.0)}% |"
    )
    lines.append("")

    lines.append("## Timeline")
    timeline = report.get("timeline") or []
    if timeline:
        for event in timeline:
            lines.append(f"- `{event.get('timestamp', '?')}` — {event.get('event', '')}")
    else:
        lines.append("- No timeline events identified.")
    lines.append("")

    root_cause = report.get("root_cause") or {}
    lines.append("## Root Cause")
    lines.append(f"**Hypothesis:** {root_cause.get('hypothesis', 'Unable to determine')}")
    confidence = root_cause.get("confidence", 0.0)
    lines.append(f"**Confidence:** {confidence * 100:.0f}%")
    evidence = root_cause.get("evidence") or []
    if evidence:
        lines.append("**Evidence:**")
        for item in evidence:
            lines.append(f"- {item}")
    lines.append("")

    lines.append("## Action Items")
    action_items = report.get("action_items") or []
    if action_items:
        for idx, item in enumerate(action_items, start=1):
            priority = item.get("priority", "MEDIUM")
            description = item.get("description", "")
            lines.append(f"{idx}. **[{priority}]** {description}")
    else:
        lines.append("- No action items identified.")
    lines.append("")

    return "\n".join(lines)
