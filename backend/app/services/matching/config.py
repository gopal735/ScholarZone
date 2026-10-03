"""The single source of truth for every number ScholarZone Match is allowed to use.

Nothing in this package computes a score from a literal. Every weight, matrix,
band and range lives here, is versioned here, and is validated here at import
time. That is what makes the engine auditable: a reviewer can read the complete
mathematical definition of "ScholarZone Match" in one file, and a change to a
weight is a deliberate, reviewable edit rather than an accident buried in a
scorer.

Five properties are load-bearing and are asserted by the test suite:

1. ``FIT_ENGINE_VERSION`` changes whenever any scoring behaviour changes. A score
   that silently moves under an unchanged version string is the one failure mode
   this module exists to prevent, because the version is what makes a stored
   result reproducible.

2. ``SCORING_CONFIG_VERSION`` changes whenever a weight, matrix, band or range
   changes. It is reported separately from the engine version so a reviewer can
   tell "the code changed" apart from "the numbers changed".

3. Every weight table totals exactly 1.0. ``validate_config()`` re-checks that at
   import time so an arithmetic slip fails immediately instead of silently
   rescaling every score in the product.

4. Malformed weights are never silently rescaled. A total that is not 1.0 raises.

5. The engine is pure. It contains no clock, no randomness and no network access;
   ``as_of`` is injected. Given the same profile, the same scholarship facts and
   the same ``as_of``, every function here returns the same value.

Compatibility matrices are tables rather than branching logic. ``funding_score``
and ``preference_score`` are resolvers over these tables, so revising a number
never requires editing a scorer and never risks one branch being forgotten.
"""

from __future__ import annotations

from types import MappingProxyType


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

#: Bumped whenever any scoring behaviour changes.
FIT_ENGINE_VERSION = "2.0.0"

#: Bumped whenever a weight, matrix, band or range changes.
SCORING_CONFIG_VERSION = "2.0.0"

#: Bumped whenever the programme/field alias table or relationship levels change.
FIELD_TAXONOMY_VERSION = "1.0.0"

#: Bumped whenever the published-requirement readers change what they accept.
REQUIREMENT_READER_VERSION = "2.0.0"

#: The version of ``app/services/deadline_semantics.py`` the timing component
#: depends on. Reported so a deadline-semantics change is visible alongside a
#: scoring change rather than hidden inside one.
DEADLINE_SEMANTICS_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Fit score component weights
# ---------------------------------------------------------------------------
#
# LOCKED. These seven weights total 1.0. They are the whole fit formula; there is
# no second set of coefficients anywhere in the engine.

FIT_WEIGHTS: MappingProxyType[str, float] = MappingProxyType(
    {
        "academic": 0.25,
        "field": 0.20,
        "funding": 0.20,
        "requirement": 0.15,
        "language": 0.10,
        "preference": 0.05,
        "timing": 0.05,
    }
)

ACADEMIC_WEIGHT = FIT_WEIGHTS["academic"]
FIELD_WEIGHT = FIT_WEIGHTS["field"]
FUNDING_WEIGHT = FIT_WEIGHTS["funding"]
REQUIREMENT_WEIGHT = FIT_WEIGHTS["requirement"]
LANGUAGE_WEIGHT = FIT_WEIGHTS["language"]
PREFERENCE_WEIGHT = FIT_WEIGHTS["preference"]
TIMING_WEIGHT = FIT_WEIGHTS["timing"]

#: Presentation order for the score breakdown. Scoring is order-independent; the
#: UI is not, and a stable order makes two results comparable at a glance.
FIT_COMPONENT_ORDER: tuple[str, ...] = (
    "academic",
    "field",
    "funding",
    "requirement",
    "language",
    "preference",
    "timing",
)

#: Total configured weight as an integer percentage. The coverage formula
#: simplifies to a percentage only because this is exactly 100.
TOTAL_CONFIGURED_WEIGHT = 100.0

#: Human-readable component names used in explanations.
FIT_COMPONENT_LABELS: MappingProxyType[str, str] = MappingProxyType(
    {
        "academic": "Academic",
        "field": "Field / programme",
        "funding": "Funding",
        "requirement": "Requirements",
        "language": "Language",
        "preference": "Preferences",
        "timing": "Timing",
    }
)


# ---------------------------------------------------------------------------
# Fit score classification bands
# ---------------------------------------------------------------------------
#
# LOCKED. Product labels for "how closely does this profile match the published
# requirements". They are not a probability of admission, a chance of receiving an
# award, or any other statement about an outcome, and they are never rendered as
# one. Bands are inclusive lower bounds.
#
#   90 - 100  Exceptional Fit
#   80 - 89.9  Very Strong Fit
#   70 - 79.9  Strong Fit
#   55 - 69.9  Possible Fit
#    0 - 54.9  Low Fit

FIT_BANDS: tuple[tuple[int, str, str], ...] = (
    (90, "EXCEPTIONAL_FIT", "Exceptional Fit"),
    (80, "VERY_STRONG_FIT", "Very Strong Fit"),
    (70, "STRONG_FIT", "Strong Fit"),
    (55, "POSSIBLE_FIT", "Possible Fit"),
    (0, "LOW_FIT", "Low Fit"),
)

#: The band keys, in descending order. Used by the counting system so tier counts
#: and the facet builder cannot drift from the band table.
FIT_BAND_KEYS: tuple[str, ...] = tuple(key for _, key, _ in FIT_BANDS)

#: A fit band at or above this threshold counts as a "strong or better" match.
STRONG_MATCH_THRESHOLD = 70


# ---------------------------------------------------------------------------
# Data coverage bands
# ---------------------------------------------------------------------------
#
# How much of the configured scoring model was actually evaluated for one record.
# Used only for counting and for the coverage label; it never affects fit.

COVERAGE_BANDS: tuple[tuple[float, str, str], ...] = (
    (80.0, "HIGH", "High"),
    (50.0, "MEDIUM", "Medium"),
    (0.0, "LOW", "Low"),
)

COVERAGE_BAND_KEYS: tuple[str, ...] = tuple(key for _, key, _ in COVERAGE_BANDS)


def classify_coverage(coverage: float) -> str:
    """Classify one record's data coverage into a configured band key.

    Lives beside ``COVERAGE_BANDS`` rather than in the counting module, because it
    is a resolver over this table and the counting engine needs to call it while it
    is still importing. Two consequences: the coverage classifier has exactly one
    definition, and the count contract can depend on it without importing the
    module that consumes it.
    """
    for threshold, key, _ in COVERAGE_BANDS:
        if coverage >= threshold:
            return key
    return COVERAGE_BANDS[-1][1]


# ---------------------------------------------------------------------------
# Academic Profile Index
# ---------------------------------------------------------------------------
#
# The index summarises only the academic evidence a student actually supplied,
# normalised within the grading scale the student declared. It is explicitly not
# a measure of worth, intelligence or admission likelihood, and the bands below
# are ScholarZone's own classification of supplied academic data.
#
#   Overall result 60% | Relevant subject 25% | Consistency/trend 15%
#
# Renormalised across whatever is present, so an absent component never
# contributes a zero.

API_COMPONENT_WEIGHTS: MappingProxyType[str, float] = MappingProxyType(
    {
        "overall_result": 0.60,
        "subject_performance": 0.25,
        "consistency": 0.15,
    }
)

API_BANDS: tuple[tuple[int, str, str], ...] = (
    (75, "HIGH", "High"),
    (50, "MEDIUM", "Medium"),
    (0, "LOW", "Low"),
)


# ---------------------------------------------------------------------------
# Application readiness weights
# ---------------------------------------------------------------------------
#
# LOCKED. Readiness answers a third question, distinct from fit and from
# confidence: "how ready is this student to act on this opportunity right now?"
#
#   Eligibility certainty      30%
#   Requirement completeness   20%
#   Language readiness         15%
#   Application/source readiness 15%
#   Deadline readiness         20%
#
# Renormalised across the readiness components that could be evaluated, exactly
# as the fit engine renormalises over its evaluated components.

READINESS_WEIGHTS: MappingProxyType[str, float] = MappingProxyType(
    {
        "eligibility_certainty": 0.30,
        "requirement_completeness": 0.20,
        "language_readiness": 0.15,
        "application_readiness": 0.15,
        "deadline_readiness": 0.20,
    }
)

READINESS_COMPONENT_ORDER: tuple[str, ...] = (
    "eligibility_certainty",
    "requirement_completeness",
    "language_readiness",
    "application_readiness",
    "deadline_readiness",
)

READINESS_COMPONENT_LABELS: MappingProxyType[str, str] = MappingProxyType(
    {
        "eligibility_certainty": "Eligibility certainty",
        "requirement_completeness": "Requirement completeness",
        "language_readiness": "Language readiness",
        "application_readiness": "Application and source readiness",
        "deadline_readiness": "Deadline readiness",
    }
)

#: Readiness is never an outcome prediction. The bands describe how much of the
#: application preparation the evidence covers.
READINESS_BANDS: tuple[tuple[float, str, str], ...] = (
    (85.0, "READY", "Ready to apply"),
    (70.0, "READY_WITH_CHECKS", "Ready with a few checks"),
    (50.0, "CHECKS_NEEDED", "Some checks needed"),
    (0.0, "NOT_READY", "Not ready yet"),
)

READINESS_BAND_KEYS: tuple[str, ...] = tuple(key for _, key, _ in READINESS_BANDS)


# ---------------------------------------------------------------------------
# Profile strength weights
# ---------------------------------------------------------------------------
#
# LOCKED. Profile strength describes the completeness of the student's own input.
# It is emphatically NOT fit and NOT confidence: two students with an identical
# profile strength can have completely different matches.
#
#   Academic 25% | Study goal 25% | Language 20% | Funding 20% | Identity 10%

PROFILE_STRENGTH_WEIGHTS: MappingProxyType[str, float] = MappingProxyType(
    {
        "academic": 0.25,
        "study_goal": 0.25,
        "language": 0.20,
        "funding": 0.20,
        "identity": 0.10,
    }
)

PROFILE_STRENGTH_COMPONENT_ORDER: tuple[str, ...] = (
    "academic",
    "study_goal",
    "language",
    "funding",
    "identity",
)

PROFILE_STRENGTH_LABELS: MappingProxyType[str, str] = MappingProxyType(
    {
        "academic": "Academic",
        "study_goal": "Study goal",
        "language": "Language",
        "funding": "Funding",
        "identity": "Identity",
    }
)

PROFILE_STRENGTH_BANDS: tuple[tuple[float, str, str], ...] = (
    (80.0, "STRONG", "Strong profile"),
    (55.0, "GOOD", "Good profile"),
    (0.0, "LIMITED", "Limited detail"),
)


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------
#
# LOCKED. Confidence answers a different question from fit: how much of the
# scholarship's published information was actually available and trustworthy
# enough to score. It is deliberately independent of the student profile: a
# student who supplies more information cannot raise the confidence of a record,
# and two students looking at the same record must see the same confidence.
#
#   Q_data 35% | Q_provenance 25% | Q_requirement 25% | Q_freshness 15%

CONFIDENCE_WEIGHTS: MappingProxyType[str, float] = MappingProxyType(
    {
        "data_completeness": 0.35,
        "provenance_quality": 0.25,
        "requirement_explicitness": 0.25,
        "verification_freshness": 0.15,
    }
)

CONFIDENCE_BANDS: tuple[tuple[float, str, str], ...] = (
    (85.0, "HIGH", "High"),
    (65.0, "MEDIUM", "Medium"),
    (0.0, "LOW", "Low"),
)

CONFIDENCE_BAND_KEYS: tuple[str, ...] = tuple(key for _, key, _ in CONFIDENCE_BANDS)

#: LOCKED verification-freshness model, as (maximum age in days, quality).
#: A record older than the final bound, or with no verification date at all,
#: scores 0 on this axis: a statement about our verification process, not about
#: the scholarship.
VERIFICATION_FRESHNESS_STEPS: tuple[tuple[int, float], ...] = (
    (90, 1.00),
    (180, 0.75),
    (365, 0.50),
    (730, 0.25),
)

#: Retained for callers that ask how fresh is "fresh". The scoring model above is
#: the banded table; these are the same first and last bounds named explicitly.
VERIFICATION_FRESH_DAYS = VERIFICATION_FRESHNESS_STEPS[0][0]
VERIFICATION_STALE_DAYS = VERIFICATION_FRESHNESS_STEPS[-1][0]


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------
#
# LOCKED. Reuses the existing deadline semantics; never invents a deadline. Bands
# are inclusive lower bounds in days remaining, and only a fixed, trustworthy
# date produces a number. A rolling or annual deadline is NOT_EVALUATED: "no
# fixed date" is not "too late".
#
#   60+ days -> 100 | 30-59 -> 90 | 14-29 -> 75 | 7-13 -> 55 | 1-6 -> 30

TIMING_BANDS: tuple[tuple[int, float, str], ...] = (
    (60, 100.0, "comfortable"),
    (30, 90.0, "approaching"),
    (14, 75.0, "workable"),
    (7, 55.0, "tight"),
    (1, 30.0, "urgent"),
)

#: Inclusive upper bound of days remaining for the final band. A deadline in the
#: past is a hard eligibility failure, not a timing score.
TIMING_FINAL_BAND_MAX_DAYS = 6

#: Counting buckets for the results summary. These are presentation buckets over
#: the same day counts the timing component already resolved; they never invent a
#: date and never affect a score.
TIMING_BUCKETS: tuple[tuple[int, str], ...] = (
    (60, "COMFORTABLE"),
    (14, "APPROACHING"),
    (1, "CLOSING_SOON"),
)

#: Deadline states that are not a day count.
TIMING_BUCKET_CLOSED = "CLOSED"
TIMING_BUCKET_UNKNOWN = "UNKNOWN"
TIMING_BUCKET_KEYS: tuple[str, ...] = (
    "COMFORTABLE",
    "APPROACHING",
    "CLOSING_SOON",
    TIMING_BUCKET_CLOSED,
    TIMING_BUCKET_UNKNOWN,
)


# ---------------------------------------------------------------------------
# Field / programme relationship levels
# ---------------------------------------------------------------------------

FIELD_RELATIONSHIP_EXACT = 100
FIELD_RELATIONSHIP_CLOSE = 85
FIELD_RELATIONSHIP_RELATED = 65
FIELD_RELATIONSHIP_BROAD = 40
FIELD_RELATIONSHIP_UNRELATED = 0

FIELD_RELATIONSHIP_LEVELS: MappingProxyType[str, float] = MappingProxyType(
    {
        "EXACT": FIELD_RELATIONSHIP_EXACT,
        "CLOSE_SPECIALIZATION": FIELD_RELATIONSHIP_CLOSE,
        "RELATED_FIELD": FIELD_RELATIONSHIP_RELATED,
        "BROAD_FIELD": FIELD_RELATIONSHIP_BROAD,
        "UNRELATED": FIELD_RELATIONSHIP_UNRELATED,
    }
)


# ---------------------------------------------------------------------------
# Academic fit curve
# ---------------------------------------------------------------------------
#
# LOCKED, two distinct cases.
#
# Both a minimum and a preferred benchmark published:
#
#     C = 100 x (student - minimum) / (preferred - minimum)     clamped 0-100
#
# This is the literal specification. Its consequence is stated plainly because
# it is visible in the product: a student sitting exactly on the published
# minimum scores 0 on this component, and a student at the preferred benchmark
# scores 100. That is the intended reading of the formula - when the awarding
# body published a benchmark, the distance to it is the evidence, and meeting a
# floor is not the same as reaching the stated standard. Eligibility is
# unaffected: such a student is ELIGIBLE, and the gate still says so.
#
# Only a minimum published: there is no second anchor and none is invented, so the
# student receives ACADEMIC_MINIMUM_ONLY_SCORE. There is no published evidence of
# anything better to award.

ACADEMIC_MINIMUM_ONLY_SCORE = 85.0

#: Reported as part of academic fit detail so a reader can see how much headroom
#: the score represents.
ACADEMIC_HEADROOM_DISPLAY_SCALE = 100.0


# ---------------------------------------------------------------------------
# Funding / budget
# ---------------------------------------------------------------------------
#
# Normalised funding states, ordered from most to least complete coverage.
FUNDING_STATE_FULL = "FULL"
FUNDING_STATE_TUITION_PLUS_LIVING = "TUITION_PLUS_LIVING"
FUNDING_STATE_TUITION_ONLY = "TUITION_ONLY"
FUNDING_STATE_PARTIAL = "PARTIAL"
FUNDING_STATE_NONE = "NONE"
FUNDING_STATE_UNKNOWN = "UNKNOWN"

FUNDING_STATES: tuple[str, ...] = (
    FUNDING_STATE_FULL,
    FUNDING_STATE_TUITION_PLUS_LIVING,
    FUNDING_STATE_TUITION_ONLY,
    FUNDING_STATE_PARTIAL,
    FUNDING_STATE_NONE,
    FUNDING_STATE_UNKNOWN,
)

#: The student-side need keys the compatibility matrix is indexed by.
FUNDING_NEED_FULL = "FULL_COVER_REQUIRED"
FUNDING_NEED_TUITION = "TUITION_REQUIRED"
FUNDING_NEED_PARTIAL = "PARTIAL_ACCEPTABLE"
FUNDING_NEED_NEUTRAL = "NO_SPECIFIC_NEED"

#: LOCKED funding compatibility matrix.
#:
#: Row = what the student needs. Column = the normalised, evidence-backed funding
#: state of the record. A cell is how completely that state satisfies the need.
#:
#: UNKNOWN is deliberately absent from every row. An unestablished funding state
#: is not a zero: the resolver returns None and the component becomes
#: NOT_EVALUATED, so an absent record field can never masquerade as a published
#: "no funding".
FUNDING_COMPATIBILITY: MappingProxyType[str, MappingProxyType[str, float]] = MappingProxyType(
    {
        # Student needs tuition and living costs covered.
        FUNDING_NEED_FULL: MappingProxyType(
            {
                FUNDING_STATE_FULL: 100.0,
                FUNDING_STATE_TUITION_PLUS_LIVING: 92.0,
                FUNDING_STATE_TUITION_ONLY: 55.0,
                FUNDING_STATE_PARTIAL: 30.0,
                FUNDING_STATE_NONE: 0.0,
            }
        ),
        # Student needs the tuition covered and can fund the rest.
        FUNDING_NEED_TUITION: MappingProxyType(
            {
                FUNDING_STATE_FULL: 100.0,
                FUNDING_STATE_TUITION_PLUS_LIVING: 100.0,
                FUNDING_STATE_TUITION_ONLY: 100.0,
                FUNDING_STATE_PARTIAL: 65.0,
                FUNDING_STATE_NONE: 0.0,
            }
        ),
        # Student can accept a partial award.
        FUNDING_NEED_PARTIAL: MappingProxyType(
            {
                FUNDING_STATE_FULL: 100.0,
                FUNDING_STATE_TUITION_PLUS_LIVING: 100.0,
                FUNDING_STATE_TUITION_ONLY: 100.0,
                FUNDING_STATE_PARTIAL: 100.0,
                FUNDING_STATE_NONE: 0.0,
            }
        ),
        # Student stated no funding requirement. A known award is mildly
        # positive and a published "no funding" is mildly negative, but nothing
        # is treated as a failure because no need was stated.
        FUNDING_NEED_NEUTRAL: MappingProxyType(
            {
                FUNDING_STATE_FULL: 100.0,
                FUNDING_STATE_TUITION_PLUS_LIVING: 95.0,
                FUNDING_STATE_TUITION_ONLY: 85.0,
                FUNDING_STATE_PARTIAL: 65.0,
                FUNDING_STATE_NONE: 15.0,
            }
        ),
    }
)


def funding_score(need: str, state: str) -> float | None:
    """Resolve the funding compatibility matrix.

    Returns ``None`` when the matrix has no cell for the pair, which the caller
    turns into NOT_EVALUATED. Never substitutes a zero.
    """
    row = FUNDING_COMPATIBILITY.get(need)
    if row is None:
        return None
    return row.get(state)


# ---------------------------------------------------------------------------
# Language
# ---------------------------------------------------------------------------

#: No official cross-test equivalency is used anywhere in this engine. A student
#: holding TOEFL cannot be scored against an IELTS threshold, and vice versa; the
#: result is NOT_EVALUATED rather than a fabricated conversion.
LANGUAGE_CROSS_TEST_EQUIVALENCY_SUPPORTED = False

#: LOCKED bounded surplus model, used only when the student holds the SAME test
#: the record publishes a minimum for:
#:
#:     surplus_ratio    = (student_score - minimum_score) / surplus_range
#:     component_score  = 100 x clamp(surplus_ratio, 0, 1)
#:
#: ``surplus_range`` is the headroom above the published minimum at which the
#: component earns full credit. It is a documented configuration value per test,
#: because the scales are not interchangeable: two IELTS points and two TOEFL
#: points are not the same distance.
#:
#: A test with no configured range yields None from ``language_surplus_score``, and
#: the language component becomes NOT_EVALUATED. That is deliberate: without a
#: documented range there is no honest way to score the surplus, and inventing one
#: would be the same error as inventing a cross-test conversion.
LANGUAGE_SURPLUS_RANGES: MappingProxyType[str, float] = MappingProxyType(
    {
        "ielts": 2.0,
        "toefl": 15.0,
        "toefl_ibt": 15.0,
        "toefl_itp": 15.0,
        "pte": 10.0,
        "pte_academic": 10.0,
        "duolingo": 20.0,
        "duolingo_english_test": 20.0,
        "cefr": 1.0,
        "topik": 10.0,
        "jlpt": 2.0,
        "hsk": 6.0,
        "testdaf": 20.0,
        "telc": 20.0,
        "dele": 10.0,
        "goethe": 20.0,
        "dalf": 20.0,
        "tcf": 20.0,
    }
)

#: How a language component scores when the student holds the published test but
#: scores below its minimum. This is a real evaluated zero: the published gate
#: fails, and the component says so.
LANGUAGE_BELOW_MINIMUM_SCORE = 0.0


def language_surplus_range(test: str | None) -> float | None:
    """The configured surplus range for a canonical test name, or ``None``."""
    if not test:
        return None
    return LANGUAGE_SURPLUS_RANGES.get(test)


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Clamp into a closed interval. Used by every bounded model in the engine."""
    if value < low:
        return low
    if value > high:
        return high
    return value


# ---------------------------------------------------------------------------
# Preference
# ---------------------------------------------------------------------------
#
# Preferences never override eligibility and are never penalised for being
# absent. A student who supplies no preference is NOT_EVALUATED on preference and
# loses nothing.
#
# The table is deliberately small and complete: a country preference is either
# met, or stated and not met. A stated non-match scores below a match but above
# zero, because "you did not ask for this country" is weaker evidence against a
# fit than "this cannot pay for your degree".

PREFERENCE_MATCH = "MATCH"
PREFERENCE_NO_MATCH = "NO_MATCH"

PREFERENCE_COMPATIBILITY: MappingProxyType[str, float] = MappingProxyType(
    {
        PREFERENCE_MATCH: 100.0,
        PREFERENCE_NO_MATCH: 50.0,
    }
)


def preference_score(relationship: str) -> float | None:
    """Resolve the preference compatibility matrix."""
    return PREFERENCE_COMPATIBILITY.get(relationship)


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------
#
# Eligibility is the primary key and is not negotiable: an INELIGIBLE record can
# never sort above an ELIGIBLE one, regardless of fit. The final tiebreak is the
# record id, which makes the order total and therefore reproducible.

ELIGIBILITY_RANK: MappingProxyType[str, int] = MappingProxyType(
    {
        "ELIGIBLE": 0,
        "NEEDS_VERIFICATION": 1,
        "INELIGIBLE": 2,
    }
)

#: Sort keys offered to the interface. ``RECOMMENDED`` is the deterministic
#: ranking order and nothing else; there is no model-ranked list anywhere.
SORT_OPTIONS: tuple[str, ...] = (
    "RECOMMENDED",
    "DEADLINE_SOONEST",
    "HIGHEST_CONFIDENCE",
    "HIGHEST_FUNDING_ALIGNMENT",
)


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------

#: Scores are stored at full precision and rounded only here, at the edge, so the
#: interface never shows a value the arithmetic did not produce.
DISPLAY_PRECISION = 1

#: Tolerance used by the invariant tests when they assert that the component
#: contributions sum to the final score. Contributions are computed from the
#: unrounded values; the tolerance covers only display rounding.
SUM_TOLERANCE = 0.05


# ---------------------------------------------------------------------------
# Request bounds
# ---------------------------------------------------------------------------

#: Hard cap on returned results. Scoring the whole catalogue is cheap; shipping
#: ten thousand rows to a browser is not, and the frontend pages client-side.
MATCH_RESULT_LIMIT_DEFAULT = 60
MATCH_RESULT_LIMIT_MAX = 200

#: Upper bound on candidates pulled from the database in one query. The engine
#: is linear in this number and each candidate is scored in memory.
MATCH_CANDIDATE_HARD_LIMIT = 20_000

#: Bounds on the optional natural-language input, so the parser cannot be handed
#: an unbounded document.
NATURAL_LANGUAGE_MAX_LENGTH = 600
NATURAL_LANGUAGE_MAX_TOKENS = 80

#: Hard cap on how many countries a single profile may name.
#:
#: This is set to the size of the largest curated region rather than to a rounder
#: number, because the natural-language parser expands a named region into its
#: members and its output has to satisfy this very bound. Europe is 32 countries,
#: so a cap of 25 made the parser emit a payload the engine rejected - the
#: product's own documented example failed its own validation.
MAX_PREFERRED_COUNTRIES = 32


# ---------------------------------------------------------------------------
# Self-check
# ---------------------------------------------------------------------------


def _validate_weight_table(name: str, table: MappingProxyType[str, float]) -> None:
    total = round(sum(table.values()), 10)
    if total != 1.0:
        raise RuntimeError(f"{name} must total 1.0, got {total}")


def validate_config() -> None:
    """Fail at import time if any configuration table is malformed.

    A weight table that does not total 1.0 silently rescales every score in the
    product, and the failure surfaces as "the numbers changed" rather than as an
    error. Importing the package is the cheapest place to catch it. A malformed
    table raises; it is never silently rescaled.
    """
    _validate_weight_table("FIT_WEIGHTS", FIT_WEIGHTS)
    _validate_weight_table("CONFIDENCE_WEIGHTS", CONFIDENCE_WEIGHTS)
    _validate_weight_table("API_COMPONENT_WEIGHTS", API_COMPONENT_WEIGHTS)
    _validate_weight_table("READINESS_WEIGHTS", READINESS_WEIGHTS)
    _validate_weight_table("PROFILE_STRENGTH_WEIGHTS", PROFILE_STRENGTH_WEIGHTS)

    # A presentation order must name exactly the components its weight table
    # defines, in both directions. A name with no weight would divide by nothing;
    # a weight with no name would silently vanish from the breakdown.
    for order_name, order, weight_name, weights in (
        ("FIT_COMPONENT_ORDER", FIT_COMPONENT_ORDER, "FIT_WEIGHTS", FIT_WEIGHTS),
        (
            "READINESS_COMPONENT_ORDER",
            READINESS_COMPONENT_ORDER,
            "READINESS_WEIGHTS",
            READINESS_WEIGHTS,
        ),
        (
            "PROFILE_STRENGTH_COMPONENT_ORDER",
            PROFILE_STRENGTH_COMPONENT_ORDER,
            "PROFILE_STRENGTH_WEIGHTS",
            PROFILE_STRENGTH_WEIGHTS,
        ),
    ):
        unnamed = set(order) - set(weights)
        if unnamed:
            raise RuntimeError(f"{order_name} names components missing from {weight_name}: {sorted(unnamed)}")
        unsurfaced = set(weights) - set(order)
        if unsurfaced:
            raise RuntimeError(f"{weight_name} contains components missing from {order_name}: {sorted(unsurfaced)}")
        if len(set(order)) != len(order):
            raise RuntimeError(f"{order_name} repeats a component")

    for key, row in FUNDING_COMPATIBILITY.items():
        if FUNDING_STATE_UNKNOWN in row:
            raise RuntimeError(f"FUNDING_COMPATIBILITY[{key}] must not score UNKNOWN")

    for test, value in LANGUAGE_SURPLUS_RANGES.items():
        if value <= 0:
            raise RuntimeError(f"LANGUAGE_SURPLUS_RANGES[{test}] must be positive, got {value}")


validate_config()


# ---------------------------------------------------------------------------
# Presentation snapshot
# ---------------------------------------------------------------------------


def config_snapshot() -> dict:
    """The exact configuration a response was produced with.

    Reported under ``explanation`` so a stored result can be reproduced from the
    response alone, without access to the repository.
    """
    return {
        "scoring_config_version": SCORING_CONFIG_VERSION,
        "weights": dict(FIT_WEIGHTS),
        "fit_bands": [
            {"key": key, "min_score": float(threshold), "label": label}
            for threshold, key, label in FIT_BANDS
        ],
        "confidence_weights": dict(CONFIDENCE_WEIGHTS),
        "confidence_bands": [
            {"key": key, "min_score": float(threshold), "label": label}
            for threshold, key, label in CONFIDENCE_BANDS
        ],
        "readiness_weights": dict(READINESS_WEIGHTS),
        "readiness_bands": [
            {"key": key, "min_score": float(threshold), "label": label}
            for threshold, key, label in READINESS_BANDS
        ],
        "profile_strength_weights": dict(PROFILE_STRENGTH_WEIGHTS),
        "field_relationship_levels": dict(FIELD_RELATIONSHIP_LEVELS),
        "funding_compatibility": {
            need: dict(row) for need, row in FUNDING_COMPATIBILITY.items()
        },
        "language_surplus_ranges": dict(LANGUAGE_SURPLUS_RANGES),
        "language_cross_test_equivalency_supported": LANGUAGE_CROSS_TEST_EQUIVALENCY_SUPPORTED,
        "preference_compatibility": dict(PREFERENCE_COMPATIBILITY),
        "academic_minimum_only_score": ACADEMIC_MINIMUM_ONLY_SCORE,
        "verification_freshness_steps": [
            {"max_age_days": bound, "quality": quality}
            for bound, quality in VERIFICATION_FRESHNESS_STEPS
        ],
    }


__all__ = [
    "API_BANDS",
    "API_COMPONENT_WEIGHTS",
    "CONFIDENCE_BANDS",
    "CONFIDENCE_BAND_KEYS",
    "CONFIDENCE_WEIGHTS",
    "COVERAGE_BAND_KEYS",
    "COVERAGE_BANDS",
    "DEADLINE_SEMANTICS_VERSION",
    "DISPLAY_PRECISION",
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
    "LANGUAGE_BELOW_MINIMUM_SCORE",
    "LANGUAGE_CROSS_TEST_EQUIVALENCY_SUPPORTED",
    "LANGUAGE_SURPLUS_RANGES",
    "MATCH_CANDIDATE_HARD_LIMIT",
    "MATCH_RESULT_LIMIT_DEFAULT",
    "MATCH_RESULT_LIMIT_MAX",
    "MAX_PREFERRED_COUNTRIES",
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
    "classify_coverage",
    "config_snapshot",
    "funding_score",
    "language_surplus_range",
    "preference_score",
    "validate_config",
]