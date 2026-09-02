"""Source adapter executor — integrates adapters with the existing pipeline.

CRITICAL: This executor uses the existing execute_fetch_with_retry() as the
single authoritative retry path. Adapters provide configuration hints only.

No nested retries. No duplicate attempts. No conflicting backoff.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from .official_source_fetcher import OfficialSourceFetchResult, fetch_official_source
from .scholarship_extractor import ScholarshipExtractionResult, extract_scholarship_information
from .scholarship_fetch_executor import FetchExecutionResult, execute_fetch_with_retry
from .source_adapter import (
    AdapterRegistry,
    SourceAdapter,
    get_default_registry,
)
from .telemetry import PipelineStages, record_event


@dataclass(frozen=True)
class AdapterFetchResult:
    """Result of an adapter-guided fetch."""

    fetch_execution: FetchExecutionResult
    adapter_type: str
    fetch_config_applied: bool = True


@dataclass(frozen=True)
class AdapterExtractionResult:
    """Result of an adapter-guided extraction."""

    extraction: ScholarshipExtractionResult
    adapter_type: str
    extraction_config_applied: bool = True


def execute_fetch_with_adapter(
    session: Session,
    scholarship_id: int,
    source_url: str,
    adapter: SourceAdapter | None = None,
    registry: AdapterRegistry | None = None,
    max_attempts: int | None = None,
) -> AdapterFetchResult:
    """Execute a fetch using adapter configuration hints.

    Delegates retry orchestration to execute_fetch_with_retry().
    The adapter provides hints (timeout, rate limits) but the existing
    retry executor remains authoritative — no second retry loop.
    """
    if adapter is None:
        reg = registry or get_default_registry()
        adapter = reg.resolve(source_url)

    fetch_config = adapter.get_fetch_config()
    effective_max_attempts = max_attempts if max_attempts is not None else fetch_config.max_retries_hint

    fetch_start = time.monotonic()

    fetch_execution = execute_fetch_with_retry(
        session=session,
        scholarship_id=scholarship_id,
        source_url=source_url,
        max_attempts=effective_max_attempts,
    )

    fetch_duration_ms = (time.monotonic() - fetch_start) * 1000.0

    record_event(
        stage=PipelineStages.FETCH,
        metric_type="success" if fetch_execution.fetch_result.success else "failure",
        duration_ms=fetch_duration_ms,
        scholarship_id=scholarship_id,
        source=source_url,
        success=fetch_execution.fetch_result.success,
        error_type=fetch_execution.fetch_result.error_type,
        metadata={
            "adapter_type": adapter.source_type.value,
            "adapter_priority": adapter.priority,
            "fetch_status": fetch_execution.status,
        },
    )

    return AdapterFetchResult(
        fetch_execution=fetch_execution,
        adapter_type=adapter.source_type.value,
    )


def execute_extraction_with_adapter(
    html_content: str,
    source_url: str,
    adapter: SourceAdapter | None = None,
    registry: AdapterRegistry | None = None,
) -> AdapterExtractionResult:
    """Execute extraction using adapter configuration hints.

    Uses the existing extract_scholarship_information() function.
    The adapter provides hints but does not bypass any extraction logic.
    """
    if adapter is None:
        reg = registry or get_default_registry()
        adapter = reg.resolve(source_url)

    extraction_config = adapter.get_extraction_config()

    extraction_start = time.monotonic()

    extraction = extract_scholarship_information(html_content, source_url)

    extraction_duration_ms = (time.monotonic() - extraction_start) * 1000.0

    record_event(
        stage=PipelineStages.EXTRACTION,
        metric_type="success",
        duration_ms=extraction_duration_ms,
        source=source_url,
        success=True,
        metadata={
            "adapter_type": adapter.source_type.value,
            "extraction_config_parser": extraction_config.parser_strategy,
            "fields_extracted": [
                f for f in [
                    "scholarship_name", "provider", "deadline", "award_amount",
                    "eligibility", "duration", "application_url",
                ]
                if getattr(extraction, f, None) is not None
            ],
        },
    )

    return AdapterExtractionResult(
        extraction=extraction,
        adapter_type=adapter.source_type.value,
    )


def resolve_adapter_for_source(
    source_url: str,
    registry: AdapterRegistry | None = None,
) -> SourceAdapter:
    """Resolve the appropriate adapter for a source URL."""
    reg = registry or get_default_registry()
    return reg.resolve(source_url)


def resolve_adapters_batch(
    source_urls: list[str],
    registry: AdapterRegistry | None = None,
) -> dict[str, SourceAdapter]:
    """Resolve adapters for multiple source URLs in batch."""
    reg = registry or get_default_registry()
    return reg.resolve_batch(source_urls)
