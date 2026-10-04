"""Source outcomes, render budgets, and barrier detection for supervisor discovery.

This module is the vocabulary the rest of the pipeline speaks when it asks "what
happened?". The reason it exists is that a single question has at least six honest
answers, and the previous design had fewer, so two of them had to share one.

The distinction that matters most:

    SOURCE_REQUIRES_RENDERING
        !=
    NOT_FOUND_WITHIN_SEARCH_SCOPE

A JavaScript-rendered directory is a source we could not read. A directory we read
completely and which lists nobody is a true negative. Collapsing them is how a
crawler that cannot see ends up asserting that a university employs nobody.

Nothing here attempts to defeat an access barrier. Cloudflare challenges,
Turnstile, reCAPTCHA and hCaptcha are **detected** and reported as
``SOURCE_BLOCKED``, because a site that has asked for a human is a site we stop
reading. There is no CAPTCHA solving, no stealth patching and no credential use
anywhere in this feature, and the barrier detectors exist to make sure that stays
true even if somebody later tries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urlparse


class SourceOutcome(StrEnum):
    """What happened when we tried to read an institutional source."""

    #: Read successfully, with usable content.
    SUCCESS = "success"
    #: Reached and read, but the content is assembled in the browser. We cannot
    #: judge it without executing JavaScript, so we cannot call it either way.
    SOURCE_REQUIRES_RENDERING = "source_requires_rendering"
    #: The institution asked for authentication, or refused us outright.
    SOURCE_BLOCKED = "source_blocked"
    #: Read completely and no person matched. A true negative, and the only state
    #: that licenses one.
    NOT_FOUND_WITHIN_SEARCH_SCOPE = "not_found_within_search_scope"
    #: Not a usable source at all: not http(s), or not an institutional host.
    INVALID_SOURCE = "invalid_source"
    #: Something went wrong that is not about the source's content - a timeout, a
    #: DNS or TLS failure, a browser crash. Never a negative.
    ERROR = "error"


#: Outcomes that license no conclusion at all. Every one of them must resolve to
#: an inconclusive coverage state rather than to "no verified supervisor found".
NON_CONCLUSIVE_OUTCOMES: frozenset[str] = frozenset(
    {
        SourceOutcome.SOURCE_REQUIRES_RENDERING,
        SourceOutcome.SOURCE_BLOCKED,
        SourceOutcome.INVALID_SOURCE,
        SourceOutcome.ERROR,
    }
)


class RenderErrorKind(StrEnum):
    """Explicit failure taxonomy. Deliberately granular.

    Collapsing these into one value is how "the browser crashed" becomes "the
    university has no professors". Each kind below maps to its own coverage state,
    and none of them maps to a negative.
    """

    NAVIGATION_TIMEOUT = "navigation_timeout"
    PAGE_TIMEOUT = "page_timeout"
    DNS_FAILURE = "dns_failure"
    TLS_FAILURE = "tls_failure"
    HTTP_ERROR = "http_error"
    HTTP_403 = "http_403"
    HTTP_404 = "http_404"
    HTTP_429 = "http_429"
    HTTP_5XX = "http_5xx"
    BROWSER_UNAVAILABLE = "browser_unavailable"
    BROWSER_CRASH = "browser_crash"
    PAGE_NEVER_STABILISED = "page_never_stabilised"
    LOGIN_REQUIRED = "login_required"
    ANTI_BOT_CHALLENGE = "anti_bot_challenge"
    DISABLED_BY_CONFIG = "disabled_by_config"
    BUDGET_EXHAUSTED = "budget_exhausted"
    UNKNOWN = "unknown"


#: Kinds that mean "we were not allowed", as opposed to "it was broken".
ACCESS_BARRIER_KINDS: frozenset[str] = frozenset(
    {RenderErrorKind.LOGIN_REQUIRED, RenderErrorKind.ANTI_BOT_CHALLENGE, RenderErrorKind.HTTP_403}
)


@dataclass(frozen=True)
class RenderBudget:
    """Every limit the browser may consume, in one place.

    All of them are finite by construction and enforced, not advisory. A render
    budget with a single unbounded dimension is an unbounded crawl, so there is no
    way to construct one here: page count, scroll iterations, candidate count,
    content size, redirect count, concurrency and wall clock are all required
    arguments with defaults that are small enough to be safe.

    The wall-clock figure is per source, not per run. A batch of 25 institutions
    at 90 seconds each is still bounded, and a single pathological page cannot
    consume the whole batch.
    """

    #: Hard ceiling on the whole source, regardless of what happens inside it.
    total_seconds: float = 90.0
    #: Per-navigation ceiling.
    navigation_timeout_ms: int = 20_000
    #: Ceiling on pages rendered for one source (directory + profiles).
    max_pages: int = 8
    #: Ceiling on pagination/next-link steps.
    max_pagination_steps: int = 3
    #: Ceiling on scroll increments, for infinite-scroll directories.
    max_scroll_iterations: int = 6
    #: Ceiling on candidates extracted from one source.
    max_candidates: int = 40
    #: Ceiling on rendered HTML size. Bounds memory and storage.
    max_content_bytes: int = 3_000_000
    #: Ceiling on redirect hops the browser will follow.
    max_redirects: int = 5
    #: Concurrent browser contexts. One per source, capped.
    max_concurrent_contexts: int = 2
    #: Ceiling on browser jobs in a single supervisor invocation.
    max_browser_jobs: int = 5

    def budget_exhausted_reason(self, **used) -> str | None:
        """Return which bound was hit, or ``None`` if none was.

        Named rather than a bare boolean so a coverage row can say *why* a render
        stopped, which is the difference between a retryable outcome and a
        mystery.
        """
        checks = (
            ("total_seconds", "total_seconds", ">="),
            ("pages", "max_pages", ">="),
            ("pagination_steps", "max_pagination_steps", ">="),
            ("scroll_iterations", "max_scroll_iterations", ">="),
            ("candidates", "max_candidates", ">="),
        )
        for key, attribute, operator in checks:
            if key not in used:
                continue
            limit = getattr(self, attribute)
            if operator == ">=" and used[key] >= limit:
                return attribute
        return None


@dataclass
class SourceObservation:
    """The outcome of one attempt at one source, with enough detail to act on."""

    url: str
    outcome: SourceOutcome
    #: RenderErrorKind when the outcome is an error or a barrier.
    error_kind: str | None = None
    #: Short operator-facing explanation. Never published in a public response.
    detail: str | None = None
    #: Rendered HTML, when a render succeeded. Not persisted.
    html: str | None = None
    #: How the content was obtained.
    discovery_path: str | None = None
    elapsed_ms: int | None = None
    #: Which bounds were consumed, for observability.
    limits_used: dict[str, int] = field(default_factory=dict)

    @property
    def is_conclusive(self) -> bool:
        """Whether this observation licenses a negative claim."""
        return self.outcome == SourceOutcome.NOT_FOUND_WITHIN_SEARCH_SCOPE


# ---------------------------------------------------------------------------
# Barrier detection
# ---------------------------------------------------------------------------

#: Markers of an anti-bot interstitial. Detection only - this feature never
#: attempts to pass one. Sources: Cloudflare challenge/turnstile documentation,
#: and the markers those products inject.
_ANTI_BOT_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"/cdn-cgi/challenge-platform/", "cloudflare_challenge"),
    (r"\bcf_chl_(?:opt|prog|prof)\b", "cloudflare_challenge"),
    # Turnstile appears either as the widget class or as its API script; a page
    # can carry the challenge without ever mentioning "cf-turnstile" by name.
    (r"\bcf-turnstile\b|/turnstile/v0|turnstile\.js", "cloudflare_turnstile"),
    (r"\bg-recaptcha\b|recaptcha/api\.js", "recaptcha"),
    (r"\bh-captcha\b|hcaptcha\.com/1/api\.js", "hcaptcha"),
    (r"just a moment\s*\.\.\.?", "interstitial_challenge"),
    (r"checking your browser", "interstitial_challenge"),
    (r"verify(?:ing)? you are (?:a )?human", "interstitial_challenge"),
    (r"enable javascript and cookies to continue", "interstitial_challenge"),
    (r"\bcf_challenge\b", "cloudflare_challenge"),
)

#: Authentication walls. Also detection only; nothing here ever submits a
#: credential, and there is no code path that could.
_LOGIN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r'<input[^>]+type=["\']password["\']', "password_field"),
    (r'<form[^>]*action=["\'][^"\']*/(?:signin|sign-in|login|log-in|auth|authenticate|sso)', "login_form"),
    (r"\b(?:sign in|signin|log ?in|authentication required)\b", "sign_in_language"),
)


def detect_access_barrier(html: str) -> tuple[str, str] | None:
    """Return ``(kind, marker)`` if the page is a login or anti-bot wall.

    Anti-bot is checked first. A Cloudflare challenge often *also* contains a
    script tag mentioning sign-in, and reporting that as "login required" would
    invite somebody to try to authenticate against a challenge page, which is
    exactly the wrong next step.
    """
    if not html:
        return None
    lowered = html.lower()
    for pattern, marker in _ANTI_BOT_PATTERNS:
        if re.search(pattern, lowered):
            return ("anti_bot_challenge", marker)
    for pattern, marker in _LOGIN_PATTERNS:
        if re.search(pattern, lowered):
            return ("login_required", marker)
    return None


def is_valid_source_url(url: str, allowed_suffixes: tuple[str, ...]) -> bool:
    """Return whether ``url`` is an http(s) URL on an institutional host."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.netloc or "").lower()
    if not host:
        return False
    return host.endswith(allowed_suffixes)


__all__ = [
    "ACCESS_BARRIER_KINDS",
    "NON_CONCLUSIVE_OUTCOMES",
    "RenderBudget",
    "RenderErrorKind",
    "SourceObservation",
    "SourceOutcome",
    "detect_access_barrier",
    "is_valid_source_url",
]