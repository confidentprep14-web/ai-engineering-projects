"""Sliding-window rate limiter, keyed per client IP.

Same implementation as the standalone streaming-chat-api / aws-lambda-deploy
projects. A fixed-window limiter lets a client burst 2x the limit at the
window boundary. The sliding window avoids that by tracking individual
request timestamps and discarding the ones older than 60 seconds on every
check.

Caveat on Lambda: this state lives in the module-level dict of one execution
environment. A cold start (or a second concurrent execution environment)
starts with an empty window, so the rate limit is per-execution-environment,
not global across all Lambda concurrency. For a stronger global limit, this
would need to move to DynamoDB or API Gateway's own throttling.
"""
import time


class RateLimiter:
    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.window: dict[str, list[float]] = {}

    def is_allowed(self, client_ip: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds).

        retry_after_seconds is 0 when allowed, otherwise the time until the
        oldest request in the window ages out and frees up a slot.
        """
        now = time.time()
        request_timestamps = self.window.setdefault(client_ip, [])
        request_timestamps[:] = [
            timestamp for timestamp in request_timestamps if now - timestamp < 60
        ]

        if len(request_timestamps) >= self.requests_per_minute:
            oldest_timestamp = request_timestamps[0]
            retry_after_seconds = int(60 - (now - oldest_timestamp))
            return False, max(retry_after_seconds, 1)

        request_timestamps.append(now)
        return True, 0
