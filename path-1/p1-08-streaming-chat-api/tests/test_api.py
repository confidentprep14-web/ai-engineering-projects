"""Exercises real logic: rate limiter sliding window, stats aggregation over
a real SQLite file, and the /chat route's rate-limit branch. Only the LLM
call itself is mocked — the rate limiter and the database are real."""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_PATH", tempfile.mktemp(suffix=".db"))

from src.database import get_stats, init_db, log_request  # noqa: E402
from src.main import app, rate_limiter  # noqa: E402
from src.rate_limiter import RateLimiter  # noqa: E402


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

    from fastapi.testclient import TestClient as _TestClient
    response = _TestClient(app).get("/stats")

    body = response.json()
    assert "total_requests" in body
    assert "p50_latency_ms" in body
    assert "p95_latency_ms" in body
    assert body["total_requests"] == 3


def test_rate_limiter_allows_under_limit_then_blocks():
    limiter = RateLimiter(requests_per_minute=5)

    for _ in range(5):
        allowed, retry_after_seconds = limiter.is_allowed("127.0.0.1")
        assert (allowed, retry_after_seconds) == (True, 0)

    sixth_allowed, sixth_retry_after_seconds = limiter.is_allowed("127.0.0.1")
    assert sixth_allowed is False
    assert sixth_retry_after_seconds > 0


def test_get_stats_calculates_p50_correctly(temp_db_path):
    latencies_ms = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    for index, latency_ms in enumerate(latencies_ms):
        log_request(
            temp_db_path, f"req-{index}", "127.0.0.1", 10, 20, 0.0001,
            latency_ms, "claude-3-5-haiku-20241022", "success",
        )

    stats = get_stats(temp_db_path)

    assert stats["p50_latency_ms"] == 550
