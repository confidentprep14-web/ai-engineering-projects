"""Thin CLI-facing wrapper around validator's coverage summary.

Kept as its own module (rather than folded into main.py) so the
--coverage code path is independently testable and main.py stays a
pure orchestration layer.
"""

from validator import print_coverage_summary as _print_coverage_summary


def print_coverage_summary(source_file: str, test_file: str) -> None:
    """Print a pytest-cov report for test_file against source_file."""
    _print_coverage_summary(source_file, test_file)
