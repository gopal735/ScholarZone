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
    if not url:
        return None
    try:
        parsed = urlparse(url.strip())
        return parsed.netloc.lower() if parsed.netloc else None
    except Exception:
        return None


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
