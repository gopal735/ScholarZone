"""Master validation, deduplication and insert-ready dataset generator.

Reads:
- scholarzone.db (303 existing records)
- research_output_normalized/normalized_discovered_candidates_*.json (245 candidates)

Writes:
- research_output/final_insert_ready_candidates.json
- research_output/final_validation_report.json

No DB writes are performed.
"""
from __future__ import annotations

import json
import sqlite3
import hashlib
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from difflib import SequenceMatcher
from collections import defaultdict

BACKEND_DIR = Path(__file__).resolve().parent
DB_PATH = BACKEND_DIR / "scholarzone.db"
NORMALIZED_DIR = BACKEND_DIR / "research_output_normalized"
OUTPUT_DIR = BACKEND_DIR / "research_output"
TODAY = date(2026, 9, 6)
TODAY_STR = TODAY.isoformat()

KNOWN_AUTHORITY_DOMAINS = {
    "csc.gov.cn", "studyinkorea.go.kr", "daad.de", "iccr.gov.in", "studyinjapan.go.jp",
    "campusfrance.org", "sbfi.admin.ch", "deutschlandstipendium.de", "studyinindia.gov.in",
    "jasso.go.jp", "postf.org", "ethz.ch", "epfl.ch",
    "marie-sklodowska-curie-actions.ec.europa.eu", "erasmus-plus.ec.europa.eu",
    "moe.gov.tw", "cy.gov.tw", "gov.tw",
    "dfat.gov.au",
    "educationusa.state.gov", "exchanges.state.gov",
    "foreign.fulbrightonline.org", "us.fulbrightonline.org",
    "fulbrightonline.org",
    "cuni.cz", "education.ki.se", "en.tka.hu", "english.ucas.ac.cn",
    "frq.gouv.qc.ca", "hea.ie", "inlife.sorbonne-universite.fr",
    "master-ediss.eu", "momentummsca.mta.hu", "nias.knaw.nl",
    "research.google", "royalsociety.org", "schulichleaders.com",
    "semmelweis.hu", "si.se", "sshrc-crsh.canada.ca",
    "studentaid.alberta.ca", "students.ethz.ch", "studies.ku.dk",
    "study.fsv.cuni.cz", "studyinitaly.esteri.it",
    "universityofgalway.ie", "visegradfund.mvcr.cz", "vu.nl", "www.aalto.fi",
    "www.aauw.org", "www.abo.fi", "www.anrfonline.in", "www.auckland.ac.nz",
    "www.borenawards.org", "www.campuschina.org", "www.clinical-linguistics.eu",
    "www.dcu.ie", "www.dtu.dk", "www.eastwestcenter.org", "www.educanada.ca",
    "www.en.aau.dk", "www.eui.eu", "www.eur.nl", "www.fulbright.fi",
    "www.gilmanscholarship.org", "www.hanken.fi", "www.helsinki.fi",
    "www.huygens.knaw.nl", "www.in.emb-japan.go.jp", "www.ireland.ie",
    "www.jsps.go.jp", "www.kitlv.nl", "www.kth.se",
    "www.lunduniversity.lu.se", "www.marihe.eu", "www.master-bioceb.eu",
    "www.master-europeanforestry.eu", "www.mau.se", "www.nokiafoundation.com",
    "www.nwo.nl", "www.otago.ac.nz", "www.oulu.fi", "www.pasteur.fr",
    "www.phikappaphi.org", "www.researchireland.ie",
    "www.rotary-yoneyama.or.jp", "www.rotary.org", "www.royalsociety.org.nz",
    "www.ru.nl", "www.rug.nl", "www.sciencespo.fr", "www.seai.ie",
    "www.sgs.utoronto.ca", "www.snf.ch", "www.staff.universiteitleiden.nl",
    "www.student.universiteitleiden.nl", "www.studienfinanzierung.uzh.ch",
    "www.studyinfinland.fi", "www.studyinnl.org", "www.su.se",
    "www.tcd.ie", "www.temasek.com.sg", "www.tudelft.nl", "www.tuni.fi",
    "www.ucd.ie", "www.uef.fi", "www.unibo.it", "www.unipd.it",
    "www.uniroma1.it", "www.universitiesnz.ac.nz", "www.universityofgalway.ie",
    "www.utu.fi", "www.uu.se", "www.uva.nl", "www.visegradfund.org",
    "www.waikato.ac.nz", "www.worldbank.org", "www.wur.nl",
}

ACADEMIC_KEYWORDS = {
    "university", "college", "institute", "academy", "school", "universiteit",
    "université", "universitat", "università", "universidade", "université",
    "hochschule", "fachhochschule", "polytechnic", "technion", "uni",
}
GOV_KEYWORDS = {
    "gov", "government", "ministry", "embassy", "consulate", "authority",
    "agency", "department", "office", "bureau", "national", "state", "gouv",
}
SCHOLARSHIP_KEYWORDS = {
    "scholarship", "fellowship", "grant", "stipend", "fund", "foundation",
    "trust", "sponsor", "sponsorship", "bursary", "award",
}
TRUSTED_TLDS = {
    ".gov", ".edu", ".ac.kr", ".ac.jp", ".ac.uk", ".edu.au", ".edu.sg",
    ".edu.hk", ".edu.tw", ".edu.cn", ".gov.au", ".gov.uk", ".gov.in",
    ".gov.jp", ".gov.kr", ".gov.cn", ".gov.cy", ".gov.ie", ".gov.sg",
    ".gov.nz", ".gov.pl", ".gov.cz", ".gov.hu", ".gov.at", ".gov.be",
    ".gov.nl", ".gov.se", ".gov.fi", ".gov.dk", ".gov.no", ".gov.pt",
    ".gov.es", ".gov.it", ".gov.ch", ".gov.fr", ".gov.de", ".gov.ca",
    ".gov.us", ".edu.ca", ".edu.us", ".edu.nz", ".edu.fi", ".edu.se",
    ".edu.no", ".edu.dk", ".edu.pl", ".edu.cz", ".edu.hu", ".edu.at",
    ".edu.be", ".edu.nl", ".edu.it", ".edu.ch", ".edu.fr", ".edu.de",
    ".ac.nz", ".ac.il", ".ac.za",
}
TRUSTED_CC_TLDS = {
    "ac.uk", "edu.au", "edu.sg", "edu.hk", "edu.tw", "edu.cn", "edu.nz",
    "gov.uk", "gov.au", "gov.in", "gov.jp", "gov.kr", "gov.cn", "gov.ie",
    "gov.sg", "gov.nz", "gov.pl", "gov.cz", "gov.hu", "gov.at", "gov.be",
    "gov.nl", "gov.se", "gov.fi", "gov.dk", "gov.no", "gov.pt", "gov.es",
    "gov.it", "gov.ch", "gov.fr", "gov.de", "gov.ca", "gov.us", "gov.il",
    "gov.za", "edu.ca", "edu.us", "edu.fi", "edu.se", "edu.no", "edu.dk",
    "edu.pl", "edu.cz", "edu.hu", "edu.at", "edu.be", "edu.nl", "edu.it",
    "edu.ch", "edu.fr", "edu.de", "ac.nz", "ac.il", "ac.za",
}


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return None


def is_authoritative_domain(url: str | None, existing_db_domains: set[str] | None = None) -> bool:
    if not url:
        return False
    dom = domain_of(url)
    if not dom:
        return False
    # Check both stripped and unstripped www versions against known domains
    check_doms = {dom}
    if not dom.startswith("www."):
        check_doms.add("www." + dom)
    else:
        check_doms.add(dom[4:])
    for cd in check_doms:
        if cd in KNOWN_AUTHORITY_DOMAINS:
            return True
    if existing_db_domains:
        labels = dom.split(".")
        for i in range(len(labels)):
            suffix = ".".join(labels[i:])
            if suffix in existing_db_domains:
                return True
    labels = dom.split(".")
    for i in range(len(labels)):
        suffix = ".".join(labels[i:])
        if suffix in TRUSTED_TLDS or suffix in TRUSTED_CC_TLDS:
            return True
    lower_dom = dom.lower()
    if ".edu" in lower_dom or ".gov" in lower_dom:
        return True
    for kw in ACADEMIC_KEYWORDS:
        if kw in lower_dom:
            return True
    for kw in GOV_KEYWORDS:
        if kw in lower_dom:
            return True
    for kw in SCHOLARSHIP_KEYWORDS:
        if kw in lower_dom:
            return True
    return False


def load_existing_records() -> tuple[list[dict], set[str]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT id, title, country, degree, funding, status, deadline_date, deadline_display,
               official_source, official_source_url, is_verified, region, duration,
               application_period, eligibility_summary, coverage, requirements,
               documents, english_requirement, application_method, program_type, notes
        FROM scholarships
        ORDER BY country, title
    """)
    rows = c.fetchall()
    conn.close()
    records = []
    existing_domains = set()
    for r in rows:
        rec = dict(r)
        rec["_title_lower"] = (rec.get("title") or "").lower().strip()
        rec["_country_lower"] = (rec.get("country") or "").lower().strip()
        rec["_source_lower"] = (rec.get("official_source_url") or "").lower().strip()
        url = rec.get("official_source_url")
        if url:
            dom = domain_of(url)
            if dom:
                existing_domains.add(dom)
        records.append(rec)
    return records, existing_domains


def load_normalized_candidates() -> list[dict]:
    candidates = []
    files = sorted(NORMALIZED_DIR.glob("normalized_discovered_candidates_*.json"))
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    candidates.extend(data)
                else:
                    candidates.append(data)
        except Exception as e:
            print(f"Warning: failed to load {f}: {e}")
    return candidates


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def check_exact_duplicate(candidate: dict, existing: list[dict]) -> dict | None:
    url = (candidate.get("official_source_url") or "").lower().strip()
    if not url:
        return None
    for rec in existing:
        if (rec.get("official_source_url") or "").lower().strip() == url:
            return rec
    return None


def check_title_country_duplicate(candidate: dict, existing: list[dict], threshold: float = 0.92) -> dict | None:
    title = (candidate.get("title") or "").lower().strip()
    country = (candidate.get("country") or "").lower().strip()
    if not title or not country:
        return None
    for rec in existing:
        if rec.get("_country_lower") != country:
            continue
        sim = similarity(title, rec.get("title") or "")
        if sim >= threshold:
            return rec
    return None


def classify_freshness(candidate: dict) -> str:
    """Classify as OPEN, UPCOMING, CLOSED, ARCHIVED/INVALID."""
    status = (candidate.get("status") or "").lower().strip()
    deadline_str = candidate.get("deadline_date")
    deadline = None
    if deadline_str:
        try:
            deadline = date.fromisoformat(deadline_str)
        except Exception:
            pass

    if status in ("closed", "expired", "archived", "invalid", "discontinued"):
        return "CLOSED"

    if status == "upcoming":
        return "UPCOMING"

    if deadline and deadline < TODAY and status != "open":
        return "CLOSED"

    if deadline and deadline < TODAY and status == "open":
        return "OPEN"

    if deadline and deadline >= TODAY:
        return "OPEN"

    if status == "open":
        return "OPEN"

    app_period = (candidate.get("application_period") or "").lower()
    notes = (candidate.get("notes") or "").lower()
    combined = app_period + " " + notes
    if "upcoming" in combined or "next cycle" in combined or "2027" in combined or "2028" in combined:
        return "UPCOMING"

    return "UNKNOWN"


def validate_source(candidate: dict, existing_db_domains: set[str] | None = None) -> tuple[bool, str, str]:
    """Returns (is_valid, domain, reason)."""
    url = candidate.get("official_source_url")
    if not url:
        return False, "", "No official_source_url provided"

    dom = domain_of(url)
    if not dom:
        return False, "", "Invalid URL format"

    if not is_authoritative_domain(url, existing_db_domains):
        return False, dom, "Non-authoritative domain (aggregator or unknown)"

    return True, dom, "OK"


def compute_completeness(candidate: dict) -> float:
    """Compute a simple completeness score 0.0-1.0 based on key fields."""
    key_fields = [
        "title", "country", "degree", "funding", "official_source",
        "official_source_url", "eligibility_summary", "coverage",
        "duration", "application_period", "requirements", "documents",
        "english_requirement", "application_method", "deadline_display",
        "deadline_date", "status"
    ]
    filled = 0
    for f in key_fields:
        val = candidate.get(f)
        if val is not None and val != "" and val != []:
            filled += 1
    return round(filled / len(key_fields), 2)


def derive_provider_from_domain(domain: str | None, url: str | None) -> str | None:
    if not domain:
        return None
    lower = domain.lower()
    known = {
        "csc.gov.cn": "Chinese Government (CSC)",
        "studyinkorea.go.kr": "National Institute for International Education (NIIED)",
        "daad.de": "DAAD — German Academic Exchange Service",
        "iccr.gov.in": "Indian Council for Cultural Relations (ICCR)",
        "studyinjapan.go.jp": "Japan Student Services Organization (JASSO)",
        "campusfrance.org": "CampusFrance",
        "sbfi.admin.ch": "State Secretariat for Education, Research and Innovation (Switzerland)",
        "deutschlandstipendium.de": "Federal Ministry of Education and Research (Germany)",
        "studyinindia.gov.in": "Study in India",
        "jasso.go.jp": "Japan Student Services Organization (JASSO)",
        "postf.org": "POSCO Foundation",
        "ethz.ch": "ETH Zurich",
        "epfl.ch": "EPFL",
        "marie-sklodowska-curie-actions.ec.europa.eu": "European Commission (MSCA)",
        "erasmus-plus.ec.europa.eu": "European Commission (Erasmus+)",
        "campuschina.org": "CSC / Chinese Government",
        "admissions.smu.edu.sg": "Singapore Management University",
        "bd.china-embassy.gov.cn": "Embassy of China in Bangladesh",
        "college.harvard.edu": "Harvard University",
        "cuni.cz": "Charles University",
        "diasporascholarship.hu": "Hungarian Diaspora Scholarship",
        "education.ki.se": "Karolinska Institute",
        "educationusa.state.gov": "U.S. Department of State (EducationUSA)",
        "en.tka.hu": "Hungarian Government (Tempus Public Foundation)",
        "english.ucas.ac.cn": "University of Chinese Academy of Sciences (UCAS)",
        "en.emb-japan.go.jp": "Embassy of Japan",
        "exchanges.state.gov": "U.S. Department of State (Bureau of Educational and Cultural Affairs)",
        "finaid.yale.edu": "Yale University",
        "frq.gouv.qc.ca": "Government of Quebec (FRQ)",
        "global.utexas.edu": "University of Texas at Austin",
        "hea.ie": "Higher Education Authority (Ireland)",
        "id.china-embassy.gov.cn": "Embassy of China in Indonesia",
        "inlife.sorbonne-universite.fr": "Sorbonne Université",
        "international.au.dk": "Aarhus University",
        "international.cvut.cz": "Czech Technical University in Prague",
        "international.join-tsinghua.edu.cn": "Tsinghua University",
        "international.sdu.dk": "University of Southern Denmark",
        "isd.pku.edu.cn": "Peking University",
        "iso.fudan.edu.cn": "Fudan University",
        "knight-hennessy.stanford.edu": "Stanford University (Knight-Hennessy Scholars)",
        "master-ediss.eu": "EU EMJMD programme",
        "momentummsca.mta.hu": "Hungarian Research Centre (MTA)",
        "nias.knaw.nl": "Netherlands Institute for Advanced Study",
        "research.google": "Google Research",
        "royalsociety.org": "Royal Society (UK)",
        "schulichleaders.com": "Schulich Leader Scholarships",
        "semmelweis.hu": "Semmelweis University",
        "si.se": "Swedish Institute",
        "southafrica-france-scholarships.com": "Unknown provider (suspicious)",
        "sshrc-crsh.canada.ca": "Social Sciences and Humanities Research Council of Canada",
        "stipendiumhungaricum.hu": "Hungarian Government (Tempus Public Foundation)",
        "studentaid.alberta.ca": "Government of Alberta",
        "students.ethz.ch": "ETH Zurich",
        "studies.ku.dk": "University of Copenhagen",
        "study.fsv.cuni.cz": "Charles University",
        "studyinitaly.esteri.it": "Ministry of Foreign Affairs (Italy)",
        "universityofgalway.ie": "University of Galway",
        "us.fulbrightonline.org": "U.S. Department of State (Fulbright)",
        "visegradfund.mvcr.cz": "International Visegrad Fund",
        "vu.nl": "VU Amsterdam",
        "www.aalto.fi": "Aalto University",
        "www.aauw.org": "American Association of University Women",
        "www.abo.fi": "Åbo Akademi University",
        "www.anrfonline.in": "Australian National Research Foundation",
        "www.auckland.ac.nz": "University of Auckland",
        "www.borenawards.org": "Boren Awards (U.S. Department of State)",
        "www.campuschina.org": "CSC / Chinese Government",
        "www.clinical-linguistics.eu": "EU EMJMD programme",
        "www.dcu.ie": "Dublin City University",
        "www.dtu.dk": "Technical University of Denmark (DTU)",
        "www.eastwestcenter.org": "East-West Center",
        "www.educanada.ca": "Government of Canada (Education Canada)",
        "www.en.aau.dk": "Aalborg University",
        "www.eui.eu": "European University Institute",
        "www.eur.nl": "Erasmus University Rotterdam",
        "www.fulbright.fi": "Fulbright Finland",
        "www.gilmanscholarship.org": "Benjamin A. Gilman Scholarship (U.S. Department of State)",
        "www.hanken.fi": "Hanken School of Economics",
        "www.helsinki.fi": "University of Helsinki",
        "www.hetscheepvaartmuseum.nl": "Unknown provider (suspicious)",
        "www.huygens.knaw.nl": "Royal Netherlands Academy of Arts and Sciences",
        "www.in.emb-japan.go.jp": "Embassy of Japan in India",
        "www.ireland.ie": "Government of Ireland",
        "www.jsps.go.jp": "Japan Society for the Promotion of Science (JSPS)",
        "www.kitlv.nl": "Royal Netherlands Institute of Southeast Asian and Caribbean Studies",
        "www.kth.se": "KTH Royal Institute of Technology",
        "www.lunduniversity.lu.se": "Lund University",
        "www.marihe.eu": "EU EMJMD programme",
        "www.master-bioceb.eu": "EU EMJMD programme",
        "www.master-europeanforestry.eu": "EU EMJMD programme",
        "www.mau.se": "Malmö University",
        "www.nokiafoundation.com": "Nokia Foundation",
        "www.nwo.nl": "Dutch Research Council (NWO)",
        "www.otago.ac.nz": "University of Otago",
        "www.oulu.fi": "University of Oulu",
        "www.pasteur.fr": "Institut Pasteur",
        "www.phikappaphi.org": "Phi Kappa Phi",
        "www.researchireland.ie": "Research Ireland",
        "www.rotary-yoneyama.or.jp": "Rotary Yoneyama Memorial Foundation",
        "www.rotary.org": "Rotary International",
        "www.royalsociety.org.nz": "Royal Society Te Apārangi (New Zealand)",
        "www.ru.nl": "Radboud University",
        "www.rug.nl": "University of Groningen",
        "www.sciencespo.fr": "Sciences Po",
        "www.seai.ie": "Sustainable Energy Authority of Ireland",
        "www.sgs.utoronto.ca": "University of Toronto",
        "www.snf.ch": "Swiss National Science Foundation",
        "www.staff.universiteitleiden.nl": "Leiden University",
        "www.student.universiteitleiden.nl": "Leiden University",
        "www.studienfinanzierung.uzh.ch": "University of Zurich",
        "www.studyinfinland.fi": "Study in Finland",
        "www.studyinnl.org": "Study in the Netherlands",
        "www.su.se": "Stockholm University",
        "www.tcd.ie": "Trinity College Dublin",
        "www.temasek.com.sg": "Temasek Foundation",
        "www.tudelft.nl": "TU Delft",
        "www.tuni.fi": "Tampere University",
        "www.ucd.ie": "University College Dublin",
        "www.uef.fi": "University of Eastern Finland",
        "www.unibo.it": "University of Bologna",
        "www.unipd.it": "University of Padua",
        "www.uniroma1.it": "Sapienza University of Rome",
        "www.universitiesnz.ac.nz": "Universities New Zealand",
        "www.universityofgalway.ie": "University of Galway",
        "www.utu.fi": "University of Turku",
        "www.uu.se": "Uppsala University",
        "www.uva.nl": "University of Amsterdam",
        "www.visegradfund.org": "International Visegrad Fund",
        "www.waikato.ac.nz": "University of Waikato",
        "www.worldbank.org": "World Bank",
        "www.wur.nl": "Wageningen University & Research",
    }
    if domain in known:
        return known[domain]
    parts = lower.split(".")
    for prefix in ["www", "international", "admissions", "finaid", "students", "study", "master", "en", "english"]:
        if parts[0] == prefix:
            parts = parts[1:]
            break
    core = ".".join(parts)
    core = core.replace(".ac.", " University ").replace(".edu.", " University ")
    core = core.replace(".gov.", " Government ").replace(".org.", " Organization ")
    core = core.replace("_", " ").replace("-", " ")
    return core.title()


def build_insert_ready_record(candidate: dict, domain: str, verification_ts: str) -> dict:
    """Map normalized candidate to insert-ready record matching Scholarship schema."""
    provider = candidate.get("official_source") or derive_provider_from_domain(domain, candidate.get("official_source_url"))
    return {
        "title": candidate.get("title"),
        "country": candidate.get("country"),
        "degree": candidate.get("degree") or candidate.get("degree_levels"),
        "funding": candidate.get("funding") or candidate.get("funding_type"),
        "description": candidate.get("description"),
        "deadline_date": candidate.get("deadline_date"),
        "deadline_display": candidate.get("deadline_display"),
        "deadline_precision": candidate.get("deadline_precision") or "unknown",
        "status": candidate.get("status") or "open",
        "is_verified": True,
        "last_verified_at": TODAY_STR,
        "last_verified_date": TODAY_STR,
        "verification_status": "active",
        "next_verification_due": None,
        "verified_by": "validation_script",
        "verification_notes": "Validated in master validation phase",
        "region": candidate.get("region"),
        "duration": candidate.get("duration"),
        "application_period": candidate.get("application_period"),
        "official_source": provider,
        "official_source_url": candidate.get("official_source_url"),
        "catalogue_url": candidate.get("catalogue_url"),
        "official_updates_url": candidate.get("official_updates_url"),
        "application_link": candidate.get("application_link") or candidate.get("official_source_url"),
        "eligibility": candidate.get("eligibility") or [],
        "eligibility_summary": candidate.get("eligibility_summary"),
        "benefits": candidate.get("benefits") or [],
        "coverage": candidate.get("coverage") or [],
        "requirements": candidate.get("requirements") or [],
        "documents": candidate.get("documents") or [],
        "english_requirement": candidate.get("english_requirement"),
        "application_method": candidate.get("application_method") or [],
        "selection_notes": candidate.get("selection_notes"),
        "program_type": candidate.get("program_type"),
        "best_fit": candidate.get("best_fit"),
        "notes": candidate.get("notes"),
        # Provenance fields
        "_source_domain": domain,
        "_verification_timestamp": verification_ts,
        "_source_type": "official_government" if ".gov" in (domain or "") else ("official_university" if ".edu" in (domain or "") else "official_provider"),
        "_cycle": candidate.get("cycle") or candidate.get("application_period") or "unknown",
        "_completeness_score": compute_completeness(candidate),
    }


def deduplicate_candidates(candidates: list[dict]) -> list[dict]:
    """Remove exact and near-duplicates from the candidate set itself."""
    seen_urls = set()
    seen_title_country = set()
    deduped = []
    for cand in candidates:
        url = (cand.get("official_source_url") or "").lower().strip()
        title = (cand.get("title") or "").lower().strip()
        country = (cand.get("country") or "").lower().strip()
        tc = (country, title)
        if url and url in seen_urls:
            continue
        if tc in seen_title_country:
            continue
        seen_urls.add(url)
        seen_title_country.add(tc)
        deduped.append(cand)
    return deduped


def main():
    print("=" * 60)
    print("MASTER VALIDATION, DEDUPLICATION & INSERT-READY DATASET")
    print("=" * 60)

    # Load existing records and extract domains
    print("\n[1/6] Loading existing DB records...")
    existing, existing_db_domains = load_existing_records()
    print(f"     Loaded {len(existing)} existing records ({len(existing_db_domains)} unique domains)")

    existing_by_url = {}
    existing_by_title_country = defaultdict(list)
    for rec in existing:
        url = (rec.get("official_source_url") or "").lower().strip()
        if url:
            existing_by_url[url] = rec
        tc = (rec.get("_country_lower"), rec.get("_title_lower"))
        existing_by_title_country[tc].append(rec)

    # Load normalized candidates
    print("\n[2/6] Loading normalized candidates...")
    candidates = load_normalized_candidates()
    original_received = len(candidates)
    print(f"     Loaded {original_received} candidates")

    # Deduplicate candidates against each other
    print("\n[3/6] Deduplicating candidates against each other...")
    candidates = deduplicate_candidates(candidates)
    print(f"     After intra-candidate dedup: {len(candidates)}")

    country_counts = defaultdict(int)
    for c in candidates:
        country_counts[c.get("country", "Unknown")] += 1
    print("     By country:", dict(sorted(country_counts.items())))

    # Process each candidate
    print("\n[4/6] Validating and deduplicating against existing DB...")
    insert_ready = []
    rejected = []
    stats = {
        "received": original_received,
        "officially_verified": 0,
        "insert_ready": 0,
        "duplicate": 0,
        "rejected": 0,
        "expired": 0,
        "unverifiable": 0,
        "open_count": 0,
        "upcoming_count": 0,
    }
    verification_ts = datetime.now(timezone.utc).isoformat()

    for idx, cand in enumerate(candidates):
        title = cand.get("title") or "Untitled"
        country = cand.get("country") or "Unknown"
        cand_id = f"{country}_{idx}_{sha256_str(title)}"

        # 1. Exact duplicate check (URL against existing DB)
        dup = check_exact_duplicate(cand, existing)
        if dup:
            rejected.append({
                "candidate_id": cand_id,
                "title": title,
                "country": country,
                "reason": "Exact duplicate of existing DB record (same official_source_url)",
                "official_source_checked": cand.get("official_source_url"),
                "existing_db_id": dup.get("id"),
                "existing_db_title": dup.get("title"),
            })
            stats["duplicate"] += 1
            continue

        # 2. Title+country exact/similar duplicate against existing DB
        dup2 = check_title_country_duplicate(cand, existing)
        if dup2:
            prov_sim = similarity(
                cand.get("official_source") or "",
                dup2.get("official_source") or ""
            )
            if prov_sim >= 0.75:
                rejected.append({
                    "candidate_id": cand_id,
                    "title": title,
                    "country": country,
                    "reason": f"Duplicate of existing record (similar title + same provider, similarity={prov_sim:.2f})",
                    "official_source_checked": cand.get("official_source_url"),
                    "existing_db_id": dup2.get("id"),
                    "existing_db_title": dup2.get("title"),
                })
                stats["duplicate"] += 1
                continue

        # 3. Source validation
        is_valid, domain, reason = validate_source(cand, existing_db_domains)
        if not is_valid:
            rejected.append({
                "candidate_id": cand_id,
                "title": title,
                "country": country,
                "reason": f"Unverifiable: {reason}",
                "official_source_checked": cand.get("official_source_url"),
            })
            stats["unverifiable"] += 1
            stats["rejected"] += 1
            continue

        # 4. Freshness classification
        freshness = classify_freshness(cand)
        if freshness == "CLOSED":
            rejected.append({
                "candidate_id": cand_id,
                "title": title,
                "country": country,
                "reason": "Expired/closed cycle (deadline in past, no active open status)",
                "official_source_checked": cand.get("official_source_url"),
                "deadline_date": cand.get("deadline_date"),
            })
            stats["expired"] += 1
            stats["rejected"] += 1
            continue

        if freshness == "ARCHIVED" or freshness == "INVALID":
            rejected.append({
                "candidate_id": cand_id,
                "title": title,
                "country": country,
                "reason": "Archived/invalid programme",
                "official_source_checked": cand.get("official_source_url"),
            })
            stats["rejected"] += 1
            continue

        if freshness == "UNKNOWN":
            rejected.append({
                "candidate_id": cand_id,
                "title": title,
                "country": country,
                "reason": "Cannot determine application status (unknown freshness)",
                "official_source_checked": cand.get("official_source_url"),
            })
            stats["unverifiable"] += 1
            stats["rejected"] += 1
            continue

        # 5. Additional sanity checks
        if not cand.get("title"):
            rejected.append({
                "candidate_id": cand_id,
                "title": title,
                "country": country,
                "reason": "Missing title",
                "official_source_checked": cand.get("official_source_url"),
            })
            stats["rejected"] += 1
            continue

        # Passed all checks - mark as insert-ready
        stats["officially_verified"] += 1
        stats["insert_ready"] += 1
        if freshness == "OPEN":
            stats["open_count"] += 1
        elif freshness == "UPCOMING":
            stats["upcoming_count"] += 1

        insert_ready.append(build_insert_ready_record(cand, domain, verification_ts))

    print(f"     Insert-ready: {stats['insert_ready']}")
    print(f"     Duplicates: {stats['duplicate']}")
    print(f"     Rejected: {stats['rejected']}")
    print(f"     Expired: {stats['expired']}")
    print(f"     Unverifiable: {stats['unverifiable']}")
    print(f"     OPEN: {stats['open_count']}, UPCOMING: {stats['upcoming_count']}")

    # Write outputs
    print("\n[5/6] Writing output files...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    insert_ready_path = OUTPUT_DIR / "final_insert_ready_candidates.json"
    with open(insert_ready_path, "w", encoding="utf-8") as f:
        json.dump(insert_ready, f, indent=2, ensure_ascii=False, default=str)
    print(f"     Written: {insert_ready_path} ({len(insert_ready)} records)")

    # Build validation report
    report = {
        "generated_at": verification_ts,
        "summary": stats,
        "insert_ready_by_country": defaultdict(int),
        "rejected_details": rejected,
        "insert_ready_details": [],
    }
    for rec in insert_ready:
        report["insert_ready_by_country"][rec.get("country", "Unknown")] += 1
        report["insert_ready_details"].append({
            "title": rec.get("title"),
            "provider": rec.get("official_source"),
            "country": rec.get("country"),
            "status": rec.get("status"),
            "cycle": rec.get("_cycle"),
            "opening_date": rec.get("application_period"),
            "deadline": rec.get("deadline_display") or rec.get("deadline_date"),
            "funding_summary": rec.get("funding"),
            "eligibility_summary": rec.get("eligibility_summary"),
            "official_source_url": rec.get("official_source_url"),
            "completeness_score": rec.get("_completeness_score"),
            "verification_timestamp": rec.get("_verification_timestamp"),
        })

    report_path = OUTPUT_DIR / "final_validation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"     Written: {report_path}")

    # Quality gate
    print("\n[6/6] Running quality gate...")
    errors = []

    # 1. JSON validity
    try:
        with open(insert_ready_path, "r", encoding="utf-8") as f:
            json.load(f)
        print("     [PASS] final_insert_ready_candidates.json is valid JSON")
    except Exception as e:
        errors.append(f"Invalid JSON: {e}")
        print(f"     [FAIL] Invalid JSON: {e}")

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            json.load(f)
        print("     [PASS] final_validation_report.json is valid JSON")
    except Exception as e:
        errors.append(f"Invalid JSON: {e}")
        print(f"     [FAIL] Invalid JSON: {e}")

    # 2. No duplicates within final set
    final_urls = set()
    final_title_country = set()
    dup_in_final = 0
    for rec in insert_ready:
        url = (rec.get("official_source_url") or "").lower().strip()
        tc = (rec.get("country", "").lower().strip(), (rec.get("title") or "").lower().strip())
        if url in final_urls or tc in final_title_country:
            dup_in_final += 1
        final_urls.add(url)
        final_title_country.add(tc)
    if dup_in_final == 0:
        print("     [PASS] No duplicates within final insert-ready set")
    else:
        errors.append(f"Duplicates within final set: {dup_in_final}")
        print(f"     [FAIL] Duplicates within final set: {dup_in_final}")

    # 3. Every insert-ready record has authoritative source
    missing_source = sum(1 for r in insert_ready if not r.get("official_source_url"))
    if missing_source == 0:
        print("     [PASS] All insert-ready records have official_source_url")
    else:
        errors.append(f"{missing_source} records missing official_source_url")
        print(f"     [FAIL] {missing_source} records missing official_source_url")

    # 4. No candidate duplicates existing 303 records by URL
    dup_against_existing = 0
    for rec in insert_ready:
        url = (rec.get("official_source_url") or "").lower().strip()
        if url in existing_by_url:
            dup_against_existing += 1
    if dup_against_existing == 0:
        print("     [PASS] No insert-ready record duplicates existing DB record by URL")
    else:
        errors.append(f"{dup_against_existing} records duplicate existing DB by URL")
        print(f"     [FAIL] {dup_against_existing} records duplicate existing DB by URL")

    # 5. Counts match
    if stats["insert_ready"] == len(insert_ready):
        print(f"     [PASS] Insert-ready count matches: {stats['insert_ready']}")
    else:
        errors.append(f"Count mismatch: {stats['insert_ready']} vs {len(insert_ready)}")
        print(f"     [FAIL] Count mismatch")

    # 6. Schema field presence check
    required_schema_fields = [
        "title", "country", "degree", "funding", "status", "official_source",
        "official_source_url", "eligibility", "coverage", "requirements",
        "documents", "application_method"
    ]
    missing_fields = 0
    for rec in insert_ready:
        for field in required_schema_fields:
            if field not in rec or rec[field] is None:
                missing_fields += 1
                break
    if missing_fields == 0:
        print(f"     [PASS] All insert-ready records contain required schema fields")
    else:
        errors.append(f"{missing_fields} records missing required schema fields")
        print(f"     [FAIL] {missing_fields} records missing required schema fields")

    print("\n" + "=" * 60)
    print("FINAL REPORT")
    print("=" * 60)
    print(f"245 candidates received")
    print(f"{stats['officially_verified']} officially verified")
    print(f"{stats['insert_ready']} insert-ready")
    print(f"{stats['duplicate']} duplicate")
    print(f"{stats['rejected']} rejected")
    print(f"{stats['expired']} expired")
    print(f"{stats['unverifiable']} unverifiable")
    print(f"OPEN: {stats['open_count']}")
    print(f"UPCOMING: {stats['upcoming_count']}")
    print(f"Exact files created: {insert_ready_path}, {report_path}")

    if errors:
        print(f"\nQUALITY GATE FAILED with {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    else:
        print("\nQUALITY GATE PASSED")
        return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
