"""Every gate a supervisor candidate must pass before a single row is written.

This module is **pure**. It imports no database layer, no ORM model and no
session, and it holds no module-level mutable state. That is the whole point of
it, and it is a constraint rather than a stylistic preference:

    The production trigger needs to be able to *finish classification before it
    writes anything*. If the answer to "may this candidate be stored?" lived in
    the same module as the session object that performs the insert, the only way
    to reach the answer would be to reach the session, and the gating could not
    be proved to happen first. Keeping the decision here means
    :func:`approve_candidate_set` can be handed a whole run's candidates and can
    return a list, and that list either reaches a single transaction or is
    discarded.

    The test suite asserts this purity directly - it imports this module in a
    subprocess with the database layer poisoned, and fails if that import
    succeeds.

The gates, in the order they are reported, and what each one is actually asking:

``PERSONHOOD``
    Does this name claim an *individual*? Structural person shape (see
    :func:`~app.services.supervisor_person.name_is_person_shaped`) **and** not
    merely the role written out as a label. The second half is the invariant
    introduced by ``91bcdb5``: "Academic Staff" states a role and names a
    collective, so it is not a person, even though it is two capitalised words
    and would pass a naive shape test.

``ROLE_EVIDENCE``
    Did the institution state an academic role, and is the mechanism that
    established it one this product recognises? Role word alone never
    establishes personhood, and personhood alone never establishes a professor -
    the two are independent and both are required.

``INSTITUTIONAL_DOMAIN``
    Is the profile on the awarding institution's own domain? Same institution,
    not merely same-looking host, and the host must be an academic one. A
    first-party page is necessary for a relationship and is not sufficient.

``PROVENANCE``
    Is there an actual source URL for the claim, on that same institution, with
    an HTTP scheme? A candidate with no provenance cannot be stored, because
    there would be nothing to re-verify it against later.

``NORMALIZATION``
    Does the identity survive normalisation to a stable key? Two spellings of
    one person must converge, and a candidate that normalises to nothing has no
    identity to deduplicate on.

``DUPLICATE``
    Has this person already been approved earlier in this run? Keyed on the
    normalised profile URL, which is the same key the database's unique
    constraint uses - so the in-run check and the durable check cannot disagree
    about what "the same person" means. Name normalisation is deliberately *not*
    the duplicate key: two distinct people can share a name, and collapsing them
    here would delete a real professor that the schema is happy to hold.

A candidate that clears every gate becomes an
:class:`ApprovedSupervisorCandidate`. The persistence layer accepts **only**
that type, so a raw :class:`~app.services.supervisor_discovery.FacultyCandidate`
cannot reach an insert without being named here first.

Verification status is *derived* here rather than asserted by a caller, and it
never exceeds the evidence: a candidate with no stated role is
``unverified`` regardless of how person-shaped its name is. That is the
personhood-versus-role distinction the real Cornell directory exercised, where
personhood was established and role proof was not.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol
from urllib.parse import urlparse, urlunparse

from .supervisor_person import name_is_person_shaped, role_words_are_the_whole_name
from .supervisor_status import RelationshipVerificationStatus

# ---------------------------------------------------------------------------
# Institutional host vocabulary
#
# Moved here from supervisor_discovery so this module stays pure. The
# authoritative host check is a property of a host string, not of a database,
# so nothing about it needed the ORM. supervisor_discovery re-exports these
# names, so every existing import path and monkeypatch target is unchanged.
# ---------------------------------------------------------------------------

#: Only these hosts may receive a professor record. Anything else is not an
#: official institutional source.
OFFICIAL_HOST_SUFFIXES = (
    ".edu",
    ".ac.uk",
    ".edu.au",
    ".ac.jp",
    ".de",
    ".fr",
    ".nl",
    ".se",
    ".ch",
    ".at",
    ".be",
    ".dk",
    ".no",
    ".fi",
    ".es",
    ".it",
    ".ca",
    ".ac.in",
    ".ac.nz",
    ".edu.sg",
    ".ac.za",
    ".edu.tr",
    ".ac.kr",
    ".edu.cn",
    ".ac.th",
    ".edu.pl",
    ".ac.id",
    ".ac.il",
)


def host_is_official(host: str | None) -> bool:
    """Return whether ``host`` looks like an academic institution's own domain.

    A suffix allowlist, not an authority. It cannot tell Oxford from a lookalike,
    and it is not used for that: the host must additionally match the host of the
    scholarship's own official source before anything is stored. This only removes
    the obviously-wrong hosts before spending a request on them.
    """
    if not host:
        return False
    lowered = host.lower()
    return lowered.endswith(OFFICIAL_HOST_SUFFIXES) or ".gov." in lowered


def registrable_domain(host: str | None) -> str:
    """Return an academic host's own institution domain.

    Conservative by design. Only the academic suffixes this product already
    trusts are recognised, and anything unrecognised returns itself unchanged -
    so an unknown host falls back to exact-host comparison rather than being
    guessed into someone else's institution.

    The reason this exists: ``admissions.msu.edu`` and ``msu.edu`` are the same
    university, and so are ``adelaide.edu.au`` and ``staff.adelaide.edu.au``.
    Comparing hostnames alone rejects the awarding institution's own faculty
    pages and turns a reachable page into a false negative, which is a
    correctness bug rather than a safety property.
    """
    host = (host or "").lower().split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    # Longest suffix first, so `adelaide.edu.au` matches `.edu.au` rather than any
    # shorter suffix it happens to contain.
    for suffix in sorted(OFFICIAL_HOST_SUFFIXES, key=len, reverse=True):
        if not host.endswith(suffix):
            continue
        base = host[: -len(suffix)]
        if not base or "." not in base:
            # The host is the suffix itself, e.g. `msu.edu` for `.edu`.
            return host
        # Keep the final label before the suffix. `admissions.msu.edu` and
        # `msu.edu` are both `msu.edu`; stripping only the suffix would leave the
        # first as `admissions.msu` and wrongly treat one university as two.
        return f"{base.split('.')[-1]}{suffix}"
    return host


def same_institution(candidate_url_or_host: str, seed_host: str) -> bool:
    """Return whether two hosts belong to the same academic institution.

    The authority test for evidence: a faculty page is authoritative about a
    programme when it belongs to the institution that awards it. Exact hostname
    matching is used for crawl scoping; this is the looser, still-institutional
    comparison used to decide whether a page is evidence.
    """
    # Both arguments may arrive as a bare host or as a full URL; normalise both so
    # a caller cannot get a wrong answer by passing a URL where a host is expected.
    def _host_of(value: str) -> str:
        return urlparse(value).netloc if "//" in (value or "") else (value or "")

    left = registrable_domain(_host_of(candidate_url_or_host))
    right = registrable_domain(_host_of(seed_host))
    return bool(left) and left == right


# ---------------------------------------------------------------------------
# Gate vocabulary
# ---------------------------------------------------------------------------


class SupervisorGate(StrEnum):
    """The named gates a candidate is measured against.

    Reported by name rather than by a bare count so a rejection is diagnosable:
    "12 candidates rejected" is not actionable, "12 rejected on role evidence"
    is.
    """

    PERSONHOOD = "personhood"
    ROLE_EVIDENCE = "role_evidence"
    INSTITUTIONAL_DOMAIN = "institutional_domain"
    PROVENANCE = "provenance"
    NORMALIZATION = "normalization"
    DUPLICATE = "duplicate"


#: Reported in this order, so a reader always sees the earliest, most fundamental
#: reason a candidate failed rather than whichever gate happened to run last.
GATE_ORDER: tuple[SupervisorGate, ...] = (
    SupervisorGate.PERSONHOOD,
    SupervisorGate.ROLE_EVIDENCE,
    SupervisorGate.INSTITUTIONAL_DOMAIN,
    SupervisorGate.PROVENANCE,
    SupervisorGate.NORMALIZATION,
    SupervisorGate.DUPLICATE,
)

#: The role-evidence mechanisms this product recognises. A candidate whose
#: ``role_evidence`` is not one of these did not earn its role by a route the
#: product has reviewed, so it is not promoted on the strength of it.
RECOGNISED_ROLE_EVIDENCE: frozenset[str] = frozenset(
    {"honorific", "inline_role", "source_context", "profile_role"}
)

_WHITESPACE = re.compile(r"\s+")
_NAME_TRIM = re.compile(r"[^a-z0-9 ]+")


class _Candidate(Protocol):
    """The shape of a candidate this module judges.

    Declared structurally so this module can stay free of any import from the
    discovery engine - importing it would pull in the ORM, which is exactly what
    the purity constraint forbids. :class:`FacultyCandidate` satisfies this
    protocol, and so does any other object with these attributes, which is
    deliberate: the gate is about evidence, not about one concrete class.
    """

    name: str
    profile_url: str
    title: str | None
    role: str | None
    role_evidence: str | None
    #: Whether ``name`` itself claimed a person, rather than borrowing a role from
    #: a neighbouring segment of the same link text. Optional so that any object
    #: satisfying this protocol without it is still judged - absent means "no
    #: claim recorded", which is the conservative reading.
    name_claims_person: bool


@dataclass(frozen=True)
class GateVerdict:
    """The result of running every gate against one candidate.

    ``approved`` is a convenience; ``failed_gates`` is the authority. A verdict
    with no failed gate is approved, and that equivalence is asserted by the
    test suite so the two can never drift.
    """

    name: str
    profile_url: str
    failed_gates: tuple[SupervisorGate, ...]
    reasons: tuple[str, ...]
    normalized_name: str
    normalized_url: str
    verification_status: str

    @property
    def approved(self) -> bool:
        return not self.failed_gates

    @property
    def primary_failure(self) -> str | None:
        """The earliest gate this candidate failed, for a one-line summary."""
        for gate in GATE_ORDER:
            if gate in self.failed_gates:
                return str(gate)
        return None


@dataclass(frozen=True)
class ApprovedSupervisorCandidate:
    """One candidate that has cleared every gate and may be persisted.

    Only this type is accepted by the final persistence function. The
    ``verification_status`` is computed here, from the evidence, rather than
    passed in by a caller - a caller cannot promote a candidate past the
    standard by asserting a status.
    """

    candidate: _Candidate
    faculty_url: str
    normalized_name: str
    normalized_url: str
    verification_status: str
    role_evidence: str | None

    @property
    def name(self) -> str:
        return self.candidate.name

    @property
    def profile_url(self) -> str:
        return self.candidate.profile_url

    @property
    def is_verified(self) -> bool:
        return self.verification_status == str(RelationshipVerificationStatus.VERIFIED)


@dataclass(frozen=True)
class ApprovedCandidateSet:
    """The complete, final answer for one discovery run.

    ``approved`` is the only thing that may be written. ``rejected`` and
    ``rejection_reasons`` exist so a run can report what it refused and why
    without any of it having been stored.
    """

    approved: tuple[ApprovedSupervisorCandidate, ...] = ()
    rejected: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)
    examined: int = 0

    def reasons_for(self, gate: SupervisorGate) -> int:
        return self.rejection_reasons.get(str(gate), 0)

    @property
    def is_empty(self) -> bool:
        return not self.approved


# ---------------------------------------------------------------------------
# Identity normalisation
# ---------------------------------------------------------------------------


def normalize_supervisor_identity(name: str, profile_url: str) -> tuple[str, str]:
    """Return the stable ``(name_key, url_key)`` pair for a candidate.

    Deterministic and lossy on purpose: the keys exist to decide whether two
    mentions are the same person, so folding case, accents-free punctuation and
    URL fragments is what makes a repeated run converge. They are never stored
    and never displayed.
    """
    collapsed = _WHITESPACE.sub(" ", name or "").strip().casefold()
    name_key = _NAME_TRIM.sub(" ", collapsed).strip()
    name_key = _WHITESPACE.sub(" ", name_key)

    raw = (profile_url or "").strip()
    url_key = ""
    if raw:
        parts = urlparse(raw)
        if parts.scheme in ("http", "https") and parts.netloc:
            # Fragment and query are dropped: they address a position within one
            # profile, not a different person.
            url_key = urlunparse(
                (
                    parts.scheme.lower(),
                    parts.netloc.lower(),
                    (parts.path or "/").rstrip("/") or "/",
                    "",
                    "",
                    "",
                )
            )
    return name_key, url_key


def _profile_host(profile_url: str) -> str:
    return (urlparse(profile_url or "").netloc or "").lower()


def _is_official_http_url(value: str) -> bool:
    parts = urlparse(value or "")
    return parts.scheme in ("http", "https") and bool(parts.netloc)


# ---------------------------------------------------------------------------
# The gates
# ---------------------------------------------------------------------------


def verify_supervisor_candidate(
    candidate: _Candidate,
    *,
    seed_host: str,
    faculty_url: str,
    official_host_check: Callable[[str | None], bool] = host_is_official,
) -> GateVerdict:
    """Run every gate against one candidate and return a verdict.

    No side effects of any kind: this reads the candidate and returns a value.
    It cannot write, because it holds no session.

    ``official_host_check`` is injected rather than imported-and-called so the
    caller's own notion of an official host is the one that decides. Tests that
    stand up a loopback institution rely on that.
    """
    name = (candidate.name or "").strip()
    profile_url = (candidate.profile_url or "").strip()
    role = getattr(candidate, "role", None)
    role_evidence = getattr(candidate, "role_evidence", None)
    # Absent means "no claim was recorded", which is the conservative reading: a
    # candidate that cannot say it claimed a person is not vouched for.
    name_claims_person = bool(getattr(candidate, "name_claims_person", False))

    failed: list[SupervisorGate] = []
    reasons: list[str] = []

    # 1. Personhood. Structural person shape AND not merely the role restated.
    #    The second clause is the 91bcdb5 invariant; dropping it would promote
    #    "Academic Staff" and "School of Computing", which are two capitalised
    #    words apiece and no more a person than a navigation link is.
    #
    #    The third clause is the borrowed-role case, which the first two cannot
    #    reach. Both of these are a person-shaped name plus a role string:
    #
    #        "Rachit Agarwal Professor"    a person, and a role, in one clause
    #        "Nanyang Research | Researchers"  a heading, and a role beside it
    #
    #    Removing the role from the second changes nothing - the role is in the
    #    other segment - so the residue is still two capitalised words and passes.
    #    Measured on the real NTU chancellery page, where it reached VERIFIED and
    #    would have been stored as a verified professor. Surface form cannot
    #    separate it from "S Chandra Das", so this asks whether the name made the
    #    claim itself, which the classifier decided while it still had the
    #    segments in hand and recorded as ``name_claims_person``.
    #
    #    It is asked of inline-role evidence only. An honorific leads its own name,
    #    and a profile role was read off that person's own page - the case
    #    test_a_role_on_the_profile_promotes_a_structural_candidate deliberately
    #    relies on, so neither is put to it.
    if not name:
        failed.append(SupervisorGate.PERSONHOOD)
        reasons.append("no name was stated")
    elif not name_is_person_shaped(name):
        failed.append(SupervisorGate.PERSONHOOD)
        reasons.append(f"{name!r} is not the shape of one person's name")
    elif role is not None and role_words_are_the_whole_name(name, role):
        failed.append(SupervisorGate.PERSONHOOD)
        reasons.append(
            f"{name!r} states only the role {role!r} and names no individual"
        )
    elif role_evidence == "inline_role" and not name_claims_person:
        failed.append(SupervisorGate.PERSONHOOD)
        reasons.append(
            f"{name!r} borrows the role {role!r} from a neighbouring segment and "
            f"claims no individual of its own"
        )

    # 2. Role evidence. A stated academic role, established by a route this
    #    product recognises. Independent of personhood: a person with no stated
    #    role is not a professor, and a role with no person is not a professor.
    if role is None:
        failed.append(SupervisorGate.ROLE_EVIDENCE)
        reasons.append("the institution stated no academic role for this person")
    elif role_evidence is not None and role_evidence not in RECOGNISED_ROLE_EVIDENCE:
        failed.append(SupervisorGate.ROLE_EVIDENCE)
        reasons.append(f"role evidence {role_evidence!r} is not a recognised mechanism")
    elif role_evidence is None:
        # A role with no stated mechanism is a role somebody inferred. The
        # classifier always records which route it took, so its absence means
        # the value did not come from the reviewed pipeline.
        failed.append(SupervisorGate.ROLE_EVIDENCE)
        reasons.append("a role was claimed with no recorded evidence mechanism")

    # 3. Institutional domain. The awarding institution's own academic domain.
    profile_host = _profile_host(profile_url)
    if not profile_host:
        failed.append(SupervisorGate.INSTITUTIONAL_DOMAIN)
        reasons.append("no profile host could be read from the profile URL")
    elif not same_institution(profile_host, seed_host):
        failed.append(SupervisorGate.INSTITUTIONAL_DOMAIN)
        reasons.append(
            f"{profile_host} is not the awarding institution {seed_host!r}"
        )
    elif not official_host_check(profile_host) or not official_host_check(seed_host):
        failed.append(SupervisorGate.INSTITUTIONAL_DOMAIN)
        reasons.append(
            f"{profile_host} is not an academic institution domain"
        )

    # 4. Provenance. Something to re-verify against, on that same institution.
    if not _is_official_http_url(faculty_url):
        failed.append(SupervisorGate.PROVENANCE)
        reasons.append("no readable source URL was recorded for the claim")
    elif not same_institution(faculty_url, seed_host):
        failed.append(SupervisorGate.PROVENANCE)
        reasons.append(
            f"the source {faculty_url!r} is not published by {seed_host!r}"
        )
    if not _is_official_http_url(profile_url):
        failed.append(SupervisorGate.PROVENANCE)
        reasons.append("the profile URL is not an absolute http(s) URL")

    # 5. Normalization. An identity that survives to a stable key.
    normalized_name, normalized_url = normalize_supervisor_identity(name, profile_url)
    if not normalized_name:
        failed.append(SupervisorGate.NORMALIZATION)
        reasons.append("the name normalised to an empty identity key")
    elif not normalized_url:
        failed.append(SupervisorGate.NORMALIZATION)
        reasons.append("the profile URL normalised to an empty identity key")

    verification_status = verification_status_for(candidate)

    return GateVerdict(
        name=name,
        profile_url=profile_url,
        failed_gates=tuple(dict.fromkeys(failed)),
        reasons=tuple(dict.fromkeys(reasons)),
        normalized_name=normalized_name,
        normalized_url=normalized_url,
        verification_status=verification_status,
    )


def verification_status_for(candidate: _Candidate) -> str:
    """Return the relationship status a candidate has actually earned.

    Two conditions, and both are necessary.

    **A role was stated.** ``role`` is not ``None`` only when the institution
    stated an academic role, on the listing or on the profile. Directory
    structure alone is a weaker signal and earns ``UNVERIFIED``.

    **The name is a person and not the role restated.** A label like "Academic
    Staff" states a role and names a collective. It satisfies the first
    condition and evidences no individual, so consulting only that condition
    promoted two navigation links on the real Cornell directory into verified
    professors. The second condition asks whether anything person-shaped
    survives removing the role from the name.

    Deliberately identical to the rule the discovery engine already applies, and
    it lives here as well as there so the gate module can be read on its own as
    the single place where evidence strength becomes a verification decision.

    The important consequence for a production proof: **personhood alone never
    yields ``VERIFIED``**. A candidate whose name is person-shaped but whose
    role was never stated stays ``unverified`` however convincing the name is.
    """
    role = getattr(candidate, "role", None)
    name = getattr(candidate, "name", "") or ""
    if role is None:
        return str(RelationshipVerificationStatus.UNVERIFIED)
    if role_words_are_the_whole_name(name, role):
        return str(RelationshipVerificationStatus.UNVERIFIED)
    return str(RelationshipVerificationStatus.VERIFIED)


def approve_candidate_set(
    candidates: list[_Candidate],
    *,
    seed_host: str,
    faculty_url: str,
    official_host_check: Callable[[str | None], bool] = host_is_official,
    seen_urls: set[str] | None = None,
) -> ApprovedCandidateSet:
    """Return the final, persistable set for one page of candidates.

    The last step of the pipeline and the only boundary that matters for safety:
    everything upstream of here may have fetched, parsed, classified and refused
    freely, and nothing has been written. This function sees the whole set at
    once, which is what lets it apply the duplicate check across candidates
    rather than one page at a time - and it is why a mixed batch of valid and
    invalid candidates yields exactly the valid ones.

    ``seen_urls`` carries the approved profile URLs already collected earlier in
    the same run, so deduplication spans pages.
    """
    approved: list[ApprovedSupervisorCandidate] = []
    reasons: dict[str, int] = {}
    rejected = 0
    examined = 0

    for candidate in candidates:
        examined += 1
        verdict = verify_supervisor_candidate(
            candidate,
            seed_host=seed_host,
            faculty_url=faculty_url,
            official_host_check=official_host_check,
        )
        if not verdict.approved:
            rejected += 1
            primary = verdict.primary_failure or str(SupervisorGate.PROVENANCE)
            reasons[primary] = reasons.get(primary, 0) + 1
            continue

        # The duplicate check runs last, on an otherwise-valid candidate, so the
        # rejection is attributed to duplication rather than to whichever weaker
        # gate the copy also happens to trip.
        if seen_urls is not None and verdict.normalized_url in seen_urls:
            rejected += 1
            reasons[str(SupervisorGate.DUPLICATE)] = (
                reasons.get(str(SupervisorGate.DUPLICATE), 0) + 1
            )
            continue

        if seen_urls is not None:
            seen_urls.add(verdict.normalized_url)

        approved.append(
            ApprovedSupervisorCandidate(
                candidate=candidate,
                faculty_url=faculty_url,
                normalized_name=verdict.normalized_name,
                normalized_url=verdict.normalized_url,
                verification_status=verdict.verification_status,
                role_evidence=getattr(candidate, "role_evidence", None),
            )
        )

    return ApprovedCandidateSet(
        approved=tuple(approved),
        rejected=rejected,
        rejection_reasons=reasons,
        examined=examined,
    )


__all__ = [
    "GATE_ORDER",
    "OFFICIAL_HOST_SUFFIXES",
    "RECOGNISED_ROLE_EVIDENCE",
    "ApprovedCandidateSet",
    "ApprovedSupervisorCandidate",
    "GateVerdict",
    "SupervisorGate",
    "approve_candidate_set",
    "host_is_official",
    "normalize_supervisor_identity",
    "registrable_domain",
    "same_institution",
    "verification_status_for",
    "verify_supervisor_candidate",
]
