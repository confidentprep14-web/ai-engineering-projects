# AI Engineering Projects

36 hands-on projects across three learning paths — build real LLM and ML systems, not toy tutorials. Every project handles a real failure mode, measures something, and ships with tests. No notebooks as the deliverable, no mocked LLM calls in the main code path, no pre-solved "hard parts."

## Paths

| Path | For | Projects |
|---|---|---|
| [Path 1 — AI Engineering Fundamentals](path-1/) | Engineers newer to AI who want to build and deploy real things | 12 |
| [Path 2 — AI-Augmented Engineering](path-2/) | Engineers with 2–8 years experience putting AI into existing workflows | 12 |
| [Path 3 — ML Engineering on AWS](path-3/) | ML/data engineers who want to own full ML systems in production | 12 |

Complexity key: 🟢 runs locally with one API key (or Ollama for zero cost) · 🟡 local with one optional Docker/cloud step · 🔴 requires an AWS account (cost estimate + teardown script included).

## Status

Projects land one at a time, fully built and tested before merge.

### Path 1 — AI Engineering Fundamentals

- [x] p1-01 — Document Chat 🟢
- [x] p1-02 — Structured Output Extractor 🟢
- [x] p1-03 — RAG Pipeline 🟢
- [x] p1-04 — Context Window Manager 🟢
- [x] p1-05 — Multi-step LLM Pipeline 🟢
- [x] p1-06 — Tool-Calling Agent 🟢
- [x] p1-07 — Persistent Agent with Memory 🟢
- [x] p1-08 — Streaming Chat API 🟢
- [x] p1-09 — Prompt Evaluation Framework 🟢
- [ ] p1-10 — Dockerize Your App 🟡
- [ ] p1-11 — Deploy to AWS Lambda 🔴
- [ ] p1-12 — Capstone: Full AI Assistant 🔴

### Path 2 — AI-Augmented Engineering

- [ ] p2-01 — AI Code Review Bot 🟢
- [ ] p2-02 — PR & Diff Summarizer 🟢
- [ ] p2-03 — Semantic Codebase Search 🟢
- [ ] p2-04 — Code Documentation Generator 🟢
- [ ] p2-05 — LLM Test Generator 🟢
- [ ] p2-06 — LLM Observability 🟡
- [ ] p2-07 — Incident Summariser 🟢
- [ ] p2-08 — Team Knowledge Extractor 🟢
- [ ] p2-09 — Internal Docs Copilot 🟡
- [ ] p2-10 — SQL Agent 🟡
- [ ] p2-11 — Personal AI CLI Toolkit 🟡
- [ ] p2-12 — Capstone: AI Dev Workflow 🔴

### Path 3 — ML Engineering on AWS

- [ ] p3-01 — Local Training → SageMaker 🟡
- [ ] p3-02 — Data Exploration & Quality Report 🟢
- [ ] p3-03 — Feature Engineering Pipeline 🟡
- [ ] p3-04 — Manual Model Versioning 🟢
- [ ] p3-05 — Experiment Tracking with MLflow 🟢
- [ ] p3-06 — Batch Inference with SageMaker 🔴
- [ ] p3-07 — Model Serving with SageMaker Endpoints 🔴
- [ ] p3-08 — A/B Testing Inference Endpoints 🔴
- [ ] p3-09 — Model Performance Reporting 🔴
- [ ] p3-10 — Model Monitoring & Drift Detection 🔴
- [ ] p3-11 — Retraining Pipeline with Step Functions 🔴
- [ ] p3-12 — Capstone: MLOps Platform 🔴

## Each project includes

- `README.md` — what it is, setup, run, tests, what to try next
- `GUIDE.md` — the one decision that matters, what will break, how to talk about it in an interview
- A provider-agnostic `src/llm.py` — switch between Anthropic, OpenAI, or local Ollama with one env var
- Tests that exercise real logic — no mocked LLM calls in the main code path
- A measured metric: latency, cost, accuracy, retrieval quality — something a real engineer would track

## Want a curated path with mentorship?

This repo is the raw material — every project stands on its own. [confidentprep.com](https://confidentprep.com) curates these into sequenced, reviewed paths with direct mentor feedback. Free, limited spots.
