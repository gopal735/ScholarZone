"""Decorators and helpers for instrumenting pipeline functions."""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable, TypeVar

from .telemetry import (
    ErrorCategory,
    MetricType,
    PipelineStages,
    TimerContext,
    get_collector,
    record_event,
    record_failure,
    record_retry,
    record_success,
    record_terminal_failure,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def instrument_stage(
    stage: str,
    *,
    pass_context: bool = False,
) -> Callable[[F], F]:
    """Decorator to instrument a pipeline stage with timing and success/failure tracking.

    Usage:
        @instrument_stage(PipelineStages.FETCH)
        def my_fetch_function(url: str) -> FetchResult:
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.monotonic() - start) * 1000.0
                record_event(
                    stage=stage,
                    metric_type=MetricType.SUCCESS,
                    duration_ms=duration_ms,
                    success=True,
                )
                return result
            except Exception as e:
                duration_ms = (time.monotonic() - start) * 1000.0
                record_event(
                    stage=stage,
                    metric_type=MetricType.FAILURE,
                    duration_ms=duration_ms,
                    success=False,
                    error_type=type(e).__name__,
                )
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def instrument_fetch(func: F) -> F:
    """Decorator specifically for fetch operations."""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        source = _extract_source_from_args(func, args, kwargs)
        scholarship_id = _extract_scholarship_id_from_args(func, args, kwargs)
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.monotonic() - start) * 1000.0
            success = _is_success_result(result)
            error_type = _extract_error_type(result)
            record_event(
                stage=PipelineStages.FETCH,
                metric_type=MetricType.SUCCESS if success else MetricType.FAILURE,
                duration_ms=duration_ms,
                scholarship_id=scholarship_id,
                source=source,
                success=success,
                error_type=error_type,
            )
            if not success:
                _record_failure_details(stage=PipelineStages.FETCH, result=result, source=source)
            return result
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000.0
            record_event(
                stage=PipelineStages.FETCH,
                metric_type=MetricType.FAILURE,
                duration_ms=duration_ms,
                scholarship_id=scholarship_id,
                source=source,
                success=False,
                error_type=type(e).__name__,
            )
            raise

    return wrapper  # type: ignore[return-value]


def instrument_extraction(func: F) -> F:
    """Decorator for extraction operations."""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.monotonic() - start) * 1000.0
            record_event(
                stage=PipelineStages.EXTRACTION,
                metric_type=MetricType.SUCCESS,
                duration_ms=duration_ms,
                success=True,
            )
            return result
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000.0
            record_event(
                stage=PipelineStages.EXTRACTION,
                metric_type=MetricType.FAILURE,
                duration_ms=duration_ms,
                success=False,
                error_type=type(e).__name__,
            )
            raise

    return wrapper  # type: ignore[return-value]


def instrument_diff(func: F) -> F:
    """Decorator for diff operations."""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.monotonic() - start) * 1000.0
            record_event(
                stage=PipelineStages.DIFF,
                metric_type=MetricType.SUCCESS,
                duration_ms=duration_ms,
                success=True,
            )
            return result
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000.0
            record_event(
                stage=PipelineStages.DIFF,
                metric_type=MetricType.FAILURE,
                duration_ms=duration_ms,
                success=False,
                error_type=type(e).__name__,
            )
            raise

    return wrapper  # type: ignore[return-value]


def instrument_evidence(func: F) -> F:
    """Decorator for evidence collection operations."""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.monotonic() - start) * 1000.0
            record_event(
                stage=PipelineStages.EVIDENCE,
                metric_type=MetricType.SUCCESS,
                duration_ms=duration_ms,
                success=True,
            )
            return result
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000.0
            record_event(
                stage=PipelineStages.EVIDENCE,
                metric_type=MetricType.FAILURE,
                duration_ms=duration_ms,
                success=False,
                error_type=type(e).__name__,
            )
            raise

    return wrapper  # type: ignore[return-value]


def instrument_confidence(func: F) -> F:
    """Decorator for confidence assessment operations."""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.monotonic() - start) * 1000.0
            record_event(
                stage=PipelineStages.CONFIDENCE,
                metric_type=MetricType.SUCCESS,
                duration_ms=duration_ms,
                success=True,
            )
            return result
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000.0
            record_event(
                stage=PipelineStages.CONFIDENCE,
                metric_type=MetricType.FAILURE,
                duration_ms=duration_ms,
                success=False,
                error_type=type(e).__name__,
            )
            raise

    return wrapper  # type: ignore[return-value]


def instrument_verification(func: F) -> F:
    """Decorator for full verification pipeline operations."""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        scholarship_id = _extract_scholarship_id_from_args(func, args, kwargs)
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.monotonic() - start) * 1000.0
            success = result is not None
            source = _extract_source_from_result(result)
            record_event(
                stage=PipelineStages.FETCH,
                metric_type=MetricType.SUCCESS if success else MetricType.FAILURE,
                duration_ms=duration_ms,
                scholarship_id=scholarship_id,
                source=source,
                success=success,
            )
            return result
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000.0
            record_event(
                stage=PipelineStages.FETCH,
                metric_type=MetricType.FAILURE,
                duration_ms=duration_ms,
                scholarship_id=scholarship_id,
                success=False,
                error_type=type(e).__name__,
            )
            raise

    return wrapper  # type: ignore[return-value]


def instrument_update(func: F) -> F:
    """Decorator for update operations."""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        scholarship_id = _extract_scholarship_id_from_args(func, args, kwargs)
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.monotonic() - start) * 1000.0
            success = _is_update_success(result)
            record_event(
                stage=PipelineStages.UPDATE,
                metric_type=MetricType.SUCCESS if success else MetricType.FAILURE,
                duration_ms=duration_ms,
                scholarship_id=scholarship_id,
                success=success,
                metadata={"updated_fields": _extract_updated_fields(result)},
            )
            return result
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000.0
            record_event(
                stage=PipelineStages.UPDATE,
                metric_type=MetricType.FAILURE,
                duration_ms=duration_ms,
                scholarship_id=scholarship_id,
                success=False,
                error_type=type(e).__name__,
            )
            raise

    return wrapper  # type: ignore[return-value]


def instrument_review(func: F) -> F:
    """Decorator for review operations."""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        scholarship_id = _extract_scholarship_id_from_args(func, args, kwargs)
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.monotonic() - start) * 1000.0
            created = _extract_review_created(result)
            record_event(
                stage=PipelineStages.REVIEW,
                metric_type=MetricType.SUCCESS if created else MetricType.FAILURE,
                duration_ms=duration_ms,
                scholarship_id=scholarship_id,
                success=created,
                metadata={"review_count": _extract_review_count(result)},
            )
            return result
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000.0
            record_event(
                stage=PipelineStages.REVIEW,
                metric_type=MetricType.FAILURE,
                duration_ms=duration_ms,
                scholarship_id=scholarship_id,
                success=False,
                error_type=type(e).__name__,
            )
            raise

    return wrapper  # type: ignore[return-value]


def instrument_discovery(func: F) -> F:
    """Decorator for discovery operations."""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        source = _extract_source_from_args(func, args, kwargs)
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.monotonic() - start) * 1000.0
            success = _is_discovery_success(result)
            record_event(
                stage=PipelineStages.DISCOVERY,
                metric_type=MetricType.SUCCESS if success else MetricType.FAILURE,
                duration_ms=duration_ms,
                source=source,
                success=success,
            )
            return result
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000.0
            record_event(
                stage=PipelineStages.DISCOVERY,
                metric_type=MetricType.FAILURE,
                duration_ms=duration_ms,
                source=source,
                success=False,
                error_type=type(e).__name__,
            )
            raise

    return wrapper  # type: ignore[return-value]


def instrument_scheduler(func: F) -> F:
    """Decorator for scheduler operations."""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.monotonic() - start) * 1000.0
            record_event(
                stage=PipelineStages.SCHEDULER,
                metric_type=MetricType.SUCCESS,
                duration_ms=duration_ms,
                success=True,
                metadata={"jobs_processed": _extract_job_count(result)},
            )
            return result
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000.0
            record_event(
                stage=PipelineStages.SCHEDULER,
                metric_type=MetricType.FAILURE,
                duration_ms=duration_ms,
                success=False,
                error_type=type(e).__name__,
            )
            raise

    return wrapper  # type: ignore[return-value]


def _extract_source_from_args(func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> str | None:
    """Extract source URL from function arguments."""
    import inspect

    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    for i, arg in enumerate(args):
        if i < len(params):
            param_name = params[i]
            if param_name in ("url", "source_url", "official_source_url"):
                return str(arg) if arg else None
    for key in ("url", "source_url", "official_source_url"):
        if key in kwargs:
            val = kwargs[key]
            return str(val) if val else None
    return None


def _extract_scholarship_id_from_args(func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> int | None:
    """Extract scholarship ID from function arguments."""
    import inspect

    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    for i, arg in enumerate(args):
        if i < len(params):
            param_name = params[i]
            if param_name in ("scholarship_id", "id"):
                return int(arg) if arg is not None else None
    for key in ("scholarship_id", "id"):
        if key in kwargs:
            val = kwargs[key]
            return int(val) if val is not None else None
    return None


def _extract_source_from_result(result: Any) -> str | None:
    """Extract source URL from a result object."""
    if result is None:
        return None
    for attr in ("official_source_url", "source_url", "url"):
        if hasattr(result, attr):
            val = getattr(result, attr)
            return str(val) if val else None
    return None


def _is_success_result(result: Any) -> bool:
    """Check if a result indicates success."""
    if result is None:
        return False
    if hasattr(result, "success"):
        return bool(result.success)
    return True


def _extract_error_type(result: Any) -> str | None:
    """Extract error type from a result object."""
    if result is None:
        return None
    if hasattr(result, "error_type"):
        return result.error_type
    if hasattr(result, "error"):
        err = result.error
        return type(err).__name__ if err else None
    return None


def _record_failure_details(stage: str, result: Any, source: str | None) -> None:
    """Record detailed failure information."""
    error_type = _extract_error_type(result)
    if error_type is None:
        return
    if error_type in ("timeout",):
        record_event(
            stage=stage,
            metric_type=MetricType.TIMEOUT,
            source=source,
            success=False,
            error_type=error_type,
        )
    elif error_type in ("rate_limited",):
        record_event(
            stage=stage,
            metric_type=MetricType.RATE_LIMITED,
            source=source,
            success=False,
            error_type=error_type,
        )
    elif error_type in ("server_error",):
        record_event(
            stage=stage,
            metric_type=MetricType.SERVER_ERROR,
            source=source,
            success=False,
            error_type=error_type,
        )


def _is_update_success(result: Any) -> bool:
    """Check if an update result indicates success."""
    if result is None:
        return False
    if hasattr(result, "update_status"):
        return result.update_status in ("success", "partial")
    if hasattr(result, "updated_fields"):
        return len(result.updated_fields) > 0
    return False


def _extract_updated_fields(result: Any) -> list[str]:
    """Extract updated fields from a result."""
    if result is None:
        return []
    if hasattr(result, "updated_fields"):
        return list(result.updated_fields)
    return []


def _extract_review_created(result: Any) -> bool:
    """Check if reviews were created."""
    if result is None:
        return False
    if isinstance(result, list):
        return len(result) > 0
    if hasattr(result, "created"):
        return bool(result.created)
    return False


def _extract_review_count(result: Any) -> int:
    """Extract review count from result."""
    if result is None:
        return 0
    if isinstance(result, list):
        return len(result)
    if hasattr(result, "review_count"):
        return int(result.review_count)
    return 0


def _is_discovery_success(result: Any) -> bool:
    """Check if a discovery result indicates success."""
    if result is None:
        return False
    if hasattr(result, "status"):
        return result.status not in ("error", "rejected")
    return True


def _extract_job_count(result: Any) -> int:
    """Extract job count from scheduler result."""
    if result is None:
        return 0
    if isinstance(result, int):
        return result
    if hasattr(result, "job_count"):
        return int(result.job_count)
    return 0
