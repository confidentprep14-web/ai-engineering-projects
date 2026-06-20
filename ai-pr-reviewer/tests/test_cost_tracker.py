"""Tests for cost_tracker.py: PRCostTracker accumulates usage and emits an OTEL span."""

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)

from cost_tracker import PRCostTracker  # noqa: E402


# ---------------------------------------------------------------------------
# Test 3 — Cost tracker records span attributes
# ---------------------------------------------------------------------------


def test_cost_tracker_records_span_attributes(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER", "console")
    monkeypatch.setenv("LLM_MODEL", "claude-3-5-haiku-20241022")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("COST_PER_1K_INPUT_TOKENS", "0.00025")
    monkeypatch.setenv("COST_PER_1K_OUTPUT_TOKENS", "0.00125")

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    tracker = PRCostTracker(pr_number="42", repo_name="owner/repo", tracer_provider=provider)

    tracker.record_llm_call({"input_tokens": 100, "output_tokens": 50}, latency_ms=200)
    tracker.record_llm_call({"input_tokens": 200, "output_tokens": 75}, latency_ms=300)

    trace_id = tracker.log_pr_cost()

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    attrs = span.attributes
    assert attrs["pr.number"] == "42"
    assert attrs["llm.calls"] == 2
    assert attrs["llm.model"] == "claude-3-5-haiku-20241022"
    assert attrs["trace_id"] == trace_id
    assert attrs["llm.total_cost_usd"] > 0
