import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cloudwatch_fetcher  # noqa: E402


def test_fetch_returns_zero_when_no_datapoints():
    mock_cw = MagicMock()
    mock_cw.get_metric_statistics.return_value = {"Datapoints": []}

    with patch("cloudwatch_fetcher.boto3.client", return_value=mock_cw):
        result = cloudwatch_fetcher.fetch_endpoint_metrics(
            "test-endpoint", days=7, region="us-east-1"
        )

    assert result["invocation_count"] == 0
    assert result["error_count"] == 0
    assert result["error_rate"] == 0.0


def test_fetch_does_not_raise_on_empty_response():
    mock_cw = MagicMock()
    mock_cw.get_metric_statistics.return_value = {"Datapoints": []}

    with patch("cloudwatch_fetcher.boto3.client", return_value=mock_cw):
        # Should not raise.
        cloudwatch_fetcher.fetch_endpoint_metrics("test-endpoint", days=7, region="us-east-1")
