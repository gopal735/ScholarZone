"""A small in-process rate limiter.

The repository has no throttling of any kind today, so the private outreach
routes and the draft endpoint need one. Two properties matter more than
precision.

It is **in-process**, which means it bounds one application instance and no more.
That is enough to stop a single misbehaving client from looping, and it is
honest about its own limit: a multi-instance deployment would need shared state.
Writing a Redis-backed limiter now, with no Redis and no second instance to
justify it, would be a dependency bought for a problem that does not exist yet.

It **fails closed on unbounded keys**. The bucket count is capped, and once the
cap is reached a new client is simply refused rather than evicting an entry to
make room. Eviction would let a flood of new keys push real clients out of the
table, which is the opposite of what a limiter is for.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass


@dataclass
class _Bucket:
    count: int
    window_started_at: float


class RateLimitExceeded(Exception):
    """Raised when a client has used its allowance."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Too many requests.")
        self.retry_after_seconds = max(1, int(retry_after_seconds))


class InProcessRateLimiter:
    """A fixed-window counter per key."""

    def __init__(self, limit: int, window_seconds: int, max_keys: int = 10000) -> None:
        self._limit = max(1, limit)
        self._window = max(1, window_seconds)
        self._max_keys = max(1, max_keys)
        self._buckets: "OrderedDict[str, _Bucket]" = OrderedDict()
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> None:
        """Consume one unit of ``key``'s allowance, or raise.

        Raises rather than returning a boolean so a caller cannot accidentally
        proceed past a limit it did not check.
        """
        moment = time.monotonic() if now is None else now
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or moment - bucket.window_started_at >= self._window:
                if len(self._buckets) >= self._max_keys:
                    # Refuse rather than evict. See the module docstring.
                    raise RateLimitExceeded(self._window)
                self._buckets[key] = _Bucket(count=1, window_started_at=moment)
                return
            bucket.count += 1
            if bucket.count > self._limit:
                retry_after = self._window - int(moment - bucket.window_started_at)
                raise RateLimitExceeded(retry_after)

    def reset(self) -> None:
        """Clear every bucket. Used by tests."""
        with self._lock:
            self._buckets.clear()


#: Separate budgets per surface rather than one shared counter, so a student
#: reading their supervisor list cannot consume the allowance that protects
#: their own outreach writes.
supervisor_read_limiter = InProcessRateLimiter(limit=120, window_seconds=60)
draft_limiter = InProcessRateLimiter(limit=20, window_seconds=60)
outreach_write_limiter = InProcessRateLimiter(limit=60, window_seconds=60)


__all__ = [
    "InProcessRateLimiter",
    "RateLimitExceeded",
    "draft_limiter",
    "outreach_write_limiter",
    "supervisor_read_limiter",
]