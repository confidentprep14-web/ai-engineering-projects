"""Thresholds and cost configuration, all sourced from environment
variables with sane defaults.

This is the only module that should know about the anomaly thresholds
and per-token pricing — tracer.py just calls load_config()/estimate_cost()
rather than reading os.environ directly.
"""

import os


def load_config() -> dict:
    """Read all threshold and exporter config from the environment.

    Returns a dict with numeric values already converted from the
    string env vars to float/int.
    """
    latency_threshold_ms = int(os.getenv("LATENCY_THRESHOLD_MS", "5000"))
    if latency_threshold_ms == 0:
        print("WARNING | config | LATENCY_THRESHOLD_MS=0 will flag every call")

    return {
        "latency_threshold_ms": latency_threshold_ms,
        "cost_threshold_usd": float(os.getenv("COST_THRESHOLD_USD", "0.01")),
        "token_ratio_threshold": float(os.getenv("TOKEN_RATIO_THRESHOLD", "10.0")),
        "cost_per_1k_input": float(os.getenv("COST_PER_1K_INPUT_TOKENS", "0.00025")),
        "cost_per_1k_output": float(os.getenv("COST_PER_1K_OUTPUT_TOKENS", "0.00125")),
        "otel_exporter": os.getenv("OTEL_EXPORTER", "console"),
        "jaeger_endpoint": os.getenv("JAEGER_ENDPOINT", "http://localhost:4317"),
        "service_name": os.getenv("OTEL_SERVICE_NAME", "llm-observability-demo"),
    }


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Estimate the USD cost of a call from its token counts using the
    per-1K rates configured in the environment.

    Rounded to 6 decimal places — token costs are fractions of a cent,
    so this keeps the dashboard readable without losing precision that
    matters for aggregation.
    """
    config = load_config()
    cost = (input_tokens / 1000) * config["cost_per_1k_input"] + (output_tokens / 1000) * config["cost_per_1k_output"]
    return round(cost, 6)
