"""Regression tests for InProcessRateLimiter expiry and capacity handling."""

from __future__ import annotations

import threading

import pytest

from app.core.rate_limit import InProcessRateLimiter, RateLimitExceeded


def test_expired_buckets_are_reclaimed_before_capacity_rejection():
    limiter = InProcessRateLimiter(limit=5, window_seconds=10, max_keys=2)
    limiter.check("a", now=0.0)
    limiter.check("b", now=0.0)
    with pytest.raises(RateLimitExceeded):
        limiter.check("c", now=0.0)
    limiter.check("c", now=10.0)


def test_active_buckets_are_preserved_by_cleanup():
    limiter = InProcessRateLimiter(limit=1, window_seconds=10, max_keys=2)
    limiter.check("a", now=0.0)
    limiter.check("b", now=5.0)
    with pytest.raises(RateLimitExceeded):
        limiter.check("a", now=5.0)


def test_capacity_boundary_rejects_new_key():
    limiter = InProcessRateLimiter(limit=10, window_seconds=60, max_keys=1)
    limiter.check("a", now=0.0)
    with pytest.raises(RateLimitExceeded) as exc:
        limiter.check("b", now=0.0)
    assert exc.value.retry_after_seconds == 60


def test_capacity_recovers_after_expired_buckets_eligible():
    limiter = InProcessRateLimiter(limit=10, window_seconds=10, max_keys=1)
    limiter.check("a", now=0.0)
    with pytest.raises(RateLimitExceeded):
        limiter.check("b", now=5.0)
    limiter.check("b", now=10.0)


def test_expiry_boundary_uses_inclusive_window():
    limiter = InProcessRateLimiter(limit=1, window_seconds=10, max_keys=10)
    limiter.check("a", now=0.0)
    with pytest.raises(RateLimitExceeded):
        limiter.check("a", now=9.999)
    limiter.check("a", now=10.0)


def test_isolation_between_students():
    limiter = InProcessRateLimiter(limit=1, window_seconds=60, max_keys=10)
    limiter.check("student-1", now=0.0)
    with pytest.raises(RateLimitExceeded):
        limiter.check("student-1", now=0.0)
    limiter.check("student-2", now=0.0)


def test_retry_after_boundary_for_window_cap():
    limiter = InProcessRateLimiter(limit=1, window_seconds=10, max_keys=10)
    limiter.check("a", now=0.0)
    with pytest.raises(RateLimitExceeded) as exc:
        limiter.check("a", now=3.0)
    assert exc.value.retry_after_seconds == 7


def test_retry_after_clamps_to_one():
    limiter = InProcessRateLimiter(limit=1, window_seconds=10, max_keys=10)
    limiter.check("a", now=0.0)
    with pytest.raises(RateLimitExceeded) as exc:
        limiter.check("a", now=9.9)
    assert exc.value.retry_after_seconds == 1


def test_retry_after_for_capacity_rejection():
    limiter = InProcessRateLimiter(limit=5, window_seconds=60, max_keys=1)
    limiter.check("a", now=0.0)
    with pytest.raises(RateLimitExceeded) as exc:
        limiter.check("b", now=0.0)
    assert exc.value.retry_after_seconds == 60


def test_concurrency_does_not_corrupt_bucket_state():
    limiter = InProcessRateLimiter(limit=100, window_seconds=60, max_keys=1000)
    successes = {"n": 0}
    lock = threading.Lock()

    def worker():
        try:
            limiter.check("shared", now=0.0)
            with lock:
                successes["n"] += 1
        except RateLimitExceeded:
            pass

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert successes["n"] == 50
    with limiter._lock:
        assert limiter._buckets["shared"].count == 50
