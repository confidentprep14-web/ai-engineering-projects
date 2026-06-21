"""Fetch SageMaker endpoint health metrics (invocations, latency, errors)
from CloudWatch.

This module only reads CloudWatch's pre-aggregated statistics for an
endpoint -- it never invokes the endpoint itself (that is live_evaluator.py's
job). It answers "is the endpoint healthy" (traffic, latency, errors), not
"is the model accurate" (which CloudWatch has no visibility into).
"""
from datetime import datetime, timedelta

import boto3


def fetch_endpoint_metrics(endpoint_name: str, days: int, region: str) -> dict:
    """Fetch InvocationCount, ModelLatency, and Errors for `endpoint_name`
    over the last `days` days, aggregated as a single Sum/Average over the
    entire window (Period = days * 86400 seconds).

    Returns:
        {
            "endpoint_name": str,
            "period_days": int,
            "invocation_count": int,
            "model_latency_p50_ms": float,
            "error_count": int,
            "error_rate": float,
        }

    Never raises on an empty CloudWatch response (no datapoints) -- a new
    endpoint or an endpoint with no traffic in the window is a normal case,
    not an error.
    """
    cw = boto3.client("cloudwatch", region_name=region)

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)
    period = days * 86400

    invocation_count = _fetch_statistic(
        cw, endpoint_name, "InvocationCount", start_time, end_time, period, "Sum"
    )
    model_latency_us = _fetch_statistic(
        cw, endpoint_name, "ModelLatency", start_time, end_time, period, "Average"
    )
    error_count = _fetch_statistic(
        cw, endpoint_name, "Errors", start_time, end_time, period, "Sum"
    )

    invocation_count = int(invocation_count)
    error_count = int(error_count)
    model_latency_p50_ms = model_latency_us / 1000.0 if model_latency_us else 0.0

    if invocation_count == 0 and error_count == 0:
        error_rate = 0.0
    else:
        error_rate = error_count / max(invocation_count, 1)

    return {
        "endpoint_name": endpoint_name,
        "period_days": days,
        "invocation_count": invocation_count,
        "model_latency_p50_ms": model_latency_p50_ms,
        "error_count": error_count,
        "error_rate": error_rate,
    }


def _fetch_statistic(
    cw_client,
    endpoint_name: str,
    metric_name: str,
    start_time: datetime,
    end_time: datetime,
    period: int,
    statistic: str,
) -> float:
    """Call get_metric_statistics for a single metric and return the
    requested statistic from the (at most one, given the full-window period)
    datapoint, or 0.0 if there are no datapoints.
    """
    response = cw_client.get_metric_statistics(
        Namespace="AWS/SageMaker",
        MetricName=metric_name,
        Dimensions=[{"Name": "EndpointName", "Value": endpoint_name}],
        StartTime=start_time,
        EndTime=end_time,
        Period=period,
        Statistics=[statistic],
    )

    datapoints = response.get("Datapoints", [])
    if not datapoints:
        return 0.0

    return sum(dp.get(statistic, 0.0) for dp in datapoints)
