import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cost_dashboard  # noqa: E402
import end_to_end_test  # noqa: E402

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")


def test_cost_dashboard_handles_zero_cost_services(capsys):
    costs = [
        {"service": "Amazon SageMaker", "cost_usd": 0.4230},
        {"service": "Amazon S3", "cost_usd": 0.0012},
    ]

    cost_dashboard.print_cost_table(costs)
    captured = capsys.readouterr()

    for service in cost_dashboard.DASHBOARD_SERVICES:
        assert service in captured.out

    assert "AWS Lambda" in captured.out
    assert "$0.0000" in captured.out


def test_endpoint_predictions_are_valid_probabilities():
    mock_runtime = MagicMock()
    mock_body = MagicMock()
    mock_body.read.return_value = b"0.75"
    mock_runtime.invoke_endpoint.return_value = {"Body": mock_body}

    data_path = os.path.join(os.path.dirname(__file__), "..", "..", "model-monitoring", "data", "adult.data")

    with patch("boto3.client", return_value=mock_runtime):
        result = end_to_end_test.verify_endpoint_predictions("mock-endpoint", data_path, n_samples=3)

    assert result["all_valid"] is True
    assert all(0.0 <= p <= 1.0 for p in result["predictions"])


def test_runbook_has_at_least_four_failure_scenarios():
    with open(os.path.join(DOCS_DIR, "runbook.md")) as f:
        content = f.read()

    assert content.count("## Failure Scenario") >= 4


def test_architecture_md_has_mermaid_diagram():
    with open(os.path.join(DOCS_DIR, "architecture.md")) as f:
        content = f.read()

    assert "```mermaid" in content
    assert "graph" in content
