"""Sliding-window rate limiter logic — no AWS, no LLM calls, pure unit tests."""
import time

from src.rate_limiter import RateLimiter


def test_allows_requests_under_the_limit():
    limiter = RateLimiter(requests_per_minute=5)

    for _ in range(5):
        allowed, retry_after_seconds = limiter.is_allowed("127.0.0.1")
        assert (allowed, retry_after_seconds) == (True, 0)


def test_blocks_the_request_that_exceeds_the_limit():
    limiter = RateLimiter(requests_per_minute=3)
    for _ in range(3):
        limiter.is_allowed("10.0.0.1")

    allowed, retry_after_seconds = limiter.is_allowed("10.0.0.1")

    assert allowed is False
    assert retry_after_seconds > 0


def test_tracks_each_client_ip_independently():
    limiter = RateLimiter(requests_per_minute=1)

    first_client_allowed, _ = limiter.is_allowed("1.1.1.1")
    second_client_allowed, _ = limiter.is_allowed("2.2.2.2")

    assert first_client_allowed is True
    assert second_client_allowed is True


def test_old_requests_outside_the_window_are_discarded():
    limiter = RateLimiter(requests_per_minute=2)
    now = time.time()
    # Simulate two requests that happened 61 seconds ago — outside the window.
    limiter.window["3.3.3.3"] = [now - 61, now - 61]

    allowed, retry_after_seconds = limiter.is_allowed("3.3.3.3")

    assert (allowed, retry_after_seconds) == (True, 0)
    assert len(limiter.window["3.3.3.3"]) == 1
