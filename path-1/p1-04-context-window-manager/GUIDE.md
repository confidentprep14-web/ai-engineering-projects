# Build guide: Context Window Manager

## What you're building and why it matters

Every production LLM application that has multi-turn conversations eventually hits
the context window limit. At 2am on-call, this shows up as a cryptic API error
about token limits. The fix is never "just increase the limit" — even a 200k context
window fills up in long sessions, and at $15 per million tokens you don't want to
send the entire conversation history every turn. Context management is the unsexy
infrastructure that makes conversational AI work at scale.

## The decision that matters in this build

**Sliding window vs summarisation.** Sliding window is simple and deterministic:
drop the oldest messages. It always works, never calls the LLM, and costs nothing.
Its weakness: you permanently lose the context of early conversation. Summarisation
compresses old turns into a summary. It preserves semantic content at the cost of
an extra LLM call. In production, most systems combine both: summarise every N turns,
then slide the window if the summary itself gets too long. This project builds both
separately so the tradeoff is concrete, not theoretical — `--compare` replays one
saved session through each strategy and shows exactly how many messages survive
at each turn.

## What will break

**Token counting is an approximation.** tiktoken counts tokens for OpenAI models
exactly. For Claude and Ollama, you're estimating with a compatible tokenizer.
Set your `CONTEXT_LIMIT` to a fraction of the actual model limit to leave room for
the approximation error. If you set it to the exact limit and the approximation is
off, you'll get an API error instead of a clean compression cycle.

**Summarisation doubles your LLM calls.** Every time compression triggers, you
make an extra LLM call to generate the summary. In a long session, this can
add 5–10% to your total cost. `sliding_window_fired_count` and
`summarise_fired_count` are tracked on every `ContextManager` and printed on
exit so you can see how often compression actually runs.

**Sliding window can drop important context.** If the user sets up important
constraints in the first two turns ("always respond in French", "my name is Alex")
and those turns get dropped, the assistant forgets. Production systems handle this
with a "sticky context" — a separate block of critical instructions that never gets
dropped. Consider adding this as an extension.

**A failed summarisation call should not crash the session.** If the summarisation
LLM call raises (timeout, rate limit, malformed response), `apply_summarise_compression`
catches it, logs a warning to stderr, and falls back to sliding window for that one
compression cycle instead of propagating the exception up through the conversation loop.

## How to talk about this in an interview

"I built a context manager with two compression strategies. Sliding window is
zero-cost but loses history; summarisation preserves semantics but costs an extra
LLM call. I measured how many times each strategy fired per session and logged
token utilisation after every turn, so the tradeoff between cost and retained
context is something I can point to with numbers, not just describe. The right
production choice depends on how stateful the conversation needs to be — and
the two are not mutually exclusive."
