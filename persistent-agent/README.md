# Persistent Agent with Memory

A CLI chatbot that remembers you. It stores conversation history and key facts
in SQLite and recalls them across sessions — your name, preferences, and past
context are available every time you return.

## What this is

Most CLI chatbot demos forget everything the moment the process exits. This one
doesn't: every message is written to a local SQLite file as it happens, and a
lightweight fact extractor pulls out durable details ("the user's name is Alex",
"prefers Python") with an LLM-assessed confidence score. On the next run, the
agent reloads recent history and injects only the highest-confidence facts into
the system prompt — so it can say "you mentioned you're using Python" three
sessions later. A memory hit rate is logged on exit so you can see whether the
injected facts are actually showing up in responses, not just sitting unused in
a table.

## Setup

```bash
cd p1-07-persistent-agent
cp .env.example .env
# Edit .env: set LLM_PROVIDER and LLM_API_KEY
pip install -r requirements.txt
```

## Run

```bash
# Start chatting (creates agent_memory.db on first run)
python src/main.py

# View stored facts
python src/main.py --show-memory

# Clear all memory
python src/main.py --clear-memory

# Run an independent memory session
python src/main.py --session-id work-project
```

Expected output:
```
📚 Loaded 0 prior messages | 0 known facts

You: My name is Alex and I work in Python
Assistant: Nice to meet you, Alex! Python is a great language...

You: quit
Session ended: 1 turns | 1 new facts extracted | Memory hits: 0/1 (0%)
```

Next session:
```
📚 Loaded 2 prior messages | 1 known facts
  - user_name: Alex (confidence: 95%)

You: What's my name?
Assistant: Your name is Alex — you mentioned it in our last conversation.

Session ended: 1 turns | 0 new facts extracted | Memory hits: 1/1 (100%)
```

## Tests

```bash
pytest tests/ -v
```

Seven tests verify SQLite persistence (including a simulated process restart
against the same database file), fact deduplication via the `UNIQUE(fact_key)`
constraint, message limit enforcement, and graceful handling of malformed fact
extraction. No API key required — the only test that touches the LLM path mocks
`get_completion` to simulate a non-factual message.

## What to try next

- Extract facts from assistant responses too (the agent learns from its own answers)
- Add a fact expiry: facts older than 30 days are downweighted in the system prompt
- Swap the substring-based memory hit check for a second LLM call that judges whether a fact was actually used, since "Alex" appearing in a response doesn't always mean the fact was meaningfully used
