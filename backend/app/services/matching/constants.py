"""Stable import surface for the matching engine's configuration.

Every number the engine is allowed to use now lives in :mod:`config`, which is
the single source of truth and validates itself at import time. This module
re-exports the names the rest of the package, the tests and the API have
historically imported, so the move to one configuration module did not have to
touch every call site at once.

Two properties are load-bearing and are asserted by the test suite:

1. ``FIT_ENGINE_VERSION`` changes whenever any scoring behaviour changes, and
   ``SCORING_CONFIG_VERSION`` changes whenever a weight, matrix, band or range
   changes. A score that silently moves under an unchanged version string is the
   one failure mode this package exists to prevent, because the version is what
   makes a stored result reproducible.

2. The weights sum to exactly 1.0. ``validate_weight_constants()`` re-runs the
   import-time check so an arithmetic slip fails immediately instead of quietly
   rescaling every fit score in the product. Weights are never silently
   rescaled to make a table add up.

The engine is pure. It contains no clock, no randomness and no network access;
``as_of`` is injected. Given the same profile, the same scholarship facts and
the same ``as_of``, every function here returns the same value.
"""

from __future__ import annotations

from .config import (  # noqa: F401  (re-exported deliberately)
    ACADEMIC_HEADROOM_DISPLAY_SCALE,
    ACADEMIC_MINIMUM_ONLY_SCORE,
    ACADEMIC_WEIGHT,
    API_BANDS,
    API_COMPONENT_WEIGHTS,
    CONFIDENCE_BANDS,
    CONFIDENCE_BAND_KEYS,
    CONFIDENCE_WEIGHTS,
    COVERAGE_BAND_KEYS,
    COVERAGE_BANDS,
    DEADLINE_SEMANTICS_VERSION,
    DISPLAY_PRECISION,
    ELIGIBILITY_RANK,
    FIELD_RELATIONSHIP_BROAD,
    FIELD_RELATIONSHIP_CLOSE,
    FIELD_RELATIONSHIP_EXACT,
    FIELD_RELATIONSHIP_LEVELS,
    FIELD_RELATIONSHIP_RELATED,
    FIELD_RELATIONSHIP_UNRELATED,
    FIELD_TAXONOMY_VERSION,
    FIT_BANDS,
    FIT_BAND_KEYS,
    FIT_COMPONENT_LABELS,
    FIT_COMPONENT_ORDER,
    FIT_ENGINE_VERSION,
    FIT_WEIGHTS,
    FUNDING_COMPATIBILITY,
    FUNDING_NEED_FULL,
    FUNDING_NEED_NEUTRAL,
    FUNDING_NEED_PARTIAL,
    FUNDING_NEED_TUITION,
    FUNDING_STATE_FULL,
    FUNDING_STATE_NONE,
    FUNDING_STATE_PARTIAL,
    FUNDING_STATE_TUITION_ONLY,
    FUNDING_STATE_TUITION_PLUS_LIVING,
    FUNDING_STATE_UNKNOWN,
    FUNDING_STATES,
    FIELD_WEIGHT,
    FUNDING_WEIGHT,
    LANGUAGE_BELOW_MINIMUM_SCORE,
    LANGUAGE_CROSS_TEST_EQUIVALENCY_SUPPORTED,
    LANGUAGE_SURPLUS_RANGES,
    LANGUAGE_WEIGHT,
    MATCH_CANDIDATE_HARD_LIMIT,
    MATCH_RESULT_LIMIT_DEFAULT,
    MATCH_RESULT_LIMIT_MAX,
    PREFERENCE_COMPATIBILITY,
    PREFERENCE_MATCH,
    PREFERENCE_NO_MATCH,
    PREFERENCE_WEIGHT,
    PROFILE_STRENGTH_BANDS,
    PROFILE_STRENGTH_COMPONENT_ORDER,
    PROFILE_STRENGTH_LABELS,
    PROFILE_STRENGTH_WEIGHTS,
    READINESS_BANDS,
    READINESS_BAND_KEYS,
    READINESS_COMPONENT_LABELS,
    READINESS_COMPONENT_ORDER,
    READINESS_WEIGHTS,
    REQUIREMENT_READER_VERSION,
    REQUIREMENT_WEIGHT,
    SCORING_CONFIG_VERSION,
    SORT_OPTIONS,
    STRONG_MATCH_THRESHOLD,
    SUM_TOLERANCE,
    TIMING_BANDS,
    TIMING_BUCKET_CLOSED,
    TIMING_BUCKET_KEYS,
    TIMING_BUCKET_UNKNOWN,
    TIMING_BUCKETS,
    TIMING_FINAL_BAND_MAX_DAYS,
    TIMING_WEIGHT,
    TOTAL_CONFIGURED_WEIGHT,
    VERIFICATION_FRESH_DAYS,
    VERIFICATION_FRESHNESS_STEPS,
    VERIFICATION_STALE_DAYS,
    clamp,
    config_snapshot,
    funding_score,
    language_surplus_range,
    preference_score,
    validate_config,
)
from .config import FIT_WEIGHTS as FIT_WEIGHTS  # explicit re-export for tooling


def validate_weight_constants() -> None:
    """Re-run the import-time configuration self-check.

    A weight table that does not total 1.0 silently rescales every fit score in
    the product, and the failure surfaces as "the numbers changed" rather than as
    an error. The check lives in :mod:`config` and already runs on import; this
    wrapper exists so the historical entry point keeps working.
    """
    validate_config()


__all__ = [
    "ACADEMIC_HEADROOM_DISPLAY_SCALE",
    "ACADEMIC_MINIMUM_ONLY_SCORE",
    "API_BANDS",
    "API_COMPONENT_WEIGHTS",
    "CONFIDENCE_BANDS",
    "CONFIDENCE_BAND_KEYS",
    "CONFIDENCE_WEIGHTS",
    "COVERAGE_BAND_KEYS",
    "COVERAGE_BANDS",
    "DEADLINE_SEMANTICS_VERSION",
    "ELIGIBILITY_RANK",
    "FIELD_RELATIONSHIP_LEVELS",
    "FIELD_TAXONOMY_VERSION",
    "FIT_BANDS",
    "FIT_BAND_KEYS",
    "FIT_COMPONENT_LABELS",
    "FIT_COMPONENT_ORDER",
    "FIT_ENGINE_VERSION",
    "FIT_WEIGHTS",
    "FUNDING_COMPATIBILITY",
    "FUNDING_STATES",
    "LANGUAGE_CROSS_TEST_EQUIVALENCY_SUPPORTED",
    "LANGUAGE_SURPLUS_RANGES",
    "MATCH_CANDIDATE_HARD_LIMIT",
    "MATCH_RESULT_LIMIT_DEFAULT",
    "MATCH_RESULT_LIMIT_MAX",
    "PREFERENCE_COMPATIBILITY",
    "PROFILE_STRENGTH_BANDS",
    "PROFILE_STRENGTH_WEIGHTS",
    "READINESS_BANDS",
    "READINESS_COMPONENT_ORDER",
    "READINESS_WEIGHTS",
    "REQUIREMENT_READER_VERSION",
    "SCORING_CONFIG_VERSION",
    "SORT_OPTIONS",
    "STRONG_MATCH_THRESHOLD",
    "SUM_TOLERANCE",
    "TIMING_BANDS",
    "TIMING_BUCKET_KEYS",
    "TIMING_BUCKETS",
    "TOTAL_CONFIGURED_WEIGHT",
    "clamp",
    "config_snapshot",
    "funding_score",
    "language_surplus_range",
    "preference_score",
    "validate_weight_constants",
]