import os
import sys
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import verify_components  # noqa: E402


def test_verify_raises_clear_error_if_endpoint_missing():
    mock_sagemaker = MagicMock()
    mock_sagemaker.describe_endpoint.side_effect = ClientError(
        error_response={"Error": {"Code": "ValidationException", "Message": "Could not find endpoint"}},
        operation_name="DescribeEndpoint",
    )

    with patch("boto3.client", return_value=mock_sagemaker):
        result = verify_components.check_endpoint("nonexistent-endpoint", "us-east-1")

    assert result["ok"] is False
    assert result["status"] == "NOT_FOUND"


def test_verify_all_ok_is_false_when_any_component_missing():
    config = {
        "region": "us-east-1",
        "endpoint_name": "p3-07-adult-income-endpoint",
        "monitoring_schedule_name": "p3-10-hourly-monitor",
        "state_machine_arn": "arn:aws:states:us-east-1:123456789012:stateMachine:p3-11-ml-pipeline",
        "lambda_evaluator_name": "p3-11-evaluate-and-deploy",
    }

    with (
        patch("verify_components.check_endpoint", return_value={"name": config["endpoint_name"], "status": "InService", "ok": True}),
        patch("verify_components.check_monitoring_schedule", return_value={"name": config["monitoring_schedule_name"], "status": "Scheduled", "ok": True}),
        patch("verify_components.check_state_machine", return_value={"arn": config["state_machine_arn"], "name": "p3-11-ml-pipeline", "status": "ACTIVE", "ok": True}),
        patch("verify_components.check_lambda", return_value={"name": config["lambda_evaluator_name"], "runtime": "NOT_FOUND", "ok": False}),
    ):
        result = verify_components.verify_all(config)

    assert result["all_ok"] is False
