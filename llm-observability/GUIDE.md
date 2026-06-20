# Build Guide — LLM Observability

## Step 1 — OTEL setup

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("llm-observability")
```

For Jaeger, swap `ConsoleSpanExporter` with `OTLPSpanExporter`:
```python
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
```

## Step 2 — Wrapping the LLM call

```python
import time
from uuid import uuid4

def traced_completion(self, prompt, system=""):
    trace_id = uuid4().hex
    with tracer.start_as_current_span("llm.completion") as span:
        start = time.monotonic()
        response, usage = llm.get_completion(prompt, system)
        latency_ms = int((time.monotonic() - start) * 1000)

        cost = estimate_cost(usage["input_tokens"], usage["output_tokens"])

        span.set_attribute("llm.trace_id", trace_id)
        span.set_attribute("llm.model", os.getenv("LLM_MODEL"))
        span.set_attribute("llm.latency_ms", latency_ms)
        span.set_attribute("llm.cost_usd", cost)
        span.set_attribute("llm.prompt_tokens", usage["input_tokens"])
        span.set_attribute("llm.completion_tokens", usage["output_tokens"])

        self.flag_anomalies({...})
        self._update_stats(latency_ms, cost, usage)

    return response, trace_id
```

## Step 3 — Anomaly flagging

Use Python's `logging` module for WARNING output — it's structured and can be redirected:

```python
import logging
logger = logging.getLogger("llm.anomaly")

if latency_ms > self.config["latency_threshold_ms"]:
    logger.warning(f"slow_call | trace_id={trace_id} | latency_ms={latency_ms}")
    self.stats["anomalies"] += 1
```

One gotcha worth knowing: if you attach a `logging.StreamHandler()` at
import time, it binds to whatever `sys.stderr` object exists at that
moment. Under pytest with `capsys`, the stream gets swapped per-test,
so a handler created at import time silently misses the swap and your
assertions on captured output see nothing. Either leave the logger
unconfigured (it falls back to logging's "last resort" handler, which
reads `sys.stderr` dynamically) and assert with `capsys`, or assert on
the record directly with pytest's `caplog` fixture — this project uses
`caplog`, since it's the tool actually designed for asserting on logger
output regardless of how handlers are wired.

## Step 4 — Terminal dashboard

Use `rich.table.Table` for the dashboard. Call `print_dashboard()` after all requests complete.

## Step 5 — Jaeger Docker Compose

```yaml
services:
  jaeger:
    image: jaegertracing/all-in-one:1.57
    ports:
      - "16686:16686"   # UI
      - "4317:4317"     # OTLP gRPC
```

## How to talk about this in an interview

**"Why OTEL instead of just logging?"**
> OTEL gives you trace context propagation — a trace ID that connects multiple spans across services. Logs are siloed per service. OTEL lets you follow a single request through a chain of LLM calls, embeddings, and database queries in one trace view.

**"How do you estimate cost without a billing API?"**
> I use the published per-token pricing from the provider's docs, stored in env vars. It's an estimate, not a bill, but it's accurate enough for anomaly detection and capacity planning. I store it per call so I can aggregate by time period.

**"What would you add for production?"**
> Histograms for latency distribution (P50/P95/P99), a Prometheus exporter for Grafana dashboards, and budget alerts via email/Slack when cumulative cost exceeds a daily threshold.
