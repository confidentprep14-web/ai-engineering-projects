"""CLI entry point — streams and pre-filters one or more log files,
correlates them by timestamp when more than one is given, sends the
filtered/capped lines to an LLM for incident analysis, and prints or
writes a markdown incident report.
"""

import argparse
import os
import sys

from correlator import merge_multi_service_logs
from dotenv import load_dotenv
from pre_filter import cap_filtered_lines, calculate_reduction_pct, stream_filter_errors
from reporter import format_markdown_report
from summariser import build_incident_prompt, parse_incident_report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarise one or more log files into a structured incident report."
    )
    parser.add_argument(
        "log_files",
        nargs="+",
        help="Path(s) to log file(s) to analyze (1 to 5 files).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write the markdown report to this path instead of printing to stdout.",
    )
    return parser


def _service_name(filepath: str) -> str:
    return os.path.splitext(os.path.basename(filepath))[0]


def run(log_files: list[str], output: str | None) -> int:
    load_dotenv()

    max_log_files = int(os.environ.get("MAX_LOG_FILES", "5"))
    if len(log_files) > max_log_files:
        print(f"Maximum {max_log_files} log files supported")
        return 1

    max_filtered_lines = int(os.environ.get("MAX_FILTERED_LINES", "500"))

    filtered_per_file = []
    totals = []
    any_errors_found = False

    for filepath in log_files:
        service = _service_name(filepath)
        filtered, total = stream_filter_errors(filepath)
        totals.append(total)

        if total == 0:
            print(f"No lines in {filepath}")
            filtered_per_file.append([])
            continue

        pct = calculate_reduction_pct(total, len(filtered))
        print(f"[{service}] {total} lines → {len(filtered)} filtered ({pct}% reduction)")

        if filtered:
            any_errors_found = True
        filtered_per_file.append(filtered)

    service_names = [_service_name(f) for f in log_files]

    if not any_errors_found:
        print("No error lines found — generating summary from all lines (capped)")
        # Re-read raw lines (capped) since pre-filtering found nothing to work with.
        raw_lines_per_file = []
        for filepath in log_files:
            with open(filepath, encoding="utf-8", errors="replace") as f:
                raw_lines_per_file.append([line.rstrip("\n") for line in f])
        filtered_per_file = raw_lines_per_file

    if len(log_files) > 1:
        merged_lines = merge_multi_service_logs(log_files, filtered_per_file)
    else:
        merged_lines = filtered_per_file[0] if filtered_per_file else []

    capped_lines = cap_filtered_lines(merged_lines, max_filtered_lines)

    prompt = build_incident_prompt(capped_lines, service_names)
    report = parse_incident_report(prompt)

    total_lines = sum(totals)
    total_filtered = sum(len(f) for f in filtered_per_file)
    reduction_stats = {
        "total": total_lines,
        "filtered": total_filtered,
        "reduction_pct": calculate_reduction_pct(total_lines, total_filtered),
    }

    markdown_report = format_markdown_report(report, service_names, reduction_stats)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(markdown_report)
        print(f"Report written to {output}")
    else:
        print(markdown_report)

    return 0


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    return run(args.log_files, args.output)


if __name__ == "__main__":
    sys.exit(main())
