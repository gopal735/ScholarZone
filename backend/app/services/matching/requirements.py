"""Readers for explicitly published scholarship requirements.

This is the boundary between what a provider said and what ScholarZone claims.
Everything downstream trusts the requirements produced here, so the rules are
strict:

**A requirement exists only when the provider published a checkable number or
an explicit restriction.** The readers look for unambiguous phrasing -
"minimum GPA of 3.5", "IELTS 6.5 or above", "citizens of", "must be under 30" -
and return ``None`` for anything hedged, illustrative or negotiable.

**Hedged language produces no requirement.** "No fixed CGPA requirement",
"selection weighs motivation more heavily than grades" and "high school
graduate or expecting graduation" all mean the provider published *no numeric
minimum*. That is a real published fact and it is reported as
``ACADEMIC_MINIMUM_NOT_PUBLISHED`` rather than being turned into a threshold.

**Every extracted requirement keeps the provider's own sentence.** ``raw_quote``
and ``provenance_url`` travel with the requirement into the API response, so any
claim the interface makes can be traced back to the awarding body's wording.

**Nothing here repairs the database.** When a fact is absent the reader returns
nothing and the dimension is scored UNKNOWN. The enrichment pipeline owns data
quality; this module only reads what the pipeline produced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import REQUIREMENT_READER_VERSION
from .normalize import COUNTRY_CODES, normalise_text, resolve_language_test
from .types import GradingScale, NormalisedRequirement, RequirementKind


# ---------------------------------------------------------------------------
# Phrase gates
# ---------------------------------------------------------------------------

#: Phrases that mark a numeric academic threshold as explicitly required.
#: Every one of these is a mandatory qualifier. A number appearing without one of
#: these nearby is descriptive text, not a threshold.
_ACADEMIC_MINIMUM_MARKERS: tuple[str, ...] = (
    "minimum",
    "min.",
    "at least",
    "no less than",
    "not less than",
    "or higher",
    "or above",
    "or more",
    "and above",
    "and above",
    "required gpa",
    "required cgpa",
    "required score",
    "must have",
    "must possess",
    "should have at least",
)

#: Phrases that explicitly state no numeric minimum exists. Their presence
#: suppresses extraction, because a provider saying "grades are not the deciding
#: factor" must not be read as a threshold.
_ACADEMIC_NO_MINIMUM_MARKERS: tuple[str, ...] = (
    "no fixed",
    "no minimum",
    "no cgpa",
    "no gpa",
    "not required",
    "not mandatory",
    "no academic requirement",
    "no grade requirement",
    "no set cutoff",
    "no cutoff",
    "without a minimum",
    "there is no",
    "varies by",
    "set by the",
    "set by each",
)

#: Explicit "language is not required" markers. When present the language
#: dimension is NOT_EVALUATED; the student is never penalised for a test they
#: were never asked for.
_LANGUAGE_NOT_REQUIRED_MARKERS: tuple[str, ...] = (
    "not mandatory",
    "not required",
    "no requirement",
    "no formal requirement",
    "no english requirement",
    "not compulsory",
    "optional",
    "not obligatory",
    "may provide",
    "additional evaluation advantage",
    "not necessary",
)

_SCALE_PATTERNS: tuple[tuple[re.Pattern[str], GradingScale], ...] = (
    (re.compile(r"(?P<value>\d{1,2}(?:\.\d{1,2})?)\s*(?:/|out of)\s*4(?:\.0)?\b", re.I), GradingScale.GPA_4),
    (re.compile(r"(?P<value>\d{1,2}(?:\.\d{1,2})?)\s*(?:/|out of)\s*5(?:\.0)?\b", re.I), GradingScale.GPA_5),
    (re.compile(r"(?P<value>\d{1,2}(?:\.\d{1,2})?)\s*(?:/|out of)\s*10(?:\.0)?\b", re.I), GradingScale.GPA_10),
    (re.compile(r"(?P<value>\d{1,2}(?:\.\d{1,2})?)\s*%", re.I), GradingScale.PERCENTAGE),
    (re.compile(
        r"(?:gpa|cgpa|grade point average|average grade|transcript score)\D{0,24}?"
        r"(?P<value>\d{1,2}(?:\.\d{1,2})?)\b",
        re.I,
    ), GradingScale.UNKNOWN),
)

#: Test names that can carry a numeric minimum, matched case-insensitively.
_TEST_MINIMUM_PATTERN = re.compile(
    r"\b(?P<test>ielts|toefl(?:\s+ibt)?|pte(?:\s+academic)?|duolingo(?:\s+english\s+test)?|"
    r"cambridge\s+english(?:\s+c1\s+advanced)?|cefr)\b"
    r"(?P<context>[^.]{0,48}?)"
    r"(?P<value>\d{1,2}(?:\.\d{1,2})?)\s*(?P<comparator>\+)?",
    re.I,
)

_LEVEL_MINIMUM_PATTERN = re.compile(
    r"\b(?P<level>b1|b2|c1|c2)\s*(?:level)?\b(?P<context>[^.]{0,32}?)"
    r"\b(?P<required>b1|b2|c1|c2)\b",
    re.I,
)

_LEVEL_ORDER: dict[str, int] = {"b1": 1, "b2": 2, "c1": 3, "c2": 4}

#: Explicit study-mode requirements.
#:
#: Every alternative requires a study-mode noun alongside the verb. An earlier
#: version matched a bare "must be", which meant "Applicants must be citizens of
#: India" produced a full-time study-mode requirement - a false gate on the most
#: common sentence in the catalogue, and one that turned correctly eligible
#: students into NEEDS_VERIFICATION.
_STUDY_MODE_FULL_TIME = re.compile(
    r"\bmust be (?:enrolled|registered) (?:as|for)\b|"
    r"\b(?:required|expected) to (?:be )?(?:enrolled|registered)(?: (?:as|for))?\b|"
    r"\benrolled as\b|\b(?:is|are) a full[\s-]?time (?:student|enrolment|enrollment)\b|"
    r"\bfull[\s-]?time (?:student|enrolment|enrollment)\s+(?:status|required|only)\b|"
    r"\bonly (?:open to|available to|for) full[\s-]?time\b",
    re.I,
)
_STUDY_MODE_PART_TIME = re.compile(
    r"\b(?:part[\s-]?time (?:students?|programmes?|programs?)\b|"
    r"must be (?:enrolled|registered) part[\s-]?time|"
    r"\bonly (?:open to|available to|for) part[\s-]?time)\b",
    re.I,
)


#: Degree levels, matched against the curated structured ``degree`` column only.
#: Each pattern is anchored on word boundaries so "Master of Data Science" does
#: not become three separate degree levels, and no abbreviation is accepted that
#: could plausibly be a different word.
_DEGREE_LEVEL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "POSTDOCTORAL",
        re.compile(r"\bpost[\s-]?doctoral\b|\bpostdoc\b", re.I),
    ),
    (
        "DOCTORAL",
        re.compile(
            r"\bdoctoral\b|\bdoctorate\b|\bdoctor of philosophy\b|"
            r"\bd[\s-]?phil\b|\bph[\s-]?d\b|\bdoctorate level\b",
            re.I,
        ),
    ),
    (
        "MASTER",
        re.compile(
            r"\bmaster'?s?\b|\bmasters\b|\bm[\s-]?sc\b|\bmeng\b|"
            r"\bmaster degree\b|\bpostgraduate (?:course|programme|program)\b",
            re.I,
        ),
    ),
    (
        "BACHELOR",
        re.compile(
            r"\bbachelor'?s?\b|\bbachelors\b|\bb[\s-]?sc\b|"
            r"\bundergraduate (?:course|programme|program|degree)\b|\bhonours\b|\bhonors\b",
            re.I,
        ),
    ),
)


#: Phrases that mark a programme restriction as a real condition of eligibility
#: rather than a description of who usually applies.
_PROGRAMME_RESTRICTION_MARKERS: tuple[str, ...] = (
    "must be",
    "must",
    "required",
    "only open to",
    "restricted to",
    "limited to",
    "eligible only",
    "not open to",
)

#: The enrolment phrase itself. The capture group names the programme, which is
#: then resolved through the controlled taxonomy and discarded if unresolvable.
_PROGRAMME_RESTRICTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:must be|required to be|have to be|need to be)\s+"
        r"(?:enrolled|studying|registered)\s+(?:in|at|for)\s+(?:the\s+)?(?P<term>[^.;]+)",
        re.I,
    ),
    re.compile(
        r"\b(?:only\s+)?open\s+to\s+(?:students|applicants|candidates)\s+"
        r"(?:enrolled|studying|registered)\s+(?:in|at|for)\s+(?:the\s+)?(?P<term>[^.;]+)",
        re.I,
    ),
    re.compile(
        r"\brestricted\s+to\s+(?:students|applicants|candidates)\s+"
        r"(?:enrolled|studying|of|from|in)\s+(?:the\s+)?(?P<term>[^.;]+)",
        re.I,
    ),
    re.compile(
        r"\b(?:programme|program|degree|course)\s+(?:must be)\s+(?:in|of)\s+(?:the\s+)?(?P<term>[^.;]+)",
        re.I,
    ),
)

#: Age bounds. Each pattern requires a mandatory qualifier so that a descriptive
#: sentence about typical applicants is never read as an age gate.
_AGE_UNDER = re.compile(
    r"\b(?:under|below|less than|younger than|not (?:more|older) than|max(?:imum)?(?: age)? of)\s*"
    r"(?P<bound>\d{2})\b",
    re.I,
)
_AGE_OVER = re.compile(
    r"\b(?:over|above|older than|at least|min(?:imum)?(?: age)? of|no younger than)\s*"
    r"(?P<bound>\d{2})\b",
    re.I,
)
_AGE_RANGE = re.compile(
    r"\b(?:between|from)\s*(?P<low>\d{2})\s*(?:and|-|to|until)\s*(?P<high>\d{2})\b",
    re.I,
)

#: Age phrases that explicitly rule out an age limit.
_AGE_NO_LIMIT = re.compile(
    r"\bno (?:general )?age limit\b|\bno age restriction\b|\bany age\b",
    re.I,
)

#: Nationality restrictions. The capturing groups name canonical citizenship
#: terms; anything outside the vocabulary resolves to no restriction rather than
#: to a guessed one.
_NATIONALITY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:citizens?|nationals?|citizen|resident nationals?) of\s+(?P<term>[^.;]+)", re.I),
    re.compile(r"\bopen only to\s+(?P<term>[^.;]+)", re.I),
    re.compile(r"\brestricted to\s+(?P<term>[^.;]+)", re.I),
    re.compile(r"\bmust be (?:a |an )?(?:citizen|national) of\s+(?P<term>[^.;]+)", re.I),
)

#: Explicit "nationality is not restricted" markers.
_NATIONALITY_NO_RESTRICTION = re.compile(
    r"\bno nationality (?:restriction|requirement)s?\b|"
    r"\bopen to all (?:nationalities|citizens)\b|"
    r"\bnationality is not (?:a )?(?:factor|restriction)\b|"
    r"\bno citizenship requirement\b",
    re.I,
)

#: Multi-country citizenship terms.
_EU_NATIONALITIES = frozenset(
    code
    for name, code in COUNTRY_CODES.items()
    if name in {
        "austria", "belgium", "bulgaria", "croatia", "cyprus", "czech republic", "czechia",
        "denmark", "estonia", "finland", "france", "germany", "greece", "hungary", "ireland",
        "italy", "latvia", "lithuania", "luxembourg", "malta", "netherlands", "poland",
        "portugal", "romania", "slovakia", "slovenia", "spain", "sweden",
    }
)

#: Designated-country schemes. The provider's own designation is respected: a
#: student can only satisfy it if they hold a listed nationality.
_DESIGNATED_COUNTRY_TERMS = frozenset(
    {
        "nieed", "nieed-designated", "designated countries", "eligible countries",
        "developing countries", "low and middle income countries", "lmic",
        "university track", "embassy track",
    }
)


@dataclass(frozen=True)
class ReadRequirements:
    """Everything the readers could extract from one record."""

    academic_minimum: NormalisedRequirement | None
    #: True when the provider explicitly stated there is no numeric minimum.
    academic_minimum_absent_by_publication: bool
    language_minimum: NormalisedRequirement | None
    language_not_required: bool
    nationality: NormalisedRequirement | None
    age: NormalisedRequirement | None
    study_mode: NormalisedRequirement | None
    #: Degree levels the record explicitly offers. Read from the STRUCTURED
    #: ``degree`` column only - never from prose.
    degree_levels: NormalisedRequirement | None
    #: An explicitly published restriction on the programme/field of study,
    #: produced only when the named programme resolves to a canonical field in
    #: the controlled taxonomy.
    programme_restriction: NormalisedRequirement | None
    scholarship_country_code: str | None


def _sentences(text: str) -> list[str]:
    """Split text into candidate sentences, preserving the original wording."""
    if not text:
        return []
    return [part.strip() for part in re.split(r"(?<=[.;])\s+|\n+", text) if part.strip()]


def _has_marker(sentence: str, markers: tuple[str, ...]) -> bool:
    lowered = normalise_text(sentence)
    return any(marker in lowered for marker in markers)


def read_academic_minimum(texts: list[str], provenance_url: str | None) -> tuple[NormalisedRequirement | None, bool]:
    """Find an explicitly published numeric academic minimum.

    Returns ``(requirement, absence_published)``. ``absence_published`` is True
    only when the provider stated that no numeric minimum exists, which is
    meaningfully different from silence.
    """
    for text in texts:
        for sentence in _sentences(text):
            if _has_marker(sentence, _ACADEMIC_NO_MINIMUM_MARKERS):
                return None, True
            if not _has_marker(sentence, _ACADEMIC_MINIMUM_MARKERS):
                continue

            lowered = normalise_text(sentence)
            for pattern, scale in _SCALE_PATTERNS:
                match = pattern.search(sentence)
                if match is None:
                    continue
                try:
                    value = float(match.group("value"))
                except ValueError:
                    continue
                if value <= 0:
                    continue

                resolved_scale = scale
                # A bare "GPA of 3.5" with no stated denominator is not
                # interpretable, and assuming 4.0 would be exactly the guessed
                # conversion this engine refuses to make.
                if resolved_scale is GradingScale.UNKNOWN:
                    if "gpa" in lowered or "cgpa" in lowered:
                        explicit_four = re.search(r"on\s+(?:a\s+)?4(?:\.0)?\s*(?:scale|point)", lowered)
                        if not explicit_four:
                            continue
                        resolved_scale = GradingScale.GPA_4
                    elif "percentage" in lowered or "%" in sentence:
                        resolved_scale = GradingScale.PERCENTAGE
                    else:
                        continue

                return (
                    NormalisedRequirement(
                        kind=RequirementKind.ACADEMIC_MINIMUM,
                        raw_quote=sentence[:600],
                        provenance_url=provenance_url,
                        minimum_value=value,
                        scale=resolved_scale,
                    ),
                    False,
                )
    return None, False


def read_language_minimum(
    text: str | None, provenance_url: str | None
) -> tuple[NormalisedRequirement | None, bool]:
    """Find an explicitly published language threshold.

    Returns ``(requirement, not_required)``. ``not_required`` means the provider
    stated language is not a condition of eligibility.
    """
    if not text:
        return None, False

    for sentence in _sentences(text):
        if _has_marker(sentence, _LANGUAGE_NOT_REQUIRED_MARKERS):
            return None, True

    # A numeric threshold only counts when the sentence also carries a
    # mandatory qualifier, so "TOPIK or TOEFL/IELTS scores may provide additional
    # evaluation advantage" never becomes a requirement.
    for sentence in _sentences(text):
        if not _has_marker(sentence, _ACADEMIC_MINIMUM_MARKERS):
            continue
        match = _TEST_MINIMUM_PATTERN.search(sentence)
        if match is None:
            continue
        test = resolve_language_test(match.group("test"))
        if test is None:
            continue
        try:
            value = float(match.group("value"))
        except ValueError:
            continue
        return (
            NormalisedRequirement(
                kind=RequirementKind.LANGUAGE_MINIMUM,
                raw_quote=sentence[:600],
                provenance_url=provenance_url,
                minimum_value=value,
                test_name=test,
            ),
            False,
        )

    # A CEFR level requirement reads as "hold at least B2". The held level and
    # the required level have to differ for the sentence to state a threshold at
    # all, and the sentence must also carry a mandatory qualifier.
    for sentence in _sentences(text):
        level_match = _LEVEL_MINIMUM_PATTERN.search(sentence)
        if level_match is None:
            continue
        if not _has_marker(sentence, _ACADEMIC_MINIMUM_MARKERS):
            continue
        held = normalise_text(level_match.group("level"))
        required = normalise_text(level_match.group("required"))
        if _LEVEL_ORDER.get(held, 0) < _LEVEL_ORDER.get(required, 0):
            return (
                NormalisedRequirement(
                    kind=RequirementKind.LANGUAGE_MINIMUM,
                    raw_quote=sentence[:600],
                    provenance_url=provenance_url,
                    minimum_value=float(_LEVEL_ORDER[required]),
                    test_name="cefr",
                    scale=GradingScale.UNKNOWN,
                ),
                False,
            )
    return None, False


def read_nationality(texts: list[str], provenance_url: str | None) -> NormalisedRequirement | None:
    """Find an explicitly published citizenship restriction.

    Only restrictions that resolve to a known set of citizenship terms are
    returned. A term naming a scheme we cannot enumerate (``NIIED-designated
    country``) yields no requirement and therefore an UNKNOWN gate, which is
    honest: we cannot confirm eligibility from a scheme name.
    """
    for text in texts:
        for sentence in _sentences(text):
            if _NATIONALITY_NO_RESTRICTION.search(sentence):
                return None

    for text in texts:
        for sentence in _sentences(text):
            for pattern in _NATIONALITY_PATTERNS:
                match = pattern.search(sentence)
                if match is None:
                    continue
                term = normalise_text(match.group("term"))
                if not term:
                    continue

                if "eu" in term or "european union" in term:
                    codes = tuple(sorted(_EU_NATIONALITIES))
                    if codes:
                        return NormalisedRequirement(
                            kind=RequirementKind.NATIONALITY,
                            raw_quote=sentence[:600],
                            provenance_url=provenance_url,
                            allowed_terms=("EU",) + codes,
                        )
                    continue

                named = tuple(
                    code
                    for name, code in COUNTRY_CODES.items()
                    if re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", term)
                )
                if named:
                    return NormalisedRequirement(
                        kind=RequirementKind.NATIONALITY,
                        raw_quote=sentence[:600],
                        provenance_url=provenance_url,
                        allowed_terms=tuple(sorted(named)),
                    )

                if any(scheme in term for scheme in _DESIGNATED_COUNTRY_TERMS):
                    # The provider restricts by a scheme rather than by a list.
                    # The scheme is recorded for provenance but yields no
                    # comparable set, so the gate reports UNKNOWN.
                    return NormalisedRequirement(
                        kind=RequirementKind.NATIONALITY,
                        raw_quote=sentence[:600],
                        provenance_url=provenance_url,
                        allowed_terms=("DESIGNATED_SCHEME",),
                    )
    return None


def read_age(texts: list[str], provenance_url: str | None) -> NormalisedRequirement | None:
    """Find an explicitly published age bound."""
    for text in texts:
        for sentence in _sentences(text):
            if _AGE_NO_LIMIT.search(sentence):
                return None

    for text in texts:
        for sentence in _sentences(text):
            if not _has_marker(sentence, ("must", "required", "eligible", "not", "maximum", "minimum", "should")):
                continue

            range_match = _AGE_RANGE.search(sentence)
            if range_match is not None:
                low = int(range_match.group("low"))
                high = int(range_match.group("high"))
                if 13 <= low < high <= 100:
                    return NormalisedRequirement(
                        kind=RequirementKind.AGE,
                        raw_quote=sentence[:600],
                        provenance_url=provenance_url,
                        age_min=low,
                        age_max=high,
                    )

            under = _AGE_UNDER.search(sentence)
            if under is not None:
                bound = int(under.group("bound"))
                if 13 <= bound <= 100:
                    return NormalisedRequirement(
                        kind=RequirementKind.AGE,
                        raw_quote=sentence[:600],
                        provenance_url=provenance_url,
                        age_max=bound - 1,
                    )

            over = _AGE_OVER.search(sentence)
            if over is not None:
                bound = int(over.group("bound"))
                if 13 <= bound <= 100:
                    return NormalisedRequirement(
                        kind=RequirementKind.AGE,
                        raw_quote=sentence[:600],
                        provenance_url=provenance_url,
                        age_min=bound,
                    )
    return None


def read_study_mode(texts: list[str], provenance_url: str | None) -> NormalisedRequirement | None:
    """Find an explicitly published study-mode condition."""
    for text in texts:
        for sentence in _sentences(text):
            if _STUDY_MODE_FULL_TIME.search(sentence):
                return NormalisedRequirement(
                    kind=RequirementKind.STUDY_MODE,
                    raw_quote=sentence[:600],
                    provenance_url=provenance_url,
                    allowed_terms=("FULL_TIME",),
                )
            if _STUDY_MODE_PART_TIME.search(sentence):
                return NormalisedRequirement(
                    kind=RequirementKind.STUDY_MODE,
                    raw_quote=sentence[:600],
                    provenance_url=provenance_url,
                    allowed_terms=("PART_TIME",),
                )
    return None


#: Phrases that explicitly say tuition is paid by the awarding body.
_TUITION_COVERED = re.compile(
    r"\bfull\s+tuition\b|\btuition\s+(?:fees?\s+)?(?:are\s+|is\s+|will\s+be\s+)?(?:fully\s+)?"
    r"(?:covered|paid|waived|met|funded)\b|\bfees?\s+waived\b|\btuition\s+support\b|"
    r"\bnon[- ]?refundable\s+tuition\b|\b100%\s+tuition\b",
    re.I,
)

#: Phrases that say living costs are also paid.
_LIVING_COVERED = re.compile(
    r"\bmonthly\s+stipend\b|\bliving\s+costs?\b|\bliving\s+expenses?\b|\bmonthly\s+allowance\b|"
    r"\bsettlement\s+allowance\b|\baccommodation\b|\bmeals?\b|\bhousing\b|\bboarding\b",
    re.I,
)

#: Phrases that say living costs are NOT covered. Their presence is what makes
#: "tuition only" a published fact rather than an absence of information.
_LIVING_NOT_COVERED = re.compile(
    r"\bliving\s+costs?\s+(?:are\s+|is\s+)?not\s+(?:covered|included|provided)\b|"
    r"\bdoes\s+not\s+(?:cover|include)\s+living\b|\btuition\s+only\b|"
    r"\bnot\s+include\s+living\b",
    re.I,
)

#: Phrases that say no funding is offered at all.
_NO_FUNDING = re.compile(
    r"\bno\s+(?:financial\s+)?(?:funding|award|scholarship\s+amount|fee\s+waiver)\b|"
    r"\bunfunded\b|\bnot\s+funded\b|\bno\s+financial\s+support\b",
    re.I,
)


def read_funding_coverage(texts: list[str]) -> tuple[str | None, str]:
    """Read published coverage facts out of the record's benefit text.

    ``coverage``/``benefits`` holds what the awarding body published about what
    the award pays for. That is official evidence, and it is far more available
    than the structured coverage columns, which are still null on much of the
    catalogue.

    It is read with the same conservatism as every other reader here: only
    explicit statements count. "Full tuition" plus a stipend or living-cost
    phrase establishes full coverage. "Full tuition" with an explicit statement
    that living costs are not covered is tuition-only. Anything else is
    ``None``, which the scorer reports as unknown rather than resolving in the
    student's favour or against it.

    The whole list is considered before deciding. A record that publishes
    "Full tuition fees" and "Monthly stipend for living expenses" as two
    separate lines is describing one award that covers both, and stopping at the
    first line would report it as tuition-only. The returned quote names the
    lines that carried the decisive phrase so a reviewer can see why.

    Returns ``(state_or_None, quote)``.
    """
    lines = [text for text in texts if text and text.strip()]

    tuition_line = next((text for text in lines if _TUITION_COVERED.search(text)), None)
    living_line = next((text for text in lines if _LIVING_COVERED.search(text)), None)
    living_excluded_line = next((text for text in lines if _LIVING_NOT_COVERED.search(text)), None)
    no_funding_line = next((text for text in lines if _NO_FUNDING.search(text)), None)

    if tuition_line is not None:
        if living_excluded_line is not None:
            return "TUITION_ONLY", living_excluded_line[:600]
        if living_line is not None:
            # Both facts exist. Quote both lines when they differ, because the
            # reader needs the pair to justify the conclusion.
            if living_line is tuition_line:
                return "FULL", tuition_line[:600]
            return "FULL", f"{tuition_line[:300]} {living_line[:300]}".strip()
        return "TUITION_PLUS_LIVING", tuition_line[:600]

    if no_funding_line is not None:
        return "NONE", no_funding_line[:600]

    return None, ""


def read_degree_levels(
    degree_field: str | None,
    provenance_url: str | None,
) -> NormalisedRequirement | None:
    """Read the degree levels a record explicitly offers.

    This is the only reader here that takes a *structured* column rather than
    published prose, and that is deliberate. The catalogue stores
    ``degree`` as a curated, human-checked list such as ``"Master, Doctoral"``,
    so it is evidence the research pipeline already resolved - whereas a sentence
    in a description is exactly where invented thresholds hide.

    A field naming only levels this module does not recognise yields ``None``,
    which produces no gate at all. That is the correct outcome: an unreadable
    degree column means the degree condition cannot be checked, and inventing a
    gate from it would be inventing a rule.
    """
    if not degree_field:
        return None

    found: list[str] = []
    for level, pattern in _DEGREE_LEVEL_PATTERNS:
        if pattern.search(degree_field) and level not in found:
            found.append(level)

    if not found:
        return None

    return NormalisedRequirement(
        kind=RequirementKind.DEGREE_LEVEL,
        raw_quote=degree_field[:600],
        provenance_url=provenance_url,
        allowed_terms=tuple(sorted(found)),
    )


def read_programme_restriction(
    texts: list[str],
    provenance_url: str | None,
) -> NormalisedRequirement | None:
    """Find an explicitly published restriction on the programme of study.

    Extremely conservative by necessity. A programme restriction that cannot be
    resolved to a canonical field is worse than no restriction at all: reporting
    "you must be in Computer Science" from a phrase that actually said
    "engineering, technology or a related subject" would disqualify a student on
    our reading rather than the awarding body's.

    So a requirement is produced only when all three hold:

    1. the sentence carries an explicit mandatory qualifier naming enrolment in a
       programme ("must be enrolled in", "only open to students of"),
    2. the named programme resolves to exactly one canonical field through the
       controlled taxonomy, and
    3. that field's key is recorded, so the gate compares keys rather than text.

    Anything else yields ``None`` and therefore an unevaluated field dimension
    rather than a gate.
    """
    from .taxonomy import resolve_field

    for text in texts:
        for sentence in _sentences(text):
            if not _has_marker(sentence, _PROGRAMME_RESTRICTION_MARKERS):
                continue
            for pattern in _PROGRAMME_RESTRICTION_PATTERNS:
                match = pattern.search(sentence)
                if match is None:
                    continue
                term = normalise_text(match.group("term"))
                if not term:
                    continue
                resolution = resolve_field(term, source_field="eligibility")
                if resolution.key is None:
                    # Named a programme our taxonomy does not know. Skip this
                    # phrase and keep looking: one unresolvable sentence should
                    # not suppress a clear one later in the same record.
                    continue
                return NormalisedRequirement(
                    kind=RequirementKind.PROGRAMME_RESTRICTION,
                    raw_quote=sentence[:600],
                    provenance_url=provenance_url,
                    allowed_terms=(resolution.key,),
                )
    return None


def read_requirements(facts) -> ReadRequirements:
    """Run every reader over one scholarship record.

    The texts consulted are the structured published fields only: eligibility
    statements, requirements, and the English requirement line. Prose
    descriptions, titles and notes are deliberately excluded, because a
    descriptive sentence is where invented thresholds hide.
    """
    provenance = facts.official_source_url or facts.official_source

    eligibility_texts = [facts.eligibility_summary or ""]
    eligibility_texts.extend(facts.eligibility or [])
    eligibility_texts.extend(facts.requirements or [])

    academic_minimum, academic_absent = read_academic_minimum(eligibility_texts, provenance)
    language_minimum, language_not_required = read_language_minimum(
        facts.english_requirement, provenance
    )
    nationality = read_nationality(eligibility_texts, provenance)
    age = read_age(eligibility_texts, provenance)
    study_mode = read_study_mode(eligibility_texts, provenance)
    degree_levels = read_degree_levels(facts.degree_levels, provenance)
    programme_restriction = read_programme_restriction(eligibility_texts, provenance)

    from .normalize import resolve_country_code  # local import avoids a cycle at module load

    return ReadRequirements(
        academic_minimum=academic_minimum,
        academic_minimum_absent_by_publication=academic_absent,
        language_minimum=language_minimum,
        language_not_required=language_not_required,
        nationality=nationality,
        age=age,
        study_mode=study_mode,
        degree_levels=degree_levels,
        programme_restriction=programme_restriction,
        scholarship_country_code=resolve_country_code(facts.country),
    )


def reader_version() -> str:
    """The version of the readers, reported in every response."""
    return REQUIREMENT_READER_VERSION