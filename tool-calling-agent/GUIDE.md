# Build guide: Tool-Calling Agent

## What you're building and why it matters

LLMs have a training cutoff and no access to live data. An agent with tools extends
the model's capabilities: it can fetch current stock prices, query a database, run
code, or call any API. The agentic loop — reason, act, observe, reason again — is
the architecture behind GitHub Copilot, customer support bots, and coding assistants.
Understanding it at the implementation level (not just as a library abstraction)
means you can debug it when it loops, control it when it hallucinates tool arguments,
and extend it when you need a new capability.

## The decision that matters in this build

**Tool error handling: raise or inject?** When a tool fails — Wikipedia times out,
the calculator gets a bad expression — you have two choices: raise an exception
(halt the agent) or inject the error into context (let the LLM decide what to do next).
Always inject. A production agent that crashes on a tool failure is unusable. Inject
the error message: "Tool wikipedia_search failed: timeout". The LLM will usually
try a different tool or rephrase the query. The `call_tool()` function in this project
never raises — it always returns a string, even if that string is an error message.

## What will break

**The LLM will call tools in unexpected ways.** You designed `get_datetime` with no
required arguments, but the LLM might call it with `{"format": "ISO"}` — an argument
that doesn't exist. Your tool should handle unexpected kwargs gracefully (log and ignore
them) rather than raising a TypeError that crashes the agent. This project's
`get_datetime(timezone="UTC", **unexpected_kwargs)` signature absorbs anything extra.

**Max iterations is not a safety net for bad prompts.** A poorly written system prompt
can cause the LLM to call tools in circles — calculator calls leading to more calculator
calls. Set MAX_ITERATIONS conservatively (5–8) and log a clear warning when it fires.
If it fires often, your system prompt needs work.

**Wikipedia will 403 you without a User-Agent.** The REST API rejects anonymous-looking
requests per Wikimedia's User-Agent policy. `wikipedia_search()` sends a descriptive
User-Agent header on every request — drop it and the tool silently starts failing in a
way that looks like a network problem, not a policy violation.

## How to talk about this in an interview

"I built an agent with a tool registry pattern — adding a new tool is one decorator,
not a change to the agent loop. The key design decision was treating tool errors as
context, not exceptions: the agent sees 'Tool X failed: reason' and can recover.
I also implemented a max-iterations guard with a graceful partial-answer exit, which
matters in production where infinite loops cause both cost and latency issues."
