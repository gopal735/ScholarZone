"""Official contacts for scholarships with no research supervisor.

Most of the catalogue is not a PhD programme. A government scheme, a
foundation award, a short course or a language pathway has no research
supervisor to publish, and the honest thing to show a student instead is the
office that administers the award. This module collects that office, the same
way discovery collects a professor: one polite read of the awarding body's own
page, only what the page actually published, and provenance recorded for every
field.

Three rules, and they are the same rules the professor pipeline answers to.

**Only the awarding body's own page counts.** The seed URLs come from
:func:`app.services.supervisor_discovery.scholarship_seed_urls`, which returns
only the scholarship's recorded official sources. No search engine, no
aggregator, no third-party directory - the same authority standard the
professor gates apply, and the same registrable-domain comparison.

**A contact is an office, never a person.** The value stored is a URL plus,
when the page publishes one, an address on the awarding domain. There is no
field for a staff member's name, and none will be added: the moment this table
held a person, the panel would start rendering them next to the professors.
``OfficialContactKind`` names the administrative function so a reader can see
what kind of contact it is without inferring it from the wording.

**An email is stored only when the page published it.** The address must sit on
the awarding body's own registrable domain, and ``contact_email_verified`` is
set only from an actual read. There is no naming-convention derivation here,
just as there is none for professors; an address that was found but not
confirmed stays unverified and unpublished.

The module keeps network reads and persistence in separate functions so the
collection half can be exercised with a mocked fetch and the write half with a
plain session, exactly like the discovery worker.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from .supervisor_discovery import (
    polite_fetch,
    scholarship_seed_urls,
)
from .supervisor_gating import registrable_domain
from .supervisor_status import (
    AUTHORITATIVE_SOURCE_TYPES,
    OfficialContactKind,
    SourceType,
)

logger = logging.getLogger(__name__)

#: Path and anchor fragments that identify an administrative contact route.
#: Matched against the lowercased path and the lowercased link text; a contact
#: page is usually labelled with one of these outright.
_CONTACT_PATH_FRAGMENTS = (
    "/contact",
    "/enquir",
    "/admission",
    "/apply",
    "/scholarship",
    "/financial-aid",
    "/fees-and-funding",
    "/funding",
    "/office",
)
_CONTACT_ANCHOR_FRAGMENTS = (
    "contact us",
    "contact",
    "enquir",
    "admissions",
    "scholarship office",
    "scholarships office",
    "programme office",
    "program office",
    "general enquiries",
)

#: An address must look like one before it is stored. Deliberately the same
#: shape the professor extractor accepts, and no more.
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

#: Placeholders that are not an office. Skipped rather than stored.
#: Anchor text that belongs to page furniture rather than to an office. Such a
#: link may still be the contact route - the path match is what identifies that
#: - but its label is stored as absent rather than as junk, because a label is
#: what a reader sees.
_JUNK_ANCHORS = (
    "skip to",
    "back to top",
    "main content",
    "read more",
    "click here",
    "this link",
    "here",
    "sitemap",
    "toggle",
    "menu",
    "navigation",
)

_EMAIL_PLACEHOLDERS = ("example", "yourname", "noreply", "no-reply", "donotreply")

#: Bounded. One seed page plus at most one contact-route page is the whole read
#: budget: an office is one link away or it is not published at all.
MAX_CONTACT_PAGES = 1

_WHITESPACE = re.compile(r"\s+")


def _clean(value: str | None) -> str | None:
    if not value:
        return None
    collapsed = _WHITESPACE.sub(" ", value).strip()
    return collapsed or None


@dataclass(frozen=True)
class OfficialContactObservation:
    """One administrative contact read off an official page.

    ``contact_url`` is the official page the contact lives on, and
    ``evidence_source_url`` is the page that was actually read. They are the
    same URL in the common case and separate when the contact sits one link
    away, which is why both are carried rather than one being derived.
    """

    scholarship_id: int
    contact_kind: str
    contact_label: str | None
    contact_url: str
    contact_email: str | None
    evidence_source_url: str
    evidence_source_type: str
    retrieved_at: datetime

    @property
    def email_is_verified(self) -> bool:
        """Whether this observation may publish its address.

        Set only by an actual read off the awarding domain. The caller stores
        this as the durable flag; nothing downstream recomputes it from the
        address, so an address can never make itself authoritative.
        """
        return bool(self.contact_email)


def _host_of(value: str) -> str:
    return (urlparse(value or "").netloc or "").lower()


def _same_authority(url: str, seed_url: str) -> bool:
    """Return whether ``url`` is published by the awarding body itself.

    Uses the registrable-domain comparison the professor gates use rather than
    hostname equality, so ``daad.de`` and ``www.daad.de`` are one awarding
    body while ``daad.de`` and ``other-de.de`` are not. An unrecognised host
    falls back to exact equality, which is the conservative direction.
    """
    left = registrable_domain(_host_of(url))
    right = registrable_domain(_host_of(seed_url))
    return bool(left) and bool(right) and left == right


def _extract_office_email(html: str, seed_url: str) -> str | None:
    """Return an address published on the awarding domain, if any.

    The domain test is the registrable one, not hostname equality: an office
    address at ``info@daad.de`` is published by the awarding body whose page is
    ``www.daad.de``. Anything containing an obfuscation or a placeholder is
    skipped rather than repaired, because repairing an address is how a guess
    acquires the appearance of a sourced one.
    """
    seed_domain = registrable_domain(_host_of(seed_url))
    if not seed_domain:
        return None
    for match in _EMAIL_PATTERN.finditer(html or ""):
        address = match.group(0).lower()
        if any(token in address for token in _EMAIL_PLACEHOLDERS):
            continue
        if "+" in address or "%" in address:
            continue
        domain = address.rsplit("@", 1)[-1]
        if registrable_domain(domain) != seed_domain:
            continue
        return address
    return None


def _clean_label(value: str | None) -> str | None:
    """Return the page's own link text, unless it is page furniture.

    A label is shown to a student, so it has to say something. Navigation
    furniture ("Skip to main content", "Back to top") is dropped rather than
    published, and the URL alone carries the link. ``None`` means the page did
    not name the office - which is itself what a reader should see.
    """
    label = _clean(value)
    if label is None or len(label) > 160:
        return None
    lowered = label.casefold()
    if any(fragment in lowered for fragment in _JUNK_ANCHORS):
        return None
    if not any(character.isalpha() for character in label):
        return None
    return label


def _extract_contact_route(html: str, page_url: str, seed_url: str) -> tuple[str | None, str | None]:
    """Return ``(contact_url, label)`` for the page's contact route, if any.

    Scoped to links on the awarding body's own domain. A contact page linked
    from the award page is authoritative about the award; a contact page
    somewhere else is not, and is not followed.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup((html or "")[:400_000], "html.parser")
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "")
        absolute = urljoin(page_url, href)
        if not _same_authority(absolute, seed_url):
            continue
        path = (urlparse(absolute).path or "").lower()
        label = _clean_label(anchor.get_text(" ", strip=True))
        lowered_label = (label or "").lower()
        if any(fragment in path for fragment in _CONTACT_PATH_FRAGMENTS):
            return absolute, label
        if label is not None and any(fragment in lowered_label for fragment in _CONTACT_ANCHOR_FRAGMENTS):
            return absolute, label
    return None, None


def _classify_kind(contact_url: str, label: str | None) -> str:
    """Return the administrative function this route serves.

    Read from the page's own path and link text, in that order, because the
    path is the part the institution controls most tightly. Anything that does
    not name a function is stored as general enquiries rather than promoted to
    a more specific-sounding kind it did not claim.
    """
    haystack = f"{(urlparse(contact_url).path or '').lower()} {(label or '').lower()}"
    if "admission" in haystack:
        return str(OfficialContactKind.ADMISSIONS)
    if "scholarship" in haystack or "funding" in haystack or "financial-aid" in haystack:
        return str(OfficialContactKind.SCHOLARSHIP_OFFICE)
    if "enquir" in haystack or "contact" in haystack:
        return str(OfficialContactKind.GENERAL_ENQUIRIES)
    return str(OfficialContactKind.PROGRAMME_OFFICE)


def collect_official_contact(scholarship) -> OfficialContactObservation | None:
    """Read one official contact for a scholarship. Writes nothing.

    Two polite reads at most: the awarding body's own page, and the contact
    route it links to - because an office page is where the address actually
    lives, and reading it one hop away is still the awarding body's own
    publication.

    Returns ``None`` when neither page could be read, or when they publish no
    contact route and no address. Both are honest absences: an unread page
    yields no contact rather than a guessed one.
    """
    seed_urls = scholarship_seed_urls(scholarship)
    if not seed_urls:
        return None

    for seed_url in seed_urls[:MAX_CONTACT_PAGES]:
        page = polite_fetch(seed_url)
        if page is None or not getattr(page, "success", True) or not page.content:
            continue

        email = _extract_office_email(page.content, seed_url)
        route_url, route_label = _extract_contact_route(page.content, seed_url, seed_url)
        evidence_url = seed_url

        if route_url is not None and email is None:
            # The address is usually on the office page rather than on the
            # award page. One bounded read, still on the awarding domain.
            route_page = polite_fetch(route_url)
            if route_page is not None and getattr(route_page, "success", True) and route_page.content:
                route_email = _extract_office_email(route_page.content, route_url)
                if route_email:
                    email = route_email
                    evidence_url = route_url

        if route_url is None and email is None:
            # Read successfully and published neither a contact route nor an
            # address. There is nothing to store, and inventing a "Contact the
            # university" link would add no information the seed URL lacks.
            logger.info(
                "No official contact published for scholarship %s at %s",
                getattr(scholarship, "id", None),
                seed_url,
            )
            return None

        contact_url = route_url or seed_url
        return OfficialContactObservation(
            scholarship_id=scholarship.id,
            contact_kind=_classify_kind(contact_url, route_label),
            contact_label=route_label,
            contact_url=contact_url,
            contact_email=email,
            evidence_source_url=evidence_url,
            evidence_source_type=str(SourceType.OFFICIAL_PROGRAMME_PAGE),
            retrieved_at=datetime.now(timezone.utc),
        )

    return None


def upsert_official_contact(db, observation: OfficialContactObservation):
    """Store one contact, idempotently, keyed on the unique constraint.

    Re-running with the same contact refreshes the volatile fields and leaves
    the durable identity alone, so two runs cannot produce two offices. A
    verified address is never cleared by a later run that did not find one, for
    the same reason the professor upsert never clears one: absence on a re-read
    is not evidence that the office stopped publishing it.
    """
    from sqlalchemy import select

    from ..models_supervisor import ScholarshipOfficialContact

    existing = db.execute(
        select(ScholarshipOfficialContact).where(
            ScholarshipOfficialContact.scholarship_id == observation.scholarship_id,
            ScholarshipOfficialContact.contact_kind == observation.contact_kind,
            ScholarshipOfficialContact.contact_url == observation.contact_url,
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if existing is not None:
        existing.contact_label = observation.contact_label or existing.contact_label
        if observation.contact_email:
            existing.contact_email = observation.contact_email
            existing.contact_email_verified = True
        existing.evidence_source_url = observation.evidence_source_url
        existing.evidence_source_type = observation.evidence_source_type
        existing.retrieved_at = now
        if existing.contact_email_verified:
            existing.verified_at = now
        return existing

    row = ScholarshipOfficialContact(
        scholarship_id=observation.scholarship_id,
        contact_kind=observation.contact_kind,
        contact_label=observation.contact_label,
        contact_url=observation.contact_url,
        contact_email=observation.contact_email,
        contact_email_verified=observation.email_is_verified,
        evidence_source_url=observation.evidence_source_url,
        evidence_source_type=observation.evidence_source_type,
        retrieved_at=now,
        verified_at=now if observation.email_is_verified else None,
    )
    db.add(row)
    db.flush()
    return row


def official_contacts_for(db, scholarship_id: int) -> list[dict]:
    """Return the publishable contacts for one scholarship.

    Tolerant of a database that has not been migrated yet. The schema is owned
    by the out-of-band migration path rather than by application startup, so a
    deployment that predates this table must keep serving the rest of the
    supervisor payload instead of failing the request; a missing table is
    reported as "no contacts" exactly as an unread page would be.
    """
    from sqlalchemy import select
    from sqlalchemy.exc import OperationalError, ProgrammingError

    from ..models_supervisor import ScholarshipOfficialContact

    try:
        rows = list(
            db.execute(
                select(ScholarshipOfficialContact)
                .where(ScholarshipOfficialContact.scholarship_id == scholarship_id)
                .order_by(ScholarshipOfficialContact.contact_kind)
            )
            .scalars()
        )
    except (ProgrammingError, OperationalError) as exc:
        # The table does not exist yet on this deployment. Logged once per
        # request path at info, because it is a migration state and not an
        # error in the request.
        logger.info(
            "Official contacts are unavailable (table not present on this database): %s",
            exc,
        )
        return []

    contacts: list[dict] = []
    for row in rows:
        # An authoritative source type is required, not preferred: a contact
        # resting on a secondary page is not published, exactly as a professor
        # relationship on one would not be.
        if row.evidence_source_type not in AUTHORITATIVE_SOURCE_TYPES:
            continue
        contacts.append(
            {
                "kind": row.contact_kind,
                "label": row.contact_label,
                "url": row.contact_url,
                # Gated on the flag, never on presence. The frontend gates
                # again.
                "email": row.contact_email if row.contact_email_verified else None,
                "email_verified": bool(row.contact_email_verified),
                "evidence_source_url": row.evidence_source_url,
                "evidence_source_type": row.evidence_source_type,
                "retrieved_at": row.retrieved_at.isoformat() if row.retrieved_at else None,
            }
        )
    return contacts


__all__ = [
    "MAX_CONTACT_PAGES",
    "OfficialContactObservation",
    "collect_official_contact",
    "official_contacts_for",
    "upsert_official_contact",
]
