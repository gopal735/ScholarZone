"""Optional natural-language profile input, parsed deterministically.

A student should be able to type one sentence instead of filling in a form. This
module does that with a curated, deterministic parser - regexes over an approved
vocabulary - and deliberately not with a language model.

That choice is not a limitation being accepted quietly; it is the safe one. A
model-generated interpretation of "preferably somewhere cheap in Europe" would
be fluent, plausible and unverifiable, and this product's entire claim is that
every field it uses is traceable to something real. A curated parser can be
wrong in an obvious way that a test can pin.

Four rules, and they are the reason this module is safe to accept input at all:

**Validation first.** Nothing is emitted unless it resolves through the same
controlled vocabularies the engine itself uses: the country lookup, the programme
taxonomy, the degree levels, the language tests. An unresolvable country is
reported as unresolved, never guessed.

**Never silent.** Every extracted field carries the exact phrase it matched, so
the confirmation step can show the student what was read. An interpretation that
could not be resolved is reported too, rather than dropped - "we did not
understand X" is more useful than a form that quietly omits a field the student
typed.

**It never scores.** The parser produces a profile payload, nothing more. The
engine consumes that payload through the same path as a hand-filled form, so a
parsed profile and a typed profile are indistinguishable downstream. No parsing
result can reach a score except by becoming an ordinary validated field.

**It is bounded.** The input is length-limited and each field type has a hard
count, so the parser cannot be handed a document or be made to produce an
unbounded payload.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import (
    MAX_PREFERRED_COUNTRIES,
    NATURAL_LANGUAGE_MAX_LENGTH,
    NATURAL_LANGUAGE_MAX_TOKENS,
)
from .normalize import COUNTRY_CODES, normalise_text, resolve_country_code, resolve_language_test
from .taxonomy import resolve_field


#: Curated region -> the countries it expands to.
#:
#: A region preference is a convenience, so an expansion error is a mild
#: inconvenience rather than a false eligibility claim: preference is a soft
#: component that can never override the gate. It is still curated and explicit
#: rather than inferred, so a reader can see exactly what "Europe" meant.
REGION_MEMBERS: dict[str, tuple[str, ...]] = {
    "europe": (
        "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czech Republic", "Denmark",
        "Estonia", "Finland", "France", "Germany", "Greece", "Hungary", "Iceland", "Ireland",
        "Italy", "Latvia", "Liechtenstein", "Lithuania", "Luxembourg", "Malta", "Netherlands",
        "Norway", "Poland", "Portugal", "Romania", "Slovakia", "Slovenia", "Spain", "Sweden",
        "Switzerland", "United Kingdom",
    ),
    "north america": ("Canada", "Mexico", "United States"),
    "latin america": (
        "Argentina", "Brazil", "Chile", "Colombia", "Costa Rica", "Cuba", "Ecuador",
        "Jamaica", "Mexico", "Panama", "Peru", "Uruguay",
    ),
    "asia pacific": (
        "Australia", "China", "Hong Kong SAR", "Indonesia", "Japan", "Malaysia", "New Zealand",
        "Philippines", "Singapore", "South Korea", "Taiwan", "Thailand", "Vietnam",
    ),
    "middle east and north africa": (
        "Egypt", "Iran", "Israel", "Jordan", "Kuwait", "Lebanon", "Morocco", "Oman", "Qatar",
        "Saudi Arabia", "Tunisia", "Turkey", "United Arab Emirates",
    ),
    "south and southeast asia": (
        "Bangladesh", "India", "Indonesia", "Malaysia", "Myanmar", "Nepal", "Pakistan",
        "Philippines", "Singapore", "Sri Lanka", "Thailand", "Vietnam",
    ),
}

#: Phrases that introduce a nationality or residence.
_ORIGIN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:i\s*(?:'m|am)\s*from|coming from|based in|i\s*live in)\s+(?P<value>[^,.;]+)", re.I),
    re.compile(r"\b(?:citizen|national|passport)\s+of\s+(?P<value>[^,.;]+)", re.I),
    re.compile(r"\b(?:from|in)\s+(?P<value>[^,.;]+)", re.I),
)

#: Degree level phrases, longest first so "postdoctoral" is never read as
#: "doctoral".
_DEGREE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("POSTDOCTORAL", re.compile(r"\bpost[\s-]?doctoral\b|\bpostdoc\b", re.I)),
    (
        "DOCTORAL",
        re.compile(
            r"\bdoctor(?:al|ate)\b|\bph[\s.-]?d\b|\bd[\s-]?phil\b|\bdoctor of philosophy\b",
            re.I,
        ),
    ),
    (
        "MASTER",
        re.compile(
            r"\bmaster'?s?\s+(?:degree|programme|program|course)\b|\bmaster'?s?\b|\bmasters\b|"
            r"\bm[\s-]?sc\b|\bmeng\b|\bma\s+(?:in|of)\b|\bmba\b",
            re.I,
        ),
    ),
    (
        "BACHELOR",
        re.compile(
            r"\bbachelor'?s?\s+(?:degree|programme|program|course)\b|\bbachelor'?s?\b|\bbachelors\b|"
            r"\bb[\s-]?sc\b|\bundergraduate\b",
            re.I,
        ),
    ),
)

#: Study-mode phrases.
_STUDY_MODE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("FULL_TIME", re.compile(r"\bfull[\s-]?time\b", re.I)),
    ("PART_TIME", re.compile(r"\bpart[\s-]?time\b", re.I)),
)

#: Funding-need phrases. Ordered so an explicit full-funding statement wins over
#: the word "tuition" appearing inside it.
_FUNDING_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "FULL_FUNDING",
        re.compile(
            r"\bfully\s+funded\b|\bfull\s+funding\b|\bfull[\s-]?ride\b|\bfund\s+me\s+fully\b|"
            r"\bcover\s+(?:all\s+of\s+)?(?:my\s+)?(?:tuition|living\s+costs?)\b|"
            r"\ball\s+expenses\s+covered\b|\bfunded\s+including\s+living\b",
            re.I,
        ),
    ),
    (
        "NO_SPECIFIC_NEED",
        re.compile(
            r"\b(?:do\s*n[o']t|don'?t|do not)\s+need\s+(?:any\s+)?(?:funding|scholarship\s+money)\b|"
            r"\bno\s+funding\s+requirement\b|\bfunding\s+(?:is\s+)?not\s+(?:important|a\s+factor)\b",
            re.I,
        ),
    ),
    (
        "PARTIAL_OK",
        re.compile(r"\bpartial(?:ly)?\s+(?:funding\s+)?(?:is\s+)?(?:fine|ok|okay|acceptable)\b|\bany\s+partial\s+funding\b", re.I),
    ),
    (
        "TUITION_ONLY_SUFFICIENT",
        re.compile(
            r"\btuition\s+(?:only\s+)?(?:covered|waived|paid)\b|"
            r"\b(?:only|just)\s+need\s+(?:the\s+)?tuition\b|"
            r"\btuition\s+(?:fees?\s+)?(?:only|is\s+enough)\b|"
            r"\bi\s+can\s+fund\s+the\s+rest\b",
            re.I,
        ),
    ),
)

#: Language test plus an explicit score.
_LANGUAGE_SCORE_PATTERN = re.compile(
    r"\b(?P<test>ielts|toefl(?:\s+ibt)?|pte(?:\s+academic)?|duolingo(?:\s+english\s+test)?|"
    r"cambridge\s+english|cefr|topik|jlpt|hsk|testdaf|telc|dele|goethe|tcf)"
    r"\s*(?:score(?:\s+of)?|result(?:\s+of)?|of|:|=)?\s*"
    r"(?P<value>\d{1,3}(?:\.\d{1,2})?)\b",
    re.I,
)

#: A CEFR level stated on its own.
_CEFR_LEVEL_PATTERN = re.compile(r"\b(?P<level>b1|b2|c1|c2)\b", re.I)

#: Field-of-study phrases. The taxonomy resolves the captured text, so an
#: unrecognised subject is reported rather than matched loosely.
_FIELD_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:studying|in|of|degree\s+in|major\s+in)\s+(?P<value>[^,.;]+)", re.I),
    re.compile(r"\b(?P<value>[^,.;]+?)\s+(?:degree|programme|program|course)\b", re.I),
)

CEFR_ORDER: dict[str, float] = {"b1": 1.0, "b2": 2.0, "c1": 3.0, "c2": 4.0}


@dataclass(frozen=True)
class ParsedField:
    """One interpretation, with the phrase that produced it."""

    field: str
    value: object
    display: str
    #: The exact text the parser matched. Shown to the student, so an
    #: interpretation can always be traced back to their own words.
    source: str
    #: ``RESOLVED`` means the value passed a controlled vocabulary and can be
    #: used. ``UNRESOLVED`` means it was recognised as relevant but could not be
    #: resolved, and the student has to supply it themselves.
    status: str
    note: str | None = None


@dataclass(frozen=True)
class ParsedProfile:
    """The result of parsing one message."""

    #: Only resolved fields, shaped as a ``MatchProfileRequest`` payload.
    profile: dict
    resolved: tuple[ParsedField, ...]
    unresolved: tuple[ParsedField, ...]

    @property
    def is_empty(self) -> bool:
        return not self.resolved and not self.unresolved


def _clip_tokens(text: str) -> str:
    return " ".join(text.split()[:NATURAL_LANGUAGE_MAX_TOKENS])


def _resolve_country(phrase: str) -> tuple[str | None, str]:
    """Resolve a country phrase to an ISO code and a display name."""
    trimmed = phrase.strip().strip(".,;:")
    # Try progressively shorter prefixes: "Bangladesh and I have" is a country
    # followed by the rest of the sentence, not a 20-word country name.
    words = trimmed.split()
    for end in range(len(words), 0, -1):
        candidate = " ".join(words[:end])
        code = resolve_country_code(candidate)
        if code is not None:
            display = candidate.title()
            for name in COUNTRY_CODES:
                if name == normalise_text(candidate):
                    display = name.title()
                    break
            return code, display
    return None, trimmed[:80]


def _parse_origin(text: str, consumed: set[str]) -> ParsedField | None:
    for pattern in _ORIGIN_PATTERNS:
        for match in pattern.finditer(text):
            phrase = match.group("value").strip()
            code, display = _resolve_country(phrase)
            if code is None:
                return ParsedField(
                    field="citizenship",
                    value=None,
                    display=display,
                    source=match.group(0).strip(),
                    status="UNRESOLVED",
                    note=(
                        f'"{display}" is not in ScholarZone\'s country list, so it was not used. '
                        "Type the country exactly, or pick it from the list."
                    ),
                )
            consumed.add(match.group(0).lower())
            return ParsedField(
                field="citizenship",
                value=display,
                display=display,
                source=match.group(0).strip(),
                status="RESOLVED",
                note="Read from the place you said you are from.",
            )
    return None


def _parse_degree(text: str) -> ParsedField | None:
    for value, pattern in _DEGREE_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        return ParsedField(
            field="intended_degree_level",
            value=value,
            display=value.replace("_", " ").title(),
            source=match.group(0).strip(),
            status="RESOLVED",
        )
    return None


def _parse_field(text: str) -> ParsedField | None:
    for pattern in _FIELD_PATTERNS:
        for match in pattern.finditer(text):
            phrase = match.group("value").strip()
            resolution = resolve_field(phrase, source_field="natural_language")
            if resolution.key is None:
                # Do not stop here. A later phrase may name a field the taxonomy
                # knows even when this one does not.
                continue
            return ParsedField(
                field="intended_field",
                value=resolution.key,
                display=resolution.label or resolution.key,
                source=match.group(0).strip(),
                status="RESOLVED",
                note=(
                    f'Matched the alias "{resolution.matched_alias}" in ScholarZone\'s programme list.'
                    if resolution.matched_alias
                    else None
                ),
            )
    return None


def _parse_funding(text: str) -> ParsedField | None:
    for value, pattern in _FUNDING_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        return ParsedField(
            field="funding_requirement",
            value=value,
            display=value.replace("_", " ").title(),
            source=match.group(0).strip(),
            status="RESOLVED",
        )
    return None


def _parse_language(text: str) -> ParsedField | None:
    match = _LANGUAGE_SCORE_PATTERN.search(text)
    if match is not None:
        test = resolve_language_test(match.group("test"))
        if test is None:
            return ParsedField(
                field="language_credentials",
                value=None,
                display=match.group("test").strip(),
                source=match.group(0).strip(),
                status="UNRESOLVED",
                note=(
                    f'"{match.group("test").strip()}" is not a language test ScholarZone can compare, '
                    "so no score was read from it."
                ),
            )
        try:
            score = float(match.group("value"))
        except ValueError:
            return None
        if score < 0 or score > 200:
            return ParsedField(
                field="language_credentials",
                value=None,
                display=f"{test.upper()} {score:g}",
                source=match.group(0).strip(),
                status="UNRESOLVED",
                note="That score is outside every range ScholarZone accepts.",
            )
        return ParsedField(
            field="language_credentials",
            value={"test": test, "score": score},
            display=f"{test.upper()} {score:g}",
            source=match.group(0).strip(),
            status="RESOLVED",
        )

    level_match = _CEFR_LEVEL_PATTERN.search(text)
    if level_match is not None and re.search(r"\b(?:cefr|level)\b", text, re.I):
        level = normalise_text(level_match.group("level"))
        return ParsedField(
            field="language_credentials",
            value={"test": "cefr", "level": level.upper(), "score": CEFR_ORDER[level]},
            display=f"CEFR {level.upper()}",
            source=level_match.group(0).strip(),
            status="RESOLVED",
        )
    return None


def _parse_region(text: str) -> ParsedField | None:
    """Expand a named region into its countries.

    Only an explicit region name is expanded. Nothing infers a region from the
    countries a student happens to mention.
    """
    for name, members in REGION_MEMBERS.items():
        if re.search(rf"\b{re.escape(name)}\b", text, re.I):
            # The expansion is bounded by the same limit the request model
            # enforces, so a parsed profile always validates downstream.
            expanded = list(members)[:MAX_PREFERRED_COUNTRIES]
            return ParsedField(
                field="preferred_countries",
                value=expanded,
                display=f"{name.title()} ({len(expanded)} countries)",
                source=name,
                status="RESOLVED",
                note=f'Expanded from ScholarZone\'s curated list of {name.title()} countries.',
            )
    return None


def _parse_countries(text: str, origin: ParsedField | None) -> ParsedField | None:
    """Collect every country named as a preference, apart from the origin."""
    origin_value = normalise_text(origin.display) if origin and origin.status == "RESOLVED" else None
    found: list[str] = []
    matched: list[str] = []

    for name in COUNTRY_CODES:
        if len(name) <= 3:
            continue
        if re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", text, re.I):
            display = name.title()
            if origin_value == name:
                continue
            if display not in found:
                found.append(display)
                matched.append(name)

    if not found:
        return None

    return ParsedField(
        field="preferred_countries",
        value=found[:MAX_PREFERRED_COUNTRIES],
        display=", ".join(found[:6]) + ("…" if len(found) > 6 else ""),
        source=", ".join(matched[:6]),
        status="RESOLVED",
        note="Countries named in your message, kept as a preference only.",
    )


def _parse_study_mode(text: str) -> ParsedField | None:
    for value, pattern in _STUDY_MODE_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        return ParsedField(
            field="study_mode",
            value=value,
            display=value.replace("_", " ").title(),
            source=match.group(0).strip(),
            status="RESOLVED",
        )
    return None


def parse_natural_language_profile(text: str | None) -> ParsedProfile:
    """Parse one free-text message into a profile payload.

    Pure and deterministic: the same message always produces the same fields, the
    same displayed values and the same unresolved notes. Returns an empty result
    for empty input rather than raising, so the caller can show a normal empty
    confirmation state.
    """
    if text is None:
        return ParsedProfile(profile={}, resolved=(), unresolved=())

    trimmed = text.strip()
    if not trimmed:
        return ParsedProfile(profile={}, resolved=(), unresolved=())

    if len(trimmed) > NATURAL_LANGUAGE_MAX_LENGTH:
        trimmed = trimmed[:NATURAL_LANGUAGE_MAX_LENGTH]
    trimmed = _clip_tokens(trimmed)

    resolved: list[ParsedField] = []
    unresolved: list[ParsedField] = []
    consumed: set[str] = set()

    origin = _parse_origin(trimmed, consumed)
    if origin is not None:
        (resolved if origin.status == "RESOLVED" else unresolved).append(origin)

    for parser in (
        lambda: _parse_degree(trimmed),
        lambda: _parse_field(trimmed),
        lambda: _parse_funding(trimmed),
        lambda: _parse_language(trimmed),
        lambda: _parse_study_mode(trimmed),
    ):
        item = parser()
        if item is not None:
            (resolved if item.status == "RESOLVED" else unresolved).append(item)

    # A region and an explicit country list are the same field, so region wins
    # only when no explicit preference was named.
    region = _parse_region(trimmed)
    countries = _parse_countries(trimmed, origin)
    preference = region if region is not None else countries
    if preference is not None:
        (resolved if preference.status == "RESOLVED" else unresolved).append(preference)

    profile: dict = {}
    for item in resolved:
        if item.field == "language_credentials":
            existing = profile.get("language_credentials") or []
            profile["language_credentials"] = [*existing, item.value]
        else:
            profile[item.field] = item.value

    return ParsedProfile(
        profile=profile,
        resolved=tuple(resolved),
        unresolved=tuple(unresolved),
    )


def parsed_profile_response(parsed: ParsedProfile) -> dict:
    """Shape the parse result for the API.

    Returns the partial profile alongside every interpretation, resolved or not,
    so the interface can show "we understood your profile" and let the student
    correct it before anything is calculated.
    """
    return {
        "profile": parsed.profile,
        "resolved": [
            {
                "field": item.field,
                "value": item.value,
                "display": item.display,
                "source": item.source,
                "status": item.status,
                "note": item.note,
            }
            for item in parsed.resolved
        ],
        "unresolved": [
            {
                "field": item.field,
                "value": None,
                "display": item.display,
                "source": item.source,
                "status": item.status,
                "note": item.note,
            }
            for item in parsed.unresolved
        ],
        "empty": parsed.is_empty,
        "deterministic": True,
        "note": (
            "Every field above was matched against ScholarZone's own approved lists. Nothing was "
            "guessed, and you can change or remove anything before calculating."
        ),
    }


__all__ = [
    "CEFR_ORDER",
    "REGION_MEMBERS",
    "ParsedField",
    "ParsedProfile",
    "parse_natural_language_profile",
    "parsed_profile_response",
]