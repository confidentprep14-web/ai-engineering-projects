"""Per-PR OTEL cost and latency tracking.

PRCostTracker accumulates token usage and latency across every LLM call
made during a single Action run (code review + test generation), then
emits ONE OTEL span per PR with the aggregate numbers. One span per PR
(not one per LLM call) keeps the trace readable and matches what you'd
actually want to query later: "what did this PR review cost?"
"""

import os
import uuid

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

SERVICE_NAME = "ai-pr-reviewer"


def _build_tracer_provider(exporter_kind: str) -> TracerProvider:
    """Build a TracerProvider wired to console or Jaeger (OTLP gRPC)."""
    resource = Resource.create({"service.name": SERVICE_NAME})
    provider = TracerProvider(resource=resource)

    if exporter_kind == "jaeger":
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            endpoint = os.environ.get("JAEGER_ENDPOINT", "http://localhost:4317")
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
            )
        except Exception as exc:  # noqa: BLE001 - observability must never fail the PR check
            print(f"Warning: could not configure OTLP exporter ({exc}); falling back to console.")
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    return provider


class PRCostTracker:
    """Accumulates LLM usage/latency for one PR and emits a single OTEL span."""

    def __init__(self, pr_number: str, repo_name: str, tracer_provider: TracerProvider | None = None):
        self.pr_number = pr_number
        self.repo_name = repo_name
        self.model = os.environ.get("LLM_MODEL", "")
        self.provider = os.environ.get("LLM_PROVIDER", "anthropic")

        exporter_kind = os.environ.get("OTEL_EXPORTER", "console")
        self._tracer_provider = tracer_provider or _build_tracer_provider(exporter_kind)
        self._tracer = self._tracer_provider.get_tracer(SERVICE_NAME)

        self.stats = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": 0,
            "calls": 0,
        }

    def record_llm_call(self, usage: dict, latency_ms: int) -> None:
        """Accumulate token/cost/latency stats for one LLM call."""
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        cost_per_1k_input = float(os.environ.get("COST_PER_1K_INPUT_TOKENS", "0.00025"))
        cost_per_1k_output = float(os.environ.get("COST_PER_1K_OUTPUT_TOKENS", "0.00125"))
        call_cost = (input_tokens / 1000) * cost_per_1k_input + (output_tokens / 1000) * cost_per_1k_output

        self.stats["input_tokens"] += input_tokens
        self.stats["output_tokens"] += output_tokens
        self.stats["cost_usd"] += call_cost
        self.stats["latency_ms"] += latency_ms
        self.stats["calls"] += 1

    def log_pr_cost(self) -> str:
        """Create the per-PR OTEL span, print the cost summary line, and
        return the generated trace_id. Never raises — an export failure
        must not fail the PR check."""
        trace_id = uuid.uuid4().hex

        try:
            with self._tracer.start_as_current_span("ai_review.pr") as span:
                span.set_attribute("pr.number", str(self.pr_number))
                span.set_attribute("pr.repo", self.repo_name)
                span.set_attribute("llm.model", self.model)
                span.set_attribute("llm.provider", self.provider)
                span.set_attribute("llm.total_input_tokens", self.stats["input_tokens"])
                span.set_attribute("llm.total_output_tokens", self.stats["output_tokens"])
                span.set_attribute("llm.total_cost_usd", self.stats["cost_usd"])
                span.set_attribute("llm.total_latency_ms", self.stats["latency_ms"])
                span.set_attribute("llm.calls", self.stats["calls"])
                span.set_attribute("trace_id", trace_id)
        except Exception as exc:  # noqa: BLE001 - OTEL export failures must not fail the PR check
            print(f"Warning: OTEL export failed ({exc}); continuing without it.")

        total_tokens = self.stats["input_tokens"] + self.stats["output_tokens"]
        print(
            f"PR Review Cost | pr={self.pr_number} | calls={self.stats['calls']} | "
            f"tokens={total_tokens:,} | cost=${self.stats['cost_usd']:.6f} | trace_id={trace_id}"
        )

        return trace_id
