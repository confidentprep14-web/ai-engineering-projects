# Incident Summariser

Converts noisy log files (up to 100MB) into structured incident reports with timeline, root cause, and action items — using pre-filtering to reduce token usage before any LLM call.

> Part of [Path 2 — AI-Augmented Engineering](https://confidentprep.com/paths/path-2) on Confident Prep — see the full curriculum and how this project fits in.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your API key

# Single log file
python src/main.py app.log

# Multi-service correlation (up to 5 files)
python src/main.py app.log db.log auth.log --output report.md
```

## Output sections

1. **Timeline** — ordered list of key events with timestamps
2. **Root Cause** — hypothesis with confidence score (0-1) and evidence
3. **Action Items** — prioritized list (HIGH/MEDIUM/LOW)
4. **Pre-filter Stats** — how many lines were filtered and token reduction %

## Pre-filtering strategy

```
100MB log → stream read → regex filter (ERROR/WARN/Exception/Traceback)
          → stack trace capture → cap at MAX_FILTERED_LINES
          → LLM call (10-50x fewer tokens)
```

## Running tests

```bash
pytest tests/ -v
```

## Note on the live LLM path

The unit tests in `tests/` mock `get_json_completion` directly — they test
the pre-filter, timestamp correlation, and report parsing/clamping logic
without ever calling a real model. An actual end-to-end run of
`python src/main.py <log_file>` requires a configured `ANTHROPIC_API_KEY`
(or `OPENAI_API_KEY` / a running Ollama instance) and was not exercised
live in this build — there is no LLM API key configured in this
environment. The deterministic part of the pipeline (streaming pre-filter,
reduction-percentage logging, multi-file timestamp correlation, and line
capping) was verified directly: on `tests/fixtures/app.log` (1000 lines)
the pre-filter reduces to 158 lines, an 84.2% reduction.
