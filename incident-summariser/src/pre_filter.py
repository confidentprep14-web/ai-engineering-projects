"""Streaming regex pre-filter for log files.

stream_filter_errors() never loads the full file into memory — it reads
line by line with a plain `for line in f` loop, which is the key property
that lets this pipeline handle log files up to 100MB. The filter keeps
only ERROR/WARN/Exception/Traceback/FATAL/CRITICAL lines plus any stack
trace lines that immediately follow them, which is what drives the large
token reduction before the LLM ever sees the data.
"""

ERROR_PATTERNS = ("ERROR", "WARN", "Exception", "Traceback", "FATAL", "CRITICAL")


def _is_error_line(line: str) -> bool:
    return any(pattern in line for pattern in ERROR_PATTERNS)


def _is_stack_trace_line(line: str) -> bool:
    return line.startswith((" ", "\t")) or line.strip().startswith("at ")


def stream_filter_errors(filepath: str) -> tuple[list[str], int]:
    """Stream a log file and return (filtered_lines, total_lines).

    filtered_lines contains every line that matches an error pattern,
    plus any immediately-following indented/'at '-prefixed stack trace
    lines. Streaming (not readlines()) keeps memory flat regardless of
    file size.
    """
    total = 0
    filtered: list[str] = []
    in_stack_trace = False

    with open(filepath, encoding="utf-8", errors="replace") as f:
        for line in f:
            total += 1
            stripped = line.rstrip("\n")

            if _is_error_line(stripped):
                filtered.append(stripped)
                in_stack_trace = True
            elif in_stack_trace and _is_stack_trace_line(stripped):
                filtered.append(stripped)
            else:
                in_stack_trace = False

    return filtered, total


def calculate_reduction_pct(total_lines: int, filtered_lines: int) -> float:
    """Return the percentage reduction from total_lines to filtered_lines.

    Returns 0.0 if total_lines is 0 (nothing to reduce).
    """
    if total_lines == 0:
        return 0.0
    return round((1 - filtered_lines / total_lines) * 100, 1)


def cap_filtered_lines(filtered_lines: list[str], max_lines: int) -> list[str]:
    """Cap filtered_lines to max_lines, appending a truncation note if cut."""
    if len(filtered_lines) <= max_lines:
        return filtered_lines
    return filtered_lines[:max_lines] + [f"[... truncated to {max_lines} lines ...]"]
