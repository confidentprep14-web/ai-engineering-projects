import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import lambda_evaluator  # noqa: E402


def test_evaluate_improvement_returns_deploy_true_when_above_threshold():
    result = lambda_evaluator.evaluate_improvement(new_auc=0.895, baseline_auc=0.880, threshold=0.01)

    assert result["deploy"] is True
    assert result["delta"] == pytest.approx(0.015, abs=0.001)


def test_evaluate_improvement_returns_deploy_false_when_at_threshold():
    result = lambda_evaluator.evaluate_improvement(new_auc=0.890, baseline_auc=0.880, threshold=0.01)

    assert result["deploy"] is False  # delta = 0.010, not strictly > 0.01


def test_evaluate_improvement_returns_deploy_false_when_metrics_unavailable():
    result = lambda_evaluator.evaluate_improvement(new_auc=None, baseline_auc=0.880)

    assert result["deploy"] is False
    assert result["reason"] == "metrics unavailable"


def test_get_baseline_auc_uses_correct_ssm_path():
    mock_ssm = MagicMock()
    mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "0.883"}}

    with patch("boto3.client", return_value=mock_ssm):
        result = lambda_evaluator.get_baseline_auc("/p3-11/baseline/val_auc", "us-east-1")

    mock_ssm.get_parameter.assert_called_once_with(Name="/p3-11/baseline/val_auc", WithDecryption=False)
    assert result == 0.883
