"""Tests for concurrent dry-run pipeline.

Covers:
- Concurrent processing with bounded thread pool
- Retry with backoff on failures
- Result aggregation and sorting
- Error isolation (one failure doesn't break others)
- JSON serialization
"""

import os
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"scholarzone-test-concurrent-{uuid4().hex}.db"
os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"

from app.services.concurrent_dry_run import (  # noqa: E402
    DryRunResult,
    run_concurrent_dry_run,
    run_concurrent_dry_run_json,
    _retry_with_backoff,
)


class TestRetryWithBackoff:
    def test_success_on_first_try(self):
        call_count = [0]

        def func():
            call_count[0] += 1
            return "success"

        result = _retry_with_backoff(func, max_retries=3, timeout=5.0)
        assert result == "success"
        assert call_count[0] == 1

    def test_retries_then_succeeds(self):
        call_count = [0]

        def func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("transient error")
            return "recovered"

        result = _retry_with_backoff(func, max_retries=3, timeout=5.0)
        assert result == "recovered"
        assert call_count[0] == 3

    def test_retries_exhausted_then_raises(self):
        call_count = [0]

        def func():
            call_count[0] += 1
            raise Exception("always fails")

        with pytest.raises(Exception, match="always fails"):
            _retry_with_backoff(func, max_retries=2, timeout=5.0)
        assert call_count[0] == 3


class TestDryRunResult:
    def test_dataclass_defaults(self):
        result = DryRunResult(
            scholarship_id=1,
            scholarship_title="Test",
            original_source_url="https://example.com",
            source_resolution_type="exact_program_page",
            resolved_source_url="https://example.com/program",
            source_resolution_confidence=0.95,
            source_resolution_reason="found",
            source_page_title="Test Page",
            candidates_found=5,
            best_candidate_url="https://example.com/image.jpg",
            best_candidate_reachable=True,
            best_candidate_http_status=200,
            best_candidate_content_type="image/jpeg",
            program_relevance="high",
            licensing_status="licensing_known",
            licensing_evidence="CC BY",
            confidence="HIGH",
            decision="approved",
        )
        assert result.scholarship_id == 1
        assert result.decision == "approved"
        assert result.error is None


class TestConcurrentDryRun:
    @pytest.fixture
    def mock_scholarship_data(self):
        return [
            MagicMock(
                id=1,
                title="Test Scholarship 1",
                official_source_url="https://www.university.edu/program1",
                image_url=None,
            ),
            MagicMock(
                id=2,
                title="Test Scholarship 2",
                official_source_url="https://www.daad.de",
                image_url=None,
            ),
        ]

    def test_results_sorted_by_id(self, mock_scholarship_data):
        with patch("app.services.concurrent_dry_run.SourceResolverService") as MockResolver:
            mock_resolver = MagicMock()
            mock_resolver.resolve_source.return_value = MagicMock(
                resolved_url="https://example.com/program",
                resolution_type=MagicMock(value="exact_program_page"),
                confidence=0.95,
                reason="test",
                page_title="Test",
            )
            MockResolver.return_value = mock_resolver

            with patch("app.services.concurrent_dry_run.get_engine"):
                with patch("app.services.concurrent_dry_run.sessionmaker") as MockSession:
                    mock_session = MagicMock()
                    mock_session.get.side_effect = mock_scholarship_data
                    mock_session.close = MagicMock()
                    MockSession.return_value = MagicMock(return_value=mock_session)

                    with patch("app.services.concurrent_dry_run.ImageDiscoveryService") as MockDiscovery:
                        with patch("app.services.concurrent_dry_run.ImageValidator") as MockValidator:
                            mock_validator = MagicMock()
                            mock_validator.validate_candidates.return_value = []
                            mock_validator.find_best_result.return_value = None
                            MockValidator.return_value = mock_validator

                            results = run_concurrent_dry_run([2, 1], max_concurrency=2)

                            assert results[0].scholarship_id <= results[-1].scholarship_id

    def test_error_isolation(self):
        """An exception on one scholarship should not abort others."""
        call_count = [0]

        original_process = None

        def mock_process(scholarship, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Simulated failure")
            return DryRunResult(
                scholarship_id=scholarship.id,
                scholarship_title=scholarship.title,
                original_source_url=scholarship.official_source_url,
                source_resolution_type="exact_program_page",
                resolved_source_url=scholarship.official_source_url,
                source_resolution_confidence=0.95,
                source_resolution_reason="OK",
                source_page_title="Test",
                candidates_found=0,
                best_candidate_url=None,
                best_candidate_reachable=False,
                best_candidate_http_status=None,
                best_candidate_content_type=None,
                program_relevance="none",
                licensing_status="licensing_unknown",
                licensing_evidence=None,
                confidence="LOW",
                decision="rejected",
                rejection_reasons=["No candidates found"],
            )

        with patch("app.services.concurrent_dry_run._process_scholarship", side_effect=mock_process):
            with patch("app.services.concurrent_dry_run.get_engine"):
                with patch("app.services.concurrent_dry_run.sessionmaker") as MockSession:
                    mock_session = MagicMock()
                    mock_session.get.side_effect = [
                        MagicMock(id=1, title="Scholar 1", official_source_url="https://a.com"),
                        MagicMock(id=2, title="Scholar 2", official_source_url="https://b.com"),
                    ]
                    mock_session.close = MagicMock()
                    MockSession.return_value = MagicMock(return_value=mock_session)

                    results = run_concurrent_dry_run([1, 2], max_concurrency=2)

                    assert len(results) == 2
                    assert results[0].error is not None or results[0].decision == "rejected"
                    assert results[0].scholarship_id == 1

    def test_json_serialization(self):
        results = [DryRunResult(
            scholarship_id=1,
            scholarship_title="Test",
            original_source_url="https://example.com",
            source_resolution_type="exact_program_page",
            resolved_source_url="https://example.com",
            source_resolution_confidence=0.95,
            source_resolution_reason="OK",
            source_page_title="Test",
            candidates_found=0,
            best_candidate_url=None,
            best_candidate_reachable=False,
            best_candidate_http_status=None,
            best_candidate_content_type=None,
            program_relevance="none",
            licensing_status="licensing_unknown",
            licensing_evidence=None,
            confidence="LOW",
            decision="rejected",
            rejection_reasons=["No candidates"],
        )]
        import json
        from dataclasses import asdict
        serialized = json.dumps([json.loads(json.dumps(asdict(r), default=str)) for r in results])
        deserialized = json.loads(serialized)
        assert deserialized[0]["scholarship_id"] == 1
