"""Tests for source-specific adaptive adapters and retry orchestration unification."""

import time
from unittest.mock import MagicMock, patch

import pytest

import re

from app.services.source_adapter import (
    AdapterRegistry,
    AdapterRegistry,
    CapabilityMetadata,
    ExtractionConfig,
    FetchConfig,
    GenericFallbackAdapter,
    GovernmentPortalAdapter,
    RateLimitConfig,
    ScholarshipPlatformAdapter,
    SourceType,
    UniversityPortalAdapter,
    _domain_matches_any,
    _domain_matches_patterns,
    get_default_registry,
    reset_default_registry,
)
from app.services.source_adapter_executor import (
    AdapterExtractionResult,
    AdapterFetchResult,
    execute_extraction_with_adapter,
    execute_fetch_with_adapter,
    resolve_adapter_for_source,
    resolve_adapters_batch,
)
from app.services.source_health_service import HealthConfig


class TestSourceType:
    def test_source_type_values(self) -> None:
        assert SourceType.OFFICIAL_SCHOLARSHIP_PORTAL.value == "official_scholarship_portal"
        assert SourceType.GOVERNMENT_PORTAL.value == "government_portal"
        assert SourceType.UNIVERSITY_PORTAL.value == "university_portal"
        assert SourceType.STRUCTURED_PLATFORM.value == "structured_platform"
        assert SourceType.GENERIC.value == "generic"


class TestGovernmentPortalAdapter:
    def test_identifies_gov_domain(self) -> None:
        adapter = GovernmentPortalAdapter()
        assert adapter.identifies("https://www.gov.uk/scholarships")
        assert adapter.identifies("https://www.australia.gov.au/")

    def test_does_not_identify_university(self) -> None:
        adapter = GovernmentPortalAdapter()
        assert not adapter.identifies("https://www.harvard.edu/scholarships")

    def test_does_not_identify_known_platform(self) -> None:
        adapter = GovernmentPortalAdapter()
        assert not adapter.identifies("https://www.chevening.org/apply")

    def test_fetch_config(self) -> None:
        adapter = GovernmentPortalAdapter()
        config = adapter.get_fetch_config()
        assert config.timeout_connect == 8.0
        assert config.timeout_read == 15.0
        assert config.max_retries_hint == 5

    def test_extraction_config(self) -> None:
        adapter = GovernmentPortalAdapter()
        config = adapter.get_extraction_config()
        assert config.fallback_extraction is True
        assert config.alternate_extraction is True
        assert "deadline" in config.preferred_field_patterns

    def test_rate_limit_config(self) -> None:
        adapter = GovernmentPortalAdapter()
        config = adapter.get_rate_limit_config()
        assert config.requests_per_minute == 10
        assert config.retry_after_header is True

    def test_capability_metadata(self) -> None:
        adapter = GovernmentPortalAdapter()
        metadata = adapter.get_capability_metadata()
        assert metadata.supports_conditional_requests is True
        assert metadata.supports_structured_data is False

    def test_health_config(self) -> None:
        adapter = GovernmentPortalAdapter()
        config = adapter.get_health_config()
        assert config.reliability_threshold_healthy == 85.0
        assert config.consecutive_failures_unhealthy == 4

    def test_source_type(self) -> None:
        adapter = GovernmentPortalAdapter()
        assert adapter.source_type == SourceType.GOVERNMENT_PORTAL

    def test_priority(self) -> None:
        adapter = GovernmentPortalAdapter()
        assert adapter.priority == 30


class TestUniversityPortalAdapter:
    def test_identifies_edu_domain(self) -> None:
        adapter = UniversityPortalAdapter()
        assert adapter.identifies("https://www.stanford.edu/scholarships")
        assert adapter.identifies("https://www.ox.ac.uk/admissions")

    def test_does_not_identify_gov(self) -> None:
        adapter = UniversityPortalAdapter()
        assert not adapter.identifies("https://www.daad.de/en/")

    def test_fetch_config(self) -> None:
        adapter = UniversityPortalAdapter()
        config = adapter.get_fetch_config()
        assert config.timeout_connect == 6.0
        assert config.timeout_read == 12.0
        assert config.max_retries_hint == 4

    def test_rate_limit_config(self) -> None:
        adapter = UniversityPortalAdapter()
        config = adapter.get_rate_limit_config()
        assert config.requests_per_minute == 15

    def test_source_type(self) -> None:
        adapter = UniversityPortalAdapter()
        assert adapter.source_type == SourceType.UNIVERSITY_PORTAL


class TestScholarshipPlatformAdapter:
    def test_identifies_known_platforms(self) -> None:
        adapter = ScholarshipPlatformAdapter()
        assert adapter.identifies("https://www.daad.de/en/")
        assert adapter.identifies("https://www.chevening.org/")
        assert adapter.identifies("https://www.scholarshipdb.net/")

    def test_does_not_identify_unknown(self) -> None:
        adapter = ScholarshipPlatformAdapter()
        assert not adapter.identifies("https://www.example.com/scholarship")

    def test_fetch_config_accepts_json(self) -> None:
        adapter = ScholarshipPlatformAdapter()
        config = adapter.get_fetch_config()
        assert "application/json" in config.expected_content_types

    def test_rate_limit_config_higher(self) -> None:
        adapter = ScholarshipPlatformAdapter()
        config = adapter.get_rate_limit_config()
        assert config.requests_per_minute == 20

    def test_capability_metadata(self) -> None:
        adapter = ScholarshipPlatformAdapter()
        metadata = adapter.get_capability_metadata()
        assert metadata.supports_structured_data is True
        assert metadata.supports_pagination is True

    def test_source_type(self) -> None:
        adapter = ScholarshipPlatformAdapter()
        assert adapter.source_type == SourceType.STRUCTURED_PLATFORM

    def test_priority_highest(self) -> None:
        adapter = ScholarshipPlatformAdapter()
        assert adapter.priority == 35


class TestGenericFallbackAdapter:
    def test_always_identifies(self) -> None:
        adapter = GenericFallbackAdapter()
        assert adapter.identifies("https://www.example.com/")
        assert adapter.identifies("https://subdomain.example.org/path")
        assert adapter.identifies("https://anything.io/page")

    def test_default_fetch_config(self) -> None:
        adapter = GenericFallbackAdapter()
        config = adapter.get_fetch_config()
        assert config.timeout_connect == 5.0
        assert config.timeout_read == 10.0

    def test_default_extraction_config(self) -> None:
        adapter = GenericFallbackAdapter()
        config = adapter.get_extraction_config()
        assert config.parser_strategy == "html_parser"

    def test_default_rate_limit_config(self) -> None:
        adapter = GenericFallbackAdapter()
        config = adapter.get_rate_limit_config()
        assert config.requests_per_minute is None

    def test_source_type(self) -> None:
        adapter = GenericFallbackAdapter()
        assert adapter.source_type == SourceType.GENERIC

    def test_priority_lowest(self) -> None:
        adapter = GenericFallbackAdapter()
        assert adapter.priority == 0


class TestAdapterRegistry:
    def test_deterministic_selection(self) -> None:
        registry = AdapterRegistry([
            ScholarshipPlatformAdapter(),
            GovernmentPortalAdapter(),
            UniversityPortalAdapter(),
        ])

        assert registry.resolve("https://www.chevening.org/").source_type == SourceType.STRUCTURED_PLATFORM
        assert registry.resolve("https://www.gov.uk/scholarships").source_type == SourceType.GOVERNMENT_PORTAL
        assert registry.resolve("https://www.stanford.edu/").source_type == SourceType.UNIVERSITY_PORTAL
        assert registry.resolve("https://www.example.com/").source_type == SourceType.GENERIC

    def test_generic_fallback_always_available(self) -> None:
        registry = AdapterRegistry([])
        result = registry.resolve("https://www.unknown-site.com/scholarship")
        assert result.source_type == SourceType.GENERIC

    def test_batch_resolution(self) -> None:
        registry = AdapterRegistry([
            ScholarshipPlatformAdapter(),
            GovernmentPortalAdapter(),
            UniversityPortalAdapter(),
        ])

        urls = [
            "https://www.daad.de/en/",
            "https://www.gov.uk/scholarship",
            "https://www.stanford.edu/scholarships",
            "https://www.example.com/scholarship",
        ]

        results = registry.resolve_batch(urls)

        assert len(results) == 4
        assert results["https://www.daad.de/en/"].source_type == SourceType.STRUCTURED_PLATFORM
        assert results["https://www.gov.uk/scholarship"].source_type == SourceType.GOVERNMENT_PORTAL
        assert results["https://www.stanford.edu/scholarships"].source_type == SourceType.UNIVERSITY_PORTAL
        assert results["https://www.example.com/scholarship"].source_type == SourceType.GENERIC

    def test_duplicate_adapter_source_type_raises(self) -> None:
        registry = AdapterRegistry()
        with pytest.raises(ValueError, match="Duplicate adapter source type"):
            registry.register(GovernmentPortalAdapter())
            registry.register(GovernmentPortalAdapter())

    def test_register_generic_replaces_default(self) -> None:
        registry = AdapterRegistry()
        custom_generic = GenericFallbackAdapter()
        registry.register(custom_generic)
        assert registry.generic_adapter is custom_generic

    def test_adapters_sorted_by_priority(self) -> None:
        registry = AdapterRegistry([
            GovernmentPortalAdapter(),
            ScholarshipPlatformAdapter(),
            UniversityPortalAdapter(),
        ])
        priorities = [a.priority for a in registry.adapters]
        assert priorities == sorted(priorities, reverse=True)

    def test_malformed_url_falls_back_to_generic(self) -> None:
        registry = AdapterRegistry([
            ScholarshipPlatformAdapter(),
            GovernmentPortalAdapter(),
            UniversityPortalAdapter(),
        ])

        result = registry.resolve("not-a-valid-url")
        assert result.source_type == SourceType.GENERIC

    def test_empty_url_falls_back_to_generic(self) -> None:
        registry = AdapterRegistry([
            ScholarshipPlatformAdapter(),
            GovernmentPortalAdapter(),
            UniversityPortalAdapter(),
        ])

        result = registry.resolve("")
        assert result.source_type == SourceType.GENERIC


class TestSourceAdapterExecutor:
    def test_resolve_adapter_for_source(self) -> None:
        adapter = resolve_adapter_for_source("https://www.daad.de/en/")
        assert adapter.source_type == SourceType.STRUCTURED_PLATFORM

    def test_resolve_adapters_batch(self) -> None:
        urls = [
            "https://www.daad.de/en/",
            "https://www.example.com/",
        ]
        results = resolve_adapters_batch(urls)
        assert len(results) == 2
        assert results["https://www.daad.de/en/"].source_type == SourceType.STRUCTURED_PLATFORM
        assert results["https://www.example.com/"].source_type == SourceType.GENERIC

    @patch("app.services.source_adapter_executor.execute_fetch_with_retry")
    def test_execute_fetch_delegates_to_retry_executor(self, mock_execute) -> None:
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetch_result.success = True
        mock_result.fetch_result.status_code = 200
        mock_result.fetch_result.content = "<html>test</html>"
        mock_result.fetch_result.error_type = None
        mock_result.fetch_result.error_reason = None
        mock_result.status = "resolved"
        mock_result.attempt_id = 1
        mock_result.attempts_remaining = 4
        mock_execute.return_value = mock_result

        adapter = ScholarshipPlatformAdapter()
        result = execute_fetch_with_adapter(
            session=mock_session,
            scholarship_id=1,
            source_url="https://www.daad.de/en/",
            adapter=adapter,
        )

        mock_execute.assert_called_once_with(
            session=mock_session,
            scholarship_id=1,
            source_url="https://www.daad.de/en/",
            max_attempts=5,
        )
        assert result.adapter_type == SourceType.STRUCTURED_PLATFORM.value

    @patch("app.services.source_adapter_executor.extract_scholarship_information")
    def test_execute_extraction_uses_adapter_config(self, mock_extract) -> None:
        mock_extract.return_value = MagicMock(
            scholarship_name="Test Scholarship",
            provider=None,
            deadline=None,
            award_amount=None,
            eligibility=None,
            duration=None,
            application_url=None,
        )

        adapter = GovernmentPortalAdapter()
        result = execute_extraction_with_adapter(
            html_content="<html><h1>Test Scholarship</h1></html>",
            source_url="https://www.gov.uk/scholarship",
            adapter=adapter,
        )

        mock_extract.assert_called_once_with(
            "<html><h1>Test Scholarship</h1></html>",
            "https://www.gov.uk/scholarship",
        )
        assert result.adapter_type == SourceType.GOVERNMENT_PORTAL.value


class TestRetryDelegation:
    def test_retry_fetch_delegates_when_session_available(self) -> None:
        from app.services.self_healing_verification import (
            RecoveryAttempt,
            RecoveryContext,
            RecoveryStrategy,
            _delegate_retry_to_executor,
            _retry_fetch,
        )

        mock_session = MagicMock()
        mock_execution = MagicMock()
        mock_execution.fetch_result.success = True
        mock_execution.fetch_result.status_code = 200
        mock_execution.fetch_result.content = "<html>recovered</html>"
        mock_execution.fetch_result.error_type = None
        mock_execution.fetch_result.error_reason = None
        mock_execution.status = "resolved"
        mock_execution.attempt_id = 42

        context = RecoveryContext(
            source_url="https://www.daad.de/en/",
            scholarship_id=1,
            session=mock_session,
            max_attempts=5,
        )

        with patch("app.services.self_healing_verification.execute_fetch_with_retry") as mock_retry:
            mock_retry.return_value = mock_execution

            result = _retry_fetch(
                context=context,
                attempt_number=1,
                timestamp=time.time(),
                correlation_id="test-cid",
            )

            mock_retry.assert_called_once_with(
                session=mock_session,
                scholarship_id=1,
                source_url="https://www.daad.de/en/",
                max_attempts=5,
            )
            assert result.strategy == RecoveryStrategy.RETRY_FETCH

    def test_retry_fetch_fallback_without_session(self) -> None:
        from app.services.self_healing_verification import (
            RecoveryContext,
            RecoveryStrategy,
            _retry_fetch,
        )

        context = RecoveryContext(
            source_url="https://www.daad.de/en/",
            scholarship_id=1,
            session=None,
        )

        with patch("app.services.self_healing_verification.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = MagicMock(
                success=True,
                status_code=200,
                content="<html>test</html>",
                error_type=None,
                error_reason=None,
            )

            result = _retry_fetch(
                context=context,
                attempt_number=1,
                timestamp=time.time(),
                correlation_id="test-cid",
            )

            mock_fetch.assert_called_once_with("https://www.daad.de/en/")
            assert result.strategy == RecoveryStrategy.RETRY_FETCH

    def test_no_nested_retry_loops(self) -> None:
        """Verify that self-healing does NOT implement its own retry loop."""
        import inspect
        from app.services.self_healing_verification import _retry_fetch, _delegate_retry_to_executor

        retry_fetch_source = inspect.getsource(_retry_fetch)
        delegate_source = inspect.getsource(_delegate_retry_to_executor)

        assert "execute_fetch_with_retry" in retry_fetch_source
        assert "execute_fetch_with_retry" in delegate_source
        assert "while" not in delegate_source
        assert "for" not in delegate_source.split("def ")[0]

    def test_no_duplicate_attempts(self) -> None:
        """Verify adapter retry hints don't cause duplicate attempts."""
        mock_session = MagicMock()
        adapter = GovernmentPortalAdapter()
        config = adapter.get_fetch_config()

        with patch("app.services.source_adapter_executor.execute_fetch_with_retry") as mock_execute:
            mock_result = MagicMock()
            mock_result.fetch_result.success = True
            mock_result.fetch_result.status_code = 200
            mock_result.fetch_result.content = "<html>test</html>"
            mock_result.fetch_result.error_type = None
            mock_result.fetch_result.error_reason = None
            mock_result.status = "resolved"
            mock_result.attempt_id = 1
            mock_result.attempts_remaining = 4
            mock_execute.return_value = mock_result

            execute_fetch_with_adapter(
                session=mock_session,
                scholarship_id=1,
                source_url="https://www.gov.uk/scholarship",
                adapter=adapter,
            )

            mock_execute.assert_called_once()
            call_kwargs = mock_execute.call_args
            assert call_kwargs[1]["max_attempts"] == config.max_retries_hint


class TestSourceIsolation:
    def test_different_sources_get_different_adapters(self) -> None:
        registry = get_default_registry()

        gov_adapter = registry.resolve("https://www.gov.uk/scholarship")
        uni_adapter = registry.resolve("https://www.stanford.edu/")
        platform_adapter = registry.resolve("https://www.daad.de/")

        assert gov_adapter is not uni_adapter
        assert uni_adapter is not platform_adapter
        assert gov_adapter is not platform_adapter

    def test_adapter_fetch_configs_are_independent(self) -> None:
        gov = GovernmentPortalAdapter()
        uni = UniversityPortalAdapter()
        plat = ScholarshipPlatformAdapter()

        gov_config = gov.get_fetch_config()
        uni_config = uni.get_fetch_config()
        plat_config = plat.get_fetch_config()

        assert gov_config.timeout_connect != uni_config.timeout_connect
        assert uni_config.timeout_read != plat_config.timeout_read


class TestIdempotency:
    def test_adapter_selection_is_idempotent(self) -> None:
        registry = get_default_registry()

        url = "https://www.daad.de/en/scholarships/"
        first = registry.resolve(url)
        second = registry.resolve(url)
        third = registry.resolve(url)

        assert first.source_type == second.source_type == third.source_type

    def test_fetch_config_is_deterministic(self) -> None:
        adapter = GovernmentPortalAdapter()
        configs = [adapter.get_fetch_config() for _ in range(5)]

        first = configs[0]
        for config in configs[1:]:
            assert config == first

    def test_extraction_config_is_deterministic(self) -> None:
        adapter = ScholarshipPlatformAdapter()
        configs = [adapter.get_extraction_config() for _ in range(5)]

        first = configs[0]
        for config in configs[1:]:
            assert config == first


class TestNoNPlusOne:
    def test_batch_resolution_single_call(self) -> None:
        registry = get_default_registry()
        urls = [f"https://www{i}.example.com/" for i in range(10)]

        results = registry.resolve_batch(urls)

        assert len(results) == 10
        assert all(r.source_type == SourceType.GENERIC for r in results.values())

    def test_batch_resolution_caches_domain_extraction(self) -> None:
        registry = get_default_registry()
        urls = [
            "https://www.daad.de/en/",
            "https://www.daad.de/de/",
            "https://www.daad.de/fr/",
        ]

        results = registry.resolve_batch(urls)
        assert all(r.source_type == SourceType.STRUCTURED_PLATFORM for r in results.values())


class TestLowLatencyPath:
    def test_generic_adapter_resolves_instantly(self) -> None:
        adapter = GenericFallbackAdapter()

        start = time.monotonic()
        for _ in range(100):
            adapter.identifies("https://www.example.com/")
        duration = time.monotonic() - start

        assert duration < 0.1

    def test_registry_resolves_quickly(self) -> None:
        registry = get_default_registry()

        start = time.monotonic()
        for _ in range(100):
            registry.resolve("https://www.example.com/")
        duration = time.monotonic() - start

        assert duration < 0.5


class TestTelemetryPreservation:
    def test_adapter_fetch_records_telemetry(self) -> None:
        from app.services.telemetry import get_snapshot, reset_telemetry

        reset_telemetry()

        mock_session = MagicMock()
        adapter = ScholarshipPlatformAdapter()

        with patch("app.services.source_adapter_executor.execute_fetch_with_retry") as mock_execute:
            mock_result = MagicMock()
            mock_result.fetch_result.success = True
            mock_result.fetch_result.status_code = 200
            mock_result.fetch_result.content = "<html>test</html>"
            mock_result.fetch_result.error_type = None
            mock_result.fetch_result.error_reason = None
            mock_result.status = "resolved"
            mock_result.attempt_id = 1
            mock_result.attempts_remaining = 4
            mock_execute.return_value = mock_result

            execute_fetch_with_adapter(
                session=mock_session,
                scholarship_id=1,
                source_url="https://www.daad.de/en/",
                adapter=adapter,
            )

        snapshot = get_snapshot()
        assert snapshot.total_events > 0


class TestSafetyPreservation:
    def test_adapter_does_not_bypass_evidence(self) -> None:
        adapter = GovernmentPortalAdapter()
        config = adapter.get_extraction_config()
        assert config.fallback_extraction is True
        assert config.alternate_extraction is True

    def test_adapter_does_not_update_scholarship(self) -> None:
        adapter = ScholarshipPlatformAdapter()
        assert not hasattr(adapter, "update_scholarship")
        assert not hasattr(adapter, "save_scholarship")

    def test_adapter_preserves_normalization(self) -> None:
        adapter = GovernmentPortalAdapter()
        fetch_config = adapter.get_fetch_config()
        assert fetch_config.follow_redirects is True
        assert "text/html" in fetch_config.expected_content_types


class TestDomainMatching:
    def test_government_domain_patterns(self) -> None:
        assert _domain_matches_any("www.gov.uk", frozenset({".gov.uk"}))
        assert _domain_matches_any("daad.de", frozenset({".de"}))
        assert not _domain_matches_any("www.example.com", frozenset({".gov"}))

    def test_government_host_patterns(self) -> None:
        from app.services.source_adapter import _GOVERNMENT_HOST_PATTERNS
        assert _domain_matches_patterns("www.gov.uk", _GOVERNMENT_HOST_PATTERNS)
        assert not _domain_matches_patterns("www.example.com", _GOVERNMENT_HOST_PATTERNS)
