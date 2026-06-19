"""Tests for src/cost_estimator.py — estimating SageMaker training job cost from instance type + duration."""

import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import cost_estimator  # noqa: E402


def test_estimate_cost_known_value():
    assert cost_estimator.estimate_cost("ml.m5.large", 60) == 0.115
    assert cost_estimator.estimate_cost("ml.m5.xlarge", 30) == 0.115


def test_estimate_cost_unknown_instance_raises():
    with pytest.raises(ValueError):
        cost_estimator.estimate_cost("ml.p4d.24xlarge", 10)
