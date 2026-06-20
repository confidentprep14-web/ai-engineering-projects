import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cost_compare import calculate_batch_cost, format_comparison  # noqa: E402


def test_batch_cost_correct_for_known_inputs():
    assert calculate_batch_cost("ml.m5.large", 60) == 0.115
    assert calculate_batch_cost("ml.m5.xlarge", 30) == 0.115


def test_format_comparison_has_correct_column_count():
    batch_cheaper = format_comparison(0.02, 0.15, 10000)
    cheaper_line = [
        line for line in batch_cheaper.splitlines() if line.startswith("Cheaper option:")
    ][0]
    assert "Batch" in cheaper_line

    realtime_cheaper = format_comparison(0.50, 0.02, 100)
    cheaper_line = [
        line for line in realtime_cheaper.splitlines() if line.startswith("Cheaper option:")
    ][0]
    assert "Real-time" in cheaper_line
