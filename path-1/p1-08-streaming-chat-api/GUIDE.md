# Build guide: Streaming Chat API

## What you're building and why it matters

Every production LLM application eventually needs an HTTP API. SSE (Server-Sent Events)
is the standard transport for streaming text: the client opens one long-lived HTTP
connection and the server pushes data as it arrives. This is how ChatGPT, Claude.ai,
and every other chat product delivers streaming responses. Rate limiting and cost
tracking are not optional in production: without them, one busy user can exhaust your
API quota and your budget.

## The decision that matters in this build

**SSE vs WebSockets for streaming.** WebSockets are bidirectional and stateful;
SSE is one-directional (server to client) and stateless. For streaming LLM output,
SSE is the right choice: the client sends one HTTP request and the server streams
back. No need for the complexity of a WebSocket connection for this use case.
sse-starlette makes this a three-line addition to any FastAPI route.

A second, smaller decision shows up in `/chat`: the handler pulls the first
token off the LLM iterator *before* constructing the `EventSourceResponse`.
SSE responses commit to HTTP 200 the moment they start streaming, so a
connection-time failure (bad API key, provider outage) has to be caught
before the first byte goes out, or the client sees a 200 with no useful
error. Once the stream has started, a failure becomes an `[ERROR]` SSE
event instead, because the status line can no longer change.

## What will break

**`curl` without `-N` buffers SSE output.** When testing with curl, always use `-N`
(disable buffering). Without it, you'll see the entire response appear at once when
the stream closes, not token by token.

**p95 latency requires enough data.** The /stats endpoint computes p95 from all
stored requests. With fewer than 20 requests, p95 is not statistically meaningful.
Make 30+ requests before trusting the p95 number.

**A bad API key looks identical to a network outage.** Both the Anthropic and
OpenAI SDKs raise generic exceptions for auth failures, rate limits, and
connectivity problems. This project treats every pre-stream LLM exception as a
503 with `Retry-After: 10` — correct for an outage, slightly imprecise for a
bad key. In a real production system you'd inspect the exception type and
return 401 for auth failures instead of retrying forever.

## How to talk about this in an interview

"I built a streaming chat API where every request's token count, cost, and latency
is logged to SQLite. The /stats endpoint computes p50/p95 latency from real data.
I also implemented a sliding-window rate limiter that returns a Retry-After header —
the same mechanism used by real API rate limiters."
