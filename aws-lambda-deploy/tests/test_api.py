"""Exercises real logic: stats aggregation over a real SQLite file and the
/chat route's rate-limit branch. Only the LLM call itself is mocked — the
rate limiter and the database are real. No AWS calls happen in this file:
AWS_LAMBDA_FUNCTION_NAME is never set, so config.get_llm_api_key() takes the
plain env-var path, not the Secrets Manager path.
"""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_PATH", tempfile.mktemp(suffix=".db"))

from src.database import get_stats, init_db, log_request  # noqa: E402
from src.main import app, rate_limiter  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def temp_db_path(tmp_path):
    db_path = str(tmp_path / "test_requests.db")
    init_db(db_path)
    return db_path


def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "model" in body
    assert "provider" in body


def test_rate_limiter_returns_429_on_excess(client, monkeypatch):
    monkeypatch.setattr(rate_limiter, "is_allowed", lambda client_ip: (False, 30))

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"
    assert response.json()["error"] == "Rate limit exceeded"


def test_stats_returns_correct_structure(temp_db_path, monkeypatch):
    monkeypatch.setattr("src.main.config.database_path", temp_db_path)
    for latency_ms in (100, 200, 300):
        log_request(
            temp_db_path, "req-1", "127.0.0.1", 10, 20, 0.0001, latency_ms,
            "claude-3-5-haiku-20241022", "success",
        )

    response = TestClient(app).get("/stats")

    body = response.json()
    assert "total_requests" in body
    assert "p50_latency_ms" in body
    assert "p95_latency_ms" in body
    assert body["total_requests"] == 3


def test_unknown_provider_returns_500(client, monkeypatch):
    monkeypatch.setattr("src.main.config.llm_provider", "not-a-real-provider")

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 500
    assert response.json()["error"] == "Unknown LLM provider"


def test_handler_is_a_mangum_instance():
    """Confirms the Lambda entry point is wired up — this is the one bit of
    Lambda-specific glue that distinguishes this app from streaming-chat-api."""
    from mangum import Mangum

    from src.main import handler

    assert isinstance(handler, Mangum)
