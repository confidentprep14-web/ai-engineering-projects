"""Multi-service log correlation by timestamp.

Each pre-filtered line is tagged with the service it came from (the log
file's basename without extension) and parsed for a timestamp. Lines from
every service are then merged into a single list sorted by timestamp, so
the LLM sees a unified cross-service timeline in one prompt instead of
separate per-file blocks.
"""

import os
import re
from dataclasses import dataclass

ISO_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")
APACHE_PATTERN = re.compile(r"\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}")
EPOCH_PATTERN = re.compile(r"\d{10}\.\d+")


@dataclass
class TimestampedLine:
    raw: str
    timestamp: str | None  # ISO or common log format
    service: str  # Derived from filename (basename without extension)
    lineno: int


def parse_timestamp(line: str) -> str | None:
    """Return the first recognized timestamp substring in line, or None."""
    for pattern in (ISO_PATTERN, APACHE_PATTERN, EPOCH_PATTERN):
        match = pattern.search(line)
        if match:
            return match.group(0)
    return None


def _service_name(filepath: str) -> str:
    return os.path.splitext(os.path.basename(filepath))[0]


def merge_multi_service_logs(
    filepaths: list[str], filtered_lines_per_file: list[list[str]]
) -> list[TimestampedLine]:
    """Tag, parse, and merge filtered lines from multiple log files.

    Returns a flat list sorted by timestamp (lexicographic sort works for
    ISO-formatted timestamps); lines with no parseable timestamp sort to
    the end, in original encounter order.
    """
    timestamped: list[TimestampedLine] = []

    for filepath, lines in zip(filepaths, filtered_lines_per_file):
        service = _service_name(filepath)
        for lineno, raw in enumerate(lines, start=1):
            timestamped.append(
                TimestampedLine(
                    raw=raw,
                    timestamp=parse_timestamp(raw),
                    service=service,
                    lineno=lineno,
                )
            )

    with_ts = [item for item in timestamped if item.timestamp is not None]
    without_ts = [item for item in timestamped if item.timestamp is None]
    with_ts.sort(key=lambda item: item.timestamp)

    return with_ts + without_ts
