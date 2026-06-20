"""FastAPI app: /health, /chat (SSE streaming), /stats — wrapped for Lambda.

This is the HTTP surface for the LLM. Every request is rate-limited per IP,
streamed token-by-token over SSE, and logged to SQLite with cost and latency
so /stats can report real numbers instead of guesses.

The only Lambda-specific code is the Mangum handler at the bottom, which
adapts API Gateway events to ASGI calls into this same FastAPI app. Mangum
runs with lifespan="off" because API Gateway's request/response model has no
concept of an app-level startup/shutdown event, so init_db() runs eagerly at
import time instead of inside an on_event("startup") hook.
"""
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.config import config
from src.database import get_stats, init_db, log_request
from src.llm import stream_completion
from src.rate_limiter import RateLimiter

app = FastAPI(title="Streaming Chat API (Lambda)")
rate_limiter = RateLimiter(requests_per_minute=config.rate_limit_requests_per_minute)
init_db(config.database_path)


class ChatRequest(BaseModel):
    message: str
    system: str = ""


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": config.llm_model, "provider": config.llm_provider}


@app.get("/stats")
def stats() -> dict:
    return get_stats(config.database_path)


@app.post("/chat")
def chat(chat_request: ChatRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"

    allowed, retry_after_seconds = rate_limiter.is_allowed(client_ip)
    if not allowed:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_after_seconds)},
            content={"error": "Rate limit exceeded", "retry_after": retry_after_seconds},
        )

    request_id = str(uuid.uuid4())

    try:
        token_iterator = stream_completion(chat_request.message, chat_request.system)
        first_token_text, _, _ = next(token_iterator)
    except ValueError as unknown_provider_error:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Unknown LLM provider",
                "provider": config.llm_provider,
                "detail": str(unknown_provider_error),
            },
        )
    except Exception:
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "10"},
            content={"error": "LLM provider unavailable", "retry_after": 10},
        )

    return EventSourceResponse(
        _stream_chat_response(token_iterator, first_token_text, request_id, client_ip)
    )


def _stream_chat_response(
    token_iterator,
    first_token_text: str,
    request_id: str,
    client_ip: str,
):
    """Generator driving the SSE body. Wraps the rest of the LLM stream so a
    mid-stream provider error still produces a logged, visible [ERROR] event
    instead of a silently truncated connection."""
    t_start = time.perf_counter()
    if first_token_text:
        yield {"data": first_token_text}

    try:
        for token_text, prompt_tokens, completion_tokens in token_iterator:
            if token_text:
                yield {"data": token_text}
            if prompt_tokens or completion_tokens:
                latency_ms = int((time.perf_counter() - t_start) * 1000)
                cost_usd = (
                    prompt_tokens / 1_000_000 * config.cost_per_1m_input_tokens
                    + completion_tokens / 1_000_000 * config.cost_per_1m_output_tokens
                )
                log_request(
                    config.database_path,
                    request_id,
                    client_ip,
                    prompt_tokens,
                    completion_tokens,
                    cost_usd,
                    latency_ms,
                    config.llm_model,
                    "success",
                )
    except Exception as stream_error:
        latency_ms = int((time.perf_counter() - t_start) * 1000)
        log_request(
            config.database_path,
            request_id,
            client_ip,
            0,
            0,
            0.0,
            latency_ms,
            config.llm_model,
            "error",
        )
        print(f"[error] stream failed for request {request_id}: {stream_error}")
        yield {"data": "[ERROR]"}


# Lambda handler — Mangum adapts API Gateway events to ASGI calls into `app`.
handler = Mangum(app, lifespan="off")
