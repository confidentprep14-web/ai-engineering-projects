# AI Engineering Projects

36 hands-on projects — build real LLM and ML systems, not toy tutorials. Every project handles a real failure mode, measures something, and ships with tests. No notebooks as the deliverable, no mocked LLM calls in the main code path, no pre-solved "hard parts."

Complexity key: 🟢 runs locally with one API key (or Ollama for zero cost) · 🟡 local with one optional Docker/cloud step · 🔴 requires an AWS account (cost estimate + teardown script included).

## Shipped projects

- [x] [Document Chat](document-chat/) 🟢
- [x] [Structured Output Extractor](structured-output-extractor/) 🟢
- [x] [RAG Pipeline](rag-pipeline/) 🟢
- [x] [Context Window Manager](context-window-manager/) 🟢
- [x] [Multi-step LLM Pipeline](multi-step-llm-pipeline/) 🟢
- [x] [Tool-Calling Agent](tool-calling-agent/) 🟢
- [x] [Persistent Agent with Memory](persistent-agent/) 🟢
- [x] [Streaming Chat API](streaming-chat-api/) 🟢
- [x] [Prompt Evaluation Framework](prompt-eval/) 🟢
- [x] [Code Review Bot](code-review-bot/) 🟢
- [x] [PR Diff Summarizer](pr-diff-summarizer/) 🟢
- [x] [Semantic Codebase Search](semantic-codebase-search/) 🟢
- [x] [Code Documentation Generator](code-doc-generator/) 🟢
- [x] [LLM Test Generator](llm-test-generator/) 🟢
- [x] [LLM Observability](llm-observability/) 🟡
- [x] [Incident Summariser](incident-summariser/) 🟢
- [x] [Team Knowledge Extractor](team-knowledge-extractor/) 🟢
- [x] [Local to SageMaker](local-to-sagemaker/) 🟡
- [x] [Data Exploration](data-exploration/) 🟢
- [x] [Feature Engineering](feature-engineering/) 🟡
- [x] [Manual Versioning](manual-versioning/) 🟢
- [x] [Dockerize Your App](dockerize-llm-app/) 🟡
- [x] [Deploy to AWS Lambda](aws-lambda-deploy/) 🔴
- [x] [Full AI Assistant (Capstone)](ai-assistant-capstone/) 🔴
- [x] [Docs Copilot](docs-copilot/) 🟡
- [x] [SQL Agent](sql-agent/) 🟡
- [x] [AI CLI Toolkit](ai-cli-toolkit/) 🟡
- [x] [AI PR Reviewer (Capstone)](ai-pr-reviewer/) 🔴
- [x] [Experiment Tracking](experiment-tracking/) 🟢

More projects land one at a time, fully built and tested before merge.

## Each project includes

- `README.md` — what it is, setup, run, tests, what to try next
- `GUIDE.md` — the one decision that matters, what will break, how to talk about it in an interview
- A provider-agnostic `src/llm.py` — switch between Anthropic, OpenAI, or local Ollama with one env var
- Tests that exercise real logic — no mocked LLM calls in the main code path
- A measured metric: latency, cost, accuracy, retrieval quality — something a real engineer would track

## Want a curated path with mentorship?

This repo is the raw material — every project stands on its own. [confidentprep.com](https://confidentprep.com) curates these into sequenced, reviewed paths with direct mentor feedback. Free, limited spots.
