"""Tests for content fingerprinting and incremental change detection.

Tests cover:
- First fingerprint creation
- Same content produces unchanged
- Meaningful content change detected
- Whitespace-only change ignored
- Metadata-only change handled
- ETag/Last-Modified behavior
- Failed fetch preserves previous fingerprint
- Partial/invalid content -> unknown
- Algorithm versioning
- Idempotent storage
- Source isolation
- Batch lookup (no N+1)
- Deterministic hashing
- Downstream pipeline skipped only when unchanged
- Changed content still reaches existing verification
- Telemetry emitted
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.content_fingerprinting import (
    FingerprintStatus,
    ContentFingerprint,
    FingerprintComparisonResult,
    FINGERPRINT_ALGORITHM_VERSION,
    batch_check_sources_changed,
    batch_get_latest_fingerprints,
    check_source_changed,
    compare_fingerprints,
    compute_content_hash,
    create_fingerprint,
    get_latest_fingerprint,
    normalize_content,
    store_fingerprint,
)
from app.services.telemetry import PipelineStages, get_collector, reset_telemetry


class TestNormalizeContent:
    """Test content normalization."""

    def test_empty_content(self):
        assert normalize_content("") == ""

    def test_none_content(self):
        assert normalize_content(None) == ""

    def test_whitespace_collapsed(self):
        content = "Hello    world   \n\n  test"
        result = normalize_content(content)
        assert "Hello world" in result
        assert "test" in result
        assert "    " not in result

    def test_html_comments_removed(self):
        content = "Hello<!-- comment --> world"
        result = normalize_content(content)
        assert "comment" not in result
        assert "Hello" in result
        assert "world" in result

    def test_script_block_removed(self):
        content = "Hello<script>var x = 1;</script> world"
        result = normalize_content(content)
        assert "script" not in result.lower() or "var x" not in result
        assert "Hello" in result
        assert "world" in result

    def test_style_block_removed(self):
        content = "Hello<style>.cls { color: red; }</style> world"
        result = normalize_content(content)
        assert "color" not in result
        assert "Hello" in result
        assert "world" in result

    def test_tracking_params_removed(self):
        content = 'Visit https://example.com/page?utm_source=email&id=123'
        result = normalize_content(content)
        assert "utm_source" not in result
        assert "id=123" in result

    def test_fbclid_removed(self):
        content = 'Link: https://example.com/?fbclid=abc123'
        result = normalize_content(content)
        assert "fbclid" not in result

    def test_gclid_removed(self):
        content = 'Link: https://example.com/?gclid=xyz789'
        result = normalize_content(content)
        assert "gclid" not in result

    def test_multiple_tracking_params(self):
        content = 'URL: https://example.com/?utm_source=a&utm_medium=b&id=1'
        result = normalize_content(content)
        assert "utm_" not in result
        assert "id=1" in result

    def test_semantic_content_preserved(self):
        content = "Scholarship: DAAD\nAmount: Full coverage\nDeadline: 2026-06-01"
        result = normalize_content(content)
        assert "DAAD" in result
        assert "Full coverage" in result
        assert "2026-06-01" in result


class TestComputeContentHash:
    """Test deterministic hashing."""

    def test_empty_content_returns_empty(self):
        hash_val, length = compute_content_hash("")
        assert hash_val == ""
        assert length == 0

    def test_deterministic(self):
        content = "Hello world"
        hash1, len1 = compute_content_hash(content)
        hash2, len2 = compute_content_hash(content)
        assert hash1 == hash2
        assert len1 == len2

    def test_different_content_different_hash(self):
        hash1, _ = compute_content_hash("Hello world")
        hash2, _ = compute_content_hash("Different content")
        assert hash1 != hash2

    def test_hash_length(self):
        hash_val, _ = compute_content_hash("test content")
        assert len(hash_val) == 64

    def test_unicode_content(self):
        content = "Scholarship for Münster Universität"
        hash_val, length = compute_content_hash(content)
        assert len(hash_val) == 64
        assert length > 0


class TestCreateFingerprint:
    """Test fingerprint creation."""

    def test_basic_fingerprint(self):
        content = "Hello world"
        fp = create_fingerprint("https://example.com", content)
        assert fp.source_url == "https://example.com"
        assert fp.normalized_content_hash != ""
        assert fp.content_length > 0
        assert fp.algorithm_version == FINGERPRINT_ALGORITHM_VERSION

    def test_fingerprint_with_metadata(self):
        content = "Hello world"
        fp = create_fingerprint(
            "https://example.com",
            content,
            etag='"abc123"',
            last_modified="Mon, 01 Jan 2026 00:00:00 GMT",
        )
        assert fp.etag == '"abc123"'
        assert fp.last_modified == "Mon, 01 Jan 2026 00:00:00 GMT"

    def test_empty_content_fingerprint(self):
        fp = create_fingerprint("https://example.com", "")
        assert fp.normalized_content_hash == ""
        assert fp.content_length == 0

    def test_deterministic_fingerprint(self):
        content = "Scholarship content here"
        fp1 = create_fingerprint("https://example.com", content)
        fp2 = create_fingerprint("https://example.com", content)
        assert fp1.normalized_content_hash == fp2.normalized_content_hash
        assert fp1.content_length == fp2.content_length

    def test_whitespace_normalization(self):
        content1 = "Hello   world"
        content2 = "Hello world"
        fp1 = create_fingerprint("https://example.com", content1)
        fp2 = create_fingerprint("https://example.com", content2)
        assert fp1.normalized_content_hash == fp2.normalized_content_hash


class TestCompareFingerprints:
    """Test fingerprint comparison logic."""

    def test_no_previous_returns_unknown(self):
        current = create_fingerprint("https://example.com", "content")
        status = compare_fingerprints(None, current)
        assert status == FingerprintStatus.UNKNOWN

    def test_same_hash_returns_unchanged(self):
        content = "Same content"
        previous = create_fingerprint("https://example.com", content)
        current = create_fingerprint("https://example.com", content)
        status = compare_fingerprints(previous, current)
        assert status == FingerprintStatus.UNCHANGED

    def test_different_hash_returns_changed(self):
        previous = create_fingerprint("https://example.com", "old content")
        current = create_fingerprint("https://example.com", "new content")
        status = compare_fingerprints(previous, current)
        assert status == FingerprintStatus.CHANGED

    def test_different_algorithm_returns_unknown(self):
        previous = ContentFingerprint(
            source_url="https://example.com",
            normalized_content_hash="abc",
            content_length=100,
            algorithm_version="v1",
        )
        current = ContentFingerprint(
            source_url="https://example.com",
            normalized_content_hash="abc",
            content_length=100,
            algorithm_version="v2",
        )
        status = compare_fingerprints(previous, current)
        assert status == FingerprintStatus.UNKNOWN

    def test_whitespace_only_change_returns_unchanged(self):
        previous = create_fingerprint("https://example.com", "Hello   world")
        current = create_fingerprint("https://example.com", "Hello world")
        status = compare_fingerprints(previous, current)
        assert status == FingerprintStatus.UNCHANGED

    def test_html_comment_change_returns_unchanged(self):
        previous = create_fingerprint("https://example.com", "Hello<!-- old --> world")
        current = create_fingerprint("https://example.com", "Hello world")
        status = compare_fingerprints(previous, current)
        assert status == FingerprintStatus.UNCHANGED


class TestCheckSourceChanged:
    """Test main entry point for change detection."""

    def test_first_observation_returns_unknown(self, session):
        reset_telemetry()
        result = check_source_changed(
            session,
            "https://example.com/scholarship",
            "Initial content",
        )
        assert result.status == FingerprintStatus.UNKNOWN
        assert result.skipped_downstream is False
        assert result.current_fingerprint is not None

    def test_same_content_returns_unchanged(self, session):
        reset_telemetry()
        url = "https://example.com/scholarship"
        content = "Scholarship content"
        check_source_changed(session, url, content)
        result = check_source_changed(session, url, content)
        assert result.status == FingerprintStatus.UNCHANGED
        assert result.skipped_downstream is True

    def test_changed_content_returns_changed(self, session):
        reset_telemetry()
        url = "https://example.com/scholarship"
        check_source_changed(session, url, "Old content")
        result = check_source_changed(session, url, "New content")
        assert result.status == FingerprintStatus.CHANGED
        assert result.skipped_downstream is False

    def test_whitespace_only_change_unchanged(self, session):
        reset_telemetry()
        url = "https://example.com/scholarship"
        check_source_changed(session, url, "Content   with   spaces")
        result = check_source_changed(session, url, "Content with spaces")
        assert result.status == FingerprintStatus.UNCHANGED

    def test_empty_content_returns_unknown(self, session):
        reset_telemetry()
        result = check_source_changed(session, "https://example.com", "")
        assert result.status == FingerprintStatus.UNKNOWN
        assert result.skipped_downstream is False

    def test_whitespace_only_content_returns_unknown(self, session):
        reset_telemetry()
        result = check_source_changed(session, "https://example.com", "   \n\t  ")
        assert result.status == FingerprintStatus.UNKNOWN

    def test_metadata_only_change_with_same_content_unchanged(self, session):
        reset_telemetry()
        url = "https://example.com/scholarship"
        content = "Same content"
        check_source_changed(session, url, content, etag='"old"', last_modified="Mon, 01 Jan 2026 00:00:00 GMT")
        result = check_source_changed(session, url, content, etag='"new"', last_modified="Tue, 02 Jan 2026 00:00:00 GMT")
        assert result.status == FingerprintStatus.UNCHANGED

    def test_telemetry_emitted(self, session):
        reset_telemetry()
        check_source_changed(session, "https://example.com", "content", job_id="job-123")
        snapshot = get_collector().snapshot()
        assert snapshot.total_events > 0


class TestStoreFingerprint:
    """Test idempotent storage."""

    def test_new_fingerprint_stored(self, session):
        fp = create_fingerprint("https://example.com", "content")
        assert store_fingerprint(session, fp) is True

    def test_duplicate_fingerprint_not_stored(self, session):
        fp = create_fingerprint("https://example.com", "content")
        store_fingerprint(session, fp)
        result = store_fingerprint(session, fp)
        assert result is False

    def test_different_content_same_url_stored(self, session):
        fp1 = create_fingerprint("https://example.com", "content1")
        fp2 = create_fingerprint("https://example.com", "content2")
        store_fingerprint(session, fp1)
        assert store_fingerprint(session, fp2) is True


class TestGetLatestFingerprint:
    """Test fingerprint retrieval."""

    def test_no_fingerprint_returns_none(self, session):
        result = get_latest_fingerprint(session, "https://nonexistent.com")
        assert result is None

    def test_returns_latest_fingerprint(self, session):
        url = "https://example.com"
        fp1 = create_fingerprint(url, "content1")
        store_fingerprint(session, fp1)

        import time
        time.sleep(0.01)

        fp2 = create_fingerprint(url, "content2")
        store_fingerprint(session, fp2)

        latest = get_latest_fingerprint(session, url)
        assert latest is not None
        assert latest.normalized_content_hash == fp2.normalized_content_hash


class TestBatchGetLatestFingerprints:
    """Test batch retrieval (no N+1)."""

    def test_empty_list_returns_empty_dict(self, session):
        result = batch_get_latest_fingerprints(session, [])
        assert result == {}

    def test_multiple_sources(self, session):
        urls = ["https://a.com", "https://b.com", "https://c.com"]
        for url in urls:
            fp = create_fingerprint(url, f"content for {url}")
            store_fingerprint(session, fp)

        results = batch_get_latest_fingerprints(session, urls)
        assert len(results) == 3
        for url in urls:
            assert results[url] is not None
            assert results[url].source_url == url

    def test_missing_sources_return_none(self, session):
        results = batch_get_latest_fingerprints(session, ["https://nonexistent.com"])
        assert results["https://nonexistent.com"] is None


class TestBatchCheckSourcesChanged:
    """Test batch change detection."""

    def test_empty_sources_returns_empty_dict(self, session):
        results = batch_check_sources_changed(session, [])
        assert results == {}

    def test_first_observation_all_unknown(self, session):
        sources = [
            ("https://a.com", "content a"),
            ("https://b.com", "content b"),
        ]
        results = batch_check_sources_changed(session, sources)
        assert len(results) == 2
        for url, _ in sources:
            assert results[url].status == FingerprintStatus.UNKNOWN

    def test_unchanged_sources_skipped(self, session):
        sources = [
            ("https://a.com", "content a"),
            ("https://b.com", "content b"),
        ]
        batch_check_sources_changed(session, sources)
        results = batch_check_sources_changed(session, sources)
        for url, _ in sources:
            assert results[url].status == FingerprintStatus.UNCHANGED
            assert results[url].skipped_downstream is True

    def test_mixed_results(self, session):
        sources_first = [
            ("https://a.com", "content a"),
            ("https://b.com", "content b"),
        ]
        batch_check_sources_changed(session, sources_first)

        sources_second = [
            ("https://a.com", "content a"),
            ("https://b.com", "content b changed"),
        ]
        results = batch_check_sources_changed(session, sources_second)
        assert results["https://a.com"].status == FingerprintStatus.UNCHANGED
        assert results["https://b.com"].status == FingerprintStatus.CHANGED

    def test_empty_content_in_batch(self, session):
        sources = [
            ("https://a.com", "content a"),
            ("https://b.com", ""),
        ]
        results = batch_check_sources_changed(session, sources)
        assert results["https://a.com"].status == FingerprintStatus.UNKNOWN
        assert results["https://b.com"].status == FingerprintStatus.UNKNOWN


class TestSourceIsolation:
    """Test that fingerprints are isolated by source URL."""

    def test_same_content_different_urls_isolated(self, session):
        content = "Same content"
        fp1 = create_fingerprint("https://a.com", content)
        fp2 = create_fingerprint("https://b.com", content)

        store_fingerprint(session, fp1)
        store_fingerprint(session, fp2)

        latest_a = get_latest_fingerprint(session, "https://a.com")
        latest_b = get_latest_fingerprint(session, "https://b.com")

        assert latest_a is not None
        assert latest_b is not None
        assert latest_a.source_url == "https://a.com"
        assert latest_b.source_url == "https://b.com"

    def test_change_in_one_url_not_affecting_other(self, session):
        check_source_changed(session, "https://a.com", "content")
        check_source_changed(session, "https://b.com", "content")

        result_a = check_source_changed(session, "https://a.com", "new content")
        result_b = check_source_changed(session, "https://b.com", "content")

        assert result_a.status == FingerprintStatus.CHANGED
        assert result_b.status == FingerprintStatus.UNCHANGED


class TestAlgorithmVersioning:
    """Test fingerprint algorithm versioning."""

    def test_default_version(self):
        fp = create_fingerprint("https://example.com", "content")
        assert fp.algorithm_version == FINGERPRINT_ALGORITHM_VERSION

    def test_custom_version(self):
        fp = ContentFingerprint(
            source_url="https://example.com",
            normalized_content_hash="abc",
            content_length=100,
            algorithm_version="v2",
        )
        assert fp.algorithm_version == "v2"


class TestFailedFetchPreservation:
    """Test that failed fetches don't overwrite known-good fingerprints."""

    def test_no_fingerprint_stored_on_empty_content(self, session):
        check_source_changed(session, "https://example.com", "initial content")
        check_source_changed(session, "https://example.com", "")

        latest = get_latest_fingerprint(session, "https://example.com")
        assert latest is not None
        assert latest.content_length > 0

    def test_multiple_failed_fetches_preserve_fingerprint(self, session):
        check_source_changed(session, "https://example.com", "good content")
        check_source_changed(session, "https://example.com", "")
        check_source_changed(session, "https://example.com", "")

        latest = get_latest_fingerprint(session, "https://example.com")
        assert latest is not None

        expected_fp = create_fingerprint("https://example.com", "good content")
        assert latest.normalized_content_hash == expected_fp.normalized_content_hash


class TestTelemetry:
    """Test telemetry integration."""

    def test_fingerprint_latency_recorded(self, session):
        reset_telemetry()
        check_source_changed(session, "https://example.com", "content")
        snapshot = get_collector().snapshot()
        assert snapshot.total_events > 0

    def test_changed_result_recorded(self, session):
        reset_telemetry()
        check_source_changed(session, "https://example.com", "old")
        reset_telemetry()
        check_source_changed(session, "https://example.com", "new")
        snapshot = get_collector().snapshot()
        assert snapshot.total_events > 0

    def test_bytes_processed_recorded(self, session):
        reset_telemetry()
        result = check_source_changed(session, "https://example.com", "content")
        assert result.bytes_processed > 0

    def test_job_id_in_telemetry(self, session):
        reset_telemetry()
        check_source_changed(session, "https://example.com", "content", job_id="job-456")
        snapshot = get_collector().snapshot()
        assert snapshot.total_events > 0


class TestDownstreamPipelineSafety:
    """Test that fingerprinting never suppresses verification inappropriately."""

    def test_unchanged_allows_skip(self, session):
        check_source_changed(session, "https://example.com", "content")
        result = check_source_changed(session, "https://example.com", "content")
        assert result.skipped_downstream is True

    def test_changed_does_not_skip(self, session):
        check_source_changed(session, "https://example.com", "old")
        result = check_source_changed(session, "https://example.com", "new")
        assert result.skipped_downstream is False

    def test_unknown_does_not_skip(self, session):
        result = check_source_changed(session, "https://new.com", "first content")
        assert result.skipped_downstream is False

    def test_empty_content_does_not_skip(self, session):
        result = check_source_changed(session, "https://example.com", "")
        assert result.skipped_downstream is False


class TestDeterministicHashing:
    """Test that hashing is deterministic."""

    def test_same_input_same_output(self):
        content = "Scholarship: Test\nAmount: Full\nDeadline: 2026-06-01"
        results = [create_fingerprint("https://example.com", content) for _ in range(10)]
        hashes = [fp.normalized_content_hash for fp in results]
        assert len(set(hashes)) == 1

    def test_different_input_different_output(self):
        contents = ["A", "B", "C", "D", "E"]
        hashes = [create_fingerprint("https://example.com", c).normalized_content_hash for c in contents]
        assert len(set(hashes)) == 5


@pytest.fixture
def session():
    """Create a test database session."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
