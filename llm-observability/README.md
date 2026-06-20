# LLM Observability

OpenTelemetry-based observability wrapper for LLM calls. Records model, tokens, latency, and cost per call. Flags anomalies. Exports to terminal dashboard or Jaeger.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your API key

# Terminal dashboard (no Docker needed)
python src/main.py --requests 20

# With Jaeger (requires Docker)
docker compose up -d
OTEL_EXPORTER=jaeger python src/main.py --requests 20
# Open http://localhost:16686
```

## Span attributes

Every LLM call gets an OTEL span with:

| Attribute | Example |
|---|---|
| `llm.model` | `claude-3-5-haiku-20241022` |
| `llm.provider` | `anthropic` |
| `llm.prompt_tokens` | `128` |
| `llm.completion_tokens` | `64` |
| `llm.latency_ms` | `342` |
| `llm.cost_usd` | `0.000048` |
| `llm.trace_id` | `a1b2c3d4...` |

## Anomaly thresholds

Set in `.env`:
- `LATENCY_THRESHOLD_MS` — warn if a call takes longer (default 5000ms)
- `COST_THRESHOLD_USD` — warn if a single call costs more (default $0.01)
- `TOKEN_RATIO_THRESHOLD` — warn if output/input ratio is unusual (default 10.0)

## Running tests

```bash
pytest tests/ -v
```

## Note on the live LLM path

All 6 unit tests in `tests/` mock `llm.get_completion` directly — they
exercise the OTEL span attributes, anomaly flagging, dashboard
accumulation, and trace ID format without ever calling a real model
(Test 1 does use a real OpenTelemetry `InMemorySpanExporter`, since only
the LLM call itself needs to be mocked). An actual end-to-end run of
`python src/main.py --requests 20` requires a configured
`ANTHROPIC_API_KEY` (or `OPENAI_API_KEY` / a running Ollama instance) and
was not exercised live in this build — there is no LLM API key
configured in this environment.

The optional Jaeger Docker Compose path (`docker compose up -d`) was
verified locally: the Jaeger UI (port 16686) and OTLP gRPC endpoint
(port 4317) both came up successfully, then the container was torn down.
