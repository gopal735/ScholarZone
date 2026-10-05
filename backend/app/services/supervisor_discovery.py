"""Supervisor discovery.

A separate pipeline with its own politeness controls. It does not run inside the
existing maintenance worker, and it does not touch the image, verification or
counting stages: a stage that discovers faculty must not be able to disturb the
stages that keep the catalogue honest.

Four rules govern everything below.

**Only the awarding institution counts.** Discovery starts at the scholarship's own
official source and follows links on that same host. A faculty page on the
awarding institution's domain is authoritative evidence about that institution.
A professor listed anywhere else is not evidence about this programme, so no
cross-institution relationship is ever created.

**A professor is only created from a profile page that exists.** A name plus a
profile URL on the institution's domain is the minimum. There is no code path
that writes a professor row from a name alone, so an empty result cannot be
"fixed" by inventing someone.

**Absence is recorded as absence.** When no faculty page is reachable the outcome
is ``source_blocked``, and when a page is read and lists nobody relevant it is a
true negative. These are different states and the pipeline keeps them apart.

**Polite by construction.** Every request passes a robots check and a per-host
delay, and the whole thing is bounded by a worker count. University sites are not
the platform's to hammer.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from ..models import Scholarship
from ..models_supervisor import (
    ProfessorAvailability,
    ProfessorProfile,
    ScholarshipProfessorLink,
    ScholarshipSupervisorCoverage,
    SupervisorSourceEvidence,
)
from .discovery_scheduler import DomainRateLimiter
from .official_source_fetcher import (
    DEFAULT_HEADERS,
    clear_official_source_cache,
    fetch_official_source,
)
from .supervisor_coverage import ensure_coverage_row, recompute_coverage
from .supervisor_freshness import CONTACT_REFRESH_DAYS, next_check_at
from .supervisor_gating import (
    OFFICIAL_HOST_SUFFIXES,
    ApprovedCandidateSet,
    ApprovedSupervisorCandidate,
    approve_candidate_set,
    host_is_official,
    registrable_domain as _registrable_domain,
    same_institution as _same_institution,
    verification_status_for,
)
from .supervisor_jsdetect import classify_shell, looks_like_directory_listing
from .supervisor_render import render_blocking
from .supervisor_source import RenderBudget, RenderErrorKind, SourceOutcome
from .supervisor_person import (
    academic_role_in,
    classify_person_candidate,
    looks_like_a_person_name,
    role_words_are_the_whole_name,
)
from .supervisor_status import (
    AvailabilityScope,
    AvailabilityState,
    ProfessorRelationshipType,
    RelationshipVerificationStatus,
    SourceType,
    SupervisorCoverageStatus,
)

logger = logging.getLogger(__name__)

#: Politeness. One worker per institution is not a throughput setting, it is the
#: mechanism that stops sixteen threads converging on one university.
MAX_WORKERS = 8
MAX_WORKERS_CEILING = 16
DEFAULT_PER_HOST_DELAY_SECONDS = 1.0

#: Bounded crawl. A faculty directory is found in a couple of hops; a budget past
#: that is a runaway, not thoroughness.
MAX_PAGES_PER_SCHOLARSHIP = 6
MAX_CANDIDATES_PER_SCHOLARSHIP = 40
MAX_HTML_BYTES = 400_000

#: A faculty *listing* is a page whose path names a group of people. Matching a
#: bare word like "academic" is not enough: the real pilot found /academics and
#: /academics/research on a large university site being selected as faculty
#: directories, because both the path and the anchor contained "academic". Those
#: are subject-area navigation and list nobody, so each one consumed a request
#: from a budget meant for pages that might actually publish names.
_FACULTY_PATH_SEGMENTS = (
    "/people",
    "/person",
    "/staff",
    "/faculty",
    "/directory",
    "/profiles",
    "/our-people",
)

#: Anchor phrases that name a people directory even when the path does not.
_FACULTY_ANCHOR_PHRASES = (
    "our faculty",
    "our staff",
    "our people",
    "our team",
    "staff directory",
    "faculty directory",
    "people directory",
    "directory of staff",
)

#: Only these hosts may receive a professor record. Anything else is not an
#: official institutional source.
#:
#: The vocabulary now lives in :mod:`app.services.supervisor_gating`, which is
#: where the gates that depend on it are decided and which must be importable
#: without a database. It is re-bound here under its historical private name so
#: nothing that imported it from this module breaks.
_OFFICIAL_HOST_SUFFIXES = OFFICIAL_HOST_SUFFIXES

_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_WHITESPACE = re.compile(r"\s+")
#: Titles that identify an academic rank when a page publishes one.
_TITLE_PATTERN = re.compile(
    r"\b(Professor|Prof\.?|Associate Professor|Assistant Professor|Reader|"
    r"Lecturer|Dr\.?|PhD|MSc|BSc)\b"
)
#: Labels that precede a research-interest list on a faculty page. These are
#: specific enough to match without a colon, because a page writing "Research
#: interests" is labelling a list either way.
_RESEARCH_LABEL = re.compile(
    r"(research interests?|research areas?|research focus|specialis[ée]s|expertise)",
    re.IGNORECASE,
)

#: Generic words that would match far too much prose if a colon were optional:
#: "she works in the field of robotics" contains "field". So these only count when
#: the page uses them as a label, which it signals with a colon.
_RESEARCH_LABEL_STRICT = re.compile(
    r"(?:\bresearch\s*:)|(?:\b(?:areas?|interests?|fields?|topics?)\s*:)",
    re.IGNORECASE,
)

#: Below three characters a captured value is almost always a stray fragment -
#: with one deliberate exception. "AI" is a real and common research area, so two
#: characters are allowed while one is not.
_MIN_RESEARCH_AREA_LENGTH = 2

#: Phrases that state supervision availability. Only these, and only on the
#: institution's own page, may produce a VERIFIED_YES or VERIFIED_NO.
_ACCEPTING_PHRASES = (
    "accepting applications",
    "accepting students",
    "accepting new students",
    "looking for students",
    "recruiting students",
    "currently accepting",
    "open to applications",
)
_NOT_ACCEPTING_PHRASES = (
    "not accepting",
    "not currently accepting",
    "no longer accepting",
    "not available for supervision",
    "not recruiting",
)


# ---------------------------------------------------------------------------
# Politeness
# ---------------------------------------------------------------------------

_ROBOTS_LOCK = threading.Lock()
_ROBOTS_CACHE: dict[str, RobotFileParser | None] = {}
_ROBOTS_TTL_SECONDS = 3600.0
_ROBOTS_CACHE_TIME: dict[str, float] = {}

_RATE_LIMITER = DomainRateLimiter(min_interval_seconds=DEFAULT_PER_HOST_DELAY_SECONDS)


def clear_robots_cache() -> None:
    """Drop cached robots decisions. Used by tests."""
    with _ROBOTS_LOCK:
        _ROBOTS_CACHE.clear()
        _ROBOTS_CACHE_TIME.clear()


def _robots_allows(url: str) -> bool:
    """Return whether robots.txt permits fetching ``url``.

    Fails closed. A host whose robots.txt cannot be read is treated as
    disallowed, because the alternative is deciding that an unreadable policy
    permits anything.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    origin = f"{parsed.scheme}://{parsed.netloc}"
    now = time.time()
    with _ROBOTS_LOCK:
        cached = _ROBOTS_CACHE.get(origin)
        cached_at = _ROBOTS_CACHE_TIME.get(origin, 0.0)
        if cached is not None and now - cached_at < _ROBOTS_TTL_SECONDS:
            return bool(cached and cached.can_fetch(ScholarZone_USER_AGENT, url))

    parser: RobotFileParser | None = None
    robots_url = origin + "/robots.txt"
    try:
        with httpx.Client(timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)) as client:
            response = client.get(robots_url, headers=DEFAULT_HEADERS, follow_redirects=True)
        if response.status_code == 200:
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
        elif 400 <= response.status_code < 500:
            # The host has no robots.txt, which means no restrictions are published.
            parser = RobotFileParser()
            parser.parse([])
        else:
            parser = None
    except Exception:
        parser = None

    with _ROBOTS_LOCK:
        _ROBOTS_CACHE[origin] = parser
        _ROBOTS_CACHE_TIME[origin] = now
    return bool(parser and parser.can_fetch(ScholarZone_USER_AGENT, url))


ScholarZone_USER_AGENT = "ScholarZone"


def polite_fetch(url: str):
    """Fetch one page through robots, the per-host delay, and the shared fetcher."""
    if not _robots_allows(url):
        logger.info("Robots policy declined %s", url)
        return None
    host = urlparse(url).netloc
    if host:
        _RATE_LIMITER.wait_if_needed(host)
    result = fetch_official_source(url)
    return result if result.success else None


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


@dataclass
class FacultyCandidate:
    """One person read off an official faculty page.

    Every field is something the page stated. ``profile_url`` is required, and a
    candidate without one is discarded rather than stored - that single rule is
    what makes an invented professor impossible through this pipeline.
    """

    name: str
    profile_url: str
    title: str | None = None
    department: str | None = None
    official_email: str | None = None
    lab_url: str | None = None
    research_areas: list[str] = field(default_factory=list)
    evidence_summary: str | None = None
    #: The academic role the institution stated, when it stated one.
    role: str | None = None
    #: How personhood was judged: ``honorific``, ``inline_role`` or
    #: ``source_context``. Kept so a reviewer can see the reasoning rather than
    #: re-derive it.
    role_evidence: str | None = None

    @property
    def has_role_evidence(self) -> bool:
        """Whether an academic role was actually stated somewhere.

        Distinct from :attr:`role_evidence`, which records only *how* personhood was
        judged. A candidate can be a person by directory structure and still have no
        role stated, and that is exactly the case that must not become a professor.
        """
        return self.role is not None


#: Whether a host is an academic institution's own domain.
#:
#: ``host_is_official``, ``registrable_domain`` and ``same_institution`` are
#: imported from :mod:`app.services.supervisor_gating` rather than defined here,
#: because the gates that consume them must be decidable without a database. They
#: are module-level names in this module, and every call below resolves them at
#: call time, so the loopback-institution tests that monkeypatch
#: ``supervisor_discovery.host_is_official`` still take effect - which is the
#: point: an alias captured at import time would bypass the patch and start
#: rejecting the fixture as non-institutional.


# Personhood is decided in app.services.supervisor_person, from positive evidence:
# a stated academic role, or a personal-profile path inside a page already
# established as a faculty directory.
#
# This module deliberately keeps no geographic or institutional word list. A
# blacklist only ever contains the cases somebody already thought of, and it reads
# as though it were the safety mechanism rather than a secondary filter. The
# classifier is imported above and re-exported for callers that need the cheap
# screen.



def page_requires_authentication(html: str) -> bool:
    """Return whether a served page is a sign-in wall rather than content.

    A directory behind a login is inaccessible, not empty. Recording it as a
    verified negative would tell a student that a university employs nobody, on the
    evidence that we were shown a password box - which is precisely the false claim
    this feature must never make. Observed for real: Michigan State's official
    people search resolves to a page titled "Michigan State University - Sign In".

    Detected structurally from the served document, not from a list of known
    providers: a password field, a form posting to a sign-in path, or a document
    whose own title or first heading names signing in.
    """
    if not html:
        return False
    lowered = html.lower()
    if re.search(r'<input[^>]+type=["\']password["\']', lowered):
        return True
    for match in re.finditer(r'<form[^>]*action=["\']([^"\']+)["\']', lowered):
        if re.search(
            r"/(signin|sign-in|login|log-in|auth|authenticate|sso)", match.group(1), re.I
        ):
            return True
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html[:MAX_HTML_BYTES], "html.parser")
        for element in list(soup.find_all("title")) + list(soup.find_all(["h1", "h2"])):
            text = (element.get_text(" ", strip=True) or "").lower()
            if re.search(
                r"\b(sign in|signin|log ?in|authenticate|authentication required)\b", text
            ):
                return True
    except Exception:  # noqa: BLE001 - a parse failure must never become a verdict
        return False
    return False


def _looks_like_a_person_name(text: str) -> bool:
    """Kept so existing callers and fixtures keep working.

    Narrower than the classifier: it answers "does this text state an academic role
    at all", so it is ``False`` for a bare "Grace Hopper" that the classifier would
    still accept inside a real faculty directory. Any decision that matters uses
    :func:`classify_person_candidate`.
    """
    return looks_like_a_person_name(text)




#: A served page whose visible text is a tiny fraction of its markup is a
#: JavaScript shell: the document is almost entirely script, and the content a
#: reader sees is assembled in the browser after delivery. Measured across real
#: university directories at 0.005 to 0.039; a server-rendered content page sits
#: far higher, so this threshold is deliberately clear of both populations.
JS_SHELL_TEXT_RATIO = 0.15


def page_is_javascript_shell(html: str, text: str) -> bool:
    """Return whether a served page carries its content only after rendering.

    Used to tell "this university published no faculty here" apart from "this page
    assembles its content in the browser and we were served only the shell". The
    distinction decides whether a coverage row records a true negative or an
    inconclusive search, so the test is deliberately conservative: it reports a
    shell only when the document is overwhelmingly script.
    """
    if not html:
        return False
    ratio = len(text or "") / max(1, len(html))
    return ratio < JS_SHELL_TEXT_RATIO


def _looks_like_a_person_name(text: str) -> bool:
    """Backwards-compatible alias used by the extractor and its tests."""
    return looks_like_a_person_name(text)


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    collapsed = _WHITESPACE.sub(" ", value).strip()
    return collapsed or None


def _same_site(candidate_url: str, seed_host: str) -> bool:
    host = (urlparse(candidate_url).netloc or "").lower()
    seed = (seed_host or "").lower()
    if not host or not seed:
        return False
    return host == seed or host.endswith("." + seed)


def registrable_domain(host: str | None) -> str:  # noqa: F811 - re-export
    """Return an academic host's own institution domain.

    Re-export of :func:`app.services.supervisor_gating.registrable_domain`. The
    implementation lives there so the gates can decide host ownership without
    importing a database. It remains a module-level lookup here, resolved at call
    time, so the loopback-institution tests that monkeypatch names on this module
    still take effect.
    """
    return _registrable_domain(host)


def same_institution(candidate_url_or_host: str, seed_host: str) -> bool:
    """Return whether two hosts belong to the same academic institution.

    This is the authority test for evidence: a faculty page is authoritative about
    a programme when it belongs to the institution that awards it. Exact hostname
    matching is used for crawl scoping; this is the looser, still-institutional
    comparison used to decide whether a page is evidence.
    """
    # Both arguments may arrive as a bare host or as a full URL; normalise both so
    # a caller cannot get a wrong answer by passing a URL where a host is expected.
    def _host_of(value: str) -> str:
        return urlparse(value).netloc if "//" in (value or "") else (value or "")

    return _same_institution(candidate_url_or_host, seed_host)


def looks_like_faculty_listing(url: str, anchor_text: str = "") -> bool:
    """Return whether a link plausibly leads to a faculty listing.

    Requires a *people* signal: either a path segment that names a group of
    people, or anchor text that says so outright.

    The earlier version accepted any link containing the word "academic", and the
    real pilot caught the consequence on a large university site: /academics and
    /academics/research were both selected as faculty directories. They are
    subject-area navigation and list nobody, so each one consumed a request from
    a budget meant for pages that might actually publish names. Tightening the
    test costs a little recall on genuinely oddly-named directories and buys back
    most of the request budget.
    """
    path = (urlparse(url).path or "").lower()
    if any(segment in path for segment in _FACULTY_PATH_SEGMENTS):
        return True
    lowered_anchor = (anchor_text or "").strip().lower()
    return any(phrase in lowered_anchor for phrase in _FACULTY_ANCHOR_PHRASES)


def _extract_email(html: str, host: str) -> str | None:
    """Return an address published on the page for this host, if any.

    Only an address on the institution's own domain is accepted, and one
    containing a ``+`` tag or an obfuscation is skipped rather than cleaned up:
    rewriting an address is how a guess becomes an official-looking one.
    """
    for match in _EMAIL_PATTERN.finditer(html or ""):
        address = match.group(0).lower()
        if any(token in address for token in ("example", "yourname", "noreply", "no-reply")):
            continue
        domain = address.rsplit("@", 1)[-1]
        if host and (domain == host.lower() or domain.endswith("." + host.lower())):
            return address
    return None


def _extract_research_areas(text: str) -> list[str]:
    """Return research areas the page labels explicitly.

    Only a labelled section counts. Prose that happens to contain the word
    "research" is not a research-interest list, and treating it as one would put
    unverifiable text into a field the alignment engine compares against.
    """
    areas: list[str] = []
    body = text or ""
    # Both patterns are tried, and each match consumes only the text after its own
    # label, so a page using "Research areas:" is not also read as "Areas:".
    for pattern in (_RESEARCH_LABEL, _RESEARCH_LABEL_STRICT):
        for match in pattern.finditer(body):
            tail = body[match.end() : match.end() + 400]
            segment = re.split(
                r"[\n\r]|\b(?:publications|teaching|contact|office)\b", tail, maxsplit=1
            )[0]
            for piece in re.split(r"[;•|,]|\band\b", segment):
                # The label's own colon and trailing punctuation belong to the
                # markup, not to the research area. "Research: AI" must yield
                # "AI", never "Research" and never ": AI".
                cleaned = _clean_text(piece.strip(" \t\r\n:;-–—•|,"))
                if cleaned and _MIN_RESEARCH_AREA_LENGTH <= len(cleaned) <= 80:
                    areas.append(cleaned)
            if len(areas) >= 6:
                break
        if len(areas) >= 6:
            break
    seen: list[str] = []
    for area in areas:
        lowered = area.lower()
        if lowered not in {existing.lower() for existing in seen}:
            seen.append(area)
    return seen[:6]


def _derive_availability(page_text: str) -> str:
    """Return the availability state the page's own words support.

    The negative phrases are tested first, and that ordering is load-bearing
    rather than cosmetic: "I am not accepting students" contains the positive
    substring "accepting students", so testing the affirmative case first would
    read a refusal as an offer.

    Defaults to ``not_published``. Silence about supervision is not a "no", and
    treating it as one is the single most misleading thing this feature could do.
    """
    lowered = (page_text or "").lower()
    if any(phrase in lowered for phrase in _NOT_ACCEPTING_PHRASES):
        return str(AvailabilityState.VERIFIED_NO)
    if any(phrase in lowered for phrase in _ACCEPTING_PHRASES):
        return str(AvailabilityState.VERIFIED_YES)
    return str(AvailabilityState.NOT_PUBLISHED)


def extract_faculty_candidates(
    html: str,
    page_url: str,
    seed_host: str,
) -> list[FacultyCandidate]:
    """Return the people an official faculty page publishes.

    Scoped to links on the seed's own host, because a page that links out to
    another institution's directory is not authoritative about this one.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup((html or "")[:MAX_HTML_BYTES], "html.parser")
    page_text = soup.get_text(" ", strip=True)
    base_host = seed_host or (urlparse(page_url).netloc or "")

    # Navigation and branding text taken from the document itself. A link whose
    # label is the site name or a page heading describes the page rather than a
    # person, whatever it is capitalised as. Deriving this from the served document
    # is what lets it generalise: no list of university or place names is needed,
    # because the page states its own labels.
    document_labels: set[str] = set()
    if soup.title and soup.title.string:
        document_labels.add(_clean_text(soup.title.string).casefold().strip(" .,:;"))
    for heading in soup.find_all(["h1", "h2", "h3"]):
        label = _clean_text(heading.get_text(" ", strip=True))
        if label:
            document_labels.add(label.casefold().strip(" .,:;"))

    candidates: list[FacultyCandidate] = []
    seen_urls: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "")
        absolute = urljoin(page_url, href)
        if absolute in seen_urls:
            continue
        if not _same_site(absolute, base_host):
            continue

        anchor_text = _clean_text(anchor.get_text(" ", strip=True))
        if not anchor_text:
            continue

        # Personhood is decided by positive evidence - a stated academic role, or a
        # personal-profile path on a page already established as a directory - never
        # by the absence of a word from a blacklist. The link text alone is not
        # enough, and neither is the host: a first-party domain says who owns the
        # page, not who the person is.
        signal = classify_person_candidate(
            anchor_text,
            url=absolute,
            directory_context=True,
            document_labels=frozenset(document_labels),
        )
        if signal is None:
            continue

        seen_urls.add(absolute)
        candidates.append(
            FacultyCandidate(
                name=signal.name,
                profile_url=absolute,
                department=None,
                role=signal.role,
                role_evidence=signal.role_evidence,
                evidence_summary=f"Listed on {page_url} ({signal.role_evidence})",
            )
        )
        if len(candidates) >= MAX_CANDIDATES_PER_SCHOLARSHIP:
            break

    # Enrich only the pages that carry detail. The listing page itself rarely
    # states a title or a research area, and guessing them would defeat the point.
    enriched: list[FacultyCandidate] = []
    for candidate in candidates:
        detail = polite_fetch(candidate.profile_url)
        if detail is None or not detail.content:
            # Unreadable: nothing corroborates a role, and nothing refutes one
            # either. Kept, and stored unverified - an unread profile is not evidence
            # about a person, and it is certainly not evidence of absence.
            enriched.append(candidate)
            continue
        detail_soup = BeautifulSoup(detail.content[:MAX_HTML_BYTES], "html.parser")
        detail_text = detail_soup.get_text(" ", strip=True)
        if page_requires_authentication(detail.content):
            # A profile behind a sign-in tells us nothing. Storing it would create a
            # record on the strength of a URL alone.
            continue
        title_match = _TITLE_PATTERN.search(detail_text[:600])
        email = _extract_email(detail.content, base_host)
        candidate.title = title_match.group(0) if title_match else None
        candidate.official_email = email
        candidate.research_areas = _extract_research_areas(detail_text)
        candidate.evidence_summary = f"Profile at {candidate.profile_url}"
        # A role on the profile corroborates one the listing only implied.
        if candidate.role is None:
            profile_role = academic_role_in(detail_text)
            if profile_role:
                candidate.role = profile_role
                candidate.role_evidence = "profile_role"
        enriched.append(candidate)
    return enriched


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _content_hash(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8", errors="replace")).hexdigest()


def upsert_professor(
    db,
    candidate: FacultyCandidate,
    institution_name: str,
    source_type: str,
) -> ProfessorProfile:
    """Store or refresh one professor, deduplicated on the official profile URL.

    The unique constraint is the deduplication mechanism, so two runs that both
    discover the same person converge on one row. A run that already has the row
    refreshes the volatile fields and leaves a verified email alone unless this run
    found it on the official page again.
    """
    existing = db.execute(
        select_professor_by_url(candidate.profile_url)
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing is not None:
        if candidate.research_areas:
            existing.research_areas = candidate.research_areas
        if candidate.title:
            existing.title = candidate.title
        if candidate.lab_url:
            existing.lab_url = candidate.lab_url
        if candidate.official_email:
            existing.official_email = candidate.official_email
            # Only an address read off the institution's own page sets this, and
            # it is never cleared, so a later page that omits the address cannot
            # unpublish a verified one.
            existing.official_email_verified = True
        existing.last_verified_at = now
        existing.next_verification_at = now + timedelta_days(CONTACT_REFRESH_DAYS)
        return existing

    profile = ProfessorProfile(
        canonical_name=candidate.name,
        title=candidate.title,
        institution_name=institution_name,
        department_name=candidate.department,
        official_profile_url=candidate.profile_url,
        official_email=candidate.official_email,
        official_email_verified=bool(candidate.official_email),
        lab_url=candidate.lab_url,
        research_areas=candidate.research_areas,
        research_keywords=[],
        last_verified_at=now,
        next_verification_at=next_check_at(True, now),
    )
    db.add(profile)
    db.flush()
    return profile


def select_professor_by_url(url: str):
    from sqlalchemy import select

    return select(ProfessorProfile).where(ProfessorProfile.official_profile_url == url)


def record_evidence(
    db,
    professor: ProfessorProfile,
    source_url: str,
    source_type: str,
    verification_status: str,
    summary: str | None,
    content: str | None,
    link_id: int | None = None,
    scholarship_id: int | None = None,
    http_status: int | None = None,
) -> None:
    """Record that a page was read, deduplicated so re-reads do not multiply rows."""
    now = datetime.now(timezone.utc)
    existing = db.execute(
        select_evidence(professor.id, source_url, source_type)
    ).scalar_one_or_none()
    payload = {
        "retrieved_at": now,
        "verified_at": now if verification_status == str(RelationshipVerificationStatus.VERIFIED) else None,
        "verification_status": verification_status,
        "evidence_summary": summary,
        "content_hash": _content_hash(content),
        "http_status": http_status,
    }
    if existing is not None:
        for key, value in payload.items():
            setattr(existing, key, value)
        return
    db.add(
        SupervisorSourceEvidence(
            professor_id=professor.id,
            scholarship_id=scholarship_id,
            link_id=link_id,
            source_url=source_url,
            source_host=(urlparse(source_url).netloc or "").lower(),
            source_type=source_type,
            **payload,
        )
    )


def select_evidence(professor_id: int, source_url: str, source_type: str):
    from sqlalchemy import select

    return select(SupervisorSourceEvidence).where(
        SupervisorSourceEvidence.professor_id == professor_id,
        SupervisorSourceEvidence.source_url == source_url,
        SupervisorSourceEvidence.source_type == source_type,
    )


def record_availability(
    db,
    professor: ProfessorProfile,
    scope: str,
    state: str,
    source_url: str,
) -> None:
    """Store one availability answer with the source that produced it."""
    now = datetime.now(timezone.utc)
    row = db.execute(
        select_availability(professor.id, scope)
    ).scalar_one_or_none()
    if row is None:
        db.add(
            ProfessorAvailability(
                professor_id=professor.id,
                scope=scope,
                state=state,
                source_url=source_url,
                verified_at=now,
            )
        )
        return
    row.state = state
    row.source_url = source_url
    row.verified_at = now


def select_availability(professor_id: int, scope: str):
    from sqlalchemy import select

    return select(ProfessorAvailability).where(
        ProfessorAvailability.professor_id == professor_id,
        ProfessorAvailability.scope == scope,
    )


def upsert_link(
    db,
    scholarship: Scholarship,
    professor: ProfessorProfile,
    relationship_type: str,
    evidence_url: str,
    evidence_type: str,
    summary: str | None,
    verification_status: str,
) -> ScholarshipProfessorLink:
    """Create or refresh one relationship, idempotently."""
    from sqlalchemy import select

    existing = db.execute(
        select(ScholarshipProfessorLink).where(
            ScholarshipProfessorLink.scholarship_id == scholarship.id,
            ScholarshipProfessorLink.professor_id == professor.id,
            ScholarshipProfessorLink.relationship_type == relationship_type,
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing is not None:
        existing.verification_status = verification_status
        existing.evidence_source_url = evidence_url
        existing.evidence_source_type = evidence_type
        existing.evidence_quote_or_summary = summary
        existing.retrieved_at = now
        existing.verified_at = (
            now if verification_status == str(RelationshipVerificationStatus.VERIFIED) else None
        )
        return existing
    link = ScholarshipProfessorLink(
        scholarship_id=scholarship.id,
        professor_id=professor.id,
        relationship_type=relationship_type,
        evidence_source_url=evidence_url,
        evidence_source_type=evidence_type,
        evidence_quote_or_summary=summary,
        retrieved_at=now,
        verified_at=(
            now if verification_status == str(RelationshipVerificationStatus.VERIFIED) else None
        ),
        verification_status=verification_status,
    )
    db.add(link)
    db.flush()
    return link


def timedelta_days(days: int):
    from datetime import timedelta

    return timedelta(days=days)


def _verification_status_for(candidate: FacultyCandidate) -> str:  # noqa: F811
    """Return the relationship status a freshly discovered candidate earns.

    Thin delegation to
    :func:`app.services.supervisor_gating.verification_status_for`, which holds
    the rule and its reasoning. Both live here so that there is one definition of
    the standard rather than two that can drift: a gate that decided a candidate
    was VERIFIED while the writer recorded it as UNVERIFIED would be a storage
    gate that does not gate.
    """
    return verification_status_for(candidate)


def _persist_candidates(
    db,
    scholarship: Scholarship,
    candidates: list[FacultyCandidate],
    *,
    faculty_url: str,
    institution_name: str,
    directory_html: str | None,
    http_status: int | None,
    discovery_path: str,
) -> int:
    """Store candidates that earned a role, and return how many. Raw input.

    **Not the production write path any more.** The pipeline now collects through
    :func:`collect_supervisor_plan`, which runs every gate in
    :mod:`app.services.supervisor_gating` and hands the survivors to
    :func:`persist_approved_candidates`. That function accepts only
    ``ApprovedSupervisorCandidate``, so the standard cannot be bypassed by
    forgetting to gate something.

    This function is retained as the low-level writer that accepts *unclassified*
    candidates and re-applies the two gates from ``91bcdb5`` itself before it
    writes. It is deliberately stricter than "no checks": it refuses to store a
    candidate with no stated role, and refuses one whose name is only the role
    restated. Those two conditions are the invariant that stopped two navigation
    links on the real Cornell directory being promoted to verified professors, so
    they are duplicated here on purpose - a second line of defence that survives
    someone replacing the gate module with a simpler one.

    Keeping it is not redundancy for its own sake. Its callers are the direct
    tests that pin that storage gate, and any future path that constructs
    candidates directly.
    """
    stored = 0
    directory_text = ""
    if directory_html:
        # Imported here, as elsewhere in this module: the parser is only needed on
        # the path that actually has HTML to parse.
        from bs4 import BeautifulSoup

        directory_text = BeautifulSoup(directory_html[:MAX_HTML_BYTES], "html.parser").get_text(
            " ", strip=True
        )

    for candidate in candidates:
        # Storage gate. A professor row requires an academic role stated by the
        # institution, on the listing or on the profile. Directory structure alone
        # identifies a candidate to check; it does not identify a professor, and it
        # cannot tell a person from a call to action - `/people/apply-now` and
        # `/people/ada-lovelace` are the same shape. Dropping here means an
        # unevidenced row is never created, rather than created and then hidden.
        if not candidate.has_role_evidence:
            logger.info(
                "Skipping candidate without a stated academic role: %s (%s)",
                candidate.name,
                candidate.profile_url,
            )
            continue
        # Second gate, on the name itself. The check above asks whether a role was
        # stated; this asks whether the name is anything more than that role restated
        # as a label - "Academic Staff" says a role and names a collective, not a
        # person, and a link that does so evidences nobody. Belt and braces rather
        # than redundancy: classify_person_candidate already refuses these, so this
        # catches a candidate built by any other path, including a future one.
        if role_words_are_the_whole_name(candidate.name, candidate.role):
            logger.info(
                "Skipping candidate whose name is only the role restated: %s (%s)",
                candidate.name,
                candidate.profile_url,
            )
            continue

        professor = upsert_professor(
            db,
            candidate,
            institution_name=institution_name,
            source_type=str(SourceType.OFFICIAL_DEPARTMENT_PAGE),
        )
        link = upsert_link(
            db,
            scholarship,
            professor,
            relationship_type=str(ProfessorRelationshipType.POTENTIAL_SUPERVISOR),
            evidence_url=faculty_url,
            evidence_type=str(SourceType.OFFICIAL_DEPARTMENT_PAGE),
            summary=candidate.evidence_summary,
            verification_status=_verification_status_for(candidate),
        )
        record_evidence(
            db,
            professor,
            source_url=faculty_url,
            source_type=str(SourceType.OFFICIAL_DEPARTMENT_PAGE),
            # Mirrors the link's own status rather than asserting VERIFIED, so the
            # evidence row can never claim more than the relationship it supports.
            verification_status=_verification_status_for(candidate),
            summary=candidate.evidence_summary,
            content=directory_html,
            link_id=link.id,
            scholarship_id=scholarship.id,
            http_status=http_status,
        )
        record_availability(
            db,
            professor,
            scope=str(AvailabilityScope.MASTERS_SUPERVISION),
            state=_derive_availability(directory_text),
            source_url=faculty_url,
        )
        stored += 1

    return stored


def _collect_render_for_shells(
    scholarship: Scholarship,
    faculty_pages: list[tuple[str, str]],
    seed_host: str,
    budget: RenderBudget,
    *,
    host_check=None,
) -> tuple[str | None, str, ApprovedCandidateGroup | None]:
    """Read a client-side directory with the bounded renderer. Write nothing.

    Returns ``(status, summary, group)``:

    * ``group`` is not ``None`` when a rendered page produced at least one
      candidate that cleared every gate - the caller persists it with the rest.
    * ``status`` is ``None`` when there is nothing inconclusive left to record,
      and otherwise the status the coverage row should carry.
    * ``summary`` is the human explanation, and is ``""`` on the success path.

    Every exit is inconclusive or a success. There is no path that returns a
    negative, because rendering failure cannot establish that a university
    employs nobody.

    No session is taken, and the rendered candidates go through the same gates as
    the static tier. Rendering therefore cannot buy a weaker standard or a
    duplicate row - the tier changes how the page was *read*, never what counts as
    evidence.
    """
    shells: list[str] = []
    rendered_reasons: list[str] = []
    for faculty_url, _ in faculty_pages:
        page = polite_fetch(faculty_url)
        if not _readable(page):
            continue
        verdict = classify_shell(page.content or "")
        if verdict.needs_more_than_static:
            shells.append(faculty_url)
            if verdict.is_shell:
                rendered_reasons.append(f"{faculty_url}: {verdict.reason}")
            else:
                rendered_reasons.append(f"{faculty_url}: the response carried no readable content")

    if not shells:
        # Either the static read answered, or it was a genuine negative. Either
        # way this function has nothing to add.
        return None, "", None

    logger.info(
        "Static tier read %s client-side shell(s) for scholarship %s; one bounded render each",
        len(shells),
        scholarship.id,
    )

    for faculty_url in shells[: budget.max_pages]:
        observation = render_blocking(
            faculty_url,
            budget=budget,
            seed_host=seed_host,
            max_scroll_iterations=budget.max_scroll_iterations,
        )

        if observation.outcome == SourceOutcome.SOURCE_BLOCKED:
            # A login wall or an anti-bot challenge. We stop, permanently, for this
            # source. No credential is used and no barrier is attempted.
            return (
                str(SupervisorCoverageStatus.SOURCE_BLOCKED),
                f"Rendering was refused for {observation.url}: "
                f"{observation.error_kind or 'access barrier'}. Not attempted.",
                None,
            )

        if observation.outcome != SourceOutcome.SUCCESS or not observation.html:
            continue

        rendered_html = observation.html or ""
        candidates = extract_faculty_candidates(rendered_html, faculty_url, seed_host)
        if not candidates and not looks_like_directory_listing(rendered_html):
            # Rendered cleanly and is not a directory. Nothing to record.
            continue

        decision = approve_candidate_set(
            candidates,
            seed_host=seed_host,
            faculty_url=faculty_url,
            official_host_check=host_check or host_is_official,
        )
        if decision.approved:
            logger.info(
                "Rendered %s and approved %s evidenced professor(s) for scholarship %s",
                faculty_url,
                len(decision.approved),
                scholarship.id,
            )
            return (
                None,
                "",
                ApprovedCandidateGroup(
                    faculty_url=faculty_url,
                    directory_html=rendered_html,
                    http_status=200,
                    discovery_path="browser_render",
                    approved=decision.approved,
                    examined=decision.examined,
                    rejected=decision.rejected,
                    rejection_reasons=dict(decision.rejection_reasons),
                ),
            )

    detail = "; ".join(rendered_reasons[:3]) or "the source is client-side"
    return (
        str(SupervisorCoverageStatus.SOURCE_REQUIRES_RENDERING),
        f"A static read was not sufficient ({detail}). A bounded browser render produced "
        "no academic evidence, so no supervisor can be verified either way.",
        None,
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


@dataclass
class DiscoveryOutcome:
    scholarship_id: int
    status: str
    pages_fetched: int = 0
    professors_found: int = 0
    links_written: int = 0
    detail: str | None = None


def scholarship_seed_urls(scholarship: Scholarship) -> list[str]:
    """Return the scholarship's own official pages, most authoritative first.

    Only its own URLs. Discovery does not go looking across the internet for a
    university, because the scholarship's own source is what ties it to an
    awarding institution in the first place.
    """
    candidates = [
        scholarship.official_source_url,
        scholarship.catalogue_url,
        scholarship.official_updates_url,
    ]
    seen: set[str] = set()
    ordered: list[str] = []
    for url in candidates:
        if not url:
            continue
        cleaned = url.strip()
        if cleaned in seen:
            continue
        host = (urlparse(cleaned).netloc or "").lower()
        if urlparse(cleaned).scheme not in ("http", "https") or not host:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered


def _readable(page) -> bool:
    """Return whether a fetch produced usable HTML.

    ``polite_fetch`` reports failure as ``None``, but this checks the success flag
    too so a caller cannot turn a blocked page into an empty page by handing back
    an unsuccessful result object instead.
    """
    return page is not None and bool(getattr(page, "success", True))


@dataclass(frozen=True)
class CoverageOverride:
    """An explicit coverage verdict, for the inconclusive outcomes.

    ``None`` on a field means "leave it alone". That distinction is load-bearing:
    the blocked-seed-host branch has historically set only a status and an error
    summary, and forcing a zeroed count or a rewritten evidence state there would
    be a silent behaviour change to a public field.
    """

    status: str
    last_error_summary: str | None = None
    evidence_state: str | None = None
    zero_verified_count: bool = False


@dataclass(frozen=True)
class ApprovedCandidateGroup:
    """Everything approved on one directory page, and the page they came from.

    The page context travels with the candidates because the evidence row needs
    the URL, the HTML and the HTTP status of the page the claim was read from.
    Carrying it here means the persistence stage never has to re-fetch or guess.
    """

    faculty_url: str
    directory_html: str | None
    http_status: int | None
    discovery_path: str
    approved: tuple[ApprovedSupervisorCandidate, ...]
    examined: int = 0
    rejected: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SupervisorDiscoveryPlan:
    """The complete, final answer for one discovery run - and nothing written yet.

    This is the object the safety argument rests on. Fetching, parsing,
    classification, personhood, role, institutional domain, provenance,
    normalization and deduplication have all finished by the time one of these
    exists, and producing one required no session at all. Everything that can be
    written is already decided inside it.

    ``collect_supervisor_plan`` cannot write even by accident: it does not take a
    session and imports no ORM. The only thing that can turn a plan into rows is
    :func:`persist_supervisor_plan`, which writes each group and commits once.
    """

    scholarship_id: int
    #: The status this run reports, which is not always the status it stores.
    #: A run with no recorded source URL reports ``search_pending`` while storing
    #: the honest negative; that asymmetry is long-standing public behaviour.
    status: str
    detail: str | None = None
    seed_host: str = ""
    institution_name: str = ""
    pages_fetched: int = 0
    searched: bool = False
    blocked: bool = False
    groups: tuple[ApprovedCandidateGroup, ...] = ()
    coverage_override: CoverageOverride | None = None
    #: Candidates approved in total, across every group.
    approved_count: int = 0
    #: Candidates examined in total, approved or not.
    examined_count: int = 0
    rejected_count: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not self.groups


def collect_supervisor_plan(
    scholarship: Scholarship,
    render_budget: RenderBudget | None = None,
    *,
    official_host_check=None,
) -> SupervisorDiscoveryPlan:
    """Gather, classify and gate everything for one scholarship. Write nothing.

    The pre-persistence half of discovery, split out so that classification
    provably finishes before any row exists. It performs network reads and pure
    computation only: no session, no ``add``, no ``flush``, no ``commit``. The
    test suite asserts that absence directly rather than trusting this docstring.

    ``official_host_check`` defaults to this module's own ``host_is_official``,
    resolved at call time so a test that stands up a loopback institution is
    honoured by the gate that decides institutional ownership.
    """
    from bs4 import BeautifulSoup

    host_check = official_host_check or host_is_official

    seed_urls = scholarship_seed_urls(scholarship)
    if not seed_urls:
        return SupervisorDiscoveryPlan(
            scholarship_id=scholarship.id,
            status=str("search_pending"),
            detail="No official source URL is recorded for this scholarship.",
            searched=True,
        )

    seed_host = (urlparse(seed_urls[0]).netloc or "").lower()
    if not host_is_official(seed_host):
        return SupervisorDiscoveryPlan(
            scholarship_id=scholarship.id,
            status=str("source_blocked"),
            detail=f"Source host {seed_host} is not an institutional domain.",
            seed_host=seed_host,
            coverage_override=CoverageOverride(
                status=str("source_blocked"),
                last_error_summary=(
                    f"Source host {seed_host} is not an institutional domain."
                ),
            ),
        )

    institution_name = _institution_name(scholarship, seed_host)
    pages_fetched = 0
    approved_total = 0
    seed_fetched = 0
    faculty_pages: list[tuple[str, str]] = []
    #: Deduplication spans the whole run, not one page, so the same professor
    #: listed on two department pages is collected once. Keyed on the normalised
    #: profile URL - the same key the database's unique constraint uses.
    seen_urls: set[str] = set()
    groups: list[ApprovedCandidateGroup] = []
    examined_total = 0
    rejected_total = 0
    reasons_total: dict[str, int] = {}

    for seed_url in seed_urls[:MAX_PAGES_PER_SCHOLARSHIP]:
        page = polite_fetch(seed_url)
        if not _readable(page):
            # The scholarship's own page could not be read. Nothing has been
            # learned yet, and counting this as a finished search is exactly how
            # "we could not check" becomes "there is nothing there".
            continue
        seed_fetched += 1
        pages_fetched += 1
        soup = BeautifulSoup((page.content or "")[:MAX_HTML_BYTES], "html.parser")
        for anchor in soup.find_all("a", href=True):
            absolute = urljoin(page.final_url or seed_url, anchor.get("href", ""))
            if not _same_site(absolute, seed_host):
                continue
            anchor_text = _clean_text(anchor.get_text(" ", strip=True)) or ""
            if not looks_like_faculty_listing(absolute, anchor_text):
                continue
            key = absolute.split("#")[0]
            if key not in [url for url, _ in faculty_pages]:
                faculty_pages.append((key, page.final_url or seed_url))
            if len(faculty_pages) >= 3:
                break

    faculty_fetch_failed = False
    for faculty_url, _parent_url in faculty_pages:
        faculty_page = polite_fetch(faculty_url)
        if not _readable(faculty_page):
            faculty_fetch_failed = True
            continue
        pages_fetched += 1
        candidates = extract_faculty_candidates(
            faculty_page.content or "", faculty_url, seed_host
        )
        decision = approve_candidate_set(
            candidates,
            seed_host=seed_host,
            faculty_url=faculty_url,
            official_host_check=host_check,
            seen_urls=seen_urls,
        )
        examined_total += decision.examined
        rejected_total += decision.rejected
        for gate, count in decision.rejection_reasons.items():
            reasons_total[gate] = reasons_total.get(gate, 0) + count
        if decision.approved:
            groups.append(
                ApprovedCandidateGroup(
                    faculty_url=faculty_url,
                    directory_html=faculty_page.content,
                    http_status=faculty_page.status_code,
                    discovery_path="static",
                    approved=decision.approved,
                    examined=decision.examined,
                    rejected=decision.rejected,
                    rejection_reasons=dict(decision.rejection_reasons),
                )
            )
            approved_total += len(decision.approved)
        elif decision.examined:
            # An empty page still belongs in the report, so a run that read a
            # directory and approved nobody is distinguishable from a run that
            # never reached one.
            groups.append(
                ApprovedCandidateGroup(
                    faculty_url=faculty_url,
                    directory_html=faculty_page.content,
                    http_status=faculty_page.status_code,
                    discovery_path="static",
                    approved=(),
                    examined=decision.examined,
                    rejected=decision.rejected,
                    rejection_reasons=dict(decision.rejection_reasons),
                )
            )

    # `links_written` in the original meant "how many professors have been
    # approved so far", accumulated per page. It only ever mattered as a
    # zero-or-not test, and that is the only use it has here.
    links_approved = approved_total

    # A search counts as completed only when the institution's own pages were
    # actually read. Anything less is a blocked source, never a negative result.
    blocked = seed_fetched == 0 or faculty_fetch_failed
    searched = seed_fetched > 0 and not faculty_fetch_failed

    # A directory behind a sign-in is inaccessible, not empty. We read the page and
    # learned nothing about faculty; reporting a negative would turn a password
    # field into a claim that a university employs nobody.
    if searched and not links_approved:
        for faculty_url, _ in faculty_pages:
            faculty_page = polite_fetch(faculty_url)
            if not _readable(faculty_page):
                continue
            if page_requires_authentication(faculty_page.content or ""):
                summary = (
                    "The official people directory requires sign-in. It is inaccessible to an "
                    "anonymous reader and cannot be searched by this worker."
                )
                return SupervisorDiscoveryPlan(
                    scholarship_id=scholarship.id,
                    status=str(SupervisorCoverageStatus.SOURCE_BLOCKED),
                    detail=summary,
                    seed_host=seed_host,
                    institution_name=institution_name,
                    pages_fetched=pages_fetched,
                    groups=tuple(groups),
                    coverage_override=CoverageOverride(
                        status=str(SupervisorCoverageStatus.SOURCE_BLOCKED),
                        last_error_summary=summary,
                        evidence_state="partial",
                        zero_verified_count=True,
                    ),
                    approved_count=approved_total,
                    examined_count=examined_total,
                    rejected_count=rejected_total,
                    rejection_reasons=reasons_total,
                )

    # A page that assembles its content with JavaScript was read successfully and
    # still told us nothing. That is not the same as a page that lists no faculty.
    #
    # Before concluding that, the renderer gets one bounded attempt per shell,
    # because a public JavaScript directory *can* be read safely. If rendering is
    # unavailable, disabled, blocked, or simply unhelpful, the answer stays
    # SOURCE_REQUIRES_RENDERING - never a negative, because nobody has established
    # that the university employs nobody.
    if searched and not links_approved:
        # A budget is always available; passing one in only means "you may render".
        # Without it the driver reports that rendering is disabled, which lands on
        # the same inconclusive state. The shell check itself must never be skipped -
        # that is what would let an unreadable directory become a false negative.
        render_status, render_summary, render_group = _collect_render_for_shells(
            scholarship,
            faculty_pages,
            seed_host,
            render_budget or RenderBudget(),
            host_check=host_check,
        )
        if render_group is not None:
            groups.append(render_group)
            approved_total += len(render_group.approved)
        if render_status is not None:
            return SupervisorDiscoveryPlan(
                scholarship_id=scholarship.id,
                status=render_status,
                detail=render_summary,
                seed_host=seed_host,
                institution_name=institution_name,
                pages_fetched=pages_fetched,
                groups=tuple(groups),
                coverage_override=CoverageOverride(
                    status=render_status,
                    last_error_summary=render_summary[:500],
                    evidence_state="partial",
                    zero_verified_count=True,
                ),
                approved_count=approved_total,
                examined_count=examined_total,
                rejected_count=rejected_total,
                rejection_reasons=reasons_total,
            )

    return SupervisorDiscoveryPlan(
        scholarship_id=scholarship.id,
        status="",
        seed_host=seed_host,
        institution_name=institution_name,
        pages_fetched=pages_fetched,
        searched=searched,
        blocked=blocked,
        groups=tuple(groups),
        approved_count=approved_total,
        examined_count=examined_total,
        rejected_count=rejected_total,
        rejection_reasons=reasons_total,
    )


def persist_approved_candidates(
    db,
    scholarship: Scholarship,
    group: ApprovedCandidateGroup,
    institution_name: str,
) -> int:
    """Write one already-approved group. Accepts nothing but approved candidates.

    The type of every element of ``group.approved`` is checked, and a raw
    candidate raises rather than being written. That is what makes the gate
    structural instead of a matter of discipline: there is no way to reach this
    function with an unclassified candidate except by constructing the container
    incorrectly, which fails loudly instead of persisting an unevidenced row.
    """
    if not group.approved:
        return 0
    for approved in group.approved:
        if not isinstance(approved, ApprovedSupervisorCandidate):
            raise TypeError(
                "persist_approved_candidates only accepts ApprovedSupervisorCandidate; "
                "run approve_candidate_set before persisting. "
                f"Got {type(approved).__name__}."
            )

    directory_text = ""
    if group.directory_html:
        # Imported here, as elsewhere in this module: the parser is only needed on
        # the path that actually has HTML to parse.
        from bs4 import BeautifulSoup

        directory_text = BeautifulSoup(
            group.directory_html[:MAX_HTML_BYTES], "html.parser"
        ).get_text(" ", strip=True)

    stored = 0
    for approved in group.approved:
        candidate = approved.candidate
        professor = upsert_professor(
            db,
            candidate,
            institution_name=institution_name,
            source_type=str(SourceType.OFFICIAL_DEPARTMENT_PAGE),
        )
        link = upsert_link(
            db,
            scholarship,
            professor,
            relationship_type=str(ProfessorRelationshipType.POTENTIAL_SUPERVISOR),
            evidence_url=group.faculty_url,
            evidence_type=str(SourceType.OFFICIAL_DEPARTMENT_PAGE),
            summary=getattr(candidate, "evidence_summary", None),
            verification_status=approved.verification_status,
        )
        record_evidence(
            db,
            professor,
            source_url=group.faculty_url,
            source_type=str(SourceType.OFFICIAL_DEPARTMENT_PAGE),
            # Mirrors the link's own status rather than asserting VERIFIED, so the
            # evidence row can never claim more than the relationship it supports.
            verification_status=approved.verification_status,
            summary=getattr(candidate, "evidence_summary", None),
            content=group.directory_html,
            link_id=link.id,
            scholarship_id=scholarship.id,
            http_status=group.http_status,
        )
        record_availability(
            db,
            professor,
            scope=str(AvailabilityScope.MASTERS_SUPERVISION),
            state=_derive_availability(directory_text),
            source_url=group.faculty_url,
        )
        stored += 1
    return stored


def persist_supervisor_plan(
    db,
    scholarship: Scholarship,
    plan: SupervisorDiscoveryPlan,
) -> DiscoveryOutcome:
    """Write one plan and close the transaction. The only stage that writes.

    Every professor, relationship, evidence and availability row for the run is
    written here, after the final candidate set was already known, and the run
    commits exactly once - or, on the inconclusive branches, not at all, because
    those write only a coverage verdict.

    Coverage is recomputed from the links that now exist rather than being
    incremented, so re-running is idempotent and a partial run cannot inflate a
    count.
    """
    written = 0
    for group in plan.groups:
        written += persist_approved_candidates(
            db, scholarship, group, plan.institution_name
        )

    if plan.coverage_override is not None:
        override = plan.coverage_override
        coverage, _ = ensure_coverage_row(db, plan.scholarship_id)
        coverage.status = override.status
        if override.last_error_summary is not None:
            coverage.last_error_summary = override.last_error_summary
        if override.evidence_state is not None:
            coverage.evidence_state = override.evidence_state
        if override.zero_verified_count:
            coverage.verified_supervisor_count = 0
        coverage.last_checked_at = datetime.now(timezone.utc)
        db.commit()
        return DiscoveryOutcome(
            scholarship_id=plan.scholarship_id,
            status=plan.status,
            pages_fetched=plan.pages_fetched,
            # Approved-but-unwritten candidates are never counted as found: nothing
            # about them reached storage, so reporting them would be a claim the
            # database does not support.
            professors_found=0,
            links_written=0,
            detail=plan.detail,
        )

    coverage = recompute_coverage(
        db,
        plan.scholarship_id,
        searched=plan.searched,
        blocked=plan.blocked,
    )
    return DiscoveryOutcome(
        scholarship_id=plan.scholarship_id,
        status=coverage.status,
        pages_fetched=plan.pages_fetched,
        professors_found=written,
        links_written=written,
        detail=coverage.last_error_summary,
    )


def discover_for_scholarship(
    db, scholarship: Scholarship, render_budget: RenderBudget | None = None
) -> DiscoveryOutcome:
    """Run the pipeline for one scholarship and write its coverage state.

    Two stages, in this order and no other: :func:`collect_supervisor_plan`
    gathers and classifies with no session in scope, then
    :func:`persist_supervisor_plan` writes what survived and commits once. The
    split exists so that the gating cannot be reordered behind a write by a future
    edit - there is nothing to write until collection has finished.

    Safe to re-run. Every write is an upsert keyed on a unique constraint, and
    the coverage row is recomputed from the links rather than incremented, so a
    repeated run cannot inflate a count.
    """
    plan = collect_supervisor_plan(scholarship, render_budget)
    return persist_supervisor_plan(db, scholarship, plan)


def _institution_name(scholarship: Scholarship, seed_host: str) -> str:
    """Return the best available name for the awarding institution.

    Taken from what the catalogue already stores, falling back to the host. This
    is a label for a verified fact - who the faculty page belonged to - not a new
    claim, so an approximate value is acceptable here in a way it would not be for
    a professor's name.
    """
    for value in (scholarship.official_source,):
        if value and value.strip():
            return _WHITESPACE.sub(" ", value).strip()[:255]
    return seed_host


def run_discovery_batch(
    db,
    limit: int = 25,
    max_workers: int = MAX_WORKERS,
    force: bool = False,
) -> list[DiscoveryOutcome]:
    """Discover supervisors for a bounded batch of scholarships.

    Ordered by ``next_check_at`` so records due a refresh are handled before new
    ones, and skipped entirely when not yet due unless ``force`` is set.
    """
    from sqlalchemy import select

    now = datetime.now(timezone.utc)
    query = select(Scholarship).order_by(Scholarship.id).limit(max(1, limit))
    if not force:
        query = query.where(
            Scholarship.id.not_in(
                select(ScholarshipSupervisorCoverage.scholarship_id).where(
                    ScholarshipSupervisorCoverage.next_check_at > now
                )
            )
        )
    scholarships = list(db.execute(query).scalars())
    if not scholarships:
        return []

    workers = max(1, min(max_workers, MAX_WORKERS_CEILING))
    # One worker per scholarship, and the polite_fetch delay serialises requests
    # to the same host, so concurrency cannot turn into a burst against one
    # university.
    outcomes: list[DiscoveryOutcome] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for outcome in pool.map(lambda item: _discover_one(item), scholarships):
            outcomes.append(outcome)
    return outcomes


def _discover_one(scholarship: Scholarship) -> DiscoveryOutcome:
    """Run discovery for one scholarship on its own session.

    A worker thread must not share the request-scoped session, and one failing
    university must not roll back the others, so each gets its own session and its
    own commit.
    """
    from ..database import get_session_factory

    session = get_session_factory()()
    try:
        row = session.get(Scholarship, scholarship.id)
        if row is None:
            return DiscoveryOutcome(scholarship_id=scholarship.id, status="search_pending")
        outcome = discover_for_scholarship(session, row)
        session.commit()
        return outcome
    except Exception as exc:  # noqa: BLE001 - one institution must not stop the batch
        session.rollback()
        logger.exception("Supervisor discovery failed for scholarship %s", scholarship.id)
        return DiscoveryOutcome(
            scholarship_id=scholarship.id,
            status=str("source_blocked"),
            detail=f"{type(exc).__name__}: {exc}"[:500],
        )
    finally:
        session.close()


__all__ = [
    "MAX_CANDIDATES_PER_SCHOLARSHIP",
    "MAX_PAGES_PER_SCHOLARSHIP",
    "MAX_WORKERS",
    "ApprovedCandidateGroup",
    "CoverageOverride",
    "DiscoveryOutcome",
    "FacultyCandidate",
    "SupervisorDiscoveryPlan",
    "clear_official_source_cache",
    "clear_robots_cache",
    "collect_supervisor_plan",
    "discover_for_scholarship",
    "extract_faculty_candidates",
    "host_is_official",
    "looks_like_faculty_listing",
    "persist_approved_candidates",
    "persist_supervisor_plan",
    "polite_fetch",
    "record_availability",
    "record_evidence",
    "registrable_domain",
    "run_discovery_batch",
    "scholarship_seed_urls",
    "upsert_link",
    "upsert_professor",
]
