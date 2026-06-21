import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import deploy_ab  # noqa: E402
import evaluate_winner  # noqa: E402
import shift_traffic  # noqa: E402


def test_traffic_weights_must_sum_to_10():
    with patch("deploy_ab.boto3.client") as mock_client:
        with pytest.raises(ValueError):
            deploy_ab.create_ab_endpoint_config(
                current_model="current-model",
                challenger_model="challenger-model",
                config_name="mock-config",
                instance_type="ml.t2.medium",
                current_weight=6,
                challenger_weight=6,
            )
        mock_client.assert_not_called()


def test_decision_rule_picks_challenger_when_improvement_exceeds_threshold():
    result = evaluate_winner.apply_decision_rule(
        challenger_auc=0.895, baseline_auc=0.880, threshold=0.01
    )

    assert result["deploy_challenger"] is True
    assert result["delta"] == pytest.approx(0.015, abs=0.001)


def test_decision_rule_keeps_current_when_improvement_below_threshold():
    result = evaluate_winner.apply_decision_rule(
        challenger_auc=0.885, baseline_auc=0.880, threshold=0.01
    )

    assert result["deploy_challenger"] is False


def test_shift_traffic_validates_weights():
    with pytest.raises(ValueError):
        shift_traffic.validate_weights(7, 2)
