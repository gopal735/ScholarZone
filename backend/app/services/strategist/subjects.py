"""The three launch subjects for the Study-to-Career Strategist.

Subject keys reuse the existing Match taxonomy's canonical field names
(``app.services.matching.taxonomy.CANONICAL_FIELDS``) so that scholarship → subject
linking and subject selection share one vocabulary with the rest of the product.

A subject only produces *subject-level* career data through the verified
occupation-salary layer. The occupation mapping here is what a verified cell
attaches to; where no occupation-level figure exists the strategist reports
"Insufficient data" and never falls back to a country career average. That
reduction of ambition is the honest one and is documented per country in
``docs/strategist/RESEARCH_REPORT.md``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Subject:
    key: str
    name_en: str
    name_bn: str
    #: Canonical field keys in the Match taxonomy this subject spans. Used to link
    #: scholarships to the subject only when the scholarship record resolves to one
    #: of these (never assumed).
    taxonomy_fields: tuple[str, ...]
    #: Occupation slug the verified occupation-salary layer is keyed by.
    occupation_slug: str
    coverage_note_en: str


SUBJECTS: tuple[Subject, ...] = (
    Subject(
        key="computer_science",
        name_en="Computer Science / AI",
        name_bn="কম্পিউটার সায়েন্স / এআই",
        taxonomy_fields=("computer_science", "software_engineering"),
        occupation_slug="software_developer",
        coverage_note_en=(
            "Occupation-level pay is officially sourced in the US, Canada, "
            "Germany and Australia; other launch countries show 'Insufficient "
            "data' rather than a country average."
        ),
    ),
    Subject(
        key="data_science",
        name_en="Data Science",
        name_bn="ডেটা সায়েন্স",
        taxonomy_fields=("data_science",),
        occupation_slug="data_scientist",
        coverage_note_en=(
            "Official occupation-level pay is sourced in the US and Canada only; "
            "elsewhere it is 'Insufficient data'. Data roles vary widely by title."
        ),
    ),
    Subject(
        key="civil_engineering",
        name_en="Civil Engineering",
        name_bn="সিভিল ইঞ্জিনিয়ারিং",
        taxonomy_fields=("civil_engineering",),
        occupation_slug="civil_engineer",
        coverage_note_en=(
            "Occupation-level pay is officially sourced in the US, Canada, "
            "Germany and Australia; elsewhere 'Insufficient data'."
        ),
    ),
)


def get_subject(key: str) -> Subject | None:
    normalised = (key or "").strip().lower()
    for subject in SUBJECTS:
        if subject.key == normalised:
            return subject
    return None


def subject_keys() -> tuple[str, ...]:
    return tuple(subject.key for subject in SUBJECTS)


__all__ = ["Subject", "SUBJECTS", "get_subject", "subject_keys"]
