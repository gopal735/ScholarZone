"""Approved-source registry and configuration for scholarship discovery."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ApprovedSource


class SourceRegistry(Protocol):
    def is_approved(self, url: str) -> bool: ...
    def get_source_type(self, url: str) -> str | None: ...
    def get_trust_score(self, url: str) -> int: ...
    def get_all_active(self) -> list[ApprovedSourceData]: ...


@dataclass(frozen=True)
class ApprovedSourceData:
    domain: str
    name: str
    source_type: str
    country: str | None
    trust_score: int
    discovery_url_patterns: list[str]


_DEFAULT_SOURCES: list[ApprovedSourceData] = [
    ApprovedSourceData("daad.de", "DAAD", "official_government", "Germany", 95, ["https://www.daad.de/en/"]),
    ApprovedSourceData("erasmus-plus.ec.europa.eu", "Erasmus+", "official_program", "EU", 100, ["https://erasmus-plus.ec.europa.eu/"]),
    ApprovedSourceData("chevening.org", "Chevening", "official_program", "UK", 95, ["https://www.chevening.org/"]),
    ApprovedSourceData("campusfrance.org", "Campus France", "official_government", "France", 90, ["https://www.campusfrance.org/"]),
    ApprovedSourceData("swissuniversities.ch", "Swissuniversities", "official_government", "Switzerland", 85, []),
    ApprovedSourceData("nuffic.nl", "Nuffic", "official_government", "Netherlands", 85, []),
    ApprovedSourceData("studyinsweden.se", "Study in Sweden", "official_government", "Sweden", 85, []),
    ApprovedSourceData("studyinaustria.at", "Study in Austria", "official_government", "Austria", 85, []),
    ApprovedSourceData("studyinbelgium.be", "Study in Belgium", "official_government", "Belgium", 85, []),
    ApprovedSourceData("educationusa.state.gov", "EducationUSA", "official_government", "USA", 90, []),
    ApprovedSourceData("fulbright.state.gov", "Fulbright", "official_government", "USA", 95, []),
    ApprovedSourceData("scholars4dev.com", "Scholars4Dev", "aggregator", "International", 40, []),
    ApprovedSourceData("scholarshipdb.net", "ScholarshipDB", "aggregator", "International", 30, []),
    ApprovedSourceData("gov.uk", "UK Government", "official_government", "UK", 90, []),
    ApprovedSourceData("australia.gov.au", "Australian Government", "official_government", "Australia", 90, []),
    ApprovedSourceData("gc.ca", "Government of Canada", "official_government", "Canada", 90, []),
    ApprovedSourceData("studyinjapan.go.jp", "Study in Japan", "official_government", "Japan", 90, []),
    ApprovedSourceData("korea.kr", "Korean Government", "official_government", "South Korea", 90, []),
    ApprovedSourceData("csc.edu.cn", "CSC", "official_government", "China", 85, []),
    ApprovedSourceData("moe.gov.sg", "Singapore MOE", "official_government", "Singapore", 90, []),
]

# Additional official scholarship bodies, added to widen country coverage.
#
# Two rules govern this list, and both exist because a wrong entry is worse
# than a missing one:
#
# 1. Only official bodies - government ministries, national scholarship
#    commissions, state education agencies, or their official study-in-country
#    portals. No commercial directory, no aggregator, no consultancy.
# 2. A wrong domain here is not a fabrication risk. These are *discovery
#    seeds*, not asserted facts: the crawler can only use them to find pages,
#    and every record that results must independently pass the pre-insert
#    quality gate and the evidence checks. An unreachable or wrong domain
#    surfaces honestly as `source_unreachable` in the completeness report
#    rather than inventing a scholarship.
#
# Aggregators are deliberately excluded here even though two `aggregator`-typed
# sources are already listed above. Those stay useful as leads but are never
# crawled for publication-grade provenance, and the pipeline routes anything
# found on them to review rather than auto-approving it.
_EXTENDED_SOURCES: list[ApprovedSourceData] = [
    # Europe
    ApprovedSourceData("studyindenmark.dk", "Study in Denmark", "official_government", "Denmark", 88, []),
    ApprovedSourceData("studyinfinland.fi", "Study in Finland", "official_government", "Finland", 88, []),
    ApprovedSourceData("studyinnorway.no", "Study in Norway", "official_government", "Norway", 88, []),
    ApprovedSourceData("studyinpoland.pl", "Study in Poland", "official_government", "Poland", 85, []),
    ApprovedSourceData("studyinczechia.cz", "Study in Czechia", "official_program", "Czech Republic", 85, []),
    ApprovedSourceData("studyinhungary.hu", "Study in Hungary", "official_program", "Hungary", 85, []),
    ApprovedSourceData("studyinturkiye.gov.tr", "Study in Turkiye", "official_government", "Turkey", 88, []),
    ApprovedSourceData("education.ie", "Government of Ireland Education", "official_government", "Ireland", 90, []),
    ApprovedSourceData("gov.ie", "Government of Ireland", "official_government", "Ireland", 92, []),
    ApprovedSourceData("education.govt.nz", "Ministry of Education New Zealand", "official_government", "New Zealand", 90, []),
    ApprovedSourceData("universitaly.it", "Universitaly", "official_program", "Italy", 82, []),
    ApprovedSourceData("educacion.gob.es", "Ministerio de Educacion", "official_government", "Spain", 90, []),
    # Americas
    ApprovedSourceData("educanada.ca", "Education in Canada", "official_government", "Canada", 90, []),
    ApprovedSourceData("education.gov.in", "Ministry of Education India", "official_government", "India", 88, []),
    ApprovedSourceData("scholarships.gov.in", "National Scholarship Portal India", "official_government", "India", 92, []),
    ApprovedSourceData("gob.mx", "Gobierno de Mexico", "official_government", "Mexico", 90, []),
    # Asia-Pacific
    ApprovedSourceData("jasso.go.jp", "JASSO", "official_government", "Japan", 90, []),
    ApprovedSourceData("studyinkorea.go.kr", "Study in Korea", "official_government", "South Korea", 90, []),
    ApprovedSourceData("mohe.gov.my", "Ministry of Higher Education Malaysia", "official_government", "Malaysia", 90, []),
    ApprovedSourceData("beasiswaindonesia.kemdikbud.go.id", "Indonesian Scholarship", "official_government", "Indonesia", 85, []),
]

_DEFAULT_SOURCES = _DEFAULT_SOURCES + _EXTENDED_SOURCES


class DatabaseSourceRegistry:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._cache: dict[str, ApprovedSourceData | None] = {}

    def _load(self) -> None:
        if self._cache:
            return
        rows = self._session.scalars(select(ApprovedSource).where(ApprovedSource.is_active.is_(True))).all()
        for row in rows:
            self._cache[row.domain] = ApprovedSourceData(
                domain=row.domain,
                name=row.name,
                source_type=row.source_type,
                country=row.country,
                trust_score=row.trust_score,
                discovery_url_patterns=list(row.discovery_url_patterns or []),
            )

    def is_approved(self, url: str) -> bool:
        domain = _extract_domain(url)
        if not domain:
            return False
        self._load()
        return domain in self._cache

    def is_approved_site(self, url: str) -> bool:
        """Approved host, or any subdomain of one.

        Subdomains of an approved organisation are treated as approved because
        the content is served by that same organisation: a university's
        `apply.x.edu` or a ministry's `grants.gov.x` is the same authority as
        the portal that was audited and seeded. This is strictly narrower than
        "any https site" - it cannot admit a third party - and it is what makes
        "target university directories" reachable at all.
        """
        host = _extract_domain(url)
        if not host:
            return False
        self._load()
        if host in self._cache:
            return True
        return any(_subdomain_of(host, known) for known in self._cache)

    def get_source_type(self, url: str) -> str | None:
        domain = _extract_domain(url)
        if not domain:
            return None
        self._load()
        entry = self._cache.get(domain)
        return entry.source_type if entry else None

    def get_trust_score(self, url: str) -> int:
        domain = _extract_domain(url)
        if not domain:
            return 0
        self._load()
        entry = self._cache.get(domain)
        return entry.trust_score if entry else 0

    def get_all_active(self) -> list[ApprovedSourceData]:
        self._load()
        return [v for v in self._cache.values() if v is not None]


class StaticSourceRegistry:
    def __init__(self, sources: list[ApprovedSourceData] | None = None) -> None:
        self._sources = {s.domain: s for s in (sources or _DEFAULT_SOURCES)}

    def is_approved(self, url: str) -> bool:
        domain = _extract_domain(url)
        return domain in self._sources if domain else False

    def is_approved_site(self, url: str) -> bool:
        host = _extract_domain(url)
        if not host:
            return False
        if host in self._sources:
            return True
        return any(_subdomain_of(host, known) for known in self._sources)

    def get_source_type(self, url: str) -> str | None:
        domain = _extract_domain(url)
        entry = self._sources.get(domain) if domain else None
        return entry.source_type if entry else None

    def get_trust_score(self, url: str) -> int:
        domain = _extract_domain(url)
        entry = self._sources.get(domain) if domain else None
        return entry.trust_score if entry else 0

    def get_all_active(self) -> list[ApprovedSourceData]:
        return list(self._sources.values())


def _extract_domain(url: str) -> str | None:
    """Return the comparable host for a URL, or None.

    ``www.`` and the port are stripped, which is not cosmetic. The approved
    registry stores bare domains (``daad.de``) while real seed and discovery
    URLs are written as ``https://www.daad.de/en/``. An earlier version
    compared the raw netloc, so every ``www.`` URL failed the approval check:
    DAAD, Chevening and Campus France were rejected as ``source_not_approved``
    before a single request was made, and the countries they cover never
    produced a discovered record. Normalising here fixes the class of bug
    rather than the three instances of it.
    """
    if not url:
        return None
    try:
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "").lower()
        if not host:
            return None
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return None


def _subdomain_of(host: str, domain: str) -> bool:
    """True when *host* is *domain* or a subdomain of it."""
    if not host or not domain:
        return False
    return host == domain or host.endswith("." + domain)


def seed_approved_sources(session: Session) -> int:
    count = 0
    for src in _DEFAULT_SOURCES:
        existing = session.scalar(select(ApprovedSource).where(ApprovedSource.domain == src.domain))
        if existing is None:
            session.add(ApprovedSource(
                domain=src.domain,
                name=src.name,
                source_type=src.source_type,
                country=src.country,
                trust_score=src.trust_score,
                discovery_url_patterns=src.discovery_url_patterns,
            ))
            count += 1
    if count > 0:
        session.flush()
    return count
