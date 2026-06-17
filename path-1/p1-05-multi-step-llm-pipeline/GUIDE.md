# Build guide: Multi-step LLM Pipeline

## What you're building and why it matters

Most useful AI applications are not single LLM calls — they are sequences of calls
where each stage transforms or enriches the data. A legal contract analyser might:
extract clauses, classify each clause, flag risk, then summarise. A customer support
tool might: classify the ticket, retrieve relevant docs, generate a draft response,
then check tone. Understanding how to orchestrate these stages — in sequence, with
error handling and latency tracking per stage — is the foundation of production AI
engineering.

## The decision that matters in this build

**How much to pass between stages.** Stage 1 extracts entities. Stage 2 fetches
summaries. You could pass everything from Stage 1 to Stage 2 (all text, all context).
Instead, pass only what Stage 2 needs: the entity names. This keeps stages decoupled.
If Stage 1's output format changes, Stage 2 doesn't break as long as it still receives
a list of strings. Decoupled stages are the only kind you can test independently,
swap out, or run in parallel. That's why `fetch_entity_summaries` takes `list[str]`
rather than the raw LLM completion, and why `synthesise_briefing` takes structured
`list[dict]` summaries rather than re-deriving them from the original topic text.

## What will break

**Wikipedia API throttles aggressive requests.** Fetching summaries for many entities
sequentially with no delay can trigger rate limiting on a busy network. This project
fetches sequentially for simplicity and clear per-stage timing; a production version
should add `time.sleep(0.1)` between calls or switch to concurrent fetching with
`ThreadPoolExecutor` for a more robust and faster Stage 2.

**LLMs return varying JSON formats for entity extraction.** Claude sometimes wraps
arrays in ` ```json ... ``` ` fences. OpenAI tends to return them clean. `stages.py`
always strips fences before calling `json.loads()` — skip that step and extraction
silently breaks the moment you switch providers.

**A stage failure must not corrupt downstream state.** `run_pipeline` re-raises any
`StageError` immediately instead of continuing with partial data — there is no
"briefing synthesised from zero entities" half-success state. Wikipedia misses are
the one exception: a 404 or timeout for one entity is recorded with `found=False`
and the pipeline continues, because one missing Wikipedia article is not a reason to
fail the entire briefing.

## How to talk about this in an interview

"I built a 3-stage LLM pipeline where each stage has a clear input/output contract
and fails independently. I time each stage separately — which showed that Wikipedia
fetch is often the bottleneck, not the LLM. I also learned that passing minimal data
between stages (just entity names, not full text) is what makes each stage independently
testable and swappable."
