"""LLMTracer — instruments every LLM call with an OTEL span carrying
model, tokens, latency, cost, provider, and trace ID; accumulates
dashboard stats; and flags anomalies via the logging module.
"""

import logging
import os
import time
from uuid import uuid4

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from rich.console import Console
from rich.table import Table

from config import estimate_cost, load_config
from llm import get_completion

logger = logging.getLogger("llm.anomaly")
logger.setLevel(logging.WARNING)
# No handler is attached here deliberately: with no handler, logging
# falls back to its "last resort" handler, which writes to whatever
# sys.stderr currently is at call time. That keeps this work under
# both plain CLI runs and pytest's stream capture (capsys), which
# swaps sys.stderr per-test — a handler bound at import time would
# hold a stale stream reference and silently miss capsys.


class LLMTracer:
    """Wraps LLM calls with OTEL tracing, cost/latency accounting, and
    anomaly detection."""

    def __init__(self, service_name: str = None):
        self.config = load_config()
        self.service_name = service_name or self.config["service_name"]

        provider = TracerProvider(resource=Resource.create({SERVICE_NAME: self.service_name}))

        if self.config["otel_exporter"] == "jaeger":
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

                exporter = OTLPSpanExporter(endpoint=self.config["jaeger_endpoint"], insecure=True)
            except Exception as exc:  # noqa: BLE001 - any connector/import failure falls back to console
                logging.getLogger("llm.tracer").warning(
                    "Could not initialize Jaeger exporter (%s); falling back to console exporter", exc
                )
                exporter = ConsoleSpanExporter()
        else:
            exporter = ConsoleSpanExporter()

        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        self._tracer = trace.get_tracer("llm-observability")

        self.stats = {
            "calls": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_latency_ms": 0,
            "anomalies": 0,
        }

    def traced_completion(self, prompt: str, system: str = "") -> tuple[str, str]:
        """Call the LLM inside an OTEL span, recording latency/cost/
        token attributes, updating dashboard stats, and checking for
        anomalies. Returns (response_text, trace_id)."""
        trace_id = uuid4().hex

        with self._tracer.start_as_current_span("llm.completion") as span:
            start = time.monotonic()
            response_text, usage = get_completion(prompt, system)
            latency_ms = int((time.monotonic() - start) * 1000)

            input_tokens = usage["input_tokens"]
            output_tokens = usage["output_tokens"]
            cost_usd = estimate_cost(input_tokens, output_tokens)

            model = os.getenv("LLM_MODEL", "")
            provider_name = os.getenv("LLM_PROVIDER", "anthropic")

            span.set_attribute("llm.model", model)
            span.set_attribute("llm.provider", provider_name)
            span.set_attribute("llm.prompt_tokens", input_tokens)
            span.set_attribute("llm.completion_tokens", output_tokens)
            span.set_attribute("llm.latency_ms", latency_ms)
            span.set_attribute("llm.cost_usd", cost_usd)
            span.set_attribute("llm.trace_id", trace_id)

            self._update_stats(latency_ms, cost_usd, input_tokens, output_tokens)
            self.flag_anomalies(
                {
                    "latency_ms": latency_ms,
                    "cost_usd": cost_usd,
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "trace_id": trace_id,
                }
            )

        return response_text, trace_id

    def _update_stats(self, latency_ms: int, cost_usd: float, input_tokens: int, output_tokens: int) -> None:
        self.stats["calls"] += 1
        self.stats["total_tokens"] += input_tokens + output_tokens
        self.stats["total_cost_usd"] += cost_usd
        self.stats["total_latency_ms"] += latency_ms

    def flag_anomalies(self, data: dict) -> None:
        """Log a WARNING for each threshold exceeded by this call's
        data, and increment self.stats["anomalies"] per warning."""
        trace_id = data["trace_id"]
        latency_ms = data["latency_ms"]
        cost_usd = data["cost_usd"]
        prompt_tokens = data["prompt_tokens"]
        completion_tokens = data["completion_tokens"]

        if latency_ms > self.config["latency_threshold_ms"]:
            logger.warning("WARNING | slow_call | trace_id=%s | latency_ms=%s", trace_id, latency_ms)
            self.stats["anomalies"] += 1

        if cost_usd > self.config["cost_threshold_usd"]:
            logger.warning("WARNING | high_cost | trace_id=%s | cost_usd=%s", trace_id, cost_usd)
            self.stats["anomalies"] += 1

        token_ratio = completion_tokens / max(prompt_tokens, 1)
        if token_ratio > self.config["token_ratio_threshold"]:
            logger.warning("WARNING | high_token_ratio | trace_id=%s | ratio=%.2f", trace_id, token_ratio)
            self.stats["anomalies"] += 1

    def get_dashboard_stats(self) -> dict:
        """Return a copy of self.stats with derived averages added."""
        stats = dict(self.stats)
        calls = stats["calls"]
        stats["avg_latency_ms"] = (stats["total_latency_ms"] / calls) if calls else 0.0
        stats["avg_cost_usd"] = (stats["total_cost_usd"] / calls) if calls else 0.0
        return stats

    def print_dashboard(self) -> None:
        """Print a formatted dashboard table to stdout via rich."""
        stats = self.get_dashboard_stats()

        table = Table(title="LLM Observability Dashboard", show_header=False)
        table.add_column("metric")
        table.add_column("value")
        table.add_row("Calls", str(stats["calls"]))
        table.add_row("Total tokens", f"{stats['total_tokens']:,}")
        table.add_row("Avg latency", f"{stats['avg_latency_ms']:.0f} ms")
        table.add_row("Total cost", f"${stats['total_cost_usd']:.4f}")
        table.add_row("Anomalies", str(stats["anomalies"]))

        Console().print(table)
