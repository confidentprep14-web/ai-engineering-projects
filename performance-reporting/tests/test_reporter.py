import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import reporter  # noqa: E402


def test_delta_is_positive_when_current_better_than_baseline():
    result = reporter.compute_delta(current_metric=0.895, baseline_metric=0.880)

    assert result["delta"] == pytest.approx(0.015, abs=0.001)
    assert result["direction"] == "improvement"


def test_delta_is_negative_when_current_worse():
    result = reporter.compute_delta(current_metric=0.860, baseline_metric=0.880)

    assert result["delta"] < 0
    assert result["direction"] == "regression"


def test_delta_returns_none_when_metrics_missing():
    result = reporter.compute_delta(current_metric=None, baseline_metric=0.880)

    assert result["delta"] is None
    assert result["direction"] == "unknown"


def test_report_markdown_contains_all_sections(tmp_path):
    mock_cw_metrics = {
        "endpoint_name": "test-endpoint",
        "period_days": 7,
        "invocation_count": 842,
        "model_latency_p50_ms": 23.4,
        "error_count": 3,
        "error_rate": 0.0036,
    }
    mock_live_eval = {
        "accuracy": 0.861,
        "auc": 0.871,
        "n_samples": 200,
        "endpoint_name": "test-endpoint",
    }
    mock_baseline = {
        "val_auc": 0.883,
        "val_accuracy": 0.872,
        "run_id": "fixture_run",
        "model_name": "adult-income-xgboost",
        "alias": "production",
    }

    output_path = tmp_path / "report.md"
    reporter.generate_weekly_report(mock_cw_metrics, mock_live_eval, mock_baseline, str(output_path))

    content = output_path.read_text()

    assert output_path.stat().st_size > 200
    assert "## Summary" in content
    assert "## Endpoint Health" in content
    assert "## Baseline (MLflow Registry)" in content
