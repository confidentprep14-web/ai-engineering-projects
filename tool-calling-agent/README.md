# Tool-Calling Agent

An agent that uses tools — calculator, datetime, and Wikipedia — to answer questions
it can't answer from training alone, with a reasoning trace and max-iterations guard.

> Part of [Path 1 — AI Engineering Fundamentals](https://confidentprep.com/paths/path-1) on Confident Prep — see the full curriculum and how this project fits in.

## What this is

Project 5 ran a fixed sequence of LLM calls. This one hands the LLM a registry of
tools and lets it decide, turn by turn, which one to call, what arguments to pass,
and when it has enough information to answer — the reason → act → observe loop
behind every production agent. Tool failures (a bad Wikipedia title, a malformed
expression) are injected back into the conversation as plain text instead of raised
as exceptions, so the LLM can recover instead of the process crashing. A
max-iterations guard stops a confused model from calling tools in circles forever.
I built this with a tool registry pattern where adding a new tool is one decorator,
not a change to the agent loop.

## Setup

```bash
cd p1-06-tool-calling-agent
cp .env.example .env
pip install -r requirements.txt
```

## Run

```bash
python src/main.py "What is 15% of 847 plus the current UTC hour?"
python src/main.py "Give me a one-sentence summary of the Wikipedia article about FAISS"
python src/main.py "What is 2 to the power of 32?" --max-iter 3
```

Expected output:
```
Question: What is 15% of 847 plus the current UTC hour?

[Iter 1] 🔧 Calling calculator({"expression": "847 * 0.15"})
         → 127.05
[Iter 2] 🔧 Calling get_datetime({})
         → 2025-06-16T14:00:00Z
[Iter 3] 🔧 Calling calculator({"expression": "127.05 + 14"})
         → 141.05

Answer: 15% of 847 is 127.05. The current UTC hour is 14. The total is 141.05.

📊 Tools used: ['calculator', 'get_datetime', 'calculator'] | Iterations: 3
```

## Tests

```bash
pytest tests/ -v
```

Tests verify calculator safety, Wikipedia error handling, and unknown tool recovery.
No API key required.

## What to try next

- Add a `read_file` tool that reads a local file and returns its contents
- Add a `web_search` tool using the Brave or Serper API
- Set MAX_ITERATIONS=2 and ask a complex question — watch the graceful exit
