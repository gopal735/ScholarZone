"""Content fingerprinting and incremental change detection.

Detects whether an official source has materially changed BEFORE expensive
extraction/diff/evidence processing.

Pipeline:
    Source -> Conditional Fetch / Metadata -> Content Fingerprint
          -> Compare Previous Fingerprint
          -> UNCHANGED -> stop
          -> CHANGED -> existing extraction pipeline

Design principles:
- Deterministic hashing
- Normalize irrelevant differences before hashing
- Preserve semantic content
- Distinguish unchanged / changed / unknown
- Version fingerprint algorithm
- Idempotent storage
- Source-specific fingerprint history
- No destructive overwrite
- Low-latency streaming/memory-efficient
- No N+1 queries
- Batch fingerprint lookups
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from ..models import ContentFingerprintRecord
from .telemetry import PipelineStages, record_event


FINGERPRINT_ALGORITHM_VERSION = "v1"

_WHITESPACE_RE = re.compile(r"\s+")
_TRACKING_PARAMS_RE = re.compile(r"[?&](utm_[a-zA-Z0-9_]+|ref|source|campaign|fbclid|gclid)=[^&]*")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)


class FingerprintStatus(str, Enum):
    UNCHANGED = "unchanged"
    CHANGED = "changed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ContentFingerprint:
    source_url: str
    normalized_content_hash: str
    content_length: int
    etag: str | None = None
    last_modified: str | None = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    algorithm_version: str = FINGERPRINT_ALGORITHM_VERSION


@dataclass(frozen=True)
class FingerprintComparisonResult:
    status: FingerprintStatus
    previous_fingerprint: ContentFingerprint | None
    current_fingerprint: ContentFingerprint | None
    bytes_processed: int = 0
    skipped_downstream: bool = False


def normalize_content(content: str) -> str:
    """Normalize content to remove irrelevant differences before hashing.

    Removes:
    - HTML comments
    - Script and style blocks
    - Tracking query parameters (UTM, ref, fbclid, gclid)
    - Excessive whitespace (collapsed to single space)
    - Leading/trailing whitespace per line
    """
    if not content:
        return ""

    normalized = _HTML_COMMENT_RE.sub("", content)
    normalized = _SCRIPT_STYLE_RE.sub("", normalized)

    def _clean_url(match: re.Match[str]) -> str:
        url = match.group(0)
        cleaned = _TRACKING_PARAMS_RE.sub("", url)
        if cleaned.endswith("?") or cleaned.endswith("&"):
            cleaned = cleaned[:-1]
        return cleaned

    url_pattern = re.compile(r'https?://[^\s"\'<>]+')
    normalized = url_pattern.sub(_clean_url, normalized)

    lines = normalized.splitlines()
    cleaned_lines = []
    for line in lines:
        line = _WHITESPACE_RE.sub(" ", line).strip()
        if line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def compute_content_hash(content: str) -> tuple[str, int]:
    """Compute deterministic hash and length for content.

    Returns:
        Tuple of (hash_hex, byte_length)
    """
    if not content:
        return ("", 0)

    encoded = content.encode("utf-8")
    content_hash = hashlib.sha256(encoded).hexdigest()
    return (content_hash, len(encoded))


def create_fingerprint(
    source_url: str,
    content: str,
    etag: str | None = None,
    last_modified: str | None = None,
) -> ContentFingerprint:
    """Create a content fingerprint from source content.

    The content is normalized before hashing to ensure that irrelevant
    differences (whitespace, tracking params) don't trigger false changes.
    """
    normalized = normalize_content(content)
    content_hash, content_length = compute_content_hash(normalized)

    return ContentFingerprint(
        source_url=source_url,
        normalized_content_hash=content_hash,
        content_length=content_length,
        etag=etag,
        last_modified=last_modified,
    )


def compare_fingerprints(
    previous: ContentFingerprint | None,
    current: ContentFingerprint,
) -> FingerprintStatus:
    """Compare two fingerprints to determine change status.

    Rules:
    - No previous fingerprint -> UNKNOWN (first observation)
    - Different algorithm version -> UNKNOWN (can't reliably compare)
    - Same normalized_content_hash -> UNCHANGED
    - Different normalized_content_hash -> CHANGED
    """
    if previous is None:
        return FingerprintStatus.UNKNOWN

    if previous.algorithm_version != current.algorithm_version:
        return FingerprintStatus.UNKNOWN

    if previous.normalized_content_hash == current.normalized_content_hash:
        return FingerprintStatus.UNCHANGED

    return FingerprintStatus.CHANGED


def store_fingerprint(session: Session, fingerprint: ContentFingerprint) -> bool:
    """Store a fingerprint record idempotently.

    If an identical hash already exists for the source, no new record is created.
    Returns True if a new record was stored, False if it already existed.
    """
    existing = session.scalar(
        select(ContentFingerprintRecord).where(
            and_(
                ContentFingerprintRecord.source_url == fingerprint.source_url,
                ContentFingerprintRecord.normalized_content_hash == fingerprint.normalized_content_hash,
            )
        )
    )

    if existing is not None:
        return False

    record = ContentFingerprintRecord(
        source_url=fingerprint.source_url,
        normalized_content_hash=fingerprint.normalized_content_hash,
        content_length=fingerprint.content_length,
        etag=fingerprint.etag,
        last_modified=fingerprint.last_modified,
        algorithm_version=fingerprint.algorithm_version,
        generated_at=fingerprint.generated_at,
    )
    session.add(record)
    session.flush()
    return True


def get_latest_fingerprint(session: Session, source_url: str) -> ContentFingerprint | None:
    """Get the most recent fingerprint for a source URL."""
    row = session.scalar(
        select(ContentFingerprintRecord)
        .where(ContentFingerprintRecord.source_url == source_url)
        .order_by(ContentFingerprintRecord.generated_at.desc())
        .limit(1)
    )

    if row is None:
        return None

    return ContentFingerprint(
        source_url=row.source_url,
        normalized_content_hash=row.normalized_content_hash,
        content_length=row.content_length,
        etag=row.etag,
        last_modified=row.last_modified,
        generated_at=row.generated_at,
        algorithm_version=row.algorithm_version,
    )


def batch_get_latest_fingerprints(
    session: Session,
    source_urls: list[str],
) -> dict[str, ContentFingerprint | None]:
    """Get latest fingerprints for multiple sources in a single query (no N+1).

    Returns a dict mapping source_url to its latest fingerprint (or None).
    """
    if not source_urls:
        return {}

    stmt = (
        select(ContentFingerprintRecord)
        .where(ContentFingerprintRecord.source_url.in_(source_urls))
        .order_by(ContentFingerprintRecord.source_url, ContentFingerprintRecord.generated_at.desc())
    )
    rows = session.execute(stmt).scalars().all()

    fingerprints: dict[str, ContentFingerprint | None] = {url: None for url in source_urls}

    for row in rows:
        url = row.source_url
        if fingerprints.get(url) is None:
            fingerprints[url] = ContentFingerprint(
                source_url=row.source_url,
                normalized_content_hash=row.normalized_content_hash,
                content_length=row.content_length,
                etag=row.etag,
                last_modified=row.last_modified,
                generated_at=row.generated_at,
                algorithm_version=row.algorithm_version,
            )

    return fingerprints


def check_source_changed(
    session: Session,
    source_url: str,
    content: str,
    etag: str | None = None,
    last_modified: str | None = None,
    job_id: str | None = None,
    correlation_id: str | None = None,
) -> FingerprintComparisonResult:
    """Check if a source has changed and store the new fingerprint.

    This is the main entry point for incremental change detection.

    Returns a FingerprintComparisonResult with:
    - status: UNCHANGED, CHANGED, or UNKNOWN
    - previous_fingerprint: the last known fingerprint (if any)
    - current_fingerprint: the newly computed fingerprint
    - bytes_processed: number of bytes hashed
    - skipped_downstream: True if processing can be skipped

    Safety:
    - Empty/invalid content -> UNKNOWN (never treated as unchanged)
    - Failed fetch should NOT call this function (caller's responsibility)
    - Never suppresses verification when status is UNKNOWN
    """
    start_time = time.monotonic()

    if not content or not content.strip():
        duration_ms = (time.monotonic() - start_time) * 1000.0
        record_event(
            stage=PipelineStages.FETCH,
            metric_type="fingerprint_unknown",
            duration_ms=duration_ms,
            source=source_url,
            job_id=job_id,
            success=True,
            metadata={"reason": "empty_content", "correlation_id": correlation_id},
        )
        return FingerprintComparisonResult(
            status=FingerprintStatus.UNKNOWN,
            previous_fingerprint=None,
            current_fingerprint=None,
            bytes_processed=0,
            skipped_downstream=False,
        )

    previous = get_latest_fingerprint(session, source_url)
    current = create_fingerprint(source_url, content, etag, last_modified)
    status = compare_fingerprints(previous, current)

    bytes_processed = current.content_length
    skipped_downstream = status == FingerprintStatus.UNCHANGED

    store_fingerprint(session, current)

    duration_ms = (time.monotonic() - start_time) * 1000.0
    metric_type = (
        "fingerprint_unchanged"
        if status == FingerprintStatus.UNCHANGED
        else "fingerprint_changed"
        if status == FingerprintStatus.CHANGED
        else "fingerprint_unknown"
    )

    record_event(
        stage=PipelineStages.FETCH,
        metric_type=metric_type,
        duration_ms=duration_ms,
        source=source_url,
        job_id=job_id,
        success=True,
        metadata={
            "status": status.value,
            "bytes_processed": bytes_processed,
            "skipped_downstream": skipped_downstream,
            "correlation_id": correlation_id,
            "algorithm_version": current.algorithm_version,
        },
    )

    return FingerprintComparisonResult(
        status=status,
        previous_fingerprint=previous,
        current_fingerprint=current,
        bytes_processed=bytes_processed,
        skipped_downstream=skipped_downstream,
    )


def batch_check_sources_changed(
    session: Session,
    sources: list[tuple[str, str]],
    job_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, FingerprintComparisonResult]:
    """Check multiple sources for changes in batch (no N+1).

    Args:
        session: Database session
        sources: List of (source_url, content) tuples
        job_id: Optional job identifier for telemetry
        correlation_id: Optional correlation identifier for telemetry

    Returns:
        Dict mapping source_url to FingerprintComparisonResult
    """
    if not sources:
        return {}

    start_time = time.monotonic()

    source_urls = [url for url, _ in sources]
    previous_fingerprints = batch_get_latest_fingerprints(session, source_urls)

    results: dict[str, FingerprintComparisonResult] = {}

    for source_url, content in sources:
        if not content or not content.strip():
            results[source_url] = FingerprintComparisonResult(
                status=FingerprintStatus.UNKNOWN,
                previous_fingerprint=previous_fingerprints.get(source_url),
                current_fingerprint=None,
                bytes_processed=0,
                skipped_downstream=False,
            )
            continue

        previous = previous_fingerprints.get(source_url)
        current = create_fingerprint(source_url, content)
        status = compare_fingerprints(previous, current)

        results[source_url] = FingerprintComparisonResult(
            status=status,
            previous_fingerprint=previous,
            current_fingerprint=current,
            bytes_processed=current.content_length,
            skipped_downstream=status == FingerprintStatus.UNCHANGED,
        )

    new_fingerprints = {
        url: result.current_fingerprint
        for url, result in results.items()
        if result.current_fingerprint is not None
    }

    for url, fingerprint in new_fingerprints.items():
        store_fingerprint(session, fingerprint)

    duration_ms = (time.monotonic() - start_time) * 1000.0
    unchanged_count = sum(1 for r in results.values() if r.status == FingerprintStatus.UNCHANGED)
    changed_count = sum(1 for r in results.values() if r.status == FingerprintStatus.CHANGED)
    unknown_count = sum(1 for r in results.values() if r.status == FingerprintStatus.UNKNOWN)

    record_event(
        stage=PipelineStages.FETCH,
        metric_type="fingerprint_batch",
        duration_ms=duration_ms,
        job_id=job_id,
        success=True,
        metadata={
            "batch_size": len(sources),
            "unchanged_count": unchanged_count,
            "changed_count": changed_count,
            "unknown_count": unknown_count,
            "correlation_id": correlation_id,
        },
    )

    return results
