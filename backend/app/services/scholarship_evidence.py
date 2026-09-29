"""Evidence layer for scholarship field extraction traceability.

Every extracted scholarship field that may become an update candidate is traceable
to the official source evidence that produced it.

This module is deterministic, read-only, and does not modify the database.
It integrates with ScholarshipExtractionResult and ChangeSet architecture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from urllib.parse import urlsplit

from .scholarship_extractor import ScholarshipExtractionResult
from .scholarship_diff import ChangeSet, FieldChangeType


class SourceType(str, Enum):
    """Classification of source authority for evidence items."""

    OFFICIAL_GOVERNMENT = "official_government"
    OFFICIAL_UNIVERSITY = "official_university"
    OFFICIAL_SCHOLARSHIP_PROGRAM = "official_scholarship_program"
    OFFICIAL_APPLICATION_PORTAL = "official_application_portal"
    THIRD_PARTY = "third_party"


class EvidenceStatus(str, Enum):
    """Status of an evidence item after safety evaluation."""

    HIGH_CONFIDENCE = "high_confidence"
    LOW_CONFIDENCE = "low_confidence"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    IDENTITY_CONFLICT = "identity_conflict"


# Official government domains and patterns
_GOVERNMENT_DOMAINS: frozenset[str] = frozenset({
    ".gov", ".gov.uk", ".gov.au", ".gc.ca", ".gob.mx",
    ".go.jp", ".go.kr", ".gov.in", ".gov.br", ".gob.ec",
    ".admin.ch", ".bund.de", ".gouv.fr", ".gov.sg",
})

_GOVERNMENT_HOST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^www\.gov\.", re.IGNORECASE),
    re.compile(r"^gov\.", re.IGNORECASE),
    re.compile(r"\.gov\.", re.IGNORECASE),
    re.compile(r"\.gov$", re.IGNORECASE),          # exchanges.state.gov
    re.compile(r"\.gob\.", re.IGNORECASE),
    re.compile(r"\.go\.", re.IGNORECASE),
    re.compile(r"\.gc\.ca$", re.IGNORECASE),
    re.compile(r"\.admin\.ch$", re.IGNORECASE),
    re.compile(r"\.bund\.de$", re.IGNORECASE),
    re.compile(r"\.gouv\.fr$", re.IGNORECASE),
    re.compile(r"\.gouv\.qc\.ca$", re.IGNORECASE),  # frq.gouv.qc.ca
    re.compile(r"\.govt\.nz$", re.IGNORECASE),       # www.education.govt.nz
    re.compile(r"\.europa\.eu$", re.IGNORECASE),    # EU institutions
    re.compile(r"^europa\.eu$", re.IGNORECASE),
]

# Host normalisation: strip a leading "www" / "www2" / "web" label so that
# www2.daad.de is recognised as the same official host as www.daad.de.
_HOST_PREFIX_RE = re.compile(r"^(?:www|web|www\d+|en|fr|de|it)\d*\.", re.IGNORECASE)


def _normalize_host(hostname: str) -> str:
    host = hostname.lower().split(":")[0]
    previous = None
    while previous != host:
        previous = host
        host = _HOST_PREFIX_RE.sub("", host)
    return host


# Public-suffix fragments that must not be treated as the registrable domain.
# Without these, "www.temasek.com.sg" reduces to "com.sg" and every curated
# entry under a multi-part suffix silently stops matching.
_MULTI_PART_SUFFIXES: frozenset[str] = frozenset({
    "com.sg", "com.au", "com.br", "com.tr", "co.uk", "org.uk", "ac.uk",
    "gov.uk", "co.jp", "or.jp", "ne.jp", "ac.jp", "go.jp", "co.kr", "or.kr",
    "co.nz", "govt.nz", "co.za", "org.za", "ac.za", "co.il", "co.in", "org.in",
    "gov.in", "com.cn", "gov.cn", "edu.cn", "ac.cn", "com.hk", "org.hk",
    "com.tw", "org.tw", "edu.tw", "co.hu", "gov.hu", "com.pl", "gov.pl",
    "com.es", "gob.es", "edu.es", "com.pt", "edu.pt", "com.gr", "edu.gr",
    "com.ua", "com.ru", "com.vn", "edu.vn", "com.my", "edu.my", "com.ph",
    "co.id", "or.id", "ac.id", "co.th", "in.th", "ac.th", "co.ke", "or.ke",
})


def _registrable(host: str) -> str:
    """Best-effort registrable domain, respecting multi-part public suffixes."""
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    tail2 = ".".join(parts[-2:])
    if tail2 in _MULTI_PART_SUFFIXES:
        return ".".join(parts[-3:])
    return tail2

# Official university domains
_UNIVERSITY_DOMAINS: frozenset[str] = frozenset({
    ".edu", ".ac.uk", ".ac.jp", ".ac.kr", ".ac.in",
    ".ac.nz", ".ac.za", ".edu.au", ".edu.br", ".edu.sg",
    ".uni-", ".university",
})

_UNIVERSITY_HOST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^www\.edu\.", re.IGNORECASE),
    re.compile(r"\.edu\.", re.IGNORECASE),
    re.compile(r"\.ac\.", re.IGNORECASE),
    re.compile(r"^uni-", re.IGNORECASE),
    re.compile(r"\.edu$", re.IGNORECASE),
    re.compile(r"\.ac\.\w+$", re.IGNORECASE),
    re.compile(r"\.cern$", re.IGNORECASE),          # careers.cern (CERN programmes)
    # European university naming conventions. Many universities outside the
    # UK/US do not use .ac or .edu, so the original patterns missed the
    # majority of the catalogue.
    re.compile(r"^(?:www\d*\.)?uni[a-z0-9-]*\.", re.IGNORECASE),   # unipd.it, unitn.it, unibo.it
    re.compile(r"\.(?:www\d*\.)?uni[a-z0-9-]*\.", re.IGNORECASE),  # bandi.unibo.it
    re.compile(r"\.universit(?:e|é|ae)[\w-]*\.", re.IGNORECASE),     # universite-paris-saclay.fr
    re.compile(r"\.university[\w-]*\.", re.IGNORECASE),             # lunduniversity.lu.se
    re.compile(r"\.unibe$", re.IGNORECASE),                         # rhodes.unibe.ch
    re.compile(r"\.univie$", re.IGNORECASE),
]

# Curated registrable domains of universities that appear in the catalogue.
# A real dry run showed 261 of 489 records (53%) misclassified as third party,
# which blocked enrichment for every one of them. Structural patterns alone
# cannot separate "www.kth.se" from an arbitrary .se site, so genuine
# institutions are listed explicitly. Each entry is a real awarding body.
_OFFICIAL_UNIVERSITY_DOMAINS: frozenset[str] = frozenset({
    "aalto.fi", "abo.fi", "aau.dk", "akf.org", "ares-ac.be", "bme.hu",
    "cbs.dk", "cern.ch", "cuni.cz", "cvut.cz", "dcu.ie", "dtu.dk",
    "epfl.ch", "ethz.ch", "galway.ie", "hanken.fi", "helsinki.fi",
    "ip-paris.fr", "jku.at", "kth.se", "ku.dk", "kuleuven.be",
    "li.se", "lu.se", "lunduniversity.lu.se", "lut.fi", "mau.se",
    "mcmaster.ca", "muni.cz", "pasteur.fr", "polimi.it", "rug.nl",
    "ru.nl", "sciencespo.fr", "sdu.dk", "sorbonne-universite.fr",
    "su.se", "tcd.ie", "tudelft.nl", "tugraz.at", "ucd.ie",
    "uni-graz.at", "unibas.ch", "unibocconi.it", "unibo.it", "unibs.it",
    "unige.ch", "unil.ch", "unimib.it", "unipd.it", "uniroma1.it",
    "unisg.ch", "unitn.it", "universite-paris-saclay.fr",
    "universiteitleiden.nl", "universityofgalway.ie", "up.pt", "usu.se",
    "ut.ee", "utu.fi", "utwente.nl", "uva.nl", "uwaterloo.ca",
    "uu.nl", "uu.se", "uzh.ch", "ulisboa.pt", "vu.nl",
    "wur.nl", "yorku.ca", "ubc.ca", "maastrichtuniversity.nl",
    "vluhr.be", "unsw.edu.au", "eur.nl", "bi.no", "tuni.fi",
    "chalmers.se", "liu.se", "umu.se", "tuwien.at", "ens-lyon.fr",
    "ki.se", "ugent.be", "fct.pt", "novasbe.unl.pt", "utoronto.ca",
    "au.dk", "cemm.at", "oulu.fi", "uef.fi", "semmelweis.hu",
})

# Public research bodies and intergovernmental agencies that administer their
# own named funding programmes.
_OFFICIAL_RESEARCH_DOMAINS: frozenset[str] = frozenset({
    "cern.ch", "esa.int", "insaindia.res.in", "cis.chinese.cn",
    "snf.ch", "knaw.nl", "akf.org", "kitlv.nl", "tka.hu",
})

# National study-abroad promotion agencies and scholarship portals.
_OFFICIAL_AGENCY_DOMAINS: frozenset[str] = frozenset({
    "studyinfinland.fi", "studyindenmark.dk", "studyinbelgium.be",
    "daad-bangladesh.org", "fulbright.fi", "ireland.ie",
    "research.ie", "hea.ie", "campusfrance.org",
    # Erasmus Mundus joint master / doctoral networks
    "marihe.eu", "clinical-linguistics.eu",
    # Government research councils and provincial study-aid portals
    "sshrc-crsh.canada.ca", "studentaid.alberta.ca",
    # Fulbright-Boren and comparable national fellowship portals
    "borenawards.org",
})

# National study-abroad promotion agencies declared official by the
# ApprovedSource registry (discovery_config._DEFAULT_SOURCES). Kept in sync
# with that registry by tests/test_source_classification.py::RegistryAgreement.
_REGISTRY_DECLARED_DOMAINS: frozenset[str] = frozenset({
    "swissuniversities.ch", "nuffic.nl", "studyinsweden.se",
    "studyinaustria.at", "studyinbelgium.be", "educationusa.state.gov",
    "studyinjapan.go.jp", "korea.kr", "moe.gov.sg", "gov.uk",
    "australia.gov.au", "gc.ca",
    # Extended national study-abroad portals and scholarship agencies. These
    # were added to widen country coverage, and every one of them has to be
    # declared here as well or the classifier would call a page on an approved
    # official domain "third party" - which sends the candidate to review for a
    # reason that has nothing to do with the candidate. The two aggregators
    # (scholars4dev.com, scholarshipdb.net) are deliberately absent: they are
    # not awarding bodies, and declaring them official would defeat the
    # aggregator guard in the discovery pipeline.
    "studyindenmark.dk", "studyinfinland.fi", "studyinnorway.no",
    "studyinpoland.pl", "studyinczechia.cz", "studyinhungary.hu",
    "studyinturkiye.gov.tr", "education.ie", "gov.ie",
    "education.govt.nz", "universitaly.it", "educacion.gob.es",
    "educanada.ca", "education.gov.in", "scholarships.gov.in", "gob.mx",
    "jasso.go.jp", "studyinkorea.go.kr", "moe.gov.my",
    "beasiswaindonesia.kemdikbud.go.id",
    # Baltic & Nordic expansion added after a live reachability probe. Every
    # domain here is a real, reachable official study portal, and declaring it
    # in both registries keeps the evidence layer from calling an approved
    # official seed "third party" - which would route it to review for a
    # reason that has nothing to do with the candidate.
    "studyinestonia.ee", "studyinlatvia.lv", "studyinlithuania.lt",
    "studyinluxembourg.lu", "studyinslovenia.si", "studyincroatia.hr",
    "studyinromania.gov.ro", "studyinuae.ae", "studyinaustralia.gov.au",
    # Direct deep-link seeds added to sources that were already in the
    # registry. Declaring them here is what stops the classifier from calling
    # a page on an approved official portal "third party", which would route a
    # perfectly good candidate to review for a reason that has nothing to do
    # with the candidate.
    "mofa.gov.ae", "vietnam.gov.vn", "moe.gov.kh", "moe.gov.pk", "mofa.gov.np",
    "moe.gov.gh", "nuc.edu.ng", "au.int", "ecowas.int", "unesco.org", "un.org",
    # National scholarship programmes that are official even though the host is
    # not a ministry domain.
    "hea.ie", "studyinitaly.esteri.it", "turkiyeburslari.gov.tr",
    "scholarships.portalvs.sk", "studyabroad.state.gov",
    "amideast.org", "ethz.ch", "stanford.edu", "ug.edu.gh", "ku.ac.ke",
    "ufh.ac.za", "darmasiswa.kemendikdasmen.go.id",
    # Scholarship directories. Declared for the same reason as the entries
    # above: an approved official directory must not be downgraded to "third
    # party" by the evidence layer, because that would route a legitimate
    # candidate to review for a reason unrelated to the candidate.
    "eacea.ec.europa.eu", "marie-sklodowska-curie-actions.ec.europa.eu",
    "oead.at", "grants.at", "campusbourses.campusfrance.org", "nawa.gov.pl",
    "dzs.cz", "scholarships.sk", "portalvs.sk", "scholarship.hu", "oph.fi",
    "studyinnl.org", "dges.gov.pt", "cscuk.fcdo.gov.uk", "akf.org",
    "nzscholarships.govt.nz", "govt.nz", "hec.gov.pk", "studyinrussia.ru",
    "studyinsaudi.sa", "moe.gov.sa", "foreign.fulbrightonline.org",
    "internationalscholarships.dhet.gov.za",
})

# Curated registrable domains of official scholarship programmes, government
# agencies, and funding foundations that administer a named programme. These are
# official for their own programme even though they are not .gov/.edu.
_OFFICIAL_PROGRAMME_DOMAINS: frozenset[str] = frozenset({
    # EU programmes and agencies
    "erasmus-plus.ec.europa.eu", "eacea.ec.europa.eu",
    "marie-sklodowska-curie-actions.ec.europa.eu", "master-ediss.eu",
    "master-bioceb.eu", "master-europeanforestry.eu",
    # National scholarship schemes, agencies and ministries
    "daad.de", "campusfrance.org", "campuschina.org", "studyinnl.org",
    "fulbrightonline.org", "si.se", "educanada.ca", "oead.at",
    "aecid.es", "esteri.it", "instituto-camoes.pt", "nzscholarships.govt.nz",
    "stipendiumhungaricum.hu", "diasporascholarship.hu", "momentummsca.mta.hu",
    "visegradfund.mvcr.cz", "visegradfund.org", "bse.eu", "uhr.no",
    "nwo.nl", "knaw.nl", "researchireland.ie", "temasek.com.sg",
    "study-uk.britishcouncil.org", "twas.org", "wipo.int", "worldbank.org",
    # Foundations and trusts administering named programmes
    "nokiafoundation.com", "snf.ch", "foundation.scg.ch", "postf.org",
    "rotary.org", "rotary-yoneyama.or.jp", "humboldt-foundation.de",
    "akf.org", "royalsociety.org", "royalsociety.org.nz",
    "phikappaphi.org", "aauw.org", "anrfonline.in", "borenaawards.org",
    "cambridgetrust.org", "gatescambridge.org", "gilmanscholarship.org",
    "humphreyfellowship.org", "jeffersonscholars.org",
    "mccallmacbainscholars.org", "schulichleaders.com",
    "trudeaufoundation.ca", "youarewelcomehereusa.org",
    "eastwestcenter.org", "aai-salzburg.at", "boell.de", "cern.ch",
    "research.google",
})

# Known scholarship program domains
_SCHOLARSHIP_PROGRAM_HOSTS: frozenset[str] = frozenset({
    "www.daad.de",
    "www.campusfrance.org",
    "www.sbfi.admin.ch",
    "www.studyinindia.gov.in",
    "www.jasso.go.jp",
    "www.deutschlandstipendium.de",
    "www.chevening.org",
    "csc.edu.cn",
})

# Known application portal domains
_APPLICATION_PORTAL_HOSTS: frozenset[str] = frozenset({
    "apply.daad.de",
    "portal.campusfrance.org",
    "apply.sbfi.admin.ch",
    "www.studyinindia.gov.in",
    "apply.jasso.go.jp",
    "www.applyweb.com",
    "www.commonapp.org",
    "www.universityadmissions.se",
    "www.ucas.com",
})

# Mapping from extractor field names to source text search patterns
# Used to find the smallest useful evidence snippet
_FIELD_EVIDENCE_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "scholarship_name": [
        re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL),
    ],
    "provider": [
        re.compile(r"(?:offered?\s+by|provided?\s+by|funded?\s+by|sponsored?\s+by)[:\s]+([^\n]+)", re.IGNORECASE),
    ],
    "degree_level": [
        re.compile(r'(?:degree|level)[:\s]+([^\n]+)', re.IGNORECASE),
    ],
    "eligibility": [
        re.compile(r'(?:eligib(?:ility)\s+criteria|criteria|eligib(?:ility)|requirements?)[:\s]+([^\n]+)', re.IGNORECASE),
    ],
    "duration": [
        re.compile(r'(?:duration|length)[:\s]+([^\n]+)', re.IGNORECASE),
    ],
    "deadline": [
        re.compile(r"deadline[:\s]+(.+?)(?:\n|$)", re.IGNORECASE),
        re.compile(r"applications?\s+close[:\s]+(.+?)(?:\n|$)", re.IGNORECASE),
        re.compile(r"apply\s+by[:\s]+(.+?)(?:\n|$)", re.IGNORECASE),
        re.compile(r"applications?\s+are\s+due[:\s]+(.+?)(?:\n|$)", re.IGNORECASE),
        re.compile(r"closing\s+date[:\s]+(.+?)(?:\n|$)", re.IGNORECASE),
        re.compile(r"due\s+date[:\s]+(.+?)(?:\n|$)", re.IGNORECASE),
    ],
    "award_amount": [
        re.compile(r'(?:award|amount|value)[:\s]+([^\n]+)', re.IGNORECASE),
    ],
    "tuition_coverage": [
        re.compile(r'(?:full[\s-]?tuition|tuition)[:\s]+(.+)', re.IGNORECASE),
    ],
    "living_stipend": [
        re.compile(r'(?:living\s+stipend|stipend)[:\s]+([^\n]+)', re.IGNORECASE),
    ],
    "gpa_requirement": [
        re.compile(r'(?:gpa|grade\s+point\s+average)[:\s]+([^\n]+)', re.IGNORECASE),
    ],
    "language_requirement": [
        re.compile(r'(?:language|english|ielts|toefl)[:\s]+([^\n]+)', re.IGNORECASE),
    ],
    "application_url": [
        re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL),
    ],
}


@dataclass(frozen=True)
class EvidenceItem:
    """A single piece of evidence supporting an extracted field value.

    Each evidence item traces one extracted field back to its source.
    """

    scholarship_id: int
    field_name: str
    extracted_value: Any
    source_url: str
    evidence_text: str
    confidence: str | None
    source_type: SourceType
    verification_timestamp: str
    status: EvidenceStatus = EvidenceStatus.MISSING


@dataclass
class EvidenceCollection:
    """A collection of evidence items for a single scholarship."""

    scholarship_id: int
    source_url: str
    items: list[EvidenceItem] = field(default_factory=list)
    collected_at: str = ""

    @property
    def high_confidence_items(self) -> list[EvidenceItem]:
        return [i for i in self.items if i.status == EvidenceStatus.HIGH_CONFIDENCE]

    @property
    def low_confidence_items(self) -> list[EvidenceItem]:
        return [i for i in self.items if i.status == EvidenceStatus.LOW_CONFIDENCE]

    @property
    def missing_items(self) -> list[EvidenceItem]:
        return [i for i in self.items if i.status == EvidenceStatus.MISSING]

    @property
    def ambiguous_items(self) -> list[EvidenceItem]:
        return [i for i in self.items if i.status == EvidenceStatus.AMBIGUOUS]

    @property
    def identity_conflict_items(self) -> list[EvidenceItem]:
        return [i for i in self.items if i.status == EvidenceStatus.IDENTITY_CONFLICT]

    @property
    def has_any_evidence(self) -> bool:
        return any(i.status not in (EvidenceStatus.MISSING,) for i in self.items)

    def get_evidence_for_field(self, field_name: str) -> EvidenceItem | None:
        for item in self.items:
            if item.field_name == field_name:
                return item
        return None


def classify_source(source_url: str) -> SourceType:
    """Classify a source URL by its authority level.

    Deterministic classification based on domain patterns.

    Order matters: programme hosts are checked before government and university
    patterns, because a programme operator (for example an EU funding agency) may
    also sit on a domain that would otherwise look governmental.
    """
    if not source_url:
        return SourceType.THIRD_PARTY

    parsed = urlsplit(source_url)
    raw_host = parsed.netloc.lower().split(":")[0]
    hostname = _normalize_host(raw_host)
    if not hostname:
        return SourceType.THIRD_PARTY

    registrable = _registrable(hostname)
    # Curated sets are checked against the normalised host, the raw host, and
    # the registrable domain, so both "www.daad.de" and "www2.daad.de" resolve
    # regardless of which form the catalogue happens to store.
    hosts = {hostname, raw_host, registrable}

    # A specific application portal wins over its parent domain: with
    # registrable-domain matching enabled, "apply.daad.de" would otherwise be
    # claimed by the curated "daad.de" programme entry.
    if hostname in _APPLICATION_PORTAL_HOSTS or raw_host in _APPLICATION_PORTAL_HOSTS:
        return SourceType.OFFICIAL_APPLICATION_PORTAL

    # Curated programme operators and named scholarship foundations.
    if hosts & _SCHOLARSHIP_PROGRAM_HOSTS or hosts & _OFFICIAL_PROGRAMME_DOMAINS:
        return SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM

    if hosts & _OFFICIAL_RESEARCH_DOMAINS:
        return SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM

    if hosts & _OFFICIAL_AGENCY_DOMAINS:
        return SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM

    if hosts & _REGISTRY_DECLARED_DOMAINS:
        return SourceType.OFFICIAL_GOVERNMENT

    # Government / public-institution patterns.
    for pattern in _GOVERNMENT_HOST_PATTERNS:
        if pattern.search(hostname) or pattern.search(raw_host):
            return SourceType.OFFICIAL_GOVERNMENT

    # University patterns: structural conventions first, then curated domains.
    for pattern in _UNIVERSITY_HOST_PATTERNS:
        if pattern.search(hostname) or pattern.search(raw_host):
            return SourceType.OFFICIAL_UNIVERSITY

    if hosts & _OFFICIAL_UNIVERSITY_DOMAINS:
        return SourceType.OFFICIAL_UNIVERSITY

    return SourceType.THIRD_PARTY


def _extract_evidence_text(
    field_name: str,
    extracted_value: Any,
    source_content: str,
) -> str:
    """Extract the smallest useful evidence snippet from source content.

    Returns the matching text snippet that supports the extracted value.
    If no specific pattern matches, returns an empty string.
    """
    if not source_content or extracted_value is None:
        return ""

    patterns = _FIELD_EVIDENCE_PATTERNS.get(field_name, [])

    for pattern in patterns:
        match = pattern.search(source_content)
        if match:
            # For patterns with groups, use the first group
            if match.lastindex and match.lastindex >= 1:
                return match.group(1).strip()
            return match.group(0).strip()

    # Fallback: try to find the extracted value directly in the source
    value_str = str(extracted_value)
    if value_str and value_str != "None":
        # Search for the value in the source content
        escaped = re.escape(value_str[:100])  # Limit search length
        fallback_pattern = re.compile(escaped, re.IGNORECASE)
        match = fallback_pattern.search(source_content)
        if match:
            # Return surrounding context (up to 200 chars)
            start = max(0, match.start() - 50)
            end = min(len(source_content), match.end() + 150)
            return source_content[start:end].strip()

    return ""


def _evaluate_evidence_status(
    confidence: str | None,
    evidence_text: str,
    change_type: FieldChangeType | None,
    is_identity_conflict: bool = False,
) -> EvidenceStatus:
    """Evaluate the status of an evidence item based on confidence and context."""
    if is_identity_conflict:
        return EvidenceStatus.IDENTITY_CONFLICT

    if change_type == FieldChangeType.IDENTITY_CONFLICT:
        return EvidenceStatus.IDENTITY_CONFLICT

    if confidence == "low":
        return EvidenceStatus.LOW_CONFIDENCE

    if not evidence_text or evidence_text.strip() == "":
        return EvidenceStatus.MISSING

    if confidence == "high":
        return EvidenceStatus.HIGH_CONFIDENCE

    if confidence == "medium":
        return EvidenceStatus.HIGH_CONFIDENCE

    return EvidenceStatus.LOW_CONFIDENCE


def collect_evidence(
    scholarship_id: int,
    source_url: str,
    source_content: str,
    extraction_result: ScholarshipExtractionResult,
    changeset: ChangeSet | None = None,
) -> EvidenceCollection:
    """Collect evidence for all extracted fields from a scholarship source.

    This is the main entry point for building the evidence layer.
    It is deterministic and read-only.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    source_type = classify_source(source_url)

    collection = EvidenceCollection(
        scholarship_id=scholarship_id,
        source_url=source_url,
        collected_at=timestamp,
    )

    # Build a map of field -> change info from changeset
    change_map: dict[str, Any] = {}
    identity_conflict_fields: set[str] = set()
    if changeset:
        for change in changeset.changes:
            change_map[change.field] = change
            if change.change_type == FieldChangeType.IDENTITY_CONFLICT:
                identity_conflict_fields.add(change.field)

    # Map extractor field names to ORM field names (from scholarship_diff._FIELD_CONFIG)
    extractor_to_orm_fields = {
        "scholarship_name": "title",
        "provider": "official_source",
        "degree_level": "degree",
        "eligibility": "eligibility",
        "duration": "duration",
        "application_method": "application_method",
        "deadline": "deadline_display",
        "status": "status",
        "application_url": "application_link",
    }

    # Collect evidence for all fields present in the extraction result
    processed_orm_fields: set[str] = set()

    for extractor_field, orm_field in extractor_to_orm_fields.items():
        if orm_field in processed_orm_fields:
            continue

        extracted_value = getattr(extraction_result, extractor_field, None)
        confidence = extraction_result.confidence.get(extractor_field)

        # Get change info if available
        change = change_map.get(orm_field)
        change_type = change.change_type if change else None
        is_identity_conflict = orm_field in identity_conflict_fields

        # Extract evidence text from source
        evidence_text = _extract_evidence_text(extractor_field, extracted_value, source_content)

        # Evaluate status
        status = _evaluate_evidence_status(confidence, evidence_text, change_type, is_identity_conflict)

        item = EvidenceItem(
            scholarship_id=scholarship_id,
            field_name=orm_field,
            extracted_value=extracted_value,
            source_url=source_url,
            evidence_text=evidence_text,
            confidence=confidence,
            source_type=source_type,
            verification_timestamp=timestamp,
            status=status,
        )
        collection.items.append(item)
        processed_orm_fields.add(orm_field)

    # Also collect evidence for unmapped extractor fields that have values
    unmapped_fields = [
        "eligible_nationalities", "eligible_fields", "academic_requirements",
        "gpa_requirement", "language_requirement", "test_requirements",
        "award_amount", "tuition_coverage", "living_stipend", "housing",
        "travel", "insurance", "renewal_conditions", "deadline_type",
        "scholarship_cycle",
    ]

    for extractor_field in unmapped_fields:
        extracted_value = getattr(extraction_result, extractor_field, None)
        if extracted_value is None:
            continue

        confidence = extraction_result.confidence.get(extractor_field)
        evidence_text = _extract_evidence_text(extractor_field, extracted_value, source_content)
        status = _evaluate_evidence_status(confidence, evidence_text, None, False)

        item = EvidenceItem(
            scholarship_id=scholarship_id,
            field_name=extractor_field,
            extracted_value=extracted_value,
            source_url=source_url,
            evidence_text=evidence_text,
            confidence=confidence,
            source_type=source_type,
            verification_timestamp=timestamp,
            status=status,
        )
        collection.items.append(item)

    return collection


def is_authoritative_source(source_type: SourceType) -> bool:
    """Check if a source type is authoritative (official)."""
    return source_type in {
        SourceType.OFFICIAL_GOVERNMENT,
        SourceType.OFFICIAL_UNIVERSITY,
        SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM,
        SourceType.OFFICIAL_APPLICATION_PORTAL,
    }


def can_automatically_update(collection: EvidenceCollection) -> tuple[bool, list[str]]:
    """Determine if the evidence collection supports automatic updates.

    Safety rules:
    - No evidence -> no automatic update
    - Low-confidence evidence -> not an automatic update candidate
    - Ambiguous evidence -> needs_review
    - Identity-conflict evidence -> needs_review

    Returns:
        Tuple of (can_update, reasons)
    """
    reasons: list[str] = []

    if not collection.has_any_evidence:
        reasons.append("No evidence available for any field")
        return False, reasons

    # Check for identity conflicts
    if collection.identity_conflict_items:
        reasons.append(f"Identity conflict detected on fields: {[i.field_name for i in collection.identity_conflict_items]}")
        return False, reasons

    # Check for ambiguous evidence
    if collection.ambiguous_items:
        reasons.append(f"Ambiguous evidence on fields: {[i.field_name for i in collection.ambiguous_items]}")
        return False, reasons

    # Check that we have at least one high-confidence item
    if not collection.high_confidence_items:
        reasons.append("No high-confidence evidence available")
        return False, reasons

    # Check that source is authoritative
    if collection.items:
        source_type = collection.items[0].source_type
        if not is_authoritative_source(source_type):
            reasons.append(f"Source is not authoritative: {source_type.value}")
            return False, reasons

    return True, reasons
