"""In-process rate limiter — protects the GPU and LLM from runaway callers.

Why in-process instead of slowapi / redis: this engine is single-process,
single-user (the iPhone hits it on the LAN). A shared in-memory token bucket
is enough and adds zero deployment surface. If we ever multi-process the
worker, this needs to move to Redis — see the comment in `check()`.

Buckets are keyed by (path_prefix, identity), where identity is the auth
key id when present, otherwise the client IP. So one device flooding /v1/llm
doesn't penalise another device on /v1/clips.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from threading import Lock

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


@dataclass
class RateRule:
    """Token bucket parameters for a path prefix."""
    capacity: int          # max tokens (== max burst size)
    refill_per_sec: float  # tokens added per second of wall clock


# Default policy. Keys are URL path prefixes; first match wins so order
# matters. Tune by editing here, not by patching the middleware.
DEFAULT_POLICY: list[tuple[str, RateRule]] = [
    # Heavy GPU/LLM calls: 10 req/min sustained, burst of 5.
    ("/v1/llm/", RateRule(capacity=5, refill_per_sec=10 / 60)),
    ("/v1/translation/", RateRule(capacity=5, refill_per_sec=10 / 60)),
    ("/v1/content/", RateRule(capacity=5, refill_per_sec=10 / 60)),
    ("/v1/ml-scoring/", RateRule(capacity=5, refill_per_sec=10 / 60)),
    ("/v1/emotion/", RateRule(capacity=5, refill_per_sec=10 / 60)),
    ("/v1/virality/", RateRule(capacity=5, refill_per_sec=10 / 60)),
    # Publish endpoints: stricter — 5 req/min, no burst.
    ("/v1/social/", RateRule(capacity=2, refill_per_sec=5 / 60)),
]


@dataclass
class _Bucket:
    tokens: float
    last_refill: float
    rule: RateRule


class TokenBucketRegistry:
    """Thread-safe registry of (prefix, identity) -> bucket.

    take(key, rule) returns (allowed, retry_after_sec). retry_after is only
    meaningful when allowed is False.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, _Bucket] = {}
        self._lock = Lock()

    def take(self, key: str, rule: RateRule, now: float | None = None) -> tuple[bool, float]:
        now = now if now is not None else time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(tokens=float(rule.capacity), last_refill=now, rule=rule)
                self._buckets[key] = bucket
            # Refill since last call. Cap at capacity.
            elapsed = max(0.0, now - bucket.last_refill)
            bucket.tokens = min(rule.capacity, bucket.tokens + elapsed * rule.refill_per_sec)
            bucket.last_refill = now
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True, 0.0
            # Not enough — work out when the next token will arrive.
            missing = 1.0 - bucket.tokens
            retry_after = missing / rule.refill_per_sec if rule.refill_per_sec > 0 else 1.0
            return False, retry_after

    def reset(self) -> None:
        """Test helper — clears all buckets."""
        with self._lock:
            self._buckets.clear()


_registry = TokenBucketRegistry()


def reset_registry_for_tests() -> None:
    """Drop every bucket — pytest fixtures call this between tests."""
    _registry.reset()


def _match_rule(path: str, policy: list[tuple[str, RateRule]]) -> RateRule | None:
    for prefix, rule in policy:
        if path.startswith(prefix):
            return rule
    return None


def _identity(request: Request) -> str:
    """The rate-limit identity is the authenticated key id when we have one,
    falling back to the client IP. Keeps abusive callers contained without
    blocking the entire household when several phones share one external IP."""
    auth_row = getattr(request.state, "auth_row", None)
    if auth_row is not None and getattr(auth_row, "id", None):
        return f"key:{auth_row.id}"
    # request.client can be None in some test setups.
    client = request.client.host if request.client else "anonymous"
    return f"ip:{client}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply token-bucket limits to a list of path prefixes."""

    def __init__(
        self,
        app: ASGIApp,
        policy: list[tuple[str, RateRule]] | None = None,
        registry: TokenBucketRegistry | None = None,
    ) -> None:
        super().__init__(app)
        self._policy = policy if policy else DEFAULT_POLICY
        self._registry = registry or _registry

    async def dispatch(self, request: Request, call_next):
        rule = _match_rule(request.url.path, self._policy)
        if rule is None:
            return await call_next(request)
        identity = _identity(request)
        key = f"{request.url.path.rsplit('/', 1)[0]}|{identity}"
        allowed, retry_after = self._registry.take(key, rule)
        if not allowed:
            logger.warning("Rate limit hit: %s by %s (retry in %.1fs)", request.url.path, identity, retry_after)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after_seconds": round(retry_after, 1),
                },
                headers={"Retry-After": str(max(1, int(retry_after)))},
            )
        return await call_next(request)
