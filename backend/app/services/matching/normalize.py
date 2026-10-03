"""Normalisation of a student profile into comparable facts.

Two rules govern everything in this module.

**Rule 1 - normalise within a scale, never across scales.**
A 3.6 on a 4.0 scale and an 85% are two readings of the same kind of thing, so
each is rescaled onto 0-100 using its own declared denominator. Converting 3.6
on a 5.0 scale into "the equivalent of 2.88 on a 4.0 scale" is a different
operation: it is a claim about how one institution's grading maps onto
another's, and no such authoritative rule exists. That case returns UNKNOWN.

**Rule 2 - absence is absence.**
Every function returns ``None`` for input it cannot interpret. Nothing here
substitutes a default, a guess or a zero. The distinction between "the student
has no GPA" and "the student has a GPA of zero" is the difference between an
honest profile index and a misleading one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .constants import API_COMPONENT_WEIGHTS
from .types import AcademicMark, GradingScale, LanguageCredential, MatchProfileRequest


#: Declared denominators per numeric scale. Rescaling a mark means dividing by
#: the scale's own maximum. No value here implies any equivalence between two
#: different scales.
SCALE_MAXIMA: dict[GradingScale, float] = {
    GradingScale.PERCENTAGE: 100.0,
    GradingScale.GPA_4: 4.0,
    GradingScale.GPA_5: 5.0,
    GradingScale.GPA_10: 10.0,
}

#: Letter-grade to percentage bands, expressed as the lower bound of each band.
#: This is a *within-scale* interpretation of a letter the student was given, not
#: a conversion into any institutional GPA: the same letter means different
#: numbers at different universities, so the result is a rough band and is
#: labelled as such wherever it is used.
LETTER_BANDS: tuple[tuple[str, float], ...] = (
    ("A+", 97.0),
    ("A", 93.0),
    ("A-", 90.0),
    ("B+", 87.0),
    ("B", 83.0),
    ("B-", 80.0),
    ("C+", 77.0),
    ("C", 73.0),
    ("C-", 70.0),
    ("D+", 67.0),
    ("D", 63.0),
    ("D-", 60.0),
    ("F", 0.0),
)

#: Country name / alias -> ISO 3166-1 alpha-2, limited to countries that
#: actually appear in the catalogue plus the citizenship-bearing cases a match
#: gate has to resolve. This is a lookup, not a classifier: an unlisted country
#: is UNKNOWN, never guessed.
COUNTRY_CODES: dict[str, str] = {
    "afghanistan": "AF",
    "albania": "AL",
    "argentina": "AR",
    "armenia": "AM",
    "australia": "AU",
    "austria": "AT",
    "azerbaijan": "AZ",
    "bangladesh": "BD",
    "belarus": "BY",
    "belgium": "BE",
    "bolivia": "BO",
    "botswana": "BW",
    "brazil": "BR",
    "bulgaria": "BG",
    "canada": "CA",
    "chile": "CL",
    "china": "CN",
    "colombia": "CO",
    "costa rica": "CR",
    "croatia": "HR",
    "czech republic": "CZ",
    "czechia": "CZ",
    "denmark": "DK",
    "ecuador": "EC",
    "egypt": "EG",
    "estonia": "EE",
    "ethiopia": "ET",
    "finland": "FI",
    "france": "FR",
    "georgia": "GE",
    "germany": "DE",
    "ghana": "GH",
    "greece": "GR",
    "hungary": "HU",
    "iceland": "IS",
    "india": "IN",
    "indonesia": "ID",
    "iran": "IR",
    "iraq": "IQ",
    "ireland": "IE",
    "israel": "IL",
    "italy": "IT",
    "jamaica": "JM",
    "japan": "JP",
    "jordan": "JO",
    "kazakhstan": "KZ",
    "kenya": "KE",
    "kuwait": "KW",
    "latvia": "LV",
    "lebanon": "LB",
    "lithuania": "LT",
    "luxembourg": "LU",
    "malaysia": "MY",
    "maldives": "MV",
    "malta": "MT",
    "mexico": "MX",
    "moldova": "MD",
    "mongolia": "MN",
    "morocco": "MA",
    "myanmar": "MM",
    "nepal": "NP",
    "netherlands": "NL",
    "new zealand": "NZ",
    "nigeria": "NG",
    "north macedonia": "MK",
    "norway": "NO",
    "oman": "OM",
    "pakistan": "PK",
    "panama": "PA",
    "peru": "PE",
    "philippines": "PH",
    "poland": "PL",
    "portugal": "PT",
    "qatar": "QA",
    "romania": "RO",
    "russian federation": "RU",
    "russia": "RU",
    "saudi arabia": "SA",
    "senegal": "SN",
    "serbia": "RS",
    "singapore": "SG",
    "slovakia": "SK",
    "slovenia": "SI",
    "south africa": "ZA",
    "south korea": "KR",
    "korea, republic of": "KR",
    "spain": "ES",
    "sri lanka": "LK",
    "sweden": "SE",
    "switzerland": "CH",
    "taiwan": "TW",
    "tanzania": "TZ",
    "thailand": "TH",
    "tunisia": "TN",
    "turkey": "TR",
    "turkiye": "TR",
    "uganda": "UG",
    "ukraine": "UA",
    "united arab emirates": "AE",
    "united kingdom": "GB",
    "uk": "GB",
    "united states": "US",
    "united states of america": "US",
    "usa": "US",
    "uruguay": "UY",
    "uzbekistan": "UZ",
    "vietnam": "VN",
    "zambia": "ZM",
    "zimbabwe": "ZW",
}

#: Language tests recognised by name. A test outside this list cannot be matched
#: against a published threshold, and no cross-test equivalency is applied.
KNOWN_LANGUAGE_TESTS: frozenset[str] = frozenset(
    {
        "ielts",
        "toefl",
        "toefl ibt",
        "toefl itp",
        "pte",
        "duolingo",
        "duolingo english test",
        "cambridge",
        "cambridge english",
        "cefr",
        "topik",
        "jlpt",
        "hsk",
        "testdaF",
        "telc",
        "dele",
        "goethe",
        "dalf",
        "tcf",
        "b1",
        "b2",
        "c1",
        "c2",
    }
)


def normalise_text(value: str | None) -> str:
    """Lower-case, collapse whitespace. Never returns None for a non-None input."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value).strip().lower()


def resolve_country_code(value: str | None) -> str | None:
    """Map a country name or code to ISO alpha-2, or ``None`` if unknown.

    An unknown country stays unknown on purpose. Defaulting to the student's
    residence, or to a guess from a substring, would silently decide a
    nationality gate.
    """
    text = normalise_text(value)
    if not text:
        return None
    if re.fullmatch(r"[a-z]{2}", text):
        return text.upper()
    return COUNTRY_CODES.get(text)


def resolve_language_test(value: str | None) -> str | None:
    """Canonicalise a language test name, or ``None`` when unrecognised."""
    text = normalise_text(value)
    if not text:
        return None
    if text in KNOWN_LANGUAGE_TESTS:
        return text
    if text in {"toefl", "toefl_ibt", "toefl ibt"}:
        return "toefl"
    return None


def letter_to_band(letter: str | None) -> float | None:
    """Lower bound of a letter grade's percentage band.

    The band keys are stored upper-case and the input arrives normalised to
    lower case, so both sides are lowered before comparison. Comparing raw text
    here made every letter grade fail to match and return ``None``, which would
    have reported an A-level student as having supplied no academic result.
    """
    text = normalise_text(letter)
    if not text:
        return None
    for candidate, floor in LETTER_BANDS:
        if text == candidate.lower():
            return floor
    # "A" and "B" style grades written without a sign or plus/minus are common
    # in transcripts that only record the base letter.
    for candidate, floor in LETTER_BANDS:
        if text == candidate[0].lower():
            return floor
    return None


def normalise_numeric_mark(mark: AcademicMark | None) -> tuple[float | None, str]:
    """Rescale one academic mark onto 0-100 using only its own declared scale.

    Returns the normalised value and a short label naming the scale that was
    used, so the response can show the reader exactly what was compared. The
    second element is ``"unavailable"`` when nothing could be interpreted.
    """
    if mark is None:
        return None, "unavailable"

    scale = mark.scale
    value = mark.value

    if scale is GradingScale.LETTER or (value is None and mark.letter):
        band = letter_to_band(mark.letter)
        if band is None:
            return None, "unavailable"
        return min(band, 100.0), "letter band (approximate)"

    if value is None:
        return None, "unavailable"

    maximum = SCALE_MAXIMA.get(scale)
    if maximum is None or maximum <= 0:
        return None, "unavailable"

    if value < 0 or value > maximum:
        # A value outside its own declared scale is not interpretable. It is
        # more likely a scale mix-up than an extraordinary result, and scaling
        # it anyway would invent a number.
        return None, "unavailable"

    return (value / maximum) * 100.0, scale.value


def normalise_previous_mark(mark: AcademicMark | None) -> float | None:
    """Normalise the optional earlier mark used to describe academic trend."""
    if mark is None:
        return None
    previous_scale = mark.previous_scale or mark.scale
    if mark.previous_value is None:
        return None
    maximum = SCALE_MAXIMA.get(previous_scale)
    if maximum is None or maximum <= 0:
        return None
    if mark.previous_value < 0 or mark.previous_value > maximum:
        return None
    return (mark.previous_value / maximum) * 100.0


@dataclass(frozen=True)
class NormalisedProfile:
    """The profile as the engine will use it.

    Every attribute is either a usable value or ``None``. There is no sentinel
    for "unknown" beyond ``None``, so a component can never accidentally
    consume a fabricated value.
    """

    age: int | None
    citizenship_code: str | None
    citizenship_display: str | None
    country_of_residence_code: str | None
    country_of_residence_display: str | None

    highest_qualification: str | None
    graduation_year: int | None

    #: 0-100, or None when the student supplied nothing interpretable.
    overall_result: float | None
    overall_scale_label: str

    #: Field-canonical 0-100 marks, restricted to fields the taxonomy knows.
    subject_results: dict[str, float]
    #: Improvement in percentage points where both marks were supplied.
    trend: float | None

    intended_degree_level: str | None
    intended_field: str | None
    study_mode: str | None
    preferred_country_codes: tuple[str, ...]

    language_credentials: tuple[tuple[str, float | None, str | None], ...]

    max_self_contribution: float | None
    funding_requirement: str | None
    living_cost_support_required: bool | None

    intended_intake_year: int | None

    country_filter: str | None
    limit: int
    include_ineligible: bool

    @property
    def has_academic_data(self) -> bool:
        return self.overall_result is not None or bool(self.subject_results)


def normalise_profile(request: MatchProfileRequest) -> NormalisedProfile:
    """Convert an incoming request into the engine's internal facts.

    Pure: the same request always yields the same ``NormalisedProfile``.
    """
    overall_value, overall_label = normalise_numeric_mark(request.overall_result)
    trend = normalise_previous_mark(request.overall_result)

    subject_results: dict[str, float] = {}
    for mark in request.subject_results:
        normalised, _ = normalise_numeric_mark(mark)
        if normalised is None or not mark.field:
            continue
        # Field resolution happens in taxonomy.py; storing the raw key here
        # keeps normalisation free of taxonomy knowledge. The engine resolves
        # keys against the taxonomy and drops anything unknown.
        subject_results[normalise_text(mark.field)] = normalised

    credentials: list[tuple[str, float | None, str | None]] = []
    for credential in request.language_credentials:
        test = resolve_language_test(credential.test)
        if test is None:
            # An unrecognised test is dropped, not guessed at. No equivalency
            # table is consulted.
            continue
        credentials.append((test, credential.score, credential.level))

    preferred_codes = tuple(
        code
        for code in (resolve_country_code(country) for country in request.preferred_countries)
        if code is not None
    )

    return NormalisedProfile(
        age=request.age,
        citizenship_code=resolve_country_code(request.citizenship),
        citizenship_display=request.citizenship.strip() if request.citizenship else None,
        country_of_residence_code=resolve_country_code(request.country_of_residence),
        country_of_residence_display=(
            request.country_of_residence.strip() if request.country_of_residence else None
        ),
        highest_qualification=(
            request.highest_qualification.strip() if request.highest_qualification else None
        ),
        graduation_year=request.graduation_year,
        overall_result=overall_value,
        overall_scale_label=overall_label,
        subject_results=subject_results,
        trend=trend,
        intended_degree_level=(
            request.intended_degree_level.value if request.intended_degree_level else None
        ),
        intended_field=normalise_text(request.intended_field) or None,
        study_mode=request.study_mode.value if request.study_mode else None,
        preferred_country_codes=preferred_codes,
        language_credentials=tuple(credentials),
        max_self_contribution=request.max_self_contribution,
        funding_requirement=(
            request.funding_requirement.value if request.funding_requirement else None
        ),
        living_cost_support_required=request.living_cost_support_required,
        intended_intake_year=request.intended_intake_year,
        country_filter=normalise_text(request.country_filter) or None,
        limit=request.limit,
        include_ineligible=request.include_ineligible,
    )


# ---------------------------------------------------------------------------
# Academic Profile Index
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndexComponent:
    """One evaluated contribution to the Academic Profile Index."""

    name: str
    label: str
    score: float
    configured_weight: float
    weight: float
    detail: str


@dataclass(frozen=True)
class ProfileIndex:
    """The ScholarZone Academic Profile Index and how it was assembled."""

    score: float | None
    components: tuple[IndexComponent, ...]
    evaluated_coverage: float


#: Names of the index components, used in the response breakdown.
API_COMPONENT_LABELS: dict[str, str] = {
    "overall_result": "Overall academic result",
    "subject_performance": "Relevant subject performance",
    "consistency": "Academic consistency and trend",
}


def build_profile_index(profile: NormalisedProfile) -> ProfileIndex:
    """Compute the Academic Profile Index from supplied academic evidence.

    Only components with real data are used, and the weights of those components
    are renormalised across what is present. A student who supplied a single GPA
    therefore gets an index built entirely from that GPA, rather than an index
    dragged down by two missing components.

    Returns ``score=None`` when no academic evidence was supplied at all. That
    is not a zero: no academic data means the index is undefined, and the
    interface must say so instead of reporting LOW.
    """
    observed: list[tuple[str, float, str]] = []

    if profile.overall_result is not None:
        observed.append(
            (
                "overall_result",
                profile.overall_result,
                f"Normalised on the declared {profile.overall_scale_label} scale.",
            )
        )

    if profile.subject_results:
        subject_average = sum(profile.subject_results.values()) / len(profile.subject_results)
        observed.append(
            (
                "subject_performance",
                subject_average,
                f"Average of {len(profile.subject_results)} supplied subject result(s).",
            )
        )

    if profile.overall_result is not None and profile.trend is not None:
        difference = profile.overall_result - profile.trend
        # A flat record is neither good nor bad, so it scores mid-band; a large
        # improvement is capped at full credit and a large decline at zero.
        trend_score = max(0.0, min(100.0, 50.0 + difference))
        direction = "improvement" if difference >= 0 else "decline"
        observed.append(
            (
                "consistency",
                trend_score,
                f"{abs(difference):.1f} percentage point {direction} versus the earlier mark.",
            )
        )

    if not observed:
        return ProfileIndex(score=None, components=(), evaluated_coverage=0.0)

    configured_total = sum(API_COMPONENT_WEIGHTS[name] for name, _, _ in observed)
    components: list[IndexComponent] = []
    for name, raw_score, detail in observed:
        configured_weight = API_COMPONENT_WEIGHTS[name]
        components.append(
            IndexComponent(
                name=name,
                label=API_COMPONENT_LABELS.get(name, name),
                score=round(raw_score, 2),
                configured_weight=configured_weight,
                weight=configured_weight / configured_total,
                detail=detail,
            )
        )

    weighted = sum(component.score * component.weight for component in components)
    return ProfileIndex(
        score=round(weighted, 1),
        components=tuple(components),
        evaluated_coverage=round(configured_total * 100.0, 1),
    )