# Build guide: Full AI Assistant Capstone

## What you're building and why it matters

Every component you've built in earlier projects exists to make this one thing possible:
a deployed assistant that retrieves from your documents, uses tools for live data,
manages long conversations, and can be evaluated against a test suite. This is not
a demo. It has SSE streaming, real metrics, a live eval endpoint, and a complete
teardown script. It is the centrepiece of a portfolio and the answer to "show me
something you've built."

## The decision that matters in this build

**Eval against the live endpoint, not a local mock.** It is easy to write tests
that mock the LLM and assert that mock was called. Those tests tell you nothing
about whether the deployed system works. `run_eval.py` calls the real `/eval`
endpoint which calls the real LLM. The retrieval_hit_rate metric tells you
whether RAG is actually helping — not whether your code runs.

## What will break

**FAISS index is rebuilt on Lambda restart.** Lambda functions are stateless and
ephemeral. `/tmp` persists within a warm invocation but not across cold starts.
For a production system, the FAISS index should be loaded from S3 on cold start.
For this project, `/documents` must be called again after each cold start.
This is a real limitation to know about and discuss.

**Multi-turn context requires consistent session_id.** If the client doesn't send
the same `session_id` across turns, the assistant starts fresh every turn. The
eval suite must use a consistent session_id for multi-turn test cases.

**retrieval_hit is a heuristic, not ground truth.** `/chat` and `/eval` mark a
response as a "retrieval hit" if a chunk of retrieved text shows up verbatim
in the answer. An assistant that paraphrases retrieved content instead of
quoting it will under-report hits. This is a conservative metric on purpose —
see chat_loop.py's `retrieval_hit()` docstring.

## How to talk about this in an interview

"I built and deployed a full AI assistant to Lambda. It combines RAG over uploaded
documents with tool use for live data, all behind a streaming SSE API. I measure
retrieval hit rate — the fraction of RAG-enabled responses that actually used retrieved
context — which tells me whether the retrieval is helping or not. The eval suite runs
against the live endpoint, not a mock, with exit code 1 on failure."

## Cost estimate

| Resource | Estimated cost |
|----------|---------------|
| Lambda invocations (100 test) | ~$0.01 |
| API Gateway | ~$0.01 |
| ECR image storage | ~$0.10 |
| Secrets Manager | <$0.01 |
| **Total** | **~$3–5** |

## Failure modes to handle

| Failure | Where | How to handle |
|---------|-------|---------------|
| FAISS index empty on Lambda cold start | `rag.py` | Return empty chunks; `use_rag=false` effectively; log warning |
| Tool call loops (agent calls same tool repeatedly) | `chat_loop.py` | Max 8 iterations hard cap (`MAX_TOOL_ITERATIONS`); return partial answer |
| /eval LLM call failure (generation or judge) | `eval_runner.py` | Mark that one test case failed with "LLM unavailable" / "Judge unavailable", continue suite |
| Document upload too large | `main.py` `/documents` | Return HTTP 413 if file > `MAX_UPLOAD_BYTES` (default 10MB) |
| Lambda /tmp full | `rag.py` | Index load/save wrapped in try/except; falls back to an empty index rather than crashing |

## The metric this project measures

**Retrieval hit rate** — fraction of RAG-enabled responses where retrieved chunks were referenced.
Available at `GET /metrics` as `retrieval_hit_rate`.
Target: >60% for questions that are answerable from uploaded documents.
Low rate means either retrieval quality is poor or chunks are not relevant to the questions.
