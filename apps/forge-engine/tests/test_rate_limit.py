"""Token-bucket rate limiter tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from forge_engine.core.rate_limit import (
    DEFAULT_POLICY,
    RateLimitMiddleware,
    RateRule,
    TokenBucketRegistry,
    reset_registry_for_tests,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry_for_tests()
    yield
    reset_registry_for_tests()


def test_bucket_allows_up_to_capacity():
    reg = TokenBucketRegistry()
    rule = RateRule(capacity=3, refill_per_sec=0.0)  # no refill — pure burst
    allowed = [reg.take("k", rule)[0] for _ in range(4)]
    assert allowed == [True, True, True, False]


def test_bucket_refills_over_time():
    reg = TokenBucketRegistry()
    rule = RateRule(capacity=2, refill_per_sec=10.0)  # 10/sec
    # Drain.
    reg.take("k", rule, now=0.0)
    reg.take("k", rule, now=0.0)
    assert reg.take("k", rule, now=0.0)[0] is False
    # 0.2s later — 2 tokens refilled.
    assert reg.take("k", rule, now=0.2)[0] is True
    assert reg.take("k", rule, now=0.2)[0] is True
    assert reg.take("k", rule, now=0.2)[0] is False


def test_bucket_separates_keys():
    reg = TokenBucketRegistry()
    rule = RateRule(capacity=1, refill_per_sec=0.0)
    assert reg.take("a", rule)[0] is True
    assert reg.take("b", rule)[0] is True
    # Both drained, but they're independent.
    assert reg.take("a", rule)[0] is False
    assert reg.take("b", rule)[0] is False


def _app(policy):
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, policy=policy)

    @app.get("/v1/llm/ping")
    async def llm_ping():
        return {"ok": True}

    @app.get("/v1/clips/queue/pending")
    async def free():
        return {"free": True}

    return app


def test_middleware_429_after_burst():
    # Tiny capacity, no refill — easy to exhaust deterministically.
    policy = [("/v1/llm/", RateRule(capacity=2, refill_per_sec=0.0))]
    client = TestClient(_app(policy))
    assert client.get("/v1/llm/ping").status_code == 200
    assert client.get("/v1/llm/ping").status_code == 200
    r = client.get("/v1/llm/ping")
    assert r.status_code == 429
    assert "retry_after_seconds" in r.json()
    assert "Retry-After" in r.headers


def test_middleware_does_not_limit_unmatched_paths():
    policy = [("/v1/llm/", RateRule(capacity=1, refill_per_sec=0.0))]
    client = TestClient(_app(policy))
    # First /v1/llm passes, second 429s.
    client.get("/v1/llm/ping")
    assert client.get("/v1/llm/ping").status_code == 429
    # /v1/clips is unmatched — always 200.
    for _ in range(5):
        assert client.get("/v1/clips/queue/pending").status_code == 200


def test_default_policy_covers_heavy_endpoints():
    """Make sure we never silently drop a rule for a sensitive prefix."""
    prefixes = {prefix for prefix, _ in DEFAULT_POLICY}
    must_cover = {
        "/v1/llm/",
        "/v1/translation/",
        "/v1/content/",
        "/v1/ml-scoring/",
        "/v1/social/",
    }
    assert must_cover.issubset(prefixes)


def test_middleware_without_explicit_policy_serves_requests():
    """Regression: main.py adds the middleware with no `policy` argument. The
    default must resolve to DEFAULT_POLICY — it used to be a dataclasses.field()
    sentinel, so `_match_rule` did `for ... in <Field>` and raised TypeError on
    EVERY request through the real app."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)  # no policy → default path

    @app.get("/health")
    async def health():
        return {"ok": True}

    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200  # not 500 / TypeError
    assert r.json() == {"ok": True}
