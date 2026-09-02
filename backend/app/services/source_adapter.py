"""Source-specific adaptive adapters for scholarship fetching and extraction.

Provides a SourceAdapter abstraction that optimizes fetch/extraction behavior
for different official scholarship source types without creating parallel retry
systems or duplicating existing pipeline logic.

CRITICAL: There is ONE authoritative retry orchestration path.
Adapters provide configuration hints, but execute_fetch_with_retry() remains
the single retry owner. No nested retries. No duplicate attempts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol
from urllib.parse import urlparse

from .discovery_config import ApprovedSourceData, StaticSourceRegistry, _extract_domain
from .official_source_fetcher import DEFAULT_TIMEOUT
from .source_health_service import HealthConfig, extract_domain


class SourceType(str, Enum):
    """Classification of source types for adapter selection."""

    OFFICIAL_SCHOLARSHIP_PORTAL = "official_scholarship_portal"
    GOVERNMENT_PORTAL = "government_portal"
    UNIVERSITY_PORTAL = "university_portal"
    STRUCTURED_PLATFORM = "structured_platform"
    GENERIC = "generic"


@dataclass(frozen=True)
class FetchConfig:
    """Source-specific fetch configuration hints."""

    timeout_connect: float = 5.0
    timeout_read: float = 10.0
    timeout_write: float = 5.0
    timeout_pool: float = 5.0
    follow_redirects: bool = True
    expected_content_types: tuple[str, ...] = ("text/html", "application/xhtml+xml")
    user_agent: str = "ScholarZone/1.0 (scholarship-verification-bot; +https://scholarzone.example.com)"
    max_retries_hint: int = 5
    respect_robots_txt: bool = True


@dataclass(frozen=True)
class ExtractionConfig:
    """Source-specific extraction configuration hints."""

    parser_strategy: str = "html_parser"
    fallback_extraction: bool = True
    alternate_extraction: bool = True
    preferred_field_patterns: tuple[str, ...] = ()
    confidence_threshold: str = "low"


@dataclass(frozen=True)
class RateLimitConfig:
    """Source-specific rate limit hints."""

    requests_per_minute: int | None = None
    backoff_seconds_hint: float | None = None
    retry_after_header: bool = True


@dataclass(frozen=True)
class CapabilityMetadata:
    """Metadata describing adapter capabilities."""

    supports_partial_content: bool = False
    supports_conditional_requests: bool = False
    supports_pagination: bool = False
    supports_structured_data: bool = False
    notes: tuple[str, ...] = ()


class SourceAdapter(Protocol):
    """Protocol for source-specific adaptive adapters.

    Adapters optimize fetch/extraction behavior for specific source types.
    They do NOT implement retry logic — they provide configuration hints.
    The existing execute_fetch_with_retry() remains the single retry owner.
    """

    @property
    def source_type(self) -> SourceType: ...

    @property
    def priority(self) -> int: ...

    def identifies(self, source_url: str, source_registry: StaticSourceRegistry | None = None) -> bool: ...

    def get_fetch_config(self, domain: str | None = None) -> FetchConfig: ...

    def get_extraction_config(self, domain: str | None = None) -> ExtractionConfig: ...

    def get_rate_limit_config(self, domain: str | None = None) -> RateLimitConfig: ...

    def get_capability_metadata(self) -> CapabilityMetadata: ...

    def get_health_config(self, domain: str | None = None) -> HealthConfig: ...


_GOVERNMENT_DOMAIN_PATTERNS: frozenset[str] = frozenset({
    ".gov", ".gov.uk", ".gov.au", ".gc.ca", ".gob.mx",
    ".go.jp", ".go.kr", ".gov.in", ".gov.br", ".gob.ec",
    ".admin.ch", ".bund.de", ".gouv.fr", ".gov.sg",
})

_GOVERNMENT_HOST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^www\.gov\.", re.IGNORECASE),
    re.compile(r"^gov\.", re.IGNORECASE),
    re.compile(r"\.gov\.", re.IGNORECASE),
    re.compile(r"\.gob\.", re.IGNORECASE),
    re.compile(r"\.go\.", re.IGNORECASE),
    re.compile(r"\.gc\.ca$", re.IGNORECASE),
    re.compile(r"\.admin\.ch$", re.IGNORECASE),
    re.compile(r"\.bund\.de$", re.IGNORECASE),
    re.compile(r"\.gouv\.fr$", re.IGNORECASE),
]

_UNIVERSITY_DOMAIN_PATTERNS: frozenset[str] = frozenset({
    ".edu", ".ac.uk", ".ac.jp", ".ac.kr", ".ac.in",
    ".ac.nz", ".ac.za", ".edu.au", ".edu.br", ".edu.sg",
})

_UNIVERSITY_HOST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^www\.edu\.", re.IGNORECASE),
    re.compile(r"\.edu\.", re.IGNORECASE),
    re.compile(r"\.ac\.", re.IGNORECASE),
    re.compile(r"^uni-", re.IGNORECASE),
    re.compile(r"\.edu$", re.IGNORECASE),
    re.compile(r"\.ac\.\w+$", re.IGNORECASE),
]

_KNOWN_SCHOLARSHIP_PLATFORMS: frozenset[str] = frozenset({
    "www.daad.de", "daad.de",
    "www.chevening.org", "chevening.org",
    "www.campusfrance.org", "campusfrance.org",
    "www.scholarshipdb.net", "scholarshipdb.net",
    "www.scholars4dev.com", "scholars4dev.com",
    "www.educationusa.state.gov", "educationusa.state.gov",
    "www.fulbright.state.gov", "fulbright.state.gov",
})


def _domain_matches_any(domain: str, patterns: frozenset[str]) -> bool:
    domain_lower = domain.lower()
    for pattern in patterns:
        if domain_lower.endswith(pattern):
            return True
    return False


def _domain_matches_patterns(domain: str, patterns: list[re.Pattern[str]]) -> bool:
    domain_lower = domain.lower()
    for pattern in patterns:
        if pattern.search(domain_lower):
            return True
    return False


class GovernmentPortalAdapter:
    """Adapter for government scholarship portals."""

    def __init__(self) -> None:
        self._source_type = SourceType.GOVERNMENT_PORTAL
        self._priority = 30

    @property
    def source_type(self) -> SourceType:
        return self._source_type

    @property
    def priority(self) -> int:
        return self._priority

    def identifies(self, source_url: str, source_registry: StaticSourceRegistry | None = None) -> bool:
        domain = extract_domain(source_url)
        if domain is None:
            return False
        if domain in _KNOWN_SCHOLARSHIP_PLATFORMS:
            return False
        if _domain_matches_any(domain, _GOVERNMENT_DOMAIN_PATTERNS):
            return True
        if _domain_matches_patterns(domain, _GOVERNMENT_HOST_PATTERNS):
            return True
        if source_registry is not None:
            source_type = source_registry.get_source_type(source_url)
            if source_type == "official_government":
                return True
        return False

    def get_fetch_config(self, domain: str | None = None) -> FetchConfig:
        return FetchConfig(
            timeout_connect=8.0,
            timeout_read=15.0,
            timeout_write=8.0,
            timeout_pool=8.0,
            follow_redirects=True,
            expected_content_types=("text/html", "application/xhtml+xml"),
            max_retries_hint=5,
            respect_robots_txt=True,
        )

    def get_extraction_config(self, domain: str | None = None) -> ExtractionConfig:
        return ExtractionConfig(
            parser_strategy="html_parser",
            fallback_extraction=True,
            alternate_extraction=True,
            preferred_field_patterns=("deadline", "award_amount", "eligibility", "duration"),
            confidence_threshold="medium",
        )

    def get_rate_limit_config(self, domain: str | None = None) -> RateLimitConfig:
        return RateLimitConfig(
            requests_per_minute=10,
            backoff_seconds_hint=30.0,
            retry_after_header=True,
        )

    def get_capability_metadata(self) -> CapabilityMetadata:
        return CapabilityMetadata(
            supports_partial_content=False,
            supports_conditional_requests=True,
            supports_pagination=False,
            supports_structured_data=False,
            notes=("Government portal adapter with conservative rate limits",),
        )

    def get_health_config(self, domain: str | None = None) -> HealthConfig:
        return HealthConfig(
            reliability_threshold_healthy=85.0,
            reliability_threshold_degraded=60.0,
            consecutive_failures_degraded=2,
            consecutive_failures_unhealthy=4,
            min_attempts_for_known=3,
            window_days=30,
        )


class UniversityPortalAdapter:
    """Adapter for university scholarship portals."""

    def __init__(self) -> None:
        self._source_type = SourceType.UNIVERSITY_PORTAL
        self._priority = 25

    @property
    def source_type(self) -> SourceType:
        return self._source_type

    @property
    def priority(self) -> int:
        return self._priority

    def identifies(self, source_url: str, source_registry: StaticSourceRegistry | None = None) -> bool:
        domain = extract_domain(source_url)
        if domain is None:
            return False
        if _domain_matches_any(domain, _UNIVERSITY_DOMAIN_PATTERNS):
            return True
        if _domain_matches_patterns(domain, _UNIVERSITY_HOST_PATTERNS):
            return True
        if source_registry is not None:
            source_type = source_registry.get_source_type(source_url)
            if source_type == "official_university":
                return True
        return False

    def get_fetch_config(self, domain: str | None = None) -> FetchConfig:
        return FetchConfig(
            timeout_connect=6.0,
            timeout_read=12.0,
            timeout_write=6.0,
            timeout_pool=6.0,
            follow_redirects=True,
            expected_content_types=("text/html", "application/xhtml+xml"),
            max_retries_hint=4,
            respect_robots_txt=True,
        )

    def get_extraction_config(self, domain: str | None = None) -> ExtractionConfig:
        return ExtractionConfig(
            parser_strategy="html_parser",
            fallback_extraction=True,
            alternate_extraction=True,
            preferred_field_patterns=("scholarship_name", "deadline", "award_amount", "eligibility", "gpa_requirement"),
            confidence_threshold="medium",
        )

    def get_rate_limit_config(self, domain: str | None = None) -> RateLimitConfig:
        return RateLimitConfig(
            requests_per_minute=15,
            backoff_seconds_hint=20.0,
            retry_after_header=True,
        )

    def get_capability_metadata(self) -> CapabilityMetadata:
        return CapabilityMetadata(
            supports_partial_content=False,
            supports_conditional_requests=False,
            supports_pagination=True,
            supports_structured_data=False,
            notes=("University portal adapter with moderate rate limits",),
        )

    def get_health_config(self, domain: str | None = None) -> HealthConfig:
        return HealthConfig(
            reliability_threshold_healthy=80.0,
            reliability_threshold_degraded=50.0,
            consecutive_failures_degraded=3,
            consecutive_failures_unhealthy=5,
            min_attempts_for_known=3,
            window_days=30,
        )


class ScholarshipPlatformAdapter:
    """Adapter for known structured scholarship platforms."""

    def __init__(self) -> None:
        self._source_type = SourceType.STRUCTURED_PLATFORM
        self._priority = 35

    @property
    def source_type(self) -> SourceType:
        return self._source_type

    @property
    def priority(self) -> int:
        return self._priority

    def identifies(self, source_url: str, source_registry: StaticSourceRegistry | None = None) -> bool:
        domain = extract_domain(source_url)
        if domain is None:
            return False
        if domain in _KNOWN_SCHOLARSHIP_PLATFORMS:
            return True
        if source_registry is not None:
            source_type = source_registry.get_source_type(source_url)
            if source_type in ("official_program", "official_scholarship_program"):
                return True
        return False

    def get_fetch_config(self, domain: str | None = None) -> FetchConfig:
        return FetchConfig(
            timeout_connect=5.0,
            timeout_read=10.0,
            timeout_write=5.0,
            timeout_pool=5.0,
            follow_redirects=True,
            expected_content_types=("text/html", "application/xhtml+xml", "application/json"),
            max_retries_hint=5,
            respect_robots_txt=True,
        )

    def get_extraction_config(self, domain: str | None = None) -> ExtractionConfig:
        return ExtractionConfig(
            parser_strategy="html_parser",
            fallback_extraction=True,
            alternate_extraction=True,
            preferred_field_patterns=("scholarship_name", "deadline", "award_amount", "provider", "eligibility", "duration", "application_url"),
            confidence_threshold="medium",
        )

    def get_rate_limit_config(self, domain: str | None = None) -> RateLimitConfig:
        return RateLimitConfig(
            requests_per_minute=20,
            backoff_seconds_hint=15.0,
            retry_after_header=True,
        )

    def get_capability_metadata(self) -> CapabilityMetadata:
        return CapabilityMetadata(
            supports_partial_content=False,
            supports_conditional_requests=True,
            supports_pagination=True,
            supports_structured_data=True,
            notes=("Structured scholarship platform adapter with optimized settings",),
        )

    def get_health_config(self, domain: str | None = None) -> HealthConfig:
        return HealthConfig(
            reliability_threshold_healthy=80.0,
            reliability_threshold_degraded=50.0,
            consecutive_failures_degraded=3,
            consecutive_failures_unhealthy=5,
            min_attempts_for_known=3,
            window_days=30,
        )


class GenericFallbackAdapter:
    """Generic fallback adapter — always available for unknown sources."""

    def __init__(self) -> None:
        self._source_type = SourceType.GENERIC
        self._priority = 0

    @property
    def source_type(self) -> SourceType:
        return self._source_type

    @property
    def priority(self) -> int:
        return self._priority

    def identifies(self, source_url: str, source_registry: StaticSourceRegistry | None = None) -> bool:
        return True

    def get_fetch_config(self, domain: str | None = None) -> FetchConfig:
        return FetchConfig()

    def get_extraction_config(self, domain: str | None = None) -> ExtractionConfig:
        return ExtractionConfig()

    def get_rate_limit_config(self, domain: str | None = None) -> RateLimitConfig:
        return RateLimitConfig()

    def get_capability_metadata(self) -> CapabilityMetadata:
        return CapabilityMetadata(
            notes=("Generic fallback adapter with default settings",),
        )

    def get_health_config(self, domain: str | None = None) -> HealthConfig:
        return HealthConfig()


class AdapterRegistry:
    """Registry for source adapters with deterministic selection.

    Adapters are evaluated in priority order (highest first).
    The first adapter that identifies a source URL is selected.
    The generic fallback adapter is always available as last resort.
    """

    def __init__(self, adapters: list[SourceAdapter] | None = None) -> None:
        self._adapters: list[SourceAdapter] = []
        self._generic: SourceAdapter = GenericFallbackAdapter()

        if adapters:
            for adapter in sorted(adapters, key=lambda a: -a.priority):
                if adapter.source_type == SourceType.GENERIC:
                    self._generic = adapter
                else:
                    self._adapters.append(adapter)

    def register(self, adapter: SourceAdapter) -> None:
        if adapter.source_type == SourceType.GENERIC:
            self._generic = adapter
            return
        for existing in self._adapters:
            if existing.source_type == adapter.source_type:
                raise ValueError(f"Duplicate adapter source type: {adapter.source_type.value}")
        self._adapters.append(adapter)
        self._adapters.sort(key=lambda a: -a.priority)

    def resolve(self, source_url: str, source_registry: StaticSourceRegistry | None = None) -> SourceAdapter:
        for adapter in self._adapters:
            if adapter.identifies(source_url, source_registry):
                return adapter
        return self._generic

    def resolve_batch(self, source_urls: list[str], source_registry: StaticSourceRegistry | None = None) -> dict[str, SourceAdapter]:
        result: dict[str, SourceAdapter] = {}
        for url in source_urls:
            result[url] = self.resolve(url, source_registry)
        return result

    @property
    def adapters(self) -> list[SourceAdapter]:
        return list(self._adapters)

    @property
    def generic_adapter(self) -> SourceAdapter:
        return self._generic


_default_registry: AdapterRegistry | None = None


def get_default_registry() -> AdapterRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = AdapterRegistry([
            ScholarshipPlatformAdapter(),
            GovernmentPortalAdapter(),
            UniversityPortalAdapter(),
        ])
    return _default_registry


def reset_default_registry() -> None:
    global _default_registry
    _default_registry = None
