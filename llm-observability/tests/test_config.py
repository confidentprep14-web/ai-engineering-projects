"""Tests for src/config.py — threshold loading and cost estimation.

No LLM calls here at all; this module only reads env vars and does
arithmetic.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import estimate_cost, load_config  # noqa: E402


def test_cost_estimation_is_accurate(monkeypatch):
    """estimate_cost should match the documented formula using the
    per-1K rates configured via env vars."""
    monkeypatch.setenv("COST_PER_1K_INPUT_TOKENS", "0.00025")
    monkeypatch.setenv("COST_PER_1K_OUTPUT_TOKENS", "0.00125")

    rate_in = 0.00025
    rate_out = 0.00125
    expected = (1000 / 1000 * rate_in) + (500 / 1000 * rate_out)

    result = estimate_cost(input_tokens=1000, output_tokens=500)

    assert result == pytest.approx(expected, abs=1e-6)


def test_config_loads_thresholds_from_env(monkeypatch):
    """load_config() should reflect LATENCY_THRESHOLD_MS and
    COST_THRESHOLD_USD overrides from the environment."""
    monkeypatch.setenv("LATENCY_THRESHOLD_MS", "3000")
    monkeypatch.setenv("COST_THRESHOLD_USD", "0.05")

    config = load_config()

    assert config["latency_threshold_ms"] == 3000
    assert config["cost_threshold_usd"] == 0.05
