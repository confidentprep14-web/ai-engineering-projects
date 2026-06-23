# Streaming Chat API

A FastAPI server that streams LLM responses over SSE, tracks token usage and cost
per request in SQLite, and rate-limits callers per IP.

> Part of [Path 1 — AI Engineering Fundamentals](https://confidentprep.com/paths/path-1) on Confident Prep — see the full curriculum and how this project fits in.

## What this is

Every production LLM endpoint needs the same three things: a way to stream
tokens to the client as they're generated, a record of what each request
cost, and a guard against any one caller exhausting the quota. This project
is a minimal but real implementation of all three: `/chat` streams via
Server-Sent Events, every request's token count/cost/latency lands in
SQLite, and a sliding-window rate limiter returns `429` with a `Retry-After`
header once a client IP goes over budget.

## Setup

```bash
cd p1-08-streaming-chat-api
cp .env.example .env
pip install -r requirements.txt
```

## Run

```bash
uvicorn src.main:app --reload
```

Test with curl:
```bash
# Stream a response
curl -N -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Tell me about black holes"}' \
     -H "Accept: text/event-stream"

# Check stats
curl http://localhost:8000/stats
```

## Tests

```bash
pytest tests/ -v
```

## What to try next

- Add an API key header for authentication
- Add the persistent agent from p1-07 as the chat backend
- Deploy this with Docker (see p1-10-dockerize)
