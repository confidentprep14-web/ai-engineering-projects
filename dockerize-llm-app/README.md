# Dockerize Your App

Packages the streaming chat API into a Docker container with a persistent SQLite
volume and health check. Runs identically on any machine with Docker installed.

## Prerequisites

- Docker Desktop (https://www.docker.com/products/docker-desktop/)
- An LLM API key (or Ollama running locally)

## Setup

```bash
cd dockerize-llm-app
cp .env.example .env
# Edit .env: set LLM_API_KEY (and LLM_PROVIDER if not anthropic)
```

## Run

```bash
# Start everything
docker compose up

# In another terminal — test it
curl http://localhost:8000/health
curl -N -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Say hello"}'

# Stop
docker compose down
```

Expected:
```
chat-api  | INFO:     Application startup complete.
chat-api  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

## Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

These are the same unit tests as the streaming chat API project — they confirm
the application logic (rate limiter, stats aggregation, SQLite logging) still
works correctly with `DATABASE_PATH` pointed at the `/data` volume mount.

## Verify everything works

```bash
bash scripts/verify.sh
```

This runs the operational checks: image build, container health, an SSE chat
request, and a stats check — all against the running container, not mocks.

## What to try next

- Check image size: `docker images chat-api` — should be under 500MB
- Change RATE_LIMIT_REQUESTS_PER_MINUTE=1 in .env, restart, try 2 rapid requests
- This image is what you'll deploy to Lambda in the next project
