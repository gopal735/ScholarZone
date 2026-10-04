"""Compose the answer, deterministically, from canonical facts.

This module is the product. A language model, if one is ever enabled, would sit
behind :mod:`provider` and could only ever phrase what is decided here.

**The shape of every answer is fixed** - why this matters, what we know, what is
unknown, what to do next - because a student asking "what should I do now?" is
asking a question whose failure mode is a confident paragraph with no
provenance. Separating the known from the unknown on the face of the answer is
what makes the uncertainty legible instead of buried.

**Two rules govern the wording.**

*Unknown is never zero.* A missing deadline is not 0 days, a missing fit is not a
low fit, and an unmeasured checklist is not 0%. Absent measurements are named as
absent.

*General guidance is labelled as general guidance.* When an answer contains no
ScholarZone measurement it says so in a field of its own, so advice that is
merely sensible can never be mistaken for something the catalogue verified.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .context import MentorContext
from .evidence import EvidenceItem, collect, funding_is_unmeasured
from .guards import bound_text
from .intents import INTENT_LABELS, Intent

#: The supported list, published so the interface offers exactly these rather than
#: guessing. Mirrors ``application_states`` being published by the dashboard.
SUPPORTED_INTENTS: tuple[str, ...] = tuple(INTENT_LABELS.values())


@dataclass(frozen=True)
class AnswerSection:
    heading: str
    points: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComposedAnswer:
    """The whole answer, before it becomes a wire contract."""

    headline: str
    why: str
    known: tuple[EvidenceItem, ...] = ()
    unknown: tuple[str, ...] = ()
    next_steps: tuple = ()
    supported: bool = True
    unsupported_reason: str | None = None
    #: True when nothing in the answer is a ScholarZone measurement.
    general_guidance_only: bool = False
    caveats: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_grounded_data(self) -> bool:
        return bool(self.known)


_UNSUPPORTED_REASON = (
    "I can only answer from ScholarZone's own verified records, and I did not "
    "recognise this as something I can ground. I will not guess."
)

#: Where an unrecognised question is redirected. Chosen because each one is a
#: thing the mentor genuinely knows how to do, rather than a generic menu.
_REDIRECTS = (
    "What should I do right now?",
    "Why is a particular scholarship a good match for me?",
    "What deadlines should I care about?",
    "What should I improve in my profile?",
    "What trusted requirements do I still need to prepare?",
)


def _unknown_from_context(context: MentorContext) -> list[str]:
    """Everything the context genuinely does not know.

    Built by looking for absence, so a claim cannot slip through by omission: an
    unmeasured value appears here rather than being quietly left out of *known*.
    Absences that repeat across many records are stated once with a count, because
    eight identical lines is noise that buries the one gap the reader needed.
    """
    unknown: list[str] = []
    unestablished_funding: list[str] = []

    if not context.student.has_profile:
        unknown.append(
            "Your profile is empty, so ScholarZone cannot check any published "
            "eligibility rule against you yet."
        )
    elif context.student.strength_score is None:
        unknown.append("No profile strength has been measured yet.")

    if not context.scholarships and not context.applications:
        unknown.append(
            "No scholarship in your matched or saved list has a record ScholarZone "
            "can describe."
        )

    for item in context.scholarships:
        if not item.deadline_is_known and not item.deadline.closed:
            unknown.append(
                f"{item.name}: no published deadline ScholarZone can count down to."
            )
        if funding_is_unmeasured(item.funding):
            unestablished_funding.append(item.name)
        if not item.fit_is_measured:
            unknown.append(f"{item.name}: no fit score has been measured.")
        if item.readiness_label is None:
            unknown.append(f"{item.name}: readiness has not been assessed.")

    if len(unestablished_funding) == 1:
        unknown.append(
            f"{unestablished_funding[0]}: funding coverage has not been established "
            "from the catalogue."
        )
    elif unestablished_funding:
        unknown.append(
            f"Funding coverage has not been established from the catalogue for "
            f"{len(unestablished_funding)} of the records above."
        )

    for item in context.applications:
        if not item.progress_is_measured:
            # Careful wording. The dashboard's application list publishes no
            # progress figure, so when a question does not name a specific
            # application this context has simply not read its checklist. Saying
            # the application "has no counted checklist" would be a claim about
            # the student's record that nothing here checked - and in this very
            # product the same application can be at 40% when asked about
            # directly. What is true is that this answer does not carry it.
            unknown.append(
                f"{item.name}: checklist progress is not included in this answer; "
                "open the workspace for the counted tasks."
            )
        if not item.is_listed:
            unknown.append(
                f"{item.name}: no longer in the public catalogue, so only the "
                "record you saved when you started it is shown."
            )

    return unknown


def _why_for_intent(intent: Intent, context: MentorContext) -> str:
    """One sentence on why this question matters, built from real state."""
    kind = intent.kind

    if kind == "NEXT_ACTION":
        if context.next_actions:
            first = context.next_actions[0]
            return f"{first.title} is the highest-priority thing waiting on you."
        return "Nothing is currently waiting on you in the systems ScholarZone tracks."

    if kind in {"DEADLINE"}:
        known = [
            item
            for item in context.scholarships
            if item.deadline.has_fixed_date and not item.deadline.closed
        ]
        if known:
            soonest = min(known, key=lambda entry: entry.deadline.days_remaining or 0)
            return (
                f"{soonest.name} has the nearest published date ScholarZone can "
                f"measure: {soonest.deadline.describe()}"
            )
        return (
            "None of your tracked scholarships has a deadline ScholarZone can "
            "count down to."
        )

    if kind in {"SCHOLARSHIP_EXPLANATION", "MATCH_EXPLANATION"}:
        target = _focused_scholarship(context)
        if target is None:
            return "Name a scholarship and I can explain what ScholarZone has recorded."
        if target.fit_score is not None:
            return (
                f"{target.name} carries a fit score of {round(target.fit_score, 1)}"
                + (f" ({target.fit_label})." if target.fit_label else ".")
            )
        return (
            f"ScholarZone has not measured a fit score for {target.name}, so I will "
            "not characterise how well it matches you."
        )

    if kind == "READINESS":
        target = _focused_scholarship(context)
        if target is not None and target.readiness_label:
            return f"{target.name} reads as {target.readiness_label.lower()}."
        return "Readiness is only assessed once a profile can be checked against a record."

    if kind == "APPLICATION_PROGRESS":
        target = _focused_application(context)
        if target is None:
            return "Tell me which application and I will read its current state."
        if target.progress_is_measured:
            return (
                f"{target.name} is {target.state_label.lower()} with "
                f"{round(target.progress_percent, 1)}% of its counted tasks complete."
            )
        return (
            f"{target.name} is {target.state_label.lower()}, and it has no counted "
            "checklist, so no progress figure is available."
        )

    if kind == "PROFILE_GAPS":
        if context.student.gaps:
            return f"ScholarZone found {len(context.student.gaps)} gaps it cannot check around."
        if not context.student.has_profile:
            return "Your profile has nothing in it yet, so every published rule is unchecked."
        return "ScholarZone has not flagged a gap in your profile."

    if kind in {"SCHOLARSHIP_COMPARISON", "DECISION_SUPPORT"}:
        if len(context.scholarships) >= 2:
            return (
                f"{len(context.scholarships)} of your tracked scholarships have "
                "records ScholarZone can compare."
            )
        return "You need at least two tracked scholarships before a comparison means anything."

    if kind == "REQUIREMENT_GUIDANCE":
        unverified = [
            requirement
            for item in context.scholarships
            for requirement in item.unverified_requirements
        ]
        if unverified:
            return (
                f"{len(unverified)} published requirement(s) across your tracked "
                "scholarships are recorded as unconfirmed."
            )
        return "ScholarZone has no unconfirmed published requirements for your tracked scholarships."

    return "Here is what ScholarZone currently holds about your applications."


def _focused_scholarship(context: MentorContext):
    if context.focused_scholarship_id is not None:
        found = context.scholarship(context.focused_scholarship_id)
        if found is not None:
            return found
    return context.scholarships[0] if context.scholarships else None


def _focused_application(context: MentorContext):
    if context.focused_application_id is not None:
        found = context.application(context.focused_application_id)
        if found is not None:
            return found
    for item in context.applications:
        if not item.is_terminal:
            return item
    return context.applications[0] if context.applications else None


def _notes(intent: Intent) -> list[str]:
    notes: list[str] = []
    if intent.injection_markers:
        # Reported, not enforced. Refusing a question because it contains the
        # word "ignore" would make the mentor useless at the moment it is being
        # asked to be careful, and the answer is built from catalogue fields
        # regardless of what the message said.
        notes.append(
            "Your message contained instruction-like wording. It was treated as a "
            "question only; nothing in it could change how this answer was built."
        )
    if intent.truncated:
        notes.append("Your message was longer than the mentor reads and was shortened.")
    return notes


def compose(intent: Intent, context: MentorContext) -> ComposedAnswer:
    """Build the complete answer. Pure and deterministic."""
    notes = _notes(intent)

    if intent.unsupported:
        return ComposedAnswer(
            headline="I cannot ground that one",
            why=_UNSUPPORTED_REASON,
            unsupported_reason=_UNSUPPORTED_REASON,
            supported=False,
            general_guidance_only=True,
            next_steps=(),
            notes=tuple(notes),
        )

    if not context.has_grounded_data and not context.student.has_profile:
        return ComposedAnswer(
            headline="There is nothing to advise on yet",
            why=(
                "ScholarZone has no profile and no tracked scholarship for you, so "
                "there is no verified information to base advice on. I would rather "
                "say that than guess."
            ),
            known=(),
            unknown=(
                "Your profile is empty.",
                "You have no saved or tracked scholarships.",
            ),
            next_steps=(),
            general_guidance_only=True,
            caveats=context.caveats,
            notes=tuple(notes),
        )

    evidence = collect(context)
    unknown = _unknown_from_context(context)

    if not evidence:
        # Grounded in the student's own state but with no scholarship record to
        # cite. Still not "general guidance" - the profile facts are measured.
        return ComposedAnswer(
            headline="What ScholarZone can see right now",
            why=_why_for_intent(intent, context),
            known=(),
            unknown=tuple(unknown) or ("No record ScholarZone can describe.",),
            next_steps=tuple(context.next_actions[:3]),
            caveats=context.caveats,
            notes=tuple(notes),
        )

    headline = _why_for_intent(intent, context)
    if len(evidence) >= 10:
        headline = headline  # length note lives in caveats, not the headline

    return ComposedAnswer(
        headline=bound_text(headline, 240),
        why=bound_text(headline, 600),
        known=tuple(evidence),
        unknown=tuple(dict.fromkeys(unknown)),
        next_steps=tuple(context.next_actions[:3]),
        supported=True,
        general_guidance_only=False,
        caveats=context.caveats,
        notes=tuple(notes),
    )


def redirects() -> tuple[str, ...]:
    """The grounded questions the mentor can actually answer."""
    return _REDIRECTS