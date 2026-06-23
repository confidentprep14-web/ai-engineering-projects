# Context Window Manager

A multi-turn CLI chatbot that handles context window limits with two strategies —
sliding window and summarisation compression — and shows you exactly what each
approach loses.

> Part of [Path 1 — AI Engineering Fundamentals](https://confidentprep.com/paths/path-1) on Confident Prep — see the full curriculum and how this project fits in.

## What this is

Every multi-turn LLM conversation eventually hits the context window limit. This
project makes that failure mode visible instead of letting it crash production:
`ContextManager` tracks token usage against a configurable limit, warns at 80%
by default, and compresses the conversation once it crosses 85% — either by
dropping the oldest messages (sliding window) or by asking the LLM to summarise
old turns into one message (summarisation). A `--compare` mode replays the same
saved session through both strategies side by side so the tradeoff — cost vs.
lost history — is concrete, not theoretical.

## Setup

```bash
cd p1-04-context-window-manager
cp .env.example .env
# Edit .env: set LLM_PROVIDER, LLM_API_KEY, and CONTEXT_LIMIT (match your model)
pip install -r requirements.txt
```

## Run

```bash
# Interactive chat with default strategy (from .env)
python src/main.py

# Force a specific strategy
python src/main.py --strategy summarise

# Save your session on exit
python src/main.py --save sessions/my_session.json

# Compare both strategies on a saved session
python src/main.py --compare sessions/my_session.json
```

Expected output mid-conversation:
```
You:
> Tell me about the new auth flow we discussed

⚠ Context at 83% of limit — sliding compression will apply
Dropped [user]: "What are the main API endpoints?..."
Dropped [assistant]: "The main endpoints are /auth/login, /auth..."
Assistant: ...
📊 Tokens used: 5734/8192 (70%)
```

## Tests

```bash
pytest tests/ -v
```

Six tests verify token counting increases with messages and is deterministic,
sliding window removes oldest-first while preserving the most recent turns,
the limit warning triggers at the configured threshold, and session export/load
round-trips messages exactly. No API key required — the only test that touches
the LLM path mocks `get_completion` for the summarisation fallback.

## What to try next

- Set `CONTEXT_LIMIT=2000` and have a long conversation to see compression trigger quickly
- Export a session and run `--compare` to see what sliding vs summarise each forgets
- Add a third strategy: keep only user messages (drop all assistant turns)
