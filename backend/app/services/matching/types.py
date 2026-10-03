"""Typed contracts for ScholarZone Match.

Everything the engine returns is one of these types. That is what keeps the
router free of scoring logic and what makes the response auditable: a result
carries the engine version, the component weights that produced it, the reason
codes behind each claim, and the provenance of every published fact it used.

Two distinct vocabularies are used and must not be conflated:

``component_status``
    Whether a *scoring dimension* could be evaluated. ``EVALUATED`` or
    ``NOT_EVALUATED``. An unevaluated component is excluded from the weighted
    average; it is never a zero.

``requirement_status``
    The state of one published requirement: ``MATCH``, ``PARTIAL``, ``FAIL`` or
    ``UNKNOWN``. This is the vocabulary the eligibility gate reasons in.

Keeping them separate is what makes "UNKNOWN is not zero" enforceable rather
than aspirational.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .config import MAX_PREFERRED_COUNTRIES


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class EligibilityStatus(StrEnum):
    """The hard gate's verdict. Evaluated before any fit scoring."""

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"


class ComponentStatus(StrEnum):
    """Whether a scoring dimension produced a usable number."""

    EVALUATED = "EVALUATED"
    NOT_EVALUATED = "NOT_EVALUATED"


class RequirementStatus(StrEnum):
    """The state of one published requirement."""

    MATCH = "MATCH"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class RequirementKind(StrEnum):
    """Which published requirement is being evaluated.

    Only requirements in this vocabulary may be evaluated. Anything a provider
    published that is not listed here stays UNKNOWN with its text preserved,
    because inferring an evaluation from arbitrary prose is how a catalogue
    starts telling applicants things the awarding body never said.
    """

    NATIONALITY = "NATIONALITY"
    AGE = "AGE"
    DEGREE_LEVEL = "DEGREE_LEVEL"
    ACADEMIC_MINIMUM = "ACADEMIC_MINIMUM"
    LANGUAGE_MINIMUM = "LANGUAGE_MINIMUM"
    PROGRAMME_RESTRICTION = "PROGRAMME_RESTRICTION"
    STUDY_MODE = "STUDY_MODE"
    APPLICATION_WINDOW = "APPLICATION_WINDOW"


class DegreeLevel(StrEnum):
    BACHELOR = "BACHELOR"
    MASTER = "MASTER"
    DOCTORAL = "DOCTORAL"
    POSTDOCTORAL = "POSTDOCTORAL"
    OTHER = "OTHER"


class StudyMode(StrEnum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    OTHER = "OTHER"


class GradingScale(StrEnum):
    """Grading systems a student may declare.

    Each scale is normalised only against itself. There is no cross-scale
    conversion table in this engine, and adding one would be the single largest
    available way to make the product dishonest.
    """

    PERCENTAGE = "PERCENTAGE"
    GPA_4 = "GPA_4"
    GPA_5 = "GPA_5"
    GPA_10 = "GPA_10"
    LETTER = "LETTER"
    UNKNOWN = "UNKNOWN"


class FundingRequirement(StrEnum):
    """What the student needs from a scholarship, in their own terms."""

    FULL_FUNDING = "FULL_FUNDING"
    TUITION_ONLY_SUFFICIENT = "TUITION_ONLY_SUFFICIENT"
    PARTIAL_OK = "PARTIAL_OK"
    NO_SPECIFIC_NEED = "NO_SPECIFIC_NEED"


class FundingState(StrEnum):
    """Normalised, evidence-backed funding coverage of one scholarship."""

    FULL = "FULL"
    TUITION_PLUS_LIVING = "TUITION_PLUS_LIVING"
    TUITION_ONLY = "TUITION_ONLY"
    PARTIAL = "PARTIAL"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class ProfileBand(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# ---------------------------------------------------------------------------
# Profile request
# ---------------------------------------------------------------------------


class AcademicMark(BaseModel):
    """One supplied academic result, already on a declared scale."""

    model_config = ConfigDict(extra="forbid")

    scale: GradingScale = GradingScale.UNKNOWN
    value: float | None = Field(default=None, ge=0, le=1000)
    letter: str | None = Field(default=None, max_length=8)
    #: Canonical field this mark relates to, from the programme taxonomy.
    field: str | None = Field(default=None, max_length=120)
    #: Optional second mark used to describe improvement, e.g. a later result.
    previous_value: float | None = Field(default=None, ge=0, le=1000)
    previous_scale: GradingScale | None = None


class LanguageCredential(BaseModel):
    """A language test the student actually holds."""

    model_config = ConfigDict(extra="forbid")

    test: str = Field(min_length=1, max_length=64)
    score: float | None = Field(default=None, ge=0, le=200)
    #: Set when a proficiency level rather than a numeric score was supplied.
    level: str | None = Field(default=None, max_length=16)


class MatchProfileRequest(BaseModel):
    """The student-supplied profile.

    There is no authentication requirement and nothing here is persisted. Every
    field is optional because a student who knows their nationality and target
    degree should not be forced to invent a GPA to see their matches; the engine
    reports what it could not evaluate instead of guessing.
    """

    model_config = ConfigDict(extra="forbid")

    # Identity
    age: int | None = Field(default=None, ge=13, le=100)
    citizenship: str | None = Field(default=None, max_length=80)
    country_of_residence: str | None = Field(default=None, max_length=80)

    # Academics
    highest_qualification: str | None = Field(default=None, max_length=120)
    graduation_year: int | None = Field(default=None, ge=1950, le=2100)
    overall_result: AcademicMark | None = None
    subject_results: list[AcademicMark] = Field(default_factory=list, max_length=12)

    # Target
    intended_degree_level: DegreeLevel | None = None
    intended_field: str | None = Field(default=None, max_length=120)
    study_mode: StudyMode | None = None
    # Bounded by MAX_PREFERRED_COUNTRIES so the largest curated region the
    # natural-language parser can expand still fits.
    preferred_countries: list[str] = Field(
        default_factory=list, max_length=MAX_PREFERRED_COUNTRIES
    )

    # Language
    language_credentials: list[LanguageCredential] = Field(default_factory=list, max_length=8)

    # Financial
    max_self_contribution: float | None = Field(default=None, ge=0, le=10_000_000)
    funding_requirement: FundingRequirement | None = None
    living_cost_support_required: bool | None = None

    # Timing
    intended_intake_year: int | None = Field(default=None, ge=2000, le=2100)

    # Request-scoped options
    country_filter: str | None = Field(default=None, max_length=120)
    limit: int = Field(default=60, ge=1, le=200)
    include_ineligible: bool = True


# ---------------------------------------------------------------------------
# Internal normalised facts
# ---------------------------------------------------------------------------


class NormalisedRequirement(BaseModel):
    """One published requirement the reader was able to extract.

    ``raw_quote`` is the provider's own wording, preserved verbatim, and
    ``provenance_url`` is the official page it was read from. A reader that
    cannot produce both is not allowed to produce a requirement at all: that is
    the rule that separates "the provider published this" from "we inferred
    this".
    """

    model_config = ConfigDict(frozen=True)

    kind: RequirementKind
    raw_quote: str
    provenance_url: str | None = None
    #: Numeric minimum on the scale named by ``scale``.
    minimum_value: float | None = None
    scale: GradingScale | None = None
    #: Preferred/typical benchmark, when the provider published one. Never
    #: inferred.
    preferred_value: float | None = None
    #: Canonical terms constraining the requirement, e.g. ("NATIONALITY",).
    allowed_terms: tuple[str, ...] = ()
    #: Maximum/minimum age where the provider stated a bound.
    age_min: int | None = None
    age_max: int | None = None
    test_name: str | None = None
    raw_precision: str | None = None


class ScholarshipFacts(BaseModel):
    """The subset of a scholarship record the engine is allowed to read.

    Loaded by one bounded query and passed to the pure engine. Keeping the
    surface explicit is what guarantees the engine cannot accidentally reach a
    field that has not been through the verification pipeline, and it keeps the
    scoring path independent of the ORM.
    """

    model_config = ConfigDict(frozen=True)

    id: int
    title: str
    country: str
    degree_levels: str
    funding_label: str | None = None
    program_type: str | None = None

    status: str | None = None
    deadline_date: str | None = None
    deadline_display: str | None = None
    deadline_precision: str | None = None

    eligibility: list[str] = Field(default_factory=list)
    eligibility_summary: str | None = None
    requirements: list[str] = Field(default_factory=list)
    documents: list[str] = Field(default_factory=list)
    coverage: list[str] = Field(default_factory=list)
    english_requirement: str | None = None
    best_fit: str | None = None

    funding_amount: float | None = None
    funding_currency: str | None = None
    funding_period: str | None = None
    tuition_coverage: bool | None = None
    living_cost_coverage: bool | None = None
    travel_coverage: bool | None = None
    fully_funded: bool | None = None

    official_source: str | None = None
    official_source_url: str | None = None
    official_details: dict | None = None

    is_verified: bool | None = None
    verification_status: str | None = None
    last_verified_date: str | None = None
    next_verification_due: str | None = None
    programme_verification: dict | None = None

    image_url: str | None = None
    image_alt_text: str | None = None


# ---------------------------------------------------------------------------
# Response pieces
# ---------------------------------------------------------------------------


class Reason(BaseModel):
    """One deterministic, human-readable explanation.

    ``code`` is stable and machine-readable; ``message`` is rendered from a
    template in explain.py. No explanation text is generated by a language
    model, so the same inputs always produce the same sentences.
    """

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    component: str | None = None


class RequirementOutcome(BaseModel):
    """The evaluated state of one published requirement."""

    model_config = ConfigDict(frozen=True)

    kind: RequirementKind
    status: RequirementStatus
    summary: str
    raw_quote: str
    provenance_url: str | None = None


class ComponentScore(BaseModel):
    """One scoring dimension.

    When ``status`` is ``NOT_EVALUATED`` the score is ``None`` and the weight is
    excluded from the denominator. ``score`` is never 0 as a stand-in for
    "unknown"; a genuine zero is always ``EVALUATED`` with ``score == 0``.

    ``effective_weight`` and ``contribution`` are what the arithmetic actually
    applied, after the unevaluated components were excluded. They differ from
    ``weight`` whenever anything was excluded, which is exactly why they exist:
    reporting "Academic is 25%" next to "Academic scored 96" would imply 24
    points that the average never contained.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    label: str
    weight: float
    status: ComponentStatus
    score: float | None = None
    #: Why this dimension was or could not be evaluated.
    detail: str
    #: Machine-readable trace for the calculation, exposed under
    #: "How this is calculated".
    evidence: dict | None = None
    #: The share of the average this dimension actually carried.
    effective_weight: float | None = None
    #: effective_weight x score. Contributions sum to the fit score.
    contribution: float | None = None


class SensitivityRange(BaseModel):
    """The arithmetic bracket implied by the unevaluated components.

    Always presented with ``caveat``. It is not a prediction, it is not used for
    ranking, and it says nothing about which outcome is more likely.
    """

    model_config = ConfigDict(frozen=True)

    lower_bound: float
    upper_bound: float
    unevaluated_weight: float
    unevaluated_components: list[str] = Field(default_factory=list)
    caveat: str


class ReadinessComponent(BaseModel):
    """One application-readiness dimension."""

    model_config = ConfigDict(frozen=True)

    name: str
    label: str
    weight: float
    status: ComponentStatus
    score: float | None = None
    detail: str
    effective_weight: float | None = None
    contribution: float | None = None


class ReadinessResult(BaseModel):
    """How ready this student is to act on this opportunity right now.

    Not fit. Not confidence. Not an admission probability. It answers a third,
    separate question, and it is reported as its own layer so it can never be
    mistaken for a score about the student's chances.
    """

    model_config = ConfigDict(frozen=True)

    #: ``None`` when no readiness dimension could be evaluated. Never 0.
    score: float | None = None
    band: str | None = None
    label: str | None = None
    components: list[ReadinessComponent] = Field(default_factory=list)
    evaluated_coverage: float = 0.0
    detail: str = ""


class ProfileStrengthResult(BaseModel):
    """How complete the student's own input is.

    Explicitly NOT fit and NOT confidence. Two students with an identical
    profile strength can have completely different matches, and a strong
    profile does not make any particular scholarship a better match.
    """

    model_config = ConfigDict(frozen=True)

    score: float | None = None
    band: str | None = None
    label: str | None = None
    components: list[ReadinessComponent] = Field(default_factory=list)
    complete: list[str] = Field(default_factory=list)
    #: Concrete, non-punitive suggestions for improving matching quality.
    improvements: list[Reason] = Field(default_factory=list)
    detail: str = ""


class MatchSummary(BaseModel):
    """Real, deterministic counts over one result set.

    Every number here is computed from the same candidate set that produced
    ``results``. Nothing is hardcoded, estimated, or carried over from a previous
    calculation, and the reconciliation invariants asserted by the test suite are
    what make the dashboard trustworthy.
    """

    model_config = ConfigDict(frozen=True)

    total_candidates: int
    visible_candidate_count: int
    eligible_count: int
    needs_verification_count: int
    ineligible_count: int
    scored_count: int
    not_scored_count: int

    strong_or_better_count: int

    exceptional_count: int = 0
    very_strong_count: int = 0
    strong_count: int = 0
    possible_count: int = 0
    low_count: int = 0
    #: Fit bands that could not be classified, because nothing was evaluated or
    #: the record failed the gate. Reported so tier counts always reconcile.
    unclassified_fit_count: int = 0

    high_confidence_count: int = 0
    medium_confidence_count: int = 0
    low_confidence_count: int = 0

    high_coverage_count: int = 0
    medium_coverage_count: int = 0
    low_coverage_count: int = 0

    comfortable_deadline_count: int = 0
    approaching_deadline_count: int = 0
    closing_soon_count: int = 0
    closed_deadline_count: int = 0
    unknown_deadline_count: int = 0

    full_funding_count: int = 0
    tuition_plus_living_count: int = 0
    tuition_only_count: int = 0
    partial_funding_count: int = 0
    none_count: int = 0
    unknown_funding_count: int = 0

    average_confidence: float | None = None
    average_data_coverage: float | None = None
    truncated: bool = False


class FacetBucket(BaseModel):
    """One value in a facet, with a live count from the current result set."""

    model_config = ConfigDict(frozen=True)

    value: str
    label: str
    count: int


class MatchFacets(BaseModel):
    """Facet values and their counts.

    Built from the same ranked result set the cards are rendered from, so a
    filter's count is never stale relative to the list it filters. Values are
    never truncated: a country that appears in the catalogue is always
    selectable.

    Facet counts deliberately describe the *returned page* rather than the whole
    analysed universe, so the number beside a filter value is the number of cards
    one click away. ``count_basis`` records that basis explicitly so the interface
    can label the counts honestly when a response was truncated.
    """

    model_config = ConfigDict(frozen=True)

    #: ``"RETURNED_PAGE"``. Named rather than implied, because a facet count and a
    #: summary count that describe different sets would otherwise look like a bug.
    count_basis: str = "RETURNED_PAGE"

    countries: list[FacetBucket] = Field(default_factory=list)
    #: Canonical programme fields. Partial rather than a complete partition: a
    #: record whose programme the taxonomy cannot resolve is absent from the
    #: facet instead of being filed under an invented subject.
    fields: list[FacetBucket] = Field(default_factory=list)
    funding_states: list[FacetBucket] = Field(default_factory=list)
    degree_levels: list[FacetBucket] = Field(default_factory=list)
    eligibility_states: list[FacetBucket] = Field(default_factory=list)
    fit_bands: list[FacetBucket] = Field(default_factory=list)
    confidence_bands: list[FacetBucket] = Field(default_factory=list)
    deadline_buckets: list[FacetBucket] = Field(default_factory=list)


class EligibilityResult(BaseModel):
    """The hard gate's verdict, with the reasons that produced it."""

    model_config = ConfigDict(frozen=True)

    status: EligibilityStatus
    #: Confirmed violations. Non-empty means INELIGIBLE.
    blockers: list[RequirementOutcome] = Field(default_factory=list)
    #: Mandatory conditions that could not be evaluated. Non-empty with no
    #: blockers means NEEDS_VERIFICATION.
    unverified: list[RequirementOutcome] = Field(default_factory=list)
    #: Mandatory conditions that were evaluated and satisfied.
    satisfied: list[RequirementOutcome] = Field(default_factory=list)
    detail: str = ""
    #: The fixed order the conditions were checked in, so a reader can see the
    #: sequence rather than infer it.
    gate_order: list[str] = Field(default_factory=list)


class ActionItem(BaseModel):
    """One grounded next step.

    Every action is derived from something the record or the profile actually
    contains. An action is never invented from prose, and a document is never
    named unless the record names it.
    """

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    #: ``official_source`` actions carry the URL that was actually published.
    url: str | None = None
    url_label: str | None = None
    #: Ordering bucket, so "visit the official source" can come last.
    priority: int = 50


class GapCategory(StrEnum):
    """Why a piece of information is missing.

    Separating these four is what stops missing data being written up as a
    failure. An ``UNVERIFIED`` condition is a published rule nobody has checked
    yet; a ``MISSING_SCHOLARSHIP_DATA`` item is a gap in our catalogue and no
    action by the student can change it.
    """

    KNOWN_GAP = "KNOWN_GAP"
    UNVERIFIED = "UNVERIFIED"
    MISSING_USER_INFORMATION = "MISSING_USER_INFORMATION"
    MISSING_SCHOLARSHIP_DATA = "MISSING_SCHOLARSHIP_DATA"


class Gap(BaseModel):
    """One actionable gap, with the reason it could not be resolved.

    Missing data is never phrased as a failure. "Language requirement not
    evaluated" is a statement about measurement; "you are not eligible" is a
    statement about the student, and only the gate is allowed to make that one.
    """

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    category: GapCategory
    component: str | None = None


class MatchResult(BaseModel):
    """One scored scholarship."""

    model_config = ConfigDict(frozen=True)

    scholarship_id: int
    scholarship_name: str
    institution: str | None = None
    country: str
    degree_levels: str
    image_url: str | None = None
    image_alt_text: str | None = None
    detail_url: str = ""
    official_source_url: str | None = None

    eligibility: EligibilityStatus
    eligibility_detail: EligibilityResult

    #: ``None`` when no dimension could be evaluated at all, or when the hard gate
    #: ruled the record INELIGIBLE. Both are absences, not zeros: an ineligible
    #: scholarship never carries a fit classification, because a high score there
    #: would read as a recommendation the gate already refused. The raw
    #: arithmetic behind an ineligible result stays internal to the engine and is
    #: never part of this public contract.
    fit_score: float | None
    #: Always one of the configured fit band keys, ``INELIGIBLE`` or
    #: ``NOT_EVALUATED``. Never a composed string, so band and facet lookups
    #: cannot miss.
    fit_label: str
    fit_label_display: str
    confidence_score: float
    confidence_label: str
    data_coverage: float

    #: The canonical programme field this scholarship publishes, resolved from the
    #: controlled taxonomy, and its display label. ``None`` when the record does
    #: not publish a field the taxonomy can resolve, which is an honest absence
    #: rather than an invented subject.
    field: str | None = None
    field_label: str | None = None

    #: How much of the configured scoring model was evaluated, and how many
    #: dimensions that was.
    evaluated_components: int = 0
    total_components: int = 0

    confidence_coverage_band: str | None = None
    confidence_label_display: str | None = None

    readiness: ReadinessResult | None = None
    sensitivity: SensitivityRange | None = None

    score_breakdown: list[ComponentScore]
    requirements: list[RequirementOutcome]
    reasons: list[Reason]
    gaps: list[Gap] = Field(default_factory=list)
    blockers: list[Reason]
    #: Ordered next steps. Grounded in the record, never invented.
    actions: list[ActionItem] = Field(default_factory=list)

    #: What was known about this record, so a reader can judge the score.
    evidence_status: EvidenceStatus

    #: ``None`` when no published deadline exists. Not zero.
    days_to_deadline: int | None = None
    deadline_precision: str | None = None
    timing_bucket: str | None = None
    funding_state: FundingState
    #: The normalised, evidence-backed funding state as a facet value.
    funding_alignment_score: float | None = None
    field_alignment_level: str | None = None


class EvidenceStatus(BaseModel):
    """How much of this record was actually available and verifiable."""

    model_config = ConfigDict(frozen=True)

    has_official_source: bool
    is_verified: bool
    verification_status: str | None = None
    last_verified_date: str | None = None
    coverage_ratio: float
    provenance_ratio: float
    explicitness_ratio: float
    freshness_ratio: float


class ProfileIndexResult(BaseModel):
    """The ScholarZone Academic Profile Index.

    This describes the academic evidence the student supplied. It is not a
    measure of ability and not an admission prediction.
    """

    model_config = ConfigDict(frozen=True)

    score: float | None
    band: ProfileBand | None
    band_display: str | None
    #: Per-component contributions actually used, with their renormalised
    #: weights, so the number is reproducible by hand.
    components: list[ComponentScore]
    evaluated_coverage: float


class MatchExplanation(BaseModel):
    """The reproducible account of how the numbers were produced."""

    model_config = ConfigDict(frozen=True)

    engine_version: str
    scoring_config_version: str
    field_taxonomy_version: str
    requirement_reader_version: str
    deadline_semantics_version: str
    as_of: str
    weights: dict[str, float]
    formula: str
    coverage_formula: str
    contribution_formula: str
    sensitivity_formula: str
    sensitivity_caveat: str
    evaluated_components: list[str]
    unevaluated_components: list[str]
    normalisation_note: str
    confidence_formula: str
    readiness_formula: str
    profile_index_formula: str
    #: The exact configuration snapshot the response was produced with, so a
    #: stored result can be reproduced without the repository.
    scoring_config: dict = Field(default_factory=dict)
    #: The one sentence a reader needs about what an unevaluated dimension does.
    missing_data_note: str = ""


class MatchResponse(BaseModel):
    """The full response body."""

    engine_version: str
    scoring_config_version: str
    taxonomy_version: str
    as_of: str
    explanation: MatchExplanation

    profile_index: ProfileIndexResult
    #: Completeness of the student's own input. Not fit, not confidence.
    profile_strength: ProfileStrengthResult

    total_candidates: int
    #: Retained at the top level for continuity with the first release. The
    #: authoritative counts live in ``summary`` and are computed from the same
    #: result set.
    eligible_count: int
    needs_verification_count: int
    ineligible_count: int
    strong_match_count: int
    average_confidence: float | None

    summary: MatchSummary
    facets: MatchFacets

    results: list[MatchResult]
    truncated: bool = False


# ---------------------------------------------------------------------------
# Internal result type used between engine and explain
# ---------------------------------------------------------------------------

ScoreKind = Literal["component", "requirement"]