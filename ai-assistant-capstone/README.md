# Full AI Assistant (Capstone)

A deployed AI assistant combining RAG over uploaded documents, tool use for live data,
context window management, and streaming responses — with an eval suite that runs
against the live endpoint.

> Part of [Path 1 — AI Engineering Fundamentals](https://confidentprep.com/paths/path-1) on Confident Prep — see the full curriculum and how this project fits in.

## Deployment status

**Status: partially verified locally — needs AWS credentials and an LLM API key for
the rest.** This environment has no AWS account configured (`aws sts get-caller-identity`
fails here) and no LLM API key configured. What *was* verified without either:

- `docker build -t ai-assistant-capstone .` — runs successfully end-to-end against the
  real `public.ecr.aws/lambda/python:3.12` base image, installing every dependency
  including `sentence-transformers`, `faiss-cpu`, and `torch`.
- `docker compose up` — the container starts, passes its own healthcheck, and
  `GET /health` returns `{"status": "ok", ...}` with zero documents indexed. No LLM
  call happens on this path.
- `POST /documents` — verified for real against the running container: uploaded
  `sample_docs/test.txt`, it was chunked, embedded with `sentence-transformers`, and
  added to a real FAISS index. No LLM call happens on this path either — embeddings
  only.
- All 5 integration tests in `tests/` — 5/5 passing locally, LLM and FAISS calls
  mocked per the spec (see Tests section below).
- Every file in `src/` is under 200 lines.

What was **not** verified, and why:

- `POST /chat` and `POST /eval` require a real LLM call to produce output. With no
  `LLM_API_KEY` configured anywhere in this environment, these endpoints were not
  exercised live — same precedent as other projects in this repo that skip live-LLM
  smoke tests when no key is available. The code path is implemented and covered by
  mocked integration tests, but never run against a real provider.
- `scripts/deploy.sh` / `scripts/teardown.sh` (the actual AWS Lambda deployment) are
  implemented exactly per spec but were never run — they require IAM, ECR, Lambda,
  API Gateway, Secrets Manager, and CloudWatch access that does not exist in this
  build environment. If you have an AWS account and an LLM API key, follow Setup →
  Deploy → Teardown below; the scripts are ready to run as-is.

| Component | Status |
|---|---|
| `src/` (FastAPI app, RAG, tools, context, database) | Verified — 5/5 pytest passing locally |
| `Dockerfile` / `docker build` | Verified — builds successfully against the real Lambda base image |
| `docker compose up` + `GET /health` | Verified — container healthy, no LLM key needed |
| `POST /documents` (chunk + embed + FAISS) | Verified — real upload against the running container, no LLM key needed |
| `POST /chat` (RAG + tools + streaming) | Unverified — needs a real LLM API key |
| `POST /eval` (LLM-as-judge eval suite) | Unverified — needs a real LLM API key |
| `scripts/deploy.sh` | Unverified — needs AWS credentials |
| `scripts/teardown.sh` | Unverified — needs AWS credentials |

## Setup

```bash
cd ai-assistant-capstone
cp .env.example .env
pip install -r requirements.txt
```

## Run locally

```bash
docker compose up
python scripts/run_eval.py --base-url http://localhost:8000
```

## Deploy

```bash
bash scripts/deploy.sh
source .deployed.env
python scripts/run_eval.py --base-url $API_URL
```

## Teardown

```bash
bash scripts/teardown.sh
```

## Tests

```bash
pip install -r requirements.txt pytest
pytest tests/ -v
```

5/5 tests pass locally — covers `/health`, SSE content-type on `/chat` (LLM stream
mocked), `/metrics` structure, `/documents` upload (FAISS indexing mocked), and the
rate limiter's 429 response. No real LLM or FAISS calls happen in this test file, per
the spec.

## What to try next

- Upload a PDF of your company's documentation and ask questions about it
- Add a new tool (e.g., `fetch_url`) to the tool registry
- Tune the RAG score threshold and see how the retrieval_hit_rate changes
