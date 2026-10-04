"""Vocabulary and legal transitions for supervisor discovery.

Every state a professor, a professor-scholarship relationship, a coverage row or
an outreach record can hold is defined here, once, so the discovery worker, the
public API, the outreach API and the tests cannot drift into disagreeing about
what a value means.

The vocabulary exists because the honest answer is usually "we do not know".
``ImageEvaluationStatus`` made the same argument for images: a single success
timestamp cannot distinguish "we looked and found nothing" from "we never
looked", so an evaluated-but-empty record and an unexamined record would be
stored identically. Coverage does the same thing for supervisors, and a count of
zero is a real result that has to be distinguishable from an unfinished search.
"""

from __future__ import annotations

from enum import StrEnum


class SupervisorCoverageStatus(StrEnum):
    """The discovery state of exactly one scholarship.

    This is not a quality score and not a count. It answers one question: what
    does ScholarZone actually know about supervisors for this programme?
    """

    #: No discovery run has examined this scholarship yet. The default for a
    #: freshly created coverage row, and the only state that asserts nothing.
    SEARCH_PENDING = "search_pending"
    #: At least one professor relationship is verified against an official
    #: source and is public.
    VERIFIED_SUPERVISORS = "verified_supervisors"
    #: Discovery completed and established no qualifying relationship. This is a
    #: true negative about what was published, NOT a claim that the university
    #: has no professors, and NOT a claim that no professor exists.
    NO_VERIFIED_SUPERVISOR_FOUND = "no_verified_supervisor_found"
    #: The record cannot have supervisors by nature - a funding award with no
    #: supervising institution or degree programme attached. Distinct from a
    #: failed search.
    NOT_APPLICABLE = "not_applicable"
    #: A relationship was found but rests on secondary evidence only, so it is
    #: withheld from the public response until an official page confirms it.
    NEEDS_VERIFICATION = "needs_verification"
    #: The official source refused or could not be read. Retryable, and
    #: deliberately never reported as "no supervisors exist".
    SOURCE_BLOCKED = "source_blocked"
    #: The official source was reached and read, but it renders its content with
    #: JavaScript, so the served HTML contains no people for us to read.
    #:
    #: This is an extension beyond the original six states, and it exists because
    #: the alternative is a lie. The real-world pilot found that every reachable
    #: page of a major university directory serves a JavaScript shell: a text to
    #: markup ratio of 0.026 to 0.039 and no person links at all. Recording that as
    #: ``no_verified_supervisor_found`` would assert that the university published
    #: no faculty, when what is actually true is that ScholarZone cannot read the
    #: page yet. A distinct state keeps "we looked and it was empty" separable
    #: from "we looked and could not read it".
    SOURCE_REQUIRES_RENDERING = "source_requires_rendering"


#: States in which no supervisor may be shown publicly, whatever the count says.
NON_PUBLISHING_COVERAGE_STATUSES: frozenset[str] = frozenset(
    {
        SupervisorCoverageStatus.SEARCH_PENDING,
        SupervisorCoverageStatus.NOT_APPLICABLE,
        SupervisorCoverageStatus.NEEDS_VERIFICATION,
        SupervisorCoverageStatus.SOURCE_BLOCKED,
        SupervisorCoverageStatus.SOURCE_REQUIRES_RENDERING,
    }
)

#: States meaning "we could not complete a conclusive search", as opposed to
#: "we completed one and it was empty". Rendering is grouped with the access
#: failures rather than with the true negatives, because a reader shown one of
#: these should assume a retry could change the answer.
INCONCLUSIVE_COVERAGE_STATUSES: frozenset[str] = frozenset(
    {
        SupervisorCoverageStatus.SEARCH_PENDING,
        SupervisorCoverageStatus.SOURCE_BLOCKED,
        SupervisorCoverageStatus.SOURCE_REQUIRES_RENDERING,
        SupervisorCoverageStatus.NEEDS_VERIFICATION,
    }
)


class CoverageEvidenceState(StrEnum):
    """How far the provenance chain for a coverage row was built."""

    NOT_COLLECTED = "not_collected"
    PARTIAL = "partial"
    COMPLETE = "complete"


class ProfessorProfileStatus(StrEnum):
    """Lifecycle of a reusable professor entity.

    A professor is never deleted for leaving one scholarship's catalogue. Their
    relationships are historical facts about published pages, and the outreach
    and application rows that reference them must keep resolving.
    """

    ACTIVE = "active"
    RETIRED = "retired"
    MERGED = "merged"


class ProfessorRelationshipType(StrEnum):
    """Why a professor is connected to a scholarship.

    There is deliberately no ``SUPERVISOR``. Nothing on a public faculty page
    establishes that a named person supervises a particular scholarship, so the
    strongest wording the evidence can carry is "potential".
    """

    #: Research-relevant faculty at the institution that awards the programme.
    #: The relationship the product actually offers.
    POTENTIAL_SUPERVISOR = "potential_supervisor"
    #: Faculty of the department that hosts the programme.
    PROGRAM_FACULTY = "program_faculty"
    #: Member of a lab or research group linked from the official programme page.
    RESEARCH_GROUP = "research_group"
    #: Faculty elsewhere at the same institution, relevant by research area.
    PROGRAM_RELEVANT_FACULTY = "program_relevant_faculty"


class RelationshipVerificationStatus(StrEnum):
    """Whether the link's provenance was confirmed against an official source."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    #: Evidence was read and did not support the claimed relationship.
    REJECTED = "rejected"
    #: Was verified once, but the source has not been re-read inside the
    #: freshness window. Kept, but never presented as current.
    STALE = "stale"


#: The only relationship status that may reach a public response.
PUBLIC_RELATIONSHIP_STATUSES: frozenset[str] = frozenset(
    {RelationshipVerificationStatus.VERIFIED}
)


class SourceType(StrEnum):
    """What kind of page a piece of evidence came from.

    The distinction that matters is authoritative versus supporting. A secondary
    source may help find a person; it may never be the reason a relationship is
    published.
    """

    OFFICIAL_UNIVERSITY_PROFILE = "official_university_profile"
    OFFICIAL_DEPARTMENT_PAGE = "official_department_page"
    OFFICIAL_RESEARCH_GROUP = "official_research_group"
    OFFICIAL_PROGRAMME_PAGE = "official_programme_page"
    OFFICIAL_INSTITUTION_DOMAIN = "official_institution_domain"

    #: Discovery aids only. Never sufficient to publish a relationship.
    SECONDARY_AGGREGATOR = "secondary_aggregator"


AUTHORITATIVE_SOURCE_TYPES: frozenset[str] = frozenset(
    {
        SourceType.OFFICIAL_UNIVERSITY_PROFILE,
        SourceType.OFFICIAL_DEPARTMENT_PAGE,
        SourceType.OFFICIAL_RESEARCH_GROUP,
        SourceType.OFFICIAL_PROGRAMME_PAGE,
        SourceType.OFFICIAL_INSTITUTION_DOMAIN,
    }
)


class AvailabilityScope(StrEnum):
    """Which question an availability claim answers.

    Kept separate because a page that says "I supervise master's students" says
    nothing about PhD places, funding, or whether either is open this year.
    """

    MASTERS_SUPERVISION = "masters_supervision"
    PHD_SUPERVISION = "phd_supervision"
    POSTDOC_SUPERVISION = "postdoc_supervision"
    FUNDING = "funding"


class AvailabilityState(StrEnum):
    """An availability answer, including the two honest non-answers.

    There is no ``True`` default and no "likely". A faculty page that does not
    mention funding is ``NOT_PUBLISHED``, which is a different fact from
    ``VERIFIED_NO`` and both differ from ``UNKNOWN``.
    """

    VERIFIED_YES = "verified_yes"
    VERIFIED_NO = "verified_no"
    #: No evidence either way, and no evidence that the question was asked.
    UNKNOWN = "unknown"
    #: The source was read and does not publish an answer.
    NOT_PUBLISHED = "not_published"
    #: The claim was once verified and the freshness window has since passed.
    STALE = "stale"


#: The only availability state that may be shown as a live answer. Everything
#: else renders as an explicit absence, never as a quiet "no".
PUBLISHABLE_AVAILABILITY_STATES: frozenset[str] = frozenset(
    {AvailabilityState.VERIFIED_YES, AvailabilityState.VERIFIED_NO}
)


class ResearchAlignmentBand(StrEnum):
    """Overlap between stated interests and verified research areas.

    Not a score, not a probability, and never an admission chance. It reports
    only whether the student's own words overlap a professor's published areas.
    """

    STRONG_RESEARCH_ALIGNMENT = "strong_research_alignment"
    MODERATE_RESEARCH_ALIGNMENT = "moderate_research_alignment"
    RELATED = "related"
    #: No explicit student interest was supplied, or no verified faculty area
    #: exists to compare against. This is the default and it is correct.
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class OutreachStatus(StrEnum):
    """The single outreach state machine.

    One machine, not one per surface. An outreach record and an application are
    separate concepts with separate lifecycles; this enum governs only the
    first.
    """

    NOT_CONTACTED = "not_contacted"
    DRAFT = "draft"
    SENT = "sent"
    FOLLOW_UP_DUE = "follow_up_due"
    REPLIED = "replied"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NO_RESPONSE = "no_response"
    CLOSED = "closed"


#: The only permitted transitions. Anything absent here is rejected with 422
#: rather than silently applied, so two clients cannot invent divergent states.
OUTREACH_TRANSITIONS: dict[str, frozenset[str]] = {
    OutreachStatus.NOT_CONTACTED: frozenset(
        {OutreachStatus.DRAFT, OutreachStatus.SENT, OutreachStatus.CLOSED}
    ),
    OutreachStatus.DRAFT: frozenset(
        {OutreachStatus.SENT, OutreachStatus.NOT_CONTACTED, OutreachStatus.CLOSED}
    ),
    OutreachStatus.SENT: frozenset(
        {
            OutreachStatus.FOLLOW_UP_DUE,
            OutreachStatus.REPLIED,
            OutreachStatus.NO_RESPONSE,
            OutreachStatus.CLOSED,
        }
    ),
    OutreachStatus.FOLLOW_UP_DUE: frozenset(
        {
            OutreachStatus.REPLIED,
            OutreachStatus.NO_RESPONSE,
            OutreachStatus.FOLLOW_UP_DUE,
            OutreachStatus.CLOSED,
        }
    ),
    OutreachStatus.REPLIED: frozenset(
        {
            OutreachStatus.POSITIVE,
            OutreachStatus.NEGATIVE,
            OutreachStatus.CLOSED,
        }
    ),
    # A reply may become positive or negative, and may be re-marked while the
    # student is still reading it. Neither direction is one-way, because the
    # student is the one recording it.
    OutreachStatus.POSITIVE: frozenset(
        {OutreachStatus.REPLIED, OutreachStatus.NEGATIVE, OutreachStatus.CLOSED}
    ),
    OutreachStatus.NEGATIVE: frozenset(
        {OutreachStatus.REPLIED, OutreachStatus.POSITIVE, OutreachStatus.CLOSED}
    ),
    OutreachStatus.NO_RESPONSE: frozenset(
        {OutreachStatus.FOLLOW_UP_DUE, OutreachStatus.REPLIED, OutreachStatus.CLOSED}
    ),
    OutreachStatus.CLOSED: frozenset({OutreachStatus.NOT_CONTACTED}),
}

#: Terminal for reporting purposes. Reopening is allowed so a mistaken close is
#: recoverable rather than a dead row.
CLOSED_OUTREACH_STATUSES: frozenset[str] = frozenset({OutreachStatus.CLOSED})


def outreach_transition_is_legal(current: str, requested: str) -> bool:
    """Return whether ``current`` may become ``requested``.

    An unchanged status is always legal: a client re-saving the form it already
    has should not be told it is wrong.
    """
    if current == requested:
        return True
    return requested in OUTREACH_TRANSITIONS.get(current, frozenset())


__all__ = [
    "AUTHORITATIVE_SOURCE_TYPES",
    "CLOSED_OUTREACH_STATUSES",
    "INCONCLUSIVE_COVERAGE_STATUSES",
    "NON_PUBLISHING_COVERAGE_STATUSES",
    "OUTREACH_TRANSITIONS",
    "PUBLIC_RELATIONSHIP_STATUSES",
    "PUBLISHABLE_AVAILABILITY_STATES",
    "AvailabilityScope",
    "AvailabilityState",
    "CoverageEvidenceState",
    "OutreachStatus",
    "ProfessorProfileStatus",
    "ProfessorRelationshipType",
    "RelationshipVerificationStatus",
    "ResearchAlignmentBand",
    "SourceType",
    "SupervisorCoverageStatus",
    "outreach_transition_is_legal",
]