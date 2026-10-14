"""
Phase 1: Read-only reconciliation of 70 premium-card research records.

Reads:
- frontend/public/research/premium_card/output/index.json (70 records)
- backend/scholarzone.db (691 existing scholarships + approved_sources + knowledge_nodes)

Produces:
- research/premium_card/reconciliation_report.json
  Classification A/B/C/D/E for every research record, with match details.
"""
import json
import re
import hashlib
from pathlib import Path
from collections import defaultdict

import sqlite3

PROJECT_ROOT = Path(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone")
INDEX_JSON = PROJECT_ROOT / "frontend" / "public" / "research" / "premium_card" / "output" / "index.json"
DB_PATH = PROJECT_ROOT / "backend" / "scholarzone.db"
OUTPUT_DIR = PROJECT_ROOT / "research" / "premium_card"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SCHOLARSHIP_COLUMNS = [
    "id", "title", "country", "degree", "funding", "official_source",
    "official_source_url", "application_link", "deadline_date",
    "deadline_display", "deadline_precision", "english_requirement",
    "eligibility_summary", "is_verified", "verification_status",
    "last_verified_at", "last_verified_date", "verified_by",
    "image_url", "image_source_url", "image_source_type", "image_alt_text",
    "image_kind", "image_evaluation_status", "fully_funded",
    "tuition_coverage", "living_cost_coverage", "travel_coverage",
    "funding_amount", "funding_currency", "funding_period",
    "application_method", "official_updates_url", "catalogue_url",
    "eligibility", "benefits", "requirements", "coverage", "documents",
    "program_type", "is_archived", "status", "region", "duration",
    "application_period", "notes", "best_fit", "selection_notes",
    "official_details", "applicant_utility", "programme_verification",
    "created_at", "updated_at",
]


def normalize_url(url):
    """Normalize a URL for comparison: strip protocol, www, trailing slash."""
    if not url or not isinstance(url, str):
        return ""
    u = url.strip().lower()
    u = re.sub(r'^https?://', '', u)
    u = re.sub(r'^www\.', '', u)
    u = u.rstrip('/')
    return u


def normalize_title(title):
    """Normalize title: lowercase, remove punctuation, collapse spaces."""
    if not title:
        return ""
    t = title.lower().strip()
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def word_set(s):
    return set(normalize_title(s).split())


def jaccard(a, b):
    wa, wb = word_set(a), word_set(b)
    if not wa or not wb:
        return 0.0
    inter = wa & wb
    return len(inter) / len(wa | wb)


def contains_url(source_url, target_url):
    """Check if target_url's domain/path contains source_url's key parts."""
    if not source_url or not target_url:
        return False
    src = normalize_url(source_url)
    tgt = normalize_url(target_url)
    return src == tgt or tgt.startswith(src) or src.startswith(tgt)


def load_research():
    with open(INDEX_JSON, encoding="utf-8") as f:
        return json.load(f)


def load_scholarships(conn):
    cur = conn.cursor()
    cur.execute("SELECT * FROM scholarships")
    col_names = [d[0] for d in cur.description]
    scholarships = []
    for row in cur.fetchall():
        scholarships.append(dict(zip(col_names, row)))
    return scholarships


def load_approved_sources(conn):
    rows = conn.execute("SELECT * FROM approved_sources").fetchall()
    cur = conn.execute("SELECT * FROM approved_sources LIMIT 1")
    col_names = [d[0] for d in cur.description]
    return [dict(zip(col_names, row)) for row in rows]


def load_knowledge_nodes(conn):
    rows = conn.execute("SELECT * FROM knowledge_nodes").fetchall()
    cur = conn.execute("SELECT * FROM knowledge_nodes LIMIT 1")
    col_names = [d[0] for d in cur.description]
    return [dict(zip(col_names, row)) for row in rows]


def load_providers_from_db(conn):
    """Extract provider-like strings from scholarship data."""
    providers = set()
    for sch in load_scholarships(conn):
        if sch.get("official_source"):
            providers.add(sch["official_source"])
    return providers


def extract_research_identity(rec):
    """Extract identity signals from a research record."""
    data = rec.get("data") or {}
    title = data.get("title") or rec.get("source_title") or ""
    provider = data.get("provider") or rec.get("source_provider") or ""
    record_type = data.get("record_type") or "unknown"
    
    # Extract official source URL(s)
    official_urls = []
    official_domains = []
    source_types = []
    for src in data.get("official_sources", []) or []:
        if src.get("url"):
            official_urls.append(src["url"])
            official_domains.append(normalize_url(src["url"]))
        if src.get("source_type"):
            source_types.append(src["source_type"])
    
    # Extract application URL
    app_url = ""
    app_data = data.get("application", {}) or {}
    if app_data.get("official_application_url"):
        app_url = app_data["official_application_url"]
    
    # Extract location/country info from research
    # The research data might not have explicit country field, but we can infer from provider
    country = ""
    
    return {
        "research_id": data.get("id") or rec.get("id"),
        "title": title,
        "provider": provider,
        "record_type": record_type,
        "official_urls": official_urls,
        "official_domains": official_domains,
        "source_types": source_types,
        "app_url": app_url,
        "app_domain": normalize_url(app_url) if app_url else "",
        "country": country,
    }


def extract_db_identity(sch):
    """Extract identity signals from a DB scholarship."""
    return {
        "id": sch.get("id"),
        "title": sch.get("title") or "",
        "official_source": sch.get("official_source") or "",
        "official_source_url": normalize_url(sch.get("official_source_url") or ""),
        "application_link": normalize_url(sch.get("application_link") or ""),
        "country": sch.get("country") or "",
        "degree": sch.get("degree") or "",
        "provider_hints": extract_provider_hints(sch),
    }


def extract_provider_hints(sch):
    """Extract provider name hints from DB scholarship."""
    hints = set()
    for field in ["official_source", "notes", "program_type", "best_fit"]:
        val = sch.get(field)
        if val and isinstance(val, str) and len(val) < 200:
            hints.add(val)
    # Try to extract provider from official_details JSON
    try:
        details = sch.get("official_details")
        if details and isinstance(details, str):
            details = json.loads(details)
        if details and isinstance(details, dict):
            for k in ["provider", "institution", "organization", "award_body"]:
                v = details.get(k)
                if v:
                    hints.add(str(v))
    except (json.JSONDecodeError, TypeError):
        pass
    return hints


# Provider aliases: map research provider strings to known provider domains/names
PROVIDER_ALIASES = {
    "university of copenhagen": ["ku.dk", "ucph"],
    "aarhus university": ["au.dk", "aarhusuni"],
    "technical university of denmark": ["dtu.dk", "dtu"],
    "aalborg university": ["aau.dk", "aau"],
    "university of southern denmark": ["sdu.dk", "sdu"],
    "university of helsinki": ["helsinki.fi", "uhe"],
    "aalto university": ["aalto.fi", "aalto"],
    "tampere university": ["tuni.fi", "tampere"],
    "university of ouulu": ["oulu.fi", "oulu"],
    "university of eastern finland": ["uef.fi", "uef"],
    "university of turku": ["utu.fi", "utu"],
    "abo akademi university": ["abo.fi", "abo"],
    "stipendium hungaricum": ["stipendiumhungaricum.hu"],
    "fulbright": ["fulbright", "fulbrightonline.org"],
    "msca": ["marie-sklodowska-curie-actions.ec.europa.eu", "msca"],
    "jobbnorge": ["jobbnorge.no"],
    "uio": ["uio.no", "university of oslo"],
}

# Country inference from provider/title
def infer_country(text):
    t = text.lower()
    if any(x in t for x in ["ku.dk", "aarhus", "dtu.dk", "aau.dk", "sdu.dk", "denmark", "danish"]):
        return "Denmark"
    if any(x in t for x in ["helsinki", "aalto", "tampere", "oulu", "eastern finland", "turku", "abo akademi", "finland", "finnish"]):
        return "Finland"
    if any(x in t for x in ["hungar", "stipendium", "diaspora", "momentum", "mta.hu", "hungr"]):
        return "Hungary"
    if any(x in t for x in ["norway", "ntnu", "uio", "uib", "uiu", "stavanger", "norw"]):
        return "Norway"
    if any(x in t for x in ["fulbright", "usa", "us "]):
        return "United States"
    if any(x in t for x in ["curie", "europe", "ec.europa"]):
        return "European Union"
    if any(x in t for x in ["portugal", "coimbra", "aveiro", "nova", "ulisboa", "fct", "portug"]):
        return "Portugal"
    if any(x in t for x in ["spain", "cam es", "cAMES", "madrile", "spanish"]):
        return "Spain"
    return ""


def match_research_to_scholarship(identity, scholarships):
    """Improved matching using authoritative identity signals."""
    best_match = None
    best_score = 0.0
    match_reasons = []
    
    # Strategy 1: Exact official_source_url match (most authoritative)
    if identity["official_domains"]:
        for sch in scholarships:
            sch_url = sch.get("official_source_url") or ""
            sch_app = normalize_url(sch.get("application_link") or "")
            for dom in identity["official_domains"]:
                if dom and (normalize_url(sch_url) == dom or sch_app == dom):
                    best_match = sch
                    match_reasons.append(f"exact_url_match:{dom}")
                    return best_match, 1.0, match_reasons
    
    # Strategy 2: Application URL match
    if identity["app_domain"]:
        for sch in scholarships:
            sch_app = normalize_url(sch.get("application_link") or "")
            sch_url = normalize_url(sch.get("official_source_url") or "")
            if identity["app_domain"] == sch_app or identity["app_domain"] == sch_url:
                best_match = sch
                match_reasons.append(f"app_url_match:{identity['app_domain']}")
                return best_match, 0.95, match_reasons
    
    # Strategy 3: Enhanced title matching with provider boost
    for sch in scholarships:
        score = 0.0
        reasons = []
        
        # Title Jaccard similarity
        title_sim = jaccard(identity["title"], sch.get("title") or "")
        if title_sim > 0:
            score = max(score, title_sim)
            if title_sim >= 0.8:
                reasons.append(f"title_jaccard:{title_sim:.2f}")
        
        # Provider name overlap (extract from title since DB has no provider column)
        if identity["provider"]:
            provider_sim = jaccard(identity["provider"], sch.get("title") or "")
            if provider_sim > 0.3:
                score += 0.1
                reasons.append(f"provider_overlap:{provider_sim:.2f}")
        
        # Country match
        r_country = infer_country(identity["title"] + " " + identity["provider"])
        sch_country = (sch.get("country") or "").lower()
        if r_country and sch_country:
            if r_country.lower() in sch_country or sch_country in r_country.lower():
                score += 0.05
                reasons.append(f"country_match:{r_country}")
        
        # Official source domain match (partial)
        for dom in identity["official_domains"]:
            sch_url = normalize_url(sch.get("official_source_url") or "")
            if dom and sch_url:
                if dom.startswith(sch_url) or sch_url.startswith(dom):
                    score += 0.2
                    reasons.append(f"domain_partial:{dom}")
                elif dom in sch_url or sch_url in dom:
                    score += 0.15
                    reasons.append(f"domain_substring:{dom}")
        
        # Also check application_link domain
        for dom in identity["official_domains"]:
            sch_app = normalize_url(sch.get("application_link") or "")
            if dom and sch_app and (dom in sch_app or sch_app in dom):
                score += 0.1
                reasons.append(f"app_domain_substring:{dom}")
        
        if score > best_score:
            best_score = score
            best_match = sch
            match_reasons = reasons
    
    return best_match, best_score, match_reasons


def classify_record(identity, scholarships):
    """Classify a research record as A/B/C/D/E."""
    # Extract research data for classification
    research_id = identity["research_id"]
    title = identity["title"]
    provider = identity["provider"]
    record_type = identity["record_type"]
    official_urls = identity["official_urls"]
    
    # Check for duplicate detection
    # (handled separately)
    
    # E: Not actually a scholarship / should remain quarantined
    if record_type and record_type != "scholarship":
        return "E", "record_type is not scholarship", []
    
    # Check for research errors indicating non-scholarship
    # (will be checked in main script)
    
    # Match against DB
    matched_sch, score, reasons = match_research_to_scholarship(identity, scholarships)
    
    if matched_sch and score >= 0.7:
        # A: confidently matched existing scholarship
        return "A", reasons, [{"id": matched_sch.get("id"), "title": matched_sch.get("title"), "score": score}]
    elif matched_sch and score >= 0.4:
        # D: ambiguous match requiring manual review
        return "D", reasons, [{"id": matched_sch.get("id"), "title": matched_sch.get("title"), "score": score}]
    else:
        # B or C: need to check if it's a new scholarship or duplicate
        return "B_PENDING", reasons, []


def main():
    print("Phase 1: Read-only reconciliation")
    
    # Load research records
    research_records = load_research()
    print(f"Loaded {len(research_records)} research records")
    
    # Load DB
    conn = sqlite3.connect(str(DB_PATH))
    
    scholarships = load_scholarships(conn)
    print(f"Loaded {len(scholarships)} existing scholarships")
    
    approved_sources = load_approved_sources(conn)
    print(f"Loaded {len(approved_sources)} approved sources")
    
    # Build scholarships identity list
    sch_identities = [extract_db_identity(s) for s in scholarships]
    
    # Extract research identities
    research_identities = [extract_research_identity(rec) for rec in research_records]
    
    # Check for duplicates among research records
    # Group by normalized title + official URL
    title_url_map = defaultdict(list)
    for i, ident in enumerate(research_identities):
        key = normalize_title(ident["title"])
        if ident["official_domains"]:
            key += "|" + "|".join(sorted(ident["official_domains"]))
        title_url_map[key].append((i, ident))
    
    duplicate_groups = {k: v for k, v in title_url_map.items() if len(v) > 1}
    
    # Classify each record
    classification = []
    for i, (rec, ident) in enumerate(zip(research_records, research_identities)):
        data = rec.get("data") or {}
        research_id = ident["research_id"]
        title = ident["title"]
        record_type = ident["record_type"]
        
        # Check duplicate within research records
        norm_title = normalize_title(title)
        url_key = norm_title
        if ident["official_domains"]:
            url_key += "|" + "|".join(sorted(ident["official_domains"]))
        
        is_duplicate = False
        dup_of = None
        if url_key in duplicate_groups and len(duplicate_groups[url_key]) > 1:
            # Same title AND same URL = duplicate
            is_duplicate = True
            dup_group = duplicate_groups[url_key]
            # Find the first one as canonical
            for j, (idx, _) in enumerate(dup_group):
                if idx == i:
                    if j == 0:
                        dup_of = str(dup_group[0][1]["research_id"])
                    else:
                        dup_of = str(dup_group[0][1]["research_id"])
        
        # Check errors
        errors = data.get("research_errors", []) or []
        has_official_url = len(ident["official_urls"]) > 0
        has_source_type_official = "official_provider" in ident["source_types"]
        
        # Classify
        matches = []
        if record_type and record_type != "scholarship":
            category = "E"
            reason = f"record_type={record_type}"
        elif is_duplicate:
            category = "C"
            reason = f"duplicate of research-{dup_of}"
        else:
            category, reason, matches = classify_record(ident, scholarships)
            if category == "B_PENDING":
                if not title or not title.strip():
                    category = "E"
                    reason = "no title"
                elif has_official_url and has_source_type_official:
                    category = "B"
                    reason = f"genuinely_new (score={reason})"
                elif has_official_url:
                    category = "B"
                    reason = f"genuinely_new (has official URL, score={reason})"
                else:
                    has_provider = bool(ident["provider"])
                    if has_provider:
                        category = "D"
                        reason = f"needs_manual_review (no_official_url but has provider: {reason})"
                    else:
                        category = "E"
                        reason = f"insufficient_identity (no_url_no_provider: {reason})"

        classification.append({
            "research_id": research_id,
            "title": title,
            "provider": ident["provider"],
            "record_type": record_type,
            "official_urls": ident["official_urls"],
            "has_official_source_type": has_source_type_official,
            "has_official_url": has_official_url,
            "research_errors": errors,
            "category": category,
            "reason": reason,
            "match_details": matches,
            "match_score": matches[0]["score"] if matches else 0.0,
            "match_scholarship_id": matches[0]["id"] if matches else None,
        })
    
    # Summary
    cat_counts = defaultdict(int)
    for c in classification:
        cat_counts[c["category"]] += 1
    
    print("\n=== Classification Summary ===")
    for cat in ["A", "B", "C", "D", "E"]:
        print(f"  {cat}: {cat_counts.get(cat, 0)}")
    print(f"  B_PENDING: {cat_counts.get('B_PENDING', 0)}")
    
    # Write report
    report = {
        "generated_at": "2026-10-06T14:26:00Z",
        "phase": "Phase 1 - Read-only reconciliation",
        "total_research_records": len(research_records),
        "total_db_scholarships": len(scholarships),
        "approved_sources_count": len(approved_sources),
        "classification": classification,
        "duplicate_groups": [
            {"key": k, "research_ids": [str(r[1]["research_id"]) for r in v]}
            for k, v in duplicate_groups.items()
        ],
        "category_counts": dict(cat_counts),
        "match_analysis": {
            "matched_score_threshold": 0.7,
            "ambiguous_score_threshold": 0.4,
        },
    }
    
    output_path = OUTPUT_DIR / "reconciliation_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nReport written to: {output_path}")
    
    # Print details of each record
    print("\n=== Per-Record Classification ===")
    for c in classification:
        print(f"  [{c['category']}] {c['research_id']}: {c['title'][:60]}... - {c['reason'][:80]}")
    
    conn.close()


if __name__ == "__main__":
    main()
