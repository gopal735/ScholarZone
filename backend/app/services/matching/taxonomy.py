"""A controlled programme/field taxonomy.

The catalogue does not store a normalised subject. It stores free text in
``program_type`` and ``degree``, written by the research pipeline in whatever
wording the awarding body used. Scoring that text with keyword overlap produces a
number nobody can audit and that changes the moment a page is reworded.

So the mapping is made explicit instead. A canonical field is defined here
together with the aliases that resolve to it and the relationships between
fields, and every resolution records which alias matched and in which column.
Two consequences follow:

* A field that resolves to nothing is UNKNOWN, and its weight is redistributed.
  It is never scored as an unrelated field.
* Two fields only score 0 against each other when this table says they are
  unrelated. Absence of an entry is UNKNOWN, not zero.

The alias lists are a curated mapping, versioned with
``FIELD_TAXONOMY_VERSION``. Adding a field is a reviewed edit to this file plus
a test, not a change to a scorer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .constants import (
    FIELD_RELATIONSHIP_BROAD,
    FIELD_RELATIONSHIP_CLOSE,
    FIELD_RELATIONSHIP_EXACT,
    FIELD_RELATIONSHIP_LEVELS,
    FIELD_RELATIONSHIP_RELATED,
    FIELD_RELATIONSHIP_UNRELATED,
)
from .normalize import normalise_text


@dataclass(frozen=True)
class CanonicalField:
    """One field in the taxonomy."""

    key: str
    label: str
    #: Fields that are the same discipline under a different name.
    close: tuple[str, ...] = ()
    #: Adjacent disciplines that share substantial subject content.
    related: tuple[str, ...] = ()
    #: The parent discipline, when one exists.
    broad: str | None = None
    #: Lower-case aliases that resolve to this key. Matched on word boundaries.
    aliases: tuple[str, ...] = ()


#: The taxonomy. Order is irrelevant to scoring; the relationship tuples are
#: what matter.
CANONICAL_FIELDS: tuple[CanonicalField, ...] = (
    CanonicalField(
        key="computer_science",
        label="Computer Science",
        close=("software_engineering", "computer_engineering"),
        related=("mathematics", "statistics", "electrical_engineering", "information_science"),
        broad="engineering",
        aliases=(
            "computer science",
            "computerscience",
            "computing",
            "computing science",
            "informatics",
            "cs",
        ),
    ),
    CanonicalField(
        key="software_engineering",
        label="Software Engineering",
        close=("computer_science", "computer_engineering"),
        related=("information_science", "electrical_engineering"),
        broad="engineering",
        aliases=("software engineering", "software development", "software systems"),
    ),
    CanonicalField(
        key="computer_engineering",
        label="Computer Engineering",
        close=("computer_science", "software_engineering"),
        related=("electrical_engineering", "information_science"),
        broad="engineering",
        aliases=("computer engineering",),
    ),
    CanonicalField(
        key="information_science",
        label="Information Science",
        close=("computer_science", "software_engineering"),
        related=("statistics", "mathematics", "library_science"),
        broad=None,
        aliases=("information science", "informatics science", "information systems"),
    ),
    CanonicalField(
        key="electrical_engineering",
        label="Electrical Engineering",
        close=("computer_engineering",),
        related=("computer_science", "mechanical_engineering", "engineering"),
        broad="engineering",
        aliases=("electrical engineering", "electronics engineering", "electronic engineering"),
    ),
    CanonicalField(
        key="mechanical_engineering",
        label="Mechanical Engineering",
        close=(),
        related=("electrical_engineering", "aerospace_engineering", "civil_engineering"),
        broad="engineering",
        aliases=("mechanical engineering", "mechatronics"),
    ),
    CanonicalField(
        key="civil_engineering",
        label="Civil Engineering",
        close=(),
        related=("mechanical_engineering", "environmental_science", "architecture"),
        broad="engineering",
        aliases=("civil engineering",),
    ),
    CanonicalField(
        key="aerospace_engineering",
        label="Aerospace Engineering",
        close=("mechanical_engineering",),
        related=("mechanical_engineering", "electrical_engineering"),
        broad="engineering",
        aliases=("aerospace engineering", "aeronautical engineering", "aviation engineering"),
    ),
    CanonicalField(
        key="engineering",
        label="Engineering",
        close=("civil_engineering", "mechanical_engineering", "electrical_engineering"),
        related=("computer_science", "science", "mathematics"),
        broad=None,
        aliases=("engineering",),
    ),
    CanonicalField(
        key="mathematics",
        label="Mathematics",
        close=("statistics",),
        related=("computer_science", "science", "physics"),
        broad="science",
        aliases=("mathematics", "mathematical sciences", "pure mathematics"),
    ),
    CanonicalField(
        key="statistics",
        label="Statistics",
        close=("mathematics",),
        related=("data_science", "computer_science", "actuarial_science"),
        broad="science",
        aliases=("statistics", "statistical sciences", "biostatistics"),
    ),
    CanonicalField(
        key="data_science",
        label="Data Science",
        close=("statistics", "information_science"),
        related=("computer_science", "mathematics"),
        broad="science",
        aliases=("data science", "data analytics", "machine learning"),
    ),
    CanonicalField(
        key="science",
        label="Natural Sciences",
        close=("physics", "chemistry", "biology"),
        related=("mathematics", "engineering"),
        broad=None,
        aliases=("science", "natural science", "natural sciences"),
    ),
    CanonicalField(
        key="physics",
        label="Physics",
        close=(),
        related=("science", "mathematics", "astronomy"),
        broad="science",
        aliases=("physics",),
    ),
    CanonicalField(
        key="chemistry",
        label="Chemistry",
        close=(),
        related=("science", "biochemistry"),
        broad="science",
        aliases=("chemistry",),
    ),
    CanonicalField(
        key="biology",
        label="Biology",
        close=(),
        related=("biochemistry", "environmental_science", "science"),
        broad="science",
        aliases=("biology", "biological sciences", "life sciences"),
    ),
    CanonicalField(
        key="biochemistry",
        label="Biochemistry",
        close=("chemistry",),
        related=("biology", "science"),
        broad="science",
        aliases=("biochemistry", "molecular biology"),
    ),
    CanonicalField(
        key="environmental_science",
        label="Environmental Science",
        close=(),
        related=("biology", "civil_engineering", "science"),
        broad="science",
        aliases=("environmental science", "environmental studies", "ecology"),
    ),
    CanonicalField(
        key="astronomy",
        label="Astronomy",
        close=("physics",),
        related=("physics", "science"),
        broad="science",
        aliases=("astronomy", "astrophysics", "space science"),
    ),
    CanonicalField(
        key="medicine",
        label="Medicine",
        close=("nursing", "public_health"),
        related=("biology", "health_sciences"),
        broad="health_sciences",
        aliases=("medicine", "medical sciences", "clinical medicine", "mbbs"),
    ),
    CanonicalField(
        key="nursing",
        label="Nursing",
        close=("public_health",),
        related=("medicine", "health_sciences"),
        broad="health_sciences",
        aliases=("nursing",),
    ),
    CanonicalField(
        key="public_health",
        label="Public Health",
        close=("nursing",),
        related=("medicine", "health_sciences"),
        broad="health_sciences",
        aliases=("public health", "epidemiology", "community health"),
    ),
    CanonicalField(
        key="health_sciences",
        label="Health Sciences",
        close=("medicine", "nursing", "public_health"),
        related=("biology",),
        broad=None,
        aliases=("health sciences", "health science", "allied health"),
    ),
    CanonicalField(
        key="law",
        label="Law",
        close=("legal_studies",),
        related=("public_policy", "social_sciences"),
        broad="social_sciences",
        aliases=("law", "jurisprudence", "llb"),
    ),
    CanonicalField(
        key="legal_studies",
        label="Legal Studies",
        close=("law",),
        related=("public_policy",),
        broad="social_sciences",
        aliases=("legal studies",),
    ),
    CanonicalField(
        key="business",
        label="Business and Management",
        close=("management", "economics", "finance"),
        related=("social_sciences", "public_policy"),
        broad=None,
        aliases=(
            "business",
            "business administration",
            "business and management",
            "mba",
            "management",
            "commerce",
        ),
    ),
    CanonicalField(
        key="management",
        label="Management",
        close=("business",),
        related=("economics", "finance"),
        broad="business",
        aliases=(
            "organisational management",
            "organizational management",
            "managerial studies",
            "management studies",
        ),
    ),
    CanonicalField(
        key="finance",
        label="Finance",
        close=("economics", "accounting"),
        related=("business", "management"),
        broad="business",
        aliases=("finance", "financial management", "banking"),
    ),
    CanonicalField(
        key="accounting",
        label="Accounting",
        close=("finance",),
        related=("business",),
        broad="business",
        aliases=("accounting", "accountancy"),
    ),
    CanonicalField(
        key="economics",
        label="Economics",
        close=("finance", "management"),
        related=("business", "social_sciences", "political_science"),
        broad="social_sciences",
        aliases=("economics", "econometrics"),
    ),
    CanonicalField(
        key="political_science",
        label="Political Science",
        close=("public_policy",),
        related=("international_relations", "economics", "social_sciences"),
        broad="social_sciences",
        aliases=("political science", "politics", "political studies"),
    ),
    CanonicalField(
        key="international_relations",
        label="International Relations",
        close=("political_science",),
        related=("public_policy", "social_sciences"),
        broad="social_sciences",
        aliases=("international relations", "international studies", "diplomacy"),
    ),
    CanonicalField(
        key="public_policy",
        label="Public Policy",
        close=("political_science",),
        related=("international_relations", "social_sciences", "economics"),
        broad="social_sciences",
        aliases=("public policy", "public administration", "policy studies"),
    ),
    CanonicalField(
        key="social_sciences",
        label="Social Sciences",
        close=("sociology", "anthropology", "psychology"),
        related=("economics", "political_science", "education"),
        broad=None,
        aliases=("social science", "social sciences", "social studies"),
    ),
    CanonicalField(
        key="sociology",
        label="Sociology",
        close=("anthropology",),
        related=("social_sciences", "psychology"),
        broad="social_sciences",
        aliases=("sociology",),
    ),
    CanonicalField(
        key="anthropology",
        label="Anthropology",
        close=("sociology",),
        related=("social_sciences", "archaeology"),
        broad="social_sciences",
        aliases=("anthropology",),
    ),
    CanonicalField(
        key="psychology",
        label="Psychology",
        close=("counselling",),
        related=("social_sciences", "education", "health_sciences"),
        broad="social_sciences",
        aliases=("psychology", "psychological science"),
    ),
    CanonicalField(
        key="counselling",
        label="Counselling",
        close=("psychology",),
        related=("education", "social_sciences"),
        broad="social_sciences",
        aliases=("counselling", "counseling", "psychotherapy"),
    ),
    CanonicalField(
        key="education",
        label="Education",
        close=("teaching",),
        related=("social_sciences", "psychology"),
        broad=None,
        aliases=(
            "education",
            "education studies",
            "pedagogy",
            "educational leadership",
            "educational studies",
            "educational policy",
        ),
    ),
    CanonicalField(
        key="teaching",
        label="Teaching",
        close=("education",),
        related=("education",),
        broad="education",
        aliases=("teaching", "teacher education", "teaching methodology"),
    ),
    CanonicalField(
        key="history",
        label="History",
        close=("archaeology",),
        related=("humanities", "international_relations"),
        broad="humanities",
        aliases=("history", "historical studies"),
    ),
    CanonicalField(
        key="archaeology",
        label="Archaeology",
        close=("history",),
        related=("anthropology", "humanities"),
        broad="humanities",
        aliases=("archaeology", "archeology"),
    ),
    CanonicalField(
        key="philosophy",
        label="Philosophy",
        close=("religious_studies",),
        related=("humanities", "social_sciences"),
        broad="humanities",
        aliases=("philosophy",),
    ),
    CanonicalField(
        key="religious_studies",
        label="Religious Studies",
        close=("philosophy",),
        related=("humanities", "anthropology"),
        broad="humanities",
        aliases=("religious studies", "theology", "islamic studies"),
    ),
    CanonicalField(
        key="languages",
        label="Languages and Linguistics",
        close=("translation",),
        related=("education", "humanities"),
        broad="humanities",
        aliases=(
            "languages",
            "linguistics",
            "language studies",
            "applied linguistics",
            "modern languages",
        ),
    ),
    CanonicalField(
        key="translation",
        label="Translation and Interpreting",
        close=("languages",),
        related=("humanities",),
        broad="languages",
        aliases=("translation", "interpreting", "translation studies"),
    ),
    CanonicalField(
        key="humanities",
        label="Arts and Humanities",
        close=("history", "philosophy", "languages", "literature"),
        related=("social_sciences", "education"),
        broad=None,
        aliases=("humanities", "arts and humanities", "liberal arts", "arts"),
    ),
    CanonicalField(
        key="literature",
        label="Literature",
        close=("languages",),
        related=("humanities",),
        broad="humanities",
        aliases=("literature", "literary studies", "english literature"),
    ),
    CanonicalField(
        key="arts",
        label="Arts and Creative Practice",
        close=("design", "music", "film"),
        related=("humanities",),
        broad=None,
        aliases=(
            "fine arts",
            "creative arts",
            "visual arts",
            "performing arts",
            "applied arts",
        ),
    ),
    CanonicalField(
        key="design",
        label="Design",
        close=("arts", "architecture"),
        related=("arts", "architecture"),
        broad="arts",
        aliases=("design", "graphic design", "product design", "industrial design"),
    ),
    CanonicalField(
        key="architecture",
        label="Architecture",
        close=("design",),
        related=("arts", "civil_engineering", "urban_planning"),
        broad="arts",
        aliases=("architecture", "architectural studies"),
    ),
    CanonicalField(
        key="urban_planning",
        label="Urban Planning",
        close=("architecture",),
        related=("civil_engineering", "public_policy"),
        broad=None,
        aliases=("urban planning", "town planning", "spatial planning"),
    ),
    CanonicalField(
        key="music",
        label="Music",
        close=("arts",),
        related=("humanities",),
        broad="arts",
        aliases=("music", "musicology", "performing music"),
    ),
    CanonicalField(
        key="film",
        label="Film and Media",
        close=("arts", "media_studies"),
        related=("humanities",),
        broad="arts",
        aliases=("film", "film studies", "cinema", "television"),
    ),
    CanonicalField(
        key="media_studies",
        label="Media and Communication",
        close=("film",),
        related=("humanities", "social_sciences"),
        broad="arts",
        aliases=(
            "media studies",
            "media and communication",
            "communication",
            "journalism",
            "mass communication",
        ),
    ),
    CanonicalField(
        key="agriculture",
        label="Agriculture",
        close=("food_science",),
        related=("environmental_science", "biology"),
        broad="science",
        aliases=("agriculture", "agricultural science", "agronomy"),
    ),
    CanonicalField(
        key="food_science",
        label="Food Science and Nutrition",
        close=("agriculture",),
        related=("health_sciences", "biology"),
        broad="science",
        aliases=("food science", "nutrition", "nutrition and dietetics", "dietetics"),
    ),
    CanonicalField(
        key="actuarial_science",
        label="Actuarial Science",
        close=("statistics", "finance"),
        related=("mathematics", "economics"),
        broad="science",
        aliases=("actuarial science", "actuarial studies"),
    ),
    CanonicalField(
        key="library_science",
        label="Information and Library Science",
        close=("information_science",),
        related=("humanities", "education"),
        broad="humanities",
        aliases=("library science", "information studies", "library and information science"),
    ),
)

FIELDS_BY_KEY: dict[str, CanonicalField] = {field.key: field for field in CANONICAL_FIELDS}


@dataclass(frozen=True)
class FieldResolution:
    """The outcome of resolving one free-text string to a canonical field."""

    key: str | None
    label: str | None
    #: The alias that matched, so a reviewer can see why this field was chosen.
    matched_alias: str | None
    #: Which column the resolution came from, e.g. ``program_type``.
    source_field: str | None


UNRESOLVED = FieldResolution(key=None, label=None, matched_alias=None, source_field=None)


def _alias_pattern(alias: str) -> re.Pattern[str]:
    """Match an alias on word boundaries so 'cs' does not match 'scholarship'."""
    return re.compile(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", re.IGNORECASE)


#: Pre-compiled alias patterns, longest alias first so "computer science" is
#: preferred over a bare "cs" wherever both appear. Each entry keeps the
#: canonical key alongside the alias, because the alias is what matched the text
#: and the key is what the taxonomy is indexed by.
_ALIAS_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = tuple(
    sorted(
        (
            (field.key, alias, _alias_pattern(alias))
            for field in CANONICAL_FIELDS
            for alias in field.aliases
        ),
        key=lambda item: len(item[1]),
        reverse=True,
    )
)


def resolve_field(value: str | None, source_field: str | None = None) -> FieldResolution:
    """Resolve free text to a canonical field using only the curated aliases.

    Returns ``UNRESOLVED`` when nothing matches. Unresolved is a real state: it
    drives an UNKNOWN component, never an UNRELATED score, because a taxonomy
    that silently declares every unknown programme unrelated would punish a
    student for a gap in our table rather than in their profile.
    """
    text = normalise_text(value)
    if not text:
        return UNRESOLVED

    for field_key, alias, pattern in _ALIAS_PATTERNS:
        if pattern.search(text):
            return FieldResolution(
                key=field_key,
                label=FIELDS_BY_KEY[field_key].label,
                matched_alias=alias,
                source_field=source_field,
            )
    return UNRESOLVED


def resolve_field_by_key(key: str | None) -> FieldResolution:
    """Resolve an already-canonical key or label to a canonical field."""
    if not key:
        return UNRESOLVED
    normalised = normalise_text(key)
    if normalised in FIELDS_BY_KEY:
        return FieldResolution(
            key=normalised,
            label=FIELDS_BY_KEY[normalised].label,
            matched_alias=normalised,
            source_field="canonical",
        )
    return resolve_field(key, source_field="canonical")


def resolve_scholarship_field(facts) -> FieldResolution:
    """Resolve the field a scholarship is actually for.

    ``program_type`` is checked first because it is the field the research
    pipeline writes the programme into. ``official_details`` keys are checked
    next, then ``degree``. Nothing else is consulted: a description or a title
    is prose, and scoring prose is how a catalogue starts claiming a
    scholarship is for a subject it never said.
    """
    candidates = (
        (facts.program_type, "program_type"),
        (facts.degree_levels, "degree"),
    )
    official_details = facts.official_details or {}
    detail_candidates: list[tuple[str, str]] = []
    for detail_key in ("field", "fields", "subject", "subjects", "programme_field", "discipline"):
        detail_value = official_details.get(detail_key)
        if isinstance(detail_value, str):
            detail_candidates.append((detail_value, f"official_details.{detail_key}"))
        elif isinstance(detail_value, list):
            for item in detail_value:
                if isinstance(item, str):
                    detail_candidates.append((item, f"official_details.{detail_key}"))

    # program_type first, then official_details, then degree. The order is the
    # one documented above and it is load-bearing: program_type is the curated
    # column the research pipeline writes the programme into, so it outranks the
    # free-form official_details blob. Reading official_details first let a
    # stale JSON value override the structured column and score a record against
    # a programme the pipeline had already corrected.
    candidates = candidates + tuple(detail_candidates)

    for value, source in candidates:
        resolution = resolve_field(value, source_field=source)
        if resolution.key is not None:
            return resolution
    return UNRESOLVED


@dataclass(frozen=True)
class FieldRelationship:
    """How closely two canonical fields correspond."""

    level: str
    score: float
    detail: str


def relate_fields(student_key: str, scholarship_key: str) -> FieldRelationship:
    """Score the relationship between two canonical fields.

    Order of lookup, most specific first:

    ``EXACT``               identical keys
    ``CLOSE_SPECIALIZATION`` one field lists the other as a close sibling
    ``RELATED_FIELD``        one field lists the other as related
    ``BROAD_FIELD``          one field's broad parent is the other
    ``UNRELATED``            both known and nothing above applies

    A known field against an unresolved one is not UNRELATED. It is unknown, and
    the caller turns that into a NOT_EVALUATED component.
    """
    if student_key == scholarship_key:
        return FieldRelationship(
            level="EXACT",
            score=FIELD_RELATIONSHIP_EXACT,
            detail="Your field matches the published programme field.",
        )

    student = FIELDS_BY_KEY.get(student_key)
    scholarship = FIELDS_BY_KEY.get(scholarship_key)
    if student is None or scholarship is None:
        return FieldRelationship(level="UNRELATED", score=FIELD_RELATIONSHIP_UNRELATED, detail="")

    if scholarship.key in student.close or student.key in scholarship.close:
        return FieldRelationship(
            level="CLOSE_SPECIALIZATION",
            score=FIELD_RELATIONSHIP_CLOSE,
            detail="Your field is a close specialization of the published programme field.",
        )

    if scholarship.key in student.related or student.key in scholarship.related:
        return FieldRelationship(
            level="RELATED_FIELD",
            score=FIELD_RELATIONSHIP_RELATED,
            detail="Your field is related to the published programme field.",
        )

    if student.broad is not None and student.broad == scholarship.key:
        return FieldRelationship(
            level="BROAD_FIELD",
            score=FIELD_RELATIONSHIP_BROAD,
            detail="Your field is a specialization of the published programme field.",
        )
    if scholarship.broad is not None and scholarship.broad == student.key:
        return FieldRelationship(
            level="BROAD_FIELD",
            score=FIELD_RELATIONSHIP_BROAD,
            detail="The published programme field is a specialization of your field.",
        )

    return FieldRelationship(
        level="UNRELATED",
        score=FIELD_RELATIONSHIP_UNRELATED,
        detail="Your field and the published programme field are different disciplines.",
    )


def known_field_keys() -> tuple[str, ...]:
    """Every canonical key. Used by the profile form's field picker."""
    return tuple(field.key for field in CANONICAL_FIELDS)


def all_relationship_levels() -> dict[str, float]:
    """The scoring table for relationship levels, for the transparency panel."""
    return dict(FIELD_RELATIONSHIP_LEVELS)