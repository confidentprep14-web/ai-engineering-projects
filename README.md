![AI Engineering Projects](https://img.shields.io/badge/projects-36-8B5CF6?style=flat-square)
[![License: MIT](https://img.shields.io/github/license/confidentprep14-web/ai-engineering-projects.svg?style=flat-square)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/confidentprep14-web/ai-engineering-projects.svg?style=flat-square&label=Star)](https://github.com/confidentprep14-web/ai-engineering-projects/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/confidentprep14-web/ai-engineering-projects.svg?style=flat-square&label=Fork)](https://github.com/confidentprep14-web/ai-engineering-projects/network)
[![Issues welcome](https://img.shields.io/badge/issues-welcome-brightgreen.svg?style=flat-square)](https://github.com/confidentprep14-web/ai-engineering-projects/issues)
[![Mentored by Confident Prep](https://img.shields.io/badge/mentored%20by-confidentprep.com-0553D6?style=flat-square)](https://confidentprep.com)

# AI Engineering Projects

**36 hands-on projects across 3 structured learning paths — build real LLM and ML systems, not toy tutorials.**

Every project handles a real failure mode, measures something, and ships with tests. No notebooks as the deliverable, no mocked LLM calls in the main code path, no pre-solved "hard parts." Pick the path that matches where you are, work through the projects in order, and walk away with a portfolio that survives a technical interview.

This repo is maintained by [Confident Prep](https://confidentprep.com) — a free, mentor-curated program that sequences these projects into fortnightly cohorts with direct feedback from a 22-year production engineer. **The repo is the raw material; the site is the structured path through it.**

---

## Choose your path

| Path | For | Outcome | Projects |
|---|---|---|---|
| 🟢 **[Path 1 — AI Engineering Fundamentals](#path-1--ai-engineering-fundamentals)** | Newer engineers getting into AI/ML | Junior AI engineer–ready | 12 |
| 🔵 **[Path 2 — AI-Augmented Engineering](#path-2--ai-augmented-engineering)** | 2–8 years of software experience, adding AI to existing work | AI in your toolkit | 12 |
| 🟣 **[Path 3 — ML Engineering on AWS](#path-3--ml-engineering-on-aws)** | Some ML/data science background, owning full production systems | Own ML systems end-to-end | 12 |

Difficulty key: 🟢 runs locally with one API key (or Ollama for zero cost) · 🟡 local with one optional Docker/cloud step · 🔴 requires an AWS account (cost estimate + teardown script included).

---

## Path 1 — AI Engineering Fundamentals

*You're newer to engineering and want to get into AI/ML. You don't need ML math — you need to build and deploy real things.*

| # | Project | | Description |
|---|---|---|---|
| 1 | [Document Chat](document-chat/) | 🟢 | CLI tool that loads a PDF or text file and answers questions about it, with streaming output and exact source citations. |
| 2 | [Structured Output Extractor](structured-output-extractor/) | 🟢 | Extracts structured data from unstructured text into validated Pydantic objects, with automatic retry on malformed JSON. |
| 3 | [RAG Pipeline](rag-pipeline/) | 🟢 | Embeds documents into a persistent FAISS index, retrieves semantically relevant chunks, with score-threshold filtering and an A/B mode vs. no-RAG. |
| 4 | [Context Window Manager](context-window-manager/) | 🟢 | Multi-turn CLI chatbot handling context limits with sliding-window and summarisation-compression strategies. |
| 5 | [Multi-step LLM Pipeline](multi-step-llm-pipeline/) | 🟢 | 3-stage pipeline that extracts entities, enriches them with live Wikipedia data, and synthesises a briefing document. |
| 6 | [Tool-Calling Agent](tool-calling-agent/) | 🟢 | Agent that uses tools — calculator, datetime, Wikipedia — with a reasoning trace and max-iterations guard. |
| 7 | [Persistent Agent with Memory](persistent-agent/) | 🟢 | CLI chatbot that stores conversation history and key facts in SQLite and recalls them across sessions. |
| 8 | [Streaming Chat API](streaming-chat-api/) | 🟢 | FastAPI server streaming LLM responses over SSE, tracking token usage/cost per request, rate-limited per IP. |
| 9 | [Prompt Evaluation Framework](prompt-eval/) | 🟢 | Test harness for LLM prompts — YAML test cases, LLM-judge scoring, exit code 1 on failure for CI. |
| 10 | [Dockerize Your App](dockerize-llm-app/) | 🟡 | Containerizes an LLM app for reproducible local and cloud deployment. |
| 11 | [Deploy to AWS Lambda](aws-lambda-deploy/) | 🔴 | Serverless deployment of an LLM endpoint to AWS Lambda. |
| 12 | [Full AI Assistant (Capstone)](ai-assistant-capstone/) | 🔴 | Capstone — wires the path's pieces into one full-stack AI assistant. |

## Path 2 — AI-Augmented Engineering

*You have 2–8 years of software experience. AI is everywhere and you feel behind. These projects put AI into the work you already know how to do.*

| # | Project | | Description |
|---|---|---|---|
| 1 | [Code Review Bot](code-review-bot/) | 🟢 | Flags security and quality issues in diffs, including hardcoded-secret detection. |
| 2 | [PR Diff Summarizer](pr-diff-summarizer/) | 🟢 | Summarizes pull request diffs into human-readable review notes. |
| 3 | [Semantic Codebase Search](semantic-codebase-search/) | 🟢 | Embeddings-based search over a codebase for natural-language queries. |
| 4 | [Code Documentation Generator](code-doc-generator/) | 🟢 | Generates and keeps code documentation in sync with source. |
| 5 | [LLM Test Generator](llm-test-generator/) | 🟢 | Generates unit tests for existing code via LLM analysis. |
| 6 | [LLM Observability](llm-observability/) | 🟡 | Tracing and metrics for LLM calls in a running application. |
| 7 | [Incident Summariser](incident-summariser/) | 🟢 | Automated summarisation of incident logs/timelines. |
| 8 | [Team Knowledge Extractor](team-knowledge-extractor/) | 🟢 | Extracts structured team knowledge from unstructured docs/chat history. |
| 9 | [Docs Copilot](docs-copilot/) | 🟡 | Interactive copilot for querying internal documentation. |
| 10 | [SQL Agent](sql-agent/) | 🟡 | Agent that writes and runs SQL against a real database from natural language. |
| 11 | [AI CLI Toolkit](ai-cli-toolkit/) | 🟡 | A packaged CLI toolkit wrapping several of the path's AI utilities. |
| 12 | [AI PR Reviewer (Capstone)](ai-pr-reviewer/) | 🔴 | Capstone — full AI-augmented PR review workflow end to end. |

## Path 3 — ML Engineering on AWS

*You've done some ML or data science and want to own the full system — training, serving, monitoring — in production on AWS.*

| # | Project | | Description |
|---|---|---|---|
| 1 | [Local to SageMaker](local-to-sagemaker/) | 🟡 | Trains an XGBoost classifier locally, then submits the identical script as a managed SageMaker training job via a least-privilege CDK-provisioned IAM role, with cost estimator and CloudWatch metric fetcher. |
| 2 | [Data Exploration](data-exploration/) | 🟢 | EDA pipeline quantifying class imbalance, per-feature statistics, high-missing-rate columns, and correlated features in a structured report. |
| 3 | [Feature Engineering](feature-engineering/) | 🟡 | Reusable sklearn preprocessing pipeline with before/after validation — runs locally and as a SageMaker Processing Job. |
| 4 | [Manual Versioning](manual-versioning/) | 🟢 | Trains model variants and tracks results with timestamped folders and JSON metadata, before MLflow takes over. |
| 5 | [Experiment Tracking](experiment-tracking/) | 🟢 | MLflow-instrumented training with a hyperparameter sweep, programmatic best-run selection, and model registry with a production alias. |
| 6 | [Batch Inference](batch-inference/) | 🔴 | Packages a registered model for SageMaker Batch Transform and compares batch vs. real-time endpoint cost. |
| 7 | [Model Serving](model-serving/) | 🔴 | Deploys a registered model as a real-time SageMaker endpoint, benchmarks p50/p95/p99 latency and cold start. |
| 8 | [A/B Testing](ab-testing/) | 🔴 | Two model variants behind one multi-variant endpoint, traffic-shifted, winner promoted by AUC. |
| 9 | [Performance Reporting](performance-reporting/) | 🔴 | Weekly report comparing live endpoint AUC and CloudWatch health to the registry baseline — cron-safe. |
| 10 | [Model Monitoring](model-monitoring/) | 🔴 | SageMaker Model Monitor for data drift: data capture, baseline statistics, hourly schedule, synthetic drift alerts. |
| 11 | [Retraining Pipeline](retraining-pipeline/) | 🔴 | Automated retraining pipeline triggered by drift, orchestrated with Step Functions. |
| 12 | [MLOps Capstone](capstone-mlops/) | 🔴 | Capstone — wires the path's pieces into one end-to-end MLOps platform. |

---

## Each project includes

- `README.md` — what it is, setup, run, tests, what to try next
- `GUIDE.md` — the one decision that matters, what will break, how to talk about it in an interview
- A provider-agnostic `src/llm.py` — switch between Anthropic, OpenAI, or local Ollama with one env var
- Tests that exercise real logic — no mocked LLM calls in the main code path
- A measured metric: latency, cost, accuracy, retrieval quality — something a real engineer would track

## Getting started

```bash
git clone https://github.com/confidentprep14-web/ai-engineering-projects.git
cd ai-engineering-projects/<project-slug>   # e.g. document-chat
cat README.md                                # setup + run instructions for that project
```

Each project is self-contained — its own dependencies, its own tests, its own README. Work through a path in order; later projects assume comfort with earlier ones.

## Want a curated path with mentorship?

This repo is the raw material — every project stands on its own and can be cloned and run independently. [**confidentprep.com**](https://confidentprep.com) sequences these into reviewed paths with direct mentor feedback from a 22-year production engineer: fortnightly project delivery, a [path picker](https://confidentprep.com/paths) that matches you to Path 1/2/3 above, and a [build-your-own path](https://confidentprep.com/paths/custom) option if none of the three fit. Free, limited spots.

## Contributing

Found a bug, a broken setup step, or a typo? [Open an issue](https://github.com/confidentprep14-web/ai-engineering-projects/issues) or send a pull request — fixes and clarifications are welcome. New projects are scoped and built by the maintainer to keep each path's sequencing intentional.

## License

[MIT](LICENSE)
