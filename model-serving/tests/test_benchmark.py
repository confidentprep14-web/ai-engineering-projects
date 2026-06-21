import datetime
import os
import statistics
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import benchmark  # noqa: E402
import cost_logger  # noqa: E402


def test_benchmark_produces_exactly_n_measurements():
    with patch("benchmark.create_sample_payload", return_value="1,2,3"), \
         patch("benchmark.boto3.client"), \
         patch("benchmark.invoke_once", return_value=(50.0, "0.5")):
        results = benchmark.benchmark_endpoint(
            endpoint_name="mock", data_path="mock", n_invocations=100
        )

    assert results["n"] == 100
    assert len(results["latencies"]) == 100


def test_p95_always_less_than_or_equal_to_p99():
    import random

    rng = random.Random(42)
    latencies = [rng.uniform(5, 200) for _ in range(100)]

    quantiles = statistics.quantiles(latencies, n=100)
    p95 = quantiles[94]
    p99 = quantiles[98]

    assert p95 <= p99


def test_cost_logger_calculates_correctly():
    created_at_iso = "2025-06-16T12:00:00Z"
    created_at = datetime.datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))

    result = cost_logger.compute_cost("ml.t2.medium", created_at_iso)

    now = datetime.datetime.now(datetime.timezone.utc)
    expected_elapsed_hours = (now - created_at).total_seconds() / 3600
    expected_cost = expected_elapsed_hours * 0.056

    assert result["cost_usd"] == pytest.approx(expected_cost, abs=1e-3)
