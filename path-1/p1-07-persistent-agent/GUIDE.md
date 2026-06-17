# Build guide: Persistent Agent with Memory

## What you're building and why it matters

Memory is what separates a chatbot from an assistant. Every commercial AI assistant
— ChatGPT, Claude.ai, Gemini — has some form of memory. The fundamental pattern is
simple: extract facts from conversations, store them, inject them into future system
prompts. The engineering challenge is deciding what to remember, how long to keep it,
and how to inject it without blowing up the context window. This project gives you
that foundation with a real database, not an in-memory dict that disappears on restart.

## The decision that matters in this build

**Where to inject memory: system prompt or user message?** Facts injected into the
system prompt arrive with higher authority — the model treats them as persistent
context about who it is talking to. Facts injected as a prior user message can be
"argued with" by subsequent conversation. Put persistent facts (name, role, preferences)
in the system prompt. Put recent context (last conversation history) in the message list.
This project also adds a second gate on top of that: `build_system_prompt()` only injects
facts at or above `MIN_FACT_CONFIDENCE_TO_INJECT` (0.8). A fact with confidence 0.4 sitting
in the system prompt is worse than no fact at all — the model will state it with the same
authority as a fact you're sure about.

## What will break

**Fact extraction will hallucinate.** If the user says "I think Python is overrated,"
the extractor might extract `preferred_language: Python`. The confidence score is the
defense, not a guarantee — `extract_facts()` trusts whatever number the LLM reports, so
the 0.8 injection threshold in `agent.py` is doing real work. Tune it down and you'll see
noisier, less reliable personalization within a few sessions.

**Loading too many messages blows up the context window.** `RECENT_MESSAGES_LIMIT=20`
is a safe default. Set it to 100 and you'll eventually hit token limits. For long-running
sessions, consider summarising old messages (the pattern from Project 4) before injection.

**SQLite write contention.** A single local CLI session never contends with itself, but
`MemoryStore._execute_with_retry()` still catches `sqlite3.OperationalError` and retries
once before raising — because the moment this pattern moves behind an HTTP API serving
concurrent requests (Project 8's direction), "database is locked" stops being theoretical.

## How to talk about this in an interview

"I built a persistent agent that extracts named facts from user messages — name,
preferences, context — stores them in SQLite with a confidence score, and injects
the top-confidence facts into every future system prompt. I measured memory hit rate
as the fraction of responses where a prior fact appeared in the answer. It's the
pattern behind every 'personalised' AI assistant."
