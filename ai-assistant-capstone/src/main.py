"""FastAPI app: all 5 endpoints, wrapped for Lambda via Mangum.

/health, /documents, /chat (SSE), /eval, /metrics. The tool-calling +
RAG + context orchestration for /chat and /eval lives in chat_loop.py and
eval_runner.py respectively — this file is just routing, request/response
shaping, and the SSE generator that ties a chat turn's stream to its
post-stream logging (cost, latency, retrieval_hit, tool_used).

Lazy-loaded globals (FAISS index, metadata, embedding model) are loaded once
at import time and held in module state — same tradeoff as Lambda's /tmp:
they reset on cold start, which is why /documents must be re-called after one
(see docs/architecture.md and GUIDE.md).
"""
import os
import tempfile
import time
import uuid

import yaml
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from mangum import Mangum
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from sse_starlette.sse import EventSourceResponse

from src.chat_loop import run_chat_turn
from src.config import config
from src.database import get_metrics, init_db, log_request
from src.eval_runner import run_eval_suite
from src.rag import add_document, load_or_create_index
from src.rate_limiter import RateLimiter
from src.session_store import (
    count_documents,
    get_session_messages,
    log_document,
    log_eval_run,
    save_message,
)

app = FastAPI(title="Full AI Assistant Capstone")
rate_limiter = RateLimiter(requests_per_minute=config.rate_limit_requests_per_minute)
init_db(config.database_path)

_embedding_model: SentenceTransformer | None = None
_index, _metadata = load_or_create_index(config.index_path)


def get_embedding_model() -> SentenceTransformer:
    """Lazy-load the embedding model so /health doesn't pay the load cost."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(config.embedding_model)
    return _embedding_model


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    use_rag: bool = True


class EvalRequest(BaseModel):
    suite_yaml: str
    session_id: str | None = None


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": config.llm_model,
        "documents_indexed": count_documents(config.database_path),
        "index_size": _index.ntotal,
    }


@app.post("/documents")
async def upload_document(file: UploadFile = File(...)):
    global _index

    contents = await file.read()
    if len(contents) > config.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds maximum upload size")

    suffix = os.path.splitext(file.filename or "upload.txt")[1] or ".txt"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        chunks_added, document_id, _index = add_document(
            tmp_path, _index, _metadata, get_embedding_model(), config.index_path
        )
    finally:
        os.unlink(tmp_path)

    log_document(config.database_path, document_id, file.filename or "upload.txt", chunks_added)
    return {"document_id": document_id, "chunks_added": chunks_added, "total_chunks": _index.ntotal}


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

    session_id = chat_request.session_id or str(uuid.uuid4())
    history = get_session_messages(config.database_path, session_id, limit=20)
    save_message(config.database_path, session_id, "user", chat_request.message)

    try:
        token_iterator, tools_used, chunks, _ctx = run_chat_turn(
            chat_request.message, history, chat_request.use_rag, _index, _metadata, get_embedding_model()
        )
    except Exception as chat_setup_error:
        return JSONResponse(status_code=503, content={"error": "LLM provider unavailable", "detail": str(chat_setup_error)})

    return EventSourceResponse(
        _stream_chat_response(token_iterator, session_id, bool(tools_used), chunks)
    )


def _stream_chat_response(token_iterator, session_id: str, tool_used: bool, chunks: list[dict]):
    from src.chat_loop import retrieval_hit as _retrieval_hit_check

    t_start = time.perf_counter()
    full_answer_parts: list[str] = []

    try:
        for token_text, prompt_tokens, completion_tokens in token_iterator:
            if token_text:
                full_answer_parts.append(token_text)
                yield {"data": token_text}
            if prompt_tokens or completion_tokens:
                full_answer = "".join(full_answer_parts)
                save_message(config.database_path, session_id, "assistant", full_answer)
                latency_ms = int((time.perf_counter() - t_start) * 1000)
                cost_usd = (
                    prompt_tokens / 1_000_000 * config.cost_per_1m_input_tokens
                    + completion_tokens / 1_000_000 * config.cost_per_1m_output_tokens
                )
                hit = _retrieval_hit_check(full_answer, chunks)
                log_request(
                    config.database_path, session_id, prompt_tokens, completion_tokens,
                    cost_usd, latency_ms, hit, tool_used, "success",
                )
    except Exception as stream_error:
        latency_ms = int((time.perf_counter() - t_start) * 1000)
        log_request(config.database_path, session_id, 0, 0, 0.0, latency_ms, False, tool_used, "error")
        print(f"[error] stream failed for session {session_id}: {stream_error}")
        yield {"data": "[ERROR]"}


@app.post("/eval")
def run_eval(eval_request: EvalRequest):
    try:
        suite = yaml.safe_load(eval_request.suite_yaml)
    except yaml.YAMLError as parse_error:
        raise HTTPException(status_code=400, detail=f"Invalid suite YAML: {parse_error}")

    result = run_eval_suite(suite, _index, _metadata, get_embedding_model())
    log_eval_run(
        config.database_path, result["suite_name"], result["summary"]["passed"],
        result["summary"]["total"], result["summary"]["retrieval_hit_rate"],
    )
    return result


@app.get("/metrics")
def metrics() -> dict:
    return get_metrics(config.database_path)


# Lambda handler — Mangum adapts API Gateway events to ASGI calls into `app`.
handler = Mangum(app, lifespan="off")
