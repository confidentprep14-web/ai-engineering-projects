"""Integration tests against the FastAPI app, per the spec's 5 test cases.

Mocks the LLM and FAISS/embeddings exactly as the spec instructs — no real
network calls and no real sentence-transformers model download in CI. The
database and rate limiter are real SQLite / in-memory state, same precedent
as aws-lambda-deploy/tests/test_api.py: only the external LLM provider call
and the (slow, model-download-dependent) embedding model are mocked.
"""
import os
import tempfile

import pytest

os.environ.setdefault("DATABASE_PATH", tempfile.mktemp(suffix=".db"))
os.environ.setdefault("INDEX_PATH", tempfile.mkdtemp())
os.environ.setdefault("LLM_API_KEY", "test-key-not-real")

from fastapi.testclient import TestClient  # noqa: E402

from src.database import init_db  # noqa: E402
from src.main import app, rate_limiter  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_db(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test_assistant.db")
    init_db(db_path)
    monkeypatch.setattr("src.main.config.database_path", db_path)
    return db_path


def _mock_token_iterator(text: str, prompt_tokens: int = 12, completion_tokens: int = 8):
    """Mimic src.llm.stream_completion's (token, prompt_tokens, completion_tokens) shape."""
    for word in text.split(" "):
        yield word + " ", 0, 0
    yield "", prompt_tokens, completion_tokens


def test_health_returns_200(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "model" in body
    assert "documents_indexed" in body
    assert "index_size" in body


def test_chat_returns_sse_response(client, monkeypatch):
    """Mock the LLM stream (and skip the tool loop) — assert SSE content-type."""
    monkeypatch.setattr(
        "src.chat_loop.run_tool_loop", lambda context_manager, system_prompt: ([], 0, 0)
    )
    monkeypatch.setattr(
        "src.chat_loop.stream_completion",
        lambda messages, system="": _mock_token_iterator("Hello from the mocked LLM."),
    )

    response = client.post("/chat", json={"message": "Hi there", "use_rag": False})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


def test_metrics_returns_correct_structure(client):
    response = client.get("/metrics")

    assert response.status_code == 200
    body = response.json()
    assert "total_requests" in body
    assert "retrieval_hit_rate" in body
    assert "p50_latency_ms" in body
    assert "p95_latency_ms" in body
    assert "tool_use_rate" in body
    assert "error_rate" in body


def test_documents_accepts_file_upload(client, monkeypatch, tmp_path):
    """Mock FAISS indexing (add_document) and the embedding model lookup."""

    class _FakeIndex:
        ntotal = 3

    monkeypatch.setattr(
        "src.main.add_document", lambda *args, **kwargs: (3, "doc-123", _FakeIndex())
    )
    monkeypatch.setattr("src.main.get_embedding_model", lambda: object())

    sample_file = tmp_path / "sample.txt"
    sample_file.write_text("This is a small test document for upload.")

    with open(sample_file, "rb") as f:
        response = client.post("/documents", files={"file": ("sample.txt", f, "text/plain")})

    assert response.status_code == 200
    body = response.json()
    assert body["chunks_added"] == 3
    assert "document_id" in body


def test_rate_limiter_returns_429(client, monkeypatch):
    monkeypatch.setattr(rate_limiter, "is_allowed", lambda client_ip: (False, 42))

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "42"
    assert response.json()["error"] == "Rate limit exceeded"
