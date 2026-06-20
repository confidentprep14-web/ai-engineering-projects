"""Tests for src/tracer.py — span attributes, anomaly flagging, and the
dashboard accumulator.

`llm.get_completion` is mocked in every test here (no network, no API
key needed). OTEL itself is NOT mocked — Test 1 uses a real
InMemorySpanExporter so we assert against genuine span attributes
produced by the OTEL SDK, not a stand-in.
"""

import re
import sys
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tracer import LLMTracer  # noqa: E402


def test_span_attributes_include_all_required_fields(mocker, monkeypatch):
    """traced_completion() should emit one OTEL span carrying model,
    provider, token counts, latency, cost, and trace ID."""
    monkeypatch.setenv("OTEL_EXPORTER", "console")
    monkeypatch.setenv("LLM_MODEL", "claude-3-5-haiku-20241022")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")

    mocker.patch("tracer.get_completion", return_value=("response", {"input_tokens": 100, "output_tokens": 50}))

    # Real in-memory exporter wired into a fresh provider so we capture
    # genuine spans produced by the OTEL SDK, not a mock of OTEL itself.
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    mocker.patch.object(trace, "get_tracer_provider", return_value=provider)

    tracer = LLMTracer(service_name="test-service")
    mocker.patch.object(tracer, "_tracer", provider.get_tracer("llm-observability"))

    tracer.traced_completion("test prompt")

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    attrs = spans[0].attributes

    for key in (
        "llm.model",
        "llm.provider",
        "llm.prompt_tokens",
        "llm.completion_tokens",
        "llm.latency_ms",
        "llm.cost_usd",
        "llm.trace_id",
    ):
        assert key in attrs


def test_anomaly_flagging_triggers_at_threshold(monkeypatch, caplog):
    """flag_anomalies should log a WARNING and increment the anomaly
    counter when latency exceeds LATENCY_THRESHOLD_MS.

    Uses caplog (not capsys) to capture the log record: pytest's
    logging plugin attaches its own handler to the root logger, which
    intercepts records before they would otherwise reach a stream
    capsys can see — caplog is the correct tool for asserting on
    logger output specifically.
    """
    monkeypatch.setenv("LATENCY_THRESHOLD_MS", "100")

    tracer = LLMTracer(service_name="test-service")
    with caplog.at_level("WARNING", logger="llm.anomaly"):
        tracer.flag_anomalies(
            {
                "latency_ms": 5000,
                "cost_usd": 0.0,
                "prompt_tokens": 10,
                "completion_tokens": 10,
                "trace_id": "abc123",
            }
        )

    assert tracer.stats["anomalies"] == 1
    assert "WARNING" in caplog.text
    assert "slow_call" in caplog.text


def test_terminal_dashboard_accumulates_correctly(mocker):
    """get_dashboard_stats should report totals matching 3 simulated
    calls with known latency and token values."""
    tracer = LLMTracer(service_name="test-service")

    calls = [
        {"latency_ms": 100, "input_tokens": 50, "output_tokens": 20, "cost_usd": 0.001},
        {"latency_ms": 200, "input_tokens": 60, "output_tokens": 30, "cost_usd": 0.002},
        {"latency_ms": 300, "input_tokens": 70, "output_tokens": 40, "cost_usd": 0.003},
    ]

    for call in calls:
        mocker.patch(
            "tracer.get_completion",
            return_value=("response", {"input_tokens": call["input_tokens"], "output_tokens": call["output_tokens"]}),
        )
        mocker.patch("tracer.time.monotonic", side_effect=[0.0, call["latency_ms"] / 1000])
        tracer.traced_completion("prompt")

    stats = tracer.get_dashboard_stats()

    expected_total_tokens = sum(c["input_tokens"] + c["output_tokens"] for c in calls)

    assert stats["calls"] == 3
    assert stats["total_tokens"] == expected_total_tokens


def test_trace_id_is_uuid_hex_format(mocker):
    """The trace ID returned by traced_completion should be a 32-char
    lowercase hex string (uuid4().hex format, no dashes)."""
    mocker.patch("tracer.get_completion", return_value=("hi there", {"input_tokens": 5, "output_tokens": 5}))

    tracer = LLMTracer(service_name="test-service")
    _, trace_id = tracer.traced_completion("hello")

    assert re.match(r"^[0-9a-f]{32}$", trace_id)
