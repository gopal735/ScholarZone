"""Validate discovered scholarship candidates against existing database records.

This script:
1. Loads discovered candidates from JSON files
2. Loads existing scholarships from SQLite
3. Deduplicates against existing official_source_url and titles
4. Classifies status (OPEN, UPCOMING, CLOSED)
5. Generates final report and insert-ready dataset
"""

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any


DB_PATH = Path("scholarzone.db")
OUTPUT_DIR = Path("research_output_normalized")
OUTPUT_DIR.mkdir(exist_ok=True)


def load_existing_scholarships() -> list[dict[str, Any]]:
    """Load all existing scholarships from SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, country, degree, funding, description,
               deadline_date, deadline_display, deadline_precision, status,
               is_verified, last_verified_at, last_verified_date,
               verification_status, next_verification_due, verified_by,
               verification_notes, region, duration, application_period,
               official_source, official_source_url, image_url,
               image_source_type, image_verified_at, image_alt_text,
               eligibility, eligibility_summary, benefits, coverage,
               requirements, documents, english_requirement,
               application_method, selection_notes, program_type,
               best_fit, notes, created_at, updated_at
        FROM scholarships
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def normalize_url(url: str | None) -> str | None:
    """Normalize URL for comparison."""
    if not url:
        return None
    return url.strip().rstrip("/").lower()


def normalize_title(title: str) -> str:
    """Normalize title for comparison."""
    return " ".join(title.lower().split())


def deduplicate_candidates(
    candidates: list[dict[str, Any]],
    existing: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Deduplicate candidates against existing records.
    
    Returns:
        (new_records, duplicate_records, rejected_records)
    """
    existing_urls = set()
    existing_titles = {}
    
    for rec in existing:
        url = normalize_url(rec.get("official_source_url"))
        if url:
            existing_urls.add(url)
        title_key = normalize_title(rec.get("title", ""))
        if title_key:
            existing_titles[title_key] = rec
    
    new_records = []
    duplicate_records = []
    rejected_records = []
    
    for candidate in candidates:
        url = normalize_url(candidate.get("official_source_url"))
        title_key = normalize_title(candidate.get("title", ""))
        
        # Check URL duplicate
        if url and url in existing_urls:
            duplicate_records.append({
                "candidate": candidate,
                "reason": "URL already exists in database",
                "matched_url": url,
            })
            continue
        
        # Check title duplicate (when no URL or URL not matched)
        if title_key in existing_titles:
            existing_rec = existing_titles[title_key]
            existing_url = normalize_url(existing_rec.get("official_source_url"))
            if not url or url == existing_url:
                duplicate_records.append({
                    "candidate": candidate,
                    "reason": "Title already exists in database",
                    "matched_title": candidate.get("title"),
                })
                continue
        
        # Validate required fields
        required_fields = ["title", "country", "degree_levels", "funding_type", "official_source_url"]
        missing = [f for f in required_fields if not candidate.get(f)]
        if missing:
            rejected_records.append({
                "candidate": candidate,
                "reason": f"Missing required fields: {', '.join(missing)}",
            })
            continue
        
        # Validate URL format
        if url and not url.startswith("https://"):
            rejected_records.append({
                "candidate": candidate,
                "reason": "Invalid URL scheme (must be HTTPS)",
            })
            continue
        
        new_records.append(candidate)
    
    return new_records, duplicate_records, rejected_records


def classify_status(candidate: dict[str, Any]) -> str:
    """Classify scholarship status based on deadline information."""
    deadline_str = candidate.get("deadline_display", "") or candidate.get("deadline", "") or ""
    deadline_date = candidate.get("deadline_date")
    status = candidate.get("status", "").lower()
    
    if status in ["open", "upcoming", "closed", "expired"]:
        return status.upper()
    
    today = date.today()
    
    if deadline_date:
        if isinstance(deadline_date, str):
            try:
                deadline_date = date.fromisoformat(deadline_date)
            except (ValueError, TypeError):
                deadline_date = None
        
        if deadline_date:
            if deadline_date >= today:
                return "OPEN"
            else:
                return "CLOSED"
    
    # Fallback based on display string
    if "open" in deadline_str.lower() or "now open" in deadline_str.lower():
        return "OPEN"
    elif "upcoming" in deadline_str.lower() or "opens" in deadline_str.lower():
        return "UPCOMING"
    elif "closed" in deadline_str.lower() or "ended" in deadline_str.lower():
        return "CLOSED"
    
    return "UPCOMING"  # Default to upcoming if uncertain


def generate_report(
    country: str,
    existing_count: int,
    candidates: list[dict[str, Any]],
    new_records: list[dict[str, Any]],
    duplicates: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate a country-level report."""
    open_count = sum(1 for r in new_records if classify_status(r) == "OPEN")
    upcoming_count = sum(1 for r in new_records if classify_status(r) == "UPCOMING")
    closed_count = sum(1 for r in new_records if classify_status(r) == "CLOSED")
    
    return {
        "country": country,
        "existing_count": existing_count,
        "discovered_count": len(candidates),
        "verified_count": len(new_records),
        "open_count": open_count,
        "upcoming_count": upcoming_count,
        "closed_count": closed_count,
        "duplicate_count": len(duplicates),
        "rejected_count": len(rejected),
        "new_records": new_records,
        "duplicate_records": duplicates,
        "rejected_records": rejected,
    }


def main():
    """Main validation and reporting workflow."""
    print("Loading existing scholarships from database...")
    existing = load_existing_scholarships()
    print(f"Loaded {len(existing)} existing scholarships")
    
    # Group existing by country
    existing_by_country: dict[str, list[dict[str, Any]]] = {}
    for rec in existing:
        country = rec.get("country", "Unknown")
        existing_by_country.setdefault(country, []).append(rec)
    
    # Load discovered candidates from all JSON files
    candidate_files = sorted(OUTPUT_DIR.glob("normalized_*.json"))
    print(f"Found {len(candidate_files)} candidate files")
    
    all_candidates: dict[str, list[dict[str, Any]]] = {}
    for cf in candidate_files:
        country = cf.stem.replace("normalized_", "").replace("_", " ").title()
        # Clean up common prefixes
        for prefix in ["Discovered Candidates ", "Discovered "]:
            if country.startswith(prefix):
                country = country[len(prefix):]
        with open(cf, "r", encoding="utf-8") as f:
            candidates = json.load(f)
        all_candidates[country] = candidates
        print(f"Loaded {len(candidates)} candidates for {country}")
    
    # Process each country
    reports = {}
    all_new_records = []
    all_duplicates = []
    all_rejected = []
    
    for country, candidates in all_candidates.items():
        existing_count = len(existing_by_country.get(country, []))
        new_records, duplicates, rejected = deduplicate_candidates(candidates, existing)
        report = generate_report(country, existing_count, candidates, new_records, duplicates, rejected)
        reports[country] = report
        all_new_records.extend(new_records)
        all_duplicates.extend(duplicates)
        all_rejected.extend(rejected)
    
    # Generate summary
    total_existing = sum(len(v) for v in existing_by_country.values())
    total_discovered = sum(len(v) for v in all_candidates.values())
    total_new = len(all_new_records)
    total_duplicates = len(all_duplicates)
    total_rejected = len(all_rejected)
    total_open = sum(1 for r in all_new_records if classify_status(r) == "OPEN")
    total_upcoming = sum(1 for r in all_new_records if classify_status(r) == "UPCOMING")
    total_closed = sum(1 for r in all_new_records if classify_status(r) == "CLOSED")
    
    summary = {
        "total_existing": total_existing,
        "total_countries": len(existing_by_country),
        "total_discovered": total_discovered,
        "total_verified_new": total_new,
        "total_open": total_open,
        "total_upcoming": total_upcoming,
        "total_closed": total_closed,
        "total_duplicates": total_duplicates,
        "total_rejected": total_rejected,
        "countries_with_new_findings": sum(1 for r in reports.values() if r["verified_count"] > 0),
    }
    
    # Save outputs
    with open(OUTPUT_DIR / "validation_report.json", "w", encoding="utf-8") as f:
        json.dump({
            "summary": summary,
            "country_reports": reports,
        }, f, indent=2, ensure_ascii=False)
    
    with open(OUTPUT_DIR / "insert_ready_records.json", "w", encoding="utf-8") as f:
        json.dump(all_new_records, f, indent=2, ensure_ascii=False)
    
    # Print summary table
    print("\n" + "=" * 100)
    print("FINAL VALIDATION REPORT")
    print("=" * 100)
    print(f"{'Country':<20} {'Existing':>10} {'Found':>10} {'Verified':>10} {'OPEN':>8} {'UPCOMING':>10} {'CLOSED':>8} {'Dups':>8} {'Rej':>8}")
    print("-" * 100)
    
    for country in sorted(reports.keys()):
        r = reports[country]
        print(f"{country:<20} {r['existing_count']:>10} {r['discovered_count']:>10} {r['verified_count']:>10} "
              f"{r['open_count']:>8} {r['upcoming_count']:>10} {r['closed_count']:>8} "
              f"{r['duplicate_count']:>8} {r['rejected_count']:>8}")
    
    print("-" * 100)
    print(f"{'TOTAL':<20} {summary['total_existing']:>10} {summary['total_discovered']:>10} {summary['total_verified_new']:>10} "
          f"{summary['total_open']:>8} {summary['total_upcoming']:>10} {summary['total_closed']:>8} "
          f"{summary['total_duplicates']:>8} {summary['total_rejected']:>8}")
    print("=" * 100)
    print(f"\nCountries with new findings: {summary['countries_with_new_findings']}")
    print(f"Insert-ready records saved to: {OUTPUT_DIR / 'insert_ready_records.json'}")
    print(f"Full report saved to: {OUTPUT_DIR / 'validation_report.json'}")
    print("\n** NO RECORDS INSERTED - DRY RUN COMPLETE **")


if __name__ == "__main__":
    main()
