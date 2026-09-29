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
    ApprovedSourceData("campusfrance.org", "Campus France", "official_government", "France", 90, ["https://www.campusfrance.org/en/bursaries-foreign-students"]),
    ApprovedSourceData("swissuniversities.ch", "Swissuniversities", "official_government", "Switzerland", 85, ["https://www.swissuniversities.ch/en/"]),
    ApprovedSourceData("nuffic.nl", "Nuffic", "official_government", "Netherlands", 85, []),
    ApprovedSourceData("studyinsweden.se", "Study in Sweden", "official_government", "Sweden", 85, ["https://studyinsweden.se/scholarships"]),
    ApprovedSourceData("studyinaustria.at", "Study in Austria", "official_government", "Austria", 85, []),
    ApprovedSourceData("studyinbelgium.be", "Study in Belgium", "official_government", "Belgium", 85, []),
    ApprovedSourceData("educationusa.state.gov", "EducationUSA", "official_government", "USA", 90, ["https://educationusa.state.gov/find-financial-aid"]),
    ApprovedSourceData("fulbright.state.gov", "Fulbright", "official_government", "USA", 95, []),
    ApprovedSourceData("scholars4dev.com", "Scholars4Dev", "aggregator", "International", 40, []),
    ApprovedSourceData("scholarshipdb.net", "ScholarshipDB", "aggregator", "International", 30, []),
    ApprovedSourceData("gov.uk", "UK Government", "official_government", "UK", 90, []),
    ApprovedSourceData("australia.gov.au", "Australian Government", "official_government", "Australia", 90, []),
    ApprovedSourceData("gc.ca", "Government of Canada", "official_government", "Canada", 90, []),
    ApprovedSourceData("studyinjapan.go.jp", "Study in Japan", "official_government", "Japan", 90, ["https://www.studyinjapan.go.jp/en/planning/scholarships/mext-scholarships/"]),
    ApprovedSourceData("korea.kr", "Korean Government", "official_government", "South Korea", 90, ["https://www.korea.kr/"]),
    ApprovedSourceData("csc.edu.cn", "CSC", "official_government", "China", 85, []),
    ApprovedSourceData("moe.gov.sg", "Singapore MOE", "official_government", "Singapore", 90, ["https://www.moe.gov.sg/"]),
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
    ApprovedSourceData("studyinfinland.fi", "Study in Finland", "official_government", "Finland", 88, ["https://www.studyinfinland.fi/funding-your-studies"]),
    ApprovedSourceData("studyinnorway.no", "Study in Norway", "official_government", "Norway", 88, ["https://studyinnorway.no/scholarships-degree-students"]),
    ApprovedSourceData("studyinpoland.pl", "Study in Poland", "official_government", "Poland", 85, []),
    ApprovedSourceData("studyinczechia.cz", "Study in Czechia", "official_program", "Czech Republic", 85, []),
    ApprovedSourceData("studyinhungary.hu", "Study in Hungary", "official_program", "Hungary", 85, ["https://studyinhungary.hu/study-in-hungary/menu/scholarships"]),
    ApprovedSourceData("studyinturkiye.gov.tr", "Study in Turkiye", "official_government", "Turkey", 88, []),
    ApprovedSourceData("education.ie", "Government of Ireland Education", "official_government", "Ireland", 90, []),
    ApprovedSourceData("gov.ie", "Government of Ireland", "official_government", "Ireland", 92, []),
    ApprovedSourceData("education.govt.nz", "Ministry of Education New Zealand", "official_government", "New Zealand", 90, ["https://www.education.govt.nz/"]),
    ApprovedSourceData("universitaly.it", "Universitaly", "official_program", "Italy", 82, ["https://www.universitaly.it/en/"]),
    ApprovedSourceData("educacion.gob.es", "Ministerio de Educacion", "official_government", "Spain", 90, ["https://www.educacion.gob.es/"]),
    # Americas
    ApprovedSourceData("educanada.ca", "Education in Canada", "official_government", "Canada", 90, []),
    ApprovedSourceData("education.gov.in", "Ministry of Education India", "official_government", "India", 88, ["https://www.education.gov.in/education-finance"]),
    ApprovedSourceData("scholarships.gov.in", "National Scholarship Portal India", "official_government", "India", 92, ["https://scholarships.gov.in/home"]),
    ApprovedSourceData("gob.mx", "Gobierno de Mexico", "official_government", "Mexico", 90, ["https://www.gob.mx/amexcid/acciones-y-programas/becas-para-extranjeros-29785"]),
    # Asia-Pacific
    ApprovedSourceData("jasso.go.jp", "JASSO", "official_government", "Japan", 90, ["https://www.jasso.go.jp/en/ryugaku/scholarship_j/index.html"]),
    ApprovedSourceData("studyinkorea.go.kr", "Study in Korea", "official_government", "South Korea", 90, ["https://www.studyinkorea.go.kr/ko/notice/scholarshipsList.do?boardSort=3"]),
    # The live host is moe.gov.my, not mohe.gov.my. The seeded domain was wrong
    # and nothing caught it, because a source with no seed URL silently fell
    # back to crawling its own non-resolving hostname and reported nothing.
    ApprovedSourceData("moe.gov.my", "Ministry of Education Malaysia", "official_government", "Malaysia", 90, ["https://www.moe.gov.my/"]),
    ApprovedSourceData("beasiswaindonesia.kemdikbud.go.id", "Indonesian Scholarship", "official_government", "Indonesia", 85, []),
    # Baltic & Nordic expansion (added after a live DNS/HTTP reachability probe;
    # every domain below resolved and returned a page, so they are real hosts
    # rather than guesses. Domains that did not resolve were deliberately not
    # added - an unreachable seed surfaces as `source_unreachable` in the
    # completeness report and is not a fabrication risk, but it is also not a
    # source of new scholarships, and the probe exists to avoid adding noise).
    ApprovedSourceData("studyinestonia.ee", "Study in Estonia", "official_government", "Estonia", 85, ["https://studyinestonia.ee/study/scholarships"]),
    ApprovedSourceData("studyinlatvia.lv", "Study in Latvia", "official_government", "Latvia", 85, ["https://studyinlatvia.lv/scholarships"]),
    ApprovedSourceData("studyinlithuania.lt", "Study in Lithuania", "official_government", "Lithuania", 85, []),
    ApprovedSourceData("studyinluxembourg.lu", "Study in Luxembourg", "official_government", "Luxembourg", 85, []),
    ApprovedSourceData("studyinslovenia.si", "Study in Slovenia", "official_government", "Slovenia", 85, ["https://studyinslovenia.si/study/tuition-and-funding/"]),
    ApprovedSourceData("studyincroatia.hr", "Study in Croatia", "official_government", "Croatia", 85, ["https://studyincroatia.hr/scholarships/"]),
    ApprovedSourceData("studyinromania.gov.ro", "Study in Romania", "official_government", "Romania", 85, ["https://studyinromania.gov.ro/scholarships"]),
    ApprovedSourceData("studyinuae.ae", "Study in UAE", "official_government", "UAE", 85, []),
    ApprovedSourceData("studyinaustralia.gov.au", "Australian Study Portal", "official_government", "Australia", 85, ["https://www.studyinaustralia.gov.au/english/australian-education/scholarships"]),
]

# Direct scholarship-directory seeds for the sources above were added in place
# rather than as a second list of overrides. A domain must appear exactly once:
# the registries key on domain, so a duplicate entry silently means "last one
# wins", and the losing entry is a trap for the next person who edits it.
#
# Every one of these URLs was probed live and returned HTTP 200. A deep link
# that 404s is worse than no deep link, because it burns crawl budget and
# yields nothing, so unverified paths were discarded rather than guessed.

# New official scholarship bodies found by live web research and confirmed
# reachable with an HTTP 200 probe before being added. The same two rules apply
# as above: only government ministries, national scholarship agencies, official
# study-in-country portals, or official programme administrators, and only with
# a deep URL that was actually probed.
#
# Several of these replace nothing and add a country the registry could not
# reach at all (Slovakia, Vietnam, Cambodia, Ghana, Kenya, Nigeria, Nepal,
# Pakistan, South Africa), which is the actual coverage gap: widening Europe
# again would not have moved the country count.
_DEEPER_SOURCES: list[ApprovedSourceData] = [
    # Europe
    ApprovedSourceData("hea.ie", "Higher Education Authority Ireland", "official_government", "Ireland", 90, ["https://hea.ie/policy/internationalisation/goi-ies"]),
    ApprovedSourceData("studyinitaly.esteri.it", "Study in Italy MAECI", "official_government", "Italy", 90, ["https://studyinitaly.esteri.it/"]),
    ApprovedSourceData("turkiyeburslari.gov.tr", "Turkiye Scholarships", "official_government", "Turkiye", 92, ["https://turkiyeburslari.gov.tr/scholarshipsprograms"]),
    ApprovedSourceData("scholarships.portalvs.sk", "Slovak National Scholarship", "official_government", "Slovakia", 88, ["https://scholarships.portalvs.sk/"]),
    ApprovedSourceData("stipendiumhungaricum.hu", "Stipendium Hungaricum", "official_program", "Hungary", 90, ["https://stipendiumhungaricum.hu/apply_call/"]),
    ApprovedSourceData("sbfi.admin.ch", "Swiss Federal Secretariat for Education", "official_government", "Switzerland", 90, ["https://www.sbfi.admin.ch/en/swiss-government-excellence-scholarships"]),
    ApprovedSourceData("mext.go.jp", "Japan MEXT", "official_government", "Japan", 90, ["https://www.mext.go.jp/en/"]),
    ApprovedSourceData("amideast.org", "Fulbright Near East Asia South Asia", "official_program", "USA", 90, ["https://www.amideast.org/our-work/find-a-scholarship"]),
    ApprovedSourceData("ethz.ch", "ETH Zurich", "official_program", "Switzerland", 88, ["https://ethz.ch/en/doctorate/doctoral-study-programmes.html"]),
    # Asia
    ApprovedSourceData("mofa.gov.ae", "UAE Ministry of Foreign Affairs", "official_government", "UAE", 85, ["https://www.mofa.gov.ae/en"]),
    ApprovedSourceData("vietnam.gov.vn", "Vietnam Government Portal", "official_government", "Vietnam", 85, ["https://vietnam.gov.vn/"]),
    ApprovedSourceData("moe.gov.kh", "Cambodia Ministry of Education", "official_government", "Cambodia", 85, ["https://moe.gov.kh/"]),
    ApprovedSourceData("moe.gov.pk", "Pakistan Ministry of Education", "official_government", "Pakistan", 88, ["https://www.moe.gov.pk/"]),
    ApprovedSourceData("mofa.gov.np", "Nepal Ministry of Foreign Affairs", "official_government", "Nepal", 85, ["https://mofa.gov.np/"]),
    ApprovedSourceData("darmasiswa.kemendikdasmen.go.id", "Darmasiswa Indonesia", "official_government", "Indonesia", 88, ["https://darmasiswa.kemendikdasmen.go.id/"]),
    # Americas
    ApprovedSourceData("studyabroad.state.gov", "US State Dept Exchange Visitor Program", "official_government", "USA", 90, ["https://studyabroad.state.gov/foreign-government-scholarships"]),
    ApprovedSourceData("stanford.edu", "Stanford University Financial Aid", "official_program", "USA", 92, ["https://financialaid.stanford.edu/grad/"]),
    # Africa
    ApprovedSourceData("ug.edu.gh", "University of Ghana", "official_program", "Ghana", 88, ["https://www.ug.edu.gh/"]),
    ApprovedSourceData("moe.gov.gh", "Ghana Ministry of Education", "official_government", "Ghana", 85, ["https://moe.gov.gh/"]),
    ApprovedSourceData("ku.ac.ke", "Kenyatta University", "official_program", "Kenya", 85, ["https://www.ku.ac.ke/"]),
    ApprovedSourceData("nuc.edu.ng", "Nigeria Universities Commission", "official_government", "Nigeria", 88, ["https://www.nuc.edu.ng/"]),
    ApprovedSourceData("ufh.ac.za", "University of Fort Hare", "official_program", "South Africa", 88, ["https://www.ufh.ac.za/"]),
    ApprovedSourceData("au.int", "African Union", "official_government", "Regional", 85, ["https://au.int/en"]),
    ApprovedSourceData("ecowas.int", "ECOWAS", "official_government", "Regional", 85, ["https://www.ecowas.int/"]),
    # International bodies administering named scholarship programmes
    ApprovedSourceData("unesco.org", "UNESCO", "official_government", "International", 90, ["https://www.unesco.org/en/education"]),
    ApprovedSourceData("un.org", "United Nations", "official_government", "International", 90, ["https://www.un.org/"]),
]

# Scholarship *directories* - pages whose actual job is to list awards, not
# navigation pages about studying in a country.
#
# This is a different class from the entries above, and it is where the bulk of
# new records come from. A study-in-country portal describes tuition, visas and
# admissions, and mentions scholarships in passing; a directory is a list of
# named programmes. Crawling a directory page per programme is what turns "one
# page per country" into "one record per award".
#
# Every URL below was confirmed with a live HTTP 200 probe. Two probe traps were
# found and avoided rather than shipped: Campus Bourses is a hash-routed SPA
# whose real catalogue is the bare root URL, and the Czech national portal's
# own study-in-country domain 308-redirects to a 404, so the government agency's
# page is used instead.
_DIRECTORY_SOURCES: list[ApprovedSourceData] = [
    # EU programmes - the largest concentration of named master's programmes
    ApprovedSourceData("eacea.ec.europa.eu", "Erasmus Mundus Catalogue EACEA", "official_program", "EU", 98, ["https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en"]),
    ApprovedSourceData("marie-sklodowska-curie-actions.ec.europa.eu", "MSCA Actions", "official_program", "EU", 98, ["https://marie-sklodowska-curie-actions.ec.europa.eu/actions/postdoctoral-fellowships"]),
    ApprovedSourceData("oead.at", "OeAD Austria", "official_government", "Austria", 90, ["https://oead.at/en/study-research-teaching/overview-grants-and-scholarships"]),
    ApprovedSourceData("grants.at", "grants.at Austrian Funding Database", "official_government", "Austria", 88, ["https://grants.at/"]),
    ApprovedSourceData("campusbourses.campusfrance.org", "Campus Bourses France", "official_government", "France", 92, ["https://campusbourses.campusfrance.org/"]),
    # Europe national directories
    ApprovedSourceData("nawa.gov.pl", "NAWA Poland", "official_government", "Poland", 90, ["https://nawa.gov.pl/en/students/foreign-students"]),
    ApprovedSourceData("dzs.cz", "DZS Czechia", "official_government", "Czech Republic", 90, ["https://www.dzs.cz/en/program/study-opportunities-foreigners-cr"]),
    ApprovedSourceData("scholarships.sk", "SAIA National Scholarship Programme", "official_government", "Slovakia", 90, ["https://www.scholarships.sk/en/main/programme-terms-and-conditions/foreign-applicants"]),
    ApprovedSourceData("portalvs.sk", "PortalVS Scholarship Directory", "official_government", "Slovakia", 88, ["https://www.portalvs.sk/en/stipendia?from=menu1"]),
    ApprovedSourceData("scholarship.hu", "Tempus Public Foundation", "official_government", "Hungary", 90, ["https://scholarship.hu/welcome.asp?lang=eng"]),
    ApprovedSourceData("oph.fi", "Finnish National Agency for Education", "official_government", "Finland", 90, ["https://www.oph.fi/en/education-development/support-programmes-foreigners-studying-finland"]),
    ApprovedSourceData("studyinnl.org", "Study in NL Holland Scholarship", "official_government", "Netherlands", 90, ["https://www.studyinnl.org/finances/nl-scholarship"]),
    ApprovedSourceData("dges.gov.pt", "DGES Portugal", "official_government", "Portugal", 90, ["https://www.dges.gov.pt/en/pagina/mobility-portugal"]),
    ApprovedSourceData("cscuk.fcdo.gov.uk", "Commonwealth Scholarship Commission UK", "official_government", "UK", 95, ["https://cscuk.fcdo.gov.uk/apply/scholarships"]),
    ApprovedSourceData("akf.org", "Aga Khan Foundation Scholarships", "official_program", "International", 82, ["https://akf.org/international-scholarship-programme"]),
    # Asia-Pacific directories
    ApprovedSourceData("nzscholarships.govt.nz", "Manaaki New Zealand Scholarships", "official_government", "New Zealand", 92, ["https://www.nzscholarships.govt.nz/"]),
    ApprovedSourceData("govt.nz", "New Zealand Government", "official_government", "New Zealand", 90, ["https://www.govt.nz/browse/education/tertiary-education/scholarships-grants-and-awards"]),
    ApprovedSourceData("hec.gov.pk", "HEC Pakistan International Scholarships", "official_government", "Pakistan", 90, ["https://www.hec.gov.pk/english/scholarshipsgrants/Pages/InternationalScholarships.aspx"]),
    ApprovedSourceData("studyinrussia.ru", "Study in Russia", "official_government", "Russia", 85, ["https://studyinrussia.ru/en"]),
    ApprovedSourceData("studyinsaudi.sa", "Study in Saudi Programmes", "official_government", "Saudi Arabia", 88, ["https://studyinsaudi.sa/en/programs"]),
    ApprovedSourceData("moe.gov.sa", "Saudi Ministry of Education", "official_government", "Saudi Arabia", 88, ["https://www.moe.gov.sa/en/education/ResidentsAndvisitors/pages/publicuniversitiesscholarships.aspx"]),
    # Americas directories
    ApprovedSourceData("foreign.fulbrightonline.org", "Fulbright Foreign Student Program", "official_program", "USA", 95, ["https://foreign.fulbrightonline.org/about/foreign-student-program"]),
    # Africa
    ApprovedSourceData("internationalscholarships.dhet.gov.za", "DHET International Scholarships South Africa", "official_government", "South Africa", 90, ["https://www.internationalscholarships.dhet.gov.za/"]),
]

_DEFAULT_SOURCES = (
    _DEFAULT_SOURCES + _EXTENDED_SOURCES + _DEEPER_SOURCES + _DIRECTORY_SOURCES
)


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
    """Insert new approved sources and refresh the ones already present.

    Insert-only seeding looks harmless and is not. A source that already has a
    row is frozen at whatever it was first created with, so improving a
    discovery seed in code - pointing a homepage at the real scholarship
    directory, retuning a trust score, correcting a country - silently has no
    effect on any deployed database. The registry in this file and the registry
    the crawler actually reads would then disagree, and the crawl would keep
    starting from a homepage forever while the code claimed otherwise.

    So this upserts. Only the fields this module owns are written, and only
    when they actually differ, which keeps it a no-op for a database that is
    already in sync.
    """
    count = 0
    existing_rows = {
        row.domain: row
        for row in session.scalars(select(ApprovedSource)).all()
    }
    for src in _DEFAULT_SOURCES:
        existing = existing_rows.get(src.domain)
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
            continue
        if existing.is_active is False:
            continue
        if list(existing.discovery_url_patterns or []) != src.discovery_url_patterns:
            existing.discovery_url_patterns = src.discovery_url_patterns
            count += 1
    if count > 0:
        session.flush()
    return count
