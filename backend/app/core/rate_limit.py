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

Two further properties hold after the production-hardening pass:

* **Expired buckets are safely reclaimed.** A bucket whose window has fully aged
  out is dropped when it is read, and the table sweeps already-expired entries
  before refusing a new key at the cap. Stale buckets therefore stop consuming
  capacity, so a flood of short-lived keys cannot permanently exhaust the table
  against legitimate clients who arrive afterwards.
* **Active clients are never evicted.** Only expired buckets are removed, and
  only through the read path or an expiry-only sweep. A live bucket is never
  dropped, so a client's in-window budget is never reset behind its back.

The bucket key must identify a caller, not a request. :func:`public_api_key`
folds dynamic path segments (``/scholarships/12/supervisors`` becomes
``/scholarships/{id}/supervisors``) so the shared public limiter cannot be
drained by a caller rotating unknown scholarship ids through dynamic paths.

Client identity comes from :func:`client_identifier`, which honours
``X-Forwarded-For`` only when the immediate peer is a configured trusted proxy.
Arbitrary caller-supplied forwarded headers are ignored otherwise, and the
actual request client address is used instead. See the settings for the trusted
proxy configuration.
"""

from __future__ import annotations

import ipaddress
import re
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


def _is_trusted_proxy(address: str, trusted_proxies) -> bool:
    """Return whether *address* belongs to a configured trusted proxy.

    Entries may be bare addresses or CIDR networks, as produced by the
    ``SCHOLARZONE_TRUSTED_PROXIES`` setting. Anything that cannot be parsed is
    never treated as a trusted proxy.
    """
    token = (address or "").strip()
    if not token:
        return False
    for entry in trusted_proxies or ():
        candidate = str(entry).strip()
        if not candidate:
            continue
        if token == candidate:
            return True
        try:
            if ipaddress.ip_address(token) in ipaddress.ip_network(candidate, strict=False):
                return True
        except ValueError:
            continue
    return False


def client_identifier(request, trusted_proxies=None) -> str:
    """Return the caller identity used for rate-limit budgets.

    ``X-Forwarded-For`` is only honoured when the immediate peer the platform
    routed through is a configured trusted proxy. Behind such a proxy the header
    is built by appending the originating client on the right, with proxy hops to
    its right; any leftmost entries were supplied by the caller and cannot be
    trusted. The entries are therefore scanned from the right, and the nearest
    untrusted entry to that side is the caller; entries that name another
    trusted proxy are skipped. This preserves the single-entry behaviour when a
    proxy overwrites rather than appends the header.

    When the peer is not a trusted proxy - or no proxy is configured - the
    caller-supplied header is treated as attacker-controlled input and ignored,
    and the actual request client address is used instead.

    Returns the same value for repeated requests from one caller, so a single
    caller can never consume another caller's budget, and a caller cannot rotate
    its key by forging a header it is not allowed to set.
    """
    peer = request.client.host if request.client else "unknown"
    forwarded = None
    headers = getattr(request, "headers", None)
    if headers is not None:
        forwarded = headers.get("x-forwarded-for")
    if forwarded and _is_trusted_proxy(peer, trusted_proxies):
        entries = [entry.strip() for entry in forwarded.split(",") if entry and entry.strip()]
        # Scan from the right: the trusted proxy appends the real client on the
        # rightmost side, and any leftmost entries were supplied by the caller
        # and cannot be trusted. The first untrusted entry encountered from the
        # right is the originating client.
        for entry in reversed(entries):
            if not _is_trusted_proxy(entry, trusted_proxies):
                return entry
        # Every hop named in the header was itself a trusted proxy; the nearest
        # trusted proxy is the boundary and the actual peer is the caller we can
        # stand behind.
        return peer
    return peer


_ALLOWED_PUBLIC_TEMPLATES = frozenset(
    {
        "/scholarships",
        "/scholarships/stats",
        "/scholarships/{id}",
        "/scholarships/{id}/supervisors",
        "/scholarships/{id}/supervisor-summary",
    }
)


def public_api_key(client: str, path: str) -> str:
    """Return a bounded, caller-scoped bucket key for a public path.

    Dynamic path segments are folded onto a placeholder before the key is built,
    so ``/scholarships/12/supervisors`` and ``/scholarships/13/supervisors`` share
    one bucket for one caller instead of minting a fresh key per identifier. The
    shared public limiter therefore cannot be exhausted by rotating unknown
    scholarship ids through dynamic URL paths.

    Only a small, fixed set of static path segments is preserved verbatim; every
    other segment is folded onto the same placeholder, so arbitrary path values
    cannot mint a distinct bucket either.
    """
    raw = (path or "/").strip()
    if raw.startswith("/api/"):
        raw = raw[4:] or "/"
    if not raw or raw == "/":
        return f"{client}:/scholarships/other"
    segments = [segment for segment in raw.split("/") if segment != ""]
    normalized_segments = [
        "{id}" if segment.isdigit() else segment for segment in segments
    ]
    normalized = "/" + "/".join(normalized_segments)
    if normalized not in _ALLOWED_PUBLIC_TEMPLATES:
        normalized = "/scholarships/other"
    return f"{client}:{normalized}"


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
                # The previous window fully aged out, so the slot is free again.
                # Drop it before inserting so reclaimed keys cannot accumulate and
                # silently exhaust the table against clients that arrive later.
                if bucket is not None:
                    del self._buckets[key]
                if len(self._buckets) >= self._max_keys:
                    # Refuse rather than evict. See the module docstring. Only
                    # already-expired entries are swept here, so a live bucket is
                    # never the reason a legitimate client is refused.
                    self._sweep_expired(moment)
                if len(self._buckets) >= self._max_keys:
                    raise RateLimitExceeded(self._window)
                self._buckets[key] = _Bucket(count=1, window_started_at=moment)
                return
            bucket.count += 1
            if bucket.count > self._limit:
                retry_after = self._window - int(moment - bucket.window_started_at)
                raise RateLimitExceeded(retry_after)

    def _sweep_expired(self, moment: float) -> None:
        """Delete every bucket whose window has aged out.

        Runs under the limiter lock, so a concurrent writer cannot observe a
        half-swept table, and only ever touches expired entries.
        """
        expired = [
            key
            for key, bucket in self._buckets.items()
            if moment - bucket.window_started_at >= self._window
        ]
        for key in expired:
            del self._buckets[key]

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

#: Public API rate limiter - generous limits to avoid false positives. The key
#: is scoped per caller and per normalized path, so dynamic segments cannot mint
#: unbounded per-identifier buckets.
public_api_limiter = InProcessRateLimiter(limit=300, window_seconds=60)
public_stats_limiter = InProcessRateLimiter(limit=60, window_seconds=60)


__all__ = [
    "InProcessRateLimiter",
    "RateLimitExceeded",
    "client_identifier",
    "draft_limiter",
    "outreach_write_limiter",
    "public_api_key",
    "public_api_limiter",
    "public_stats_limiter",
    "supervisor_read_limiter",
]
