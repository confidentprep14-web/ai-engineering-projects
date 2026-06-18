# Multi-step LLM Pipeline

A 3-stage pipeline that extracts entities from any topic, enriches them with
live Wikipedia data, and synthesises a professional briefing document.

## What this is

Most useful AI features are not one LLM call — they are a fixed sequence of
calls where each stage transforms or enriches the data before the next stage
runs. This project makes that sequence explicit: `extract_entities` (LLM) →
`fetch_entity_summaries` (live HTTP) → `synthesise_briefing` (LLM). Each stage
has a narrow input/output contract, fails independently with a clear error,
and is timed on its own so you can see exactly where the pipeline spends its
time — usually the Wikipedia round-trips, not the LLM calls.

## Setup

```bash
cd p1-05-multi-step-llm-pipeline
cp .env.example .env
# Edit .env: set LLM_PROVIDER and LLM_API_KEY
pip install -r requirements.txt
```

## Run

```bash
python src/main.py "The James Webb Space Telescope"
python src/main.py "Kubernetes" --output k8s_briefing.md
```

Expected output:
```
Running pipeline for: "The James Webb Space Telescope"

[Stage 1/3] Extracting entities... ✓ 5 entities (312ms)
[Stage 2/3] Fetching Wikipedia data... ✓ 5/5 found (1,102ms)
[Stage 3/3] Synthesising briefing... ✓ done (2,140ms)

Total: 3,554ms

# Briefing: The James Webb Space Telescope
The James Webb Space Telescope (JWST) is a space telescope designed to...
```

## Tests

```bash
pytest tests/ -v
```

Five tests verify entity extraction parsing (including malformed JSON),
Wikipedia 404 and timeout handling, and per-stage latency tracking on the
pipeline result. No API key required — every test that would otherwise call
the LLM or Wikipedia mocks that boundary and exercises the real parsing and
control-flow logic around it.

## What to try next

- Add a Stage 4: generate 3 follow-up questions about the briefing
- Add a cache for Wikipedia results so the same entity isn't fetched twice
- Try topic = a company name and use the briefing for interview prep
