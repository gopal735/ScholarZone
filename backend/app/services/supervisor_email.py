"""Deterministic outreach drafting.

There is no language model in this path, and that is a deliberate choice rather
than a missing feature. Every sentence below is either a fixed template or a
value copied from a verified record, so a draft cannot assert something the
evidence does not support. A model in the loop would make the output
indistinguishable from a sourced one while giving it no way to check its own
claims.

The rule the templates are built around: **a missing fact is named, never
invented.** If no verified research area exists, the draft does not write "your
work in machine learning" - it omits the clause and reports the omission in
``unresolved`` so the student can write their own sentence.

Nothing here sends anything. It returns text for a student to read, edit and send
themselves.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models_supervisor import ContactTemplate, ProfessorProfile, ScholarshipProfessorLink
from .supervisor_freshness import PUBLISHABLE_AVAILABILITY_STATES
from .supervisor_status import PUBLIC_RELATIONSHIP_STATUSES

logger = logging.getLogger(__name__)

#: Bound on what a student may send in one message. Long enough to be
#: considered, short enough to be read.
MAX_SUBJECT_LENGTH = 200
MAX_BODY_LENGTH = 3500


@dataclass(frozen=True)
class Template:
    key: str
    title: str
    degree_level: str | None
    subject_hint: str
    body_text: str


#: The MVP set. Three situations, no more: a first master's approach, a first PhD
#: approach, and a follow-up after silence.
#:
#: Each body states only what the student knows and what the official page
#: says. None of them claims the recipient is recruiting, that a place exists, or
#: that funding is available, because none of those is something the evidence
#: establishes.
BUILTIN_TEMPLATES: tuple[Template, ...] = (
    Template(
        key="masters_initial",
        title="Initial master's enquiry",
        degree_level="master",
        subject_hint="Prospective master's applicant — research area enquiry",
        body_text=(
            "Dear {professor_surname},\n"
            "\n"
            "I am applying to master's programmes in {field} and am writing to ask "
            "whether you would be the right person to approach about research supervision.\n"
            "\n"
            "{research_sentence}"
            "\n"
            "What I am working towards\n"
            "{interest_sentence}\n"
            "\n"
            "The scholarship I am looking at\n"
            "{programme_sentence}\n"
            "\n"
            "I have read the faculty profile and understand you may not be taking "
            "students at present. If you are, or if you could point me to whoever "
            "is currently supervising in this area, I would be grateful for the "
            "direction.\n"
            "\n"
            "Thank you for your time.\n"
            "\n"
            "Kind regards,\n"
            "{student_name}"
        ),
    ),
    Template(
        key="phd_initial",
        title="Initial PhD enquiry",
        degree_level="phd",
        subject_hint="Prospective PhD applicant — research area enquiry",
        body_text=(
            "Dear {professor_surname},\n"
            "\n"
            "I am considering doctoral study in {field} and am writing to ask whether "
            "you would consider supervising a project in this area.\n"
            "\n"
            "{research_sentence}"
            "\n"
            "What I am working towards\n"
            "{interest_sentence}\n"
            "\n"
            "The position I am looking at\n"
            "{programme_sentence}\n"
            "\n"
            "I would be glad to send a research proposal and my academic record. If "
            "this is not the right group for this work, or if you are not recruiting "
            "supervisors at the moment, please say so and I will look elsewhere.\n"
            "\n"
            "Thank you for your time.\n"
            "\n"
            "Kind regards,\n"
            "{student_name}"
        ),
    ),
    Template(
        key="follow_up_no_response",
        title="Follow-up after no response",
        degree_level=None,
        subject_hint="Following up — previous enquiry",
        body_text=(
            "Dear {professor_surname},\n"
            "\n"
            "I wrote to you about postgraduate research supervision and am following "
            "up in case it was missed or arrived at a point you could not respond to. "
            "I understand the volume of correspondence this generates.\n"
            "\n"
            "If supervision in {field} is not possible this year, a short reply saying "
            "so would be genuinely useful, and I will not follow up again.\n"
            "\n"
            "With thanks,\n"
            "{student_name}"
        ),
    ),
)

_TEMPLATES_BY_KEY = {template.key: template for template in BUILTIN_TEMPLATES}


def get_builtin_template(key: str | None) -> Template:
    """Return the requested template, or the master's default.

    An unknown key falls back rather than raising: a stale client should get a
    usable draft, not an error page, and the response still names which template
    was actually used.
    """
    if key and key in _TEMPLATES_BY_KEY:
        return _TEMPLATES_BY_KEY[key]
    return _TEMPLATES_BY_KEY["masters_initial"]


def ensure_templates(db: Session) -> None:
    """Idempotently mirror the built-in templates into the table.

    The code above is the source of truth. The table exists so a template can
    eventually be edited without a deploy, and so an outreach record can point at
    the exact template a student used. Re-running this overwrites a template that
    was edited locally back to the built-in text, which is the safe direction:
    a stale edit is worse than a known one.
    """
    existing = {
        row.template_key: row
        for row in db.execute(select(ContactTemplate)).scalars()
    }
    for template in BUILTIN_TEMPLATES:
        row = existing.get(template.key)
        if row is None:
            db.add(
                ContactTemplate(
                    template_key=template.key,
                    title=template.title,
                    degree_level=template.degree_level,
                    subject_hint=template.subject_hint,
                    body_text=template.body_text,
                    is_active=True,
                )
            )
        else:
            row.title = template.title
            row.degree_level = template.degree_level
            row.subject_hint = template.subject_hint
            row.body_text = template.body_text
    db.commit()


@dataclass(frozen=True)
class DraftRequest:
    """Everything the drafter is allowed to use, and nothing else."""

    professor: ProfessorProfile
    programme_title: str
    degree_level: str
    relationship_type: str
    verified_availability: list[str]
    student_name: str
    student_interests: list[str]
    student_field: str | None


def build_draft(db: Session, request: DraftRequest, template: Template) -> dict:
    """Render one draft, reporting every variable it could not fill.

    ``unresolved`` names what is missing rather than leaving a gap in the prose,
    so the student learns what the system does not actually know before they
    send.
    """
    unresolved: list[str] = []
    display_name = request.professor.canonical_name.strip()
    surname = display_name.split()[-1] if display_name else ""
    if not surname:
        unresolved.append("professor_name")

    areas = [area for area in (request.professor.research_areas or []) if area]
    keywords = [word for word in (request.professor.research_keywords or []) if word]

    if areas:
        research_sentence = (
            "Your published research areas include "
            + ", ".join(areas[:3])
            + ", which is where my interest sits."
        )
    elif keywords:
        research_sentence = (
            "Your published research keywords include "
            + ", ".join(keywords[:3])
            + ", which is where my interest sits."
        )
        unresolved.append("research_areas")
    else:
        # No verified research area exists, so the sentence that would reference
        # one is omitted entirely rather than filled with a plausible guess.
        research_sentence = ""
        unresolved.append("research_areas")

    interests = [value for value in request.student_interests if value]
    if interests:
        interest_sentence = "I am particularly interested in " + ", ".join(interests[:3]) + "."
    else:
        interest_sentence = "I have not set out my research interests in full yet and would welcome your guidance on what to prioritise."
        unresolved.append("student_interests")

    field = request.student_field or request.professor.department_name
    if field:
        field_clause = field
    else:
        field_clause = request.programme_title
        unresolved.append("academic_field")

    programme_sentence = f"The programme I am looking at is {request.programme_title}."
    if request.degree_level:
        programme_sentence = f"{programme_sentence} It is a {request.degree_level} programme."

    values = {
        "professor_surname": surname or "Professor",
        "research_sentence": research_sentence,
        "interest_sentence": interest_sentence,
        "programme_sentence": programme_sentence,
        "field": field_clause,
    }

    # ScholarZone's account carries an email address and nothing else, so there is
    # no name to sign with. Rather than deriving one from the address - which would
    # put a guess in a message the student is about to send - the sign-off is left
    # as an obvious blank and reported as something the student must fill in.
    if request.student_name.strip():
        values["student_name"] = request.student_name.strip()
    else:
        values["student_name"] = "[Your name]"
        unresolved.append("student_name")

    body = template.body_text
    for key, value in values.items():
        body = body.replace("{" + key + "}", value)
    # Any placeholder the caller did not supply becomes a named gap, never a
    # literal brace pair left in the student's message.
    body = _strip_unresolved_placeholders(body, unresolved)

    subject = template.subject_hint.replace("{field}", field_clause)[:MAX_SUBJECT_LENGTH]
    body = body.strip()[:MAX_BODY_LENGTH]

    to_address = (
        request.professor.official_email
        if request.professor.official_email_verified
        else None
    )

    return {
        "subject": subject,
        "body": body,
        "unresolved": sorted(set(unresolved)),
        "template_key": template.key,
        "to_address": to_address,
    }


def _strip_unresolved_placeholders(body: str, unresolved: list[str]) -> str:
    import re

    def replace(match: "re.Match[str]") -> str:
        name = match.group(1)
        unresolved.append(name)
        return ""

    cleaned = re.sub(r"\{([a-z_]+)\}", replace, body)
    # A sentence left empty by a removed clause reads badly, so collapse the
    # blank lines it leaves behind.
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def list_templates(db: Session) -> list[ContactTemplate]:
    ensure_templates(db)
    return list(
        db.execute(
            select(ContactTemplate).where(ContactTemplate.is_active.is_(True)).order_by(ContactTemplate.id)
        ).scalars()
    )


def verified_relationship(
    db: Session, scholarship_id: int, professor_id: int
) -> ScholarshipProfessorLink | None:
    return db.execute(
        select(ScholarshipProfessorLink).where(
            ScholarshipProfessorLink.scholarship_id == scholarship_id,
            ScholarshipProfessorLink.professor_id == professor_id,
            ScholarshipProfessorLink.verification_status.in_(PUBLIC_RELATIONSHIP_STATUSES),
        )
    ).scalar_one_or_none()


def publishable_availability_states(db: Session, professor_id: int) -> list[str]:
    """Return only availability states that may be quoted to a recipient.

    Never used to assert anything in the draft itself; exposed so the UI can show
    what is known without restating it in an outgoing message.
    """
    from ..models_supervisor import ProfessorAvailability

    rows = db.execute(
        select(ProfessorAvailability.state).where(ProfessorAvailability.professor_id == professor_id)
    ).scalars()
    return [state for state in rows if state in PUBLISHABLE_AVAILABILITY_STATES]


__all__ = [
    "BUILTIN_TEMPLATES",
    "MAX_BODY_LENGTH",
    "MAX_SUBJECT_LENGTH",
    "DraftRequest",
    "Template",
    "build_draft",
    "ensure_templates",
    "get_builtin_template",
    "list_templates",
    "publishable_availability_states",
    "verified_relationship",
]