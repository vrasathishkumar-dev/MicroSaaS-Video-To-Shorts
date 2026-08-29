"""Lightweight in-process rate limiting for sensitive auth endpoints.

Implements a simple in-memory sliding window keyed by client IP. This is
process-local (not shared across multiple workers/instances) but is enough
to blunt basic brute-force / registration-spam attempts per CLAUDE.md
security requirements without pulling in an external dependency (e.g.
slowapi + Redis). Swap for a shared-store limiter if the app is scaled
horizontally across multiple processes/instances.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from fastapi import Request, status

from app.exceptions import AppException


class RateLimitExceededError(AppException):
    """Raised when a client exceeds the allowed request rate."""

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            message="Too many requests, please try again later",
            code="RATE_LIMITED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


class SlidingWindowRateLimiter:
    """A simple thread-safe, in-memory sliding-window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> None:
        """Record a hit for `key`, raising RateLimitExceededError if over budget."""

        now = time.monotonic()
        window_start = now - self._window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < window_start:
                hits.pop(0)
            if len(hits) >= self._max_requests:
                retry_after = int(self._window_seconds - (now - hits[0])) + 1
                raise RateLimitExceededError(retry_after_seconds=retry_after)
            hits.append(now)


def _client_key(request: Request) -> str:
    if request.client:
        return request.client.host
    return "unknown"


# 5 attempts per 60-second window per client IP for register/login.
_auth_limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60)


async def rate_limit_auth(request: Request) -> None:
    """FastAPI dependency: rate-limit sensitive auth endpoints per client IP.

    Usage: `@router.post("/login", dependencies=[Depends(rate_limit_auth)])`.
    """

    _auth_limiter.check(_client_key(request))


# Video submission triggers a paid transcription call plus background
# processing per request — 10 submissions per 5-minute window per user.
_video_submit_limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=300)

# B-roll search/auto-source calls paid Pexels/Pixabay APIs (auto-source can
# fan out to several calls per request) — 20 per 5-minute window per user.
_broll_limiter = SlidingWindowRateLimiter(max_requests=20, window_seconds=300)


def rate_limit_video_submit(user_id: int) -> None:
    """Rate-limit video submissions per authenticated user.

    Called directly from the route handler body (not as a FastAPI
    `Depends()`) once `current_user` has been resolved, since the limit
    key is the user id rather than anything derivable before auth runs.
    """

    _video_submit_limiter.check(f"user:{user_id}")


def rate_limit_broll(user_id: int) -> None:
    """Rate-limit B-roll search/auto-source calls per authenticated user.

    Called directly from the route handler body once `current_user` has
    been resolved — see `rate_limit_video_submit` for why this isn't a
    `Depends()`.
    """

    _broll_limiter.check(f"user:{user_id}")
