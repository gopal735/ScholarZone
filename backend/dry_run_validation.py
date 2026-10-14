"""Dry-run validation and coverage reporting for discovered scholarships."""

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

DB_PATH = Path("scholarzone.db")
REPORT_PATH = Path("dry_run_report.json")


def load_existing_urls() -> set[str]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT official_source_url FROM scholarships WHERE official_source_url IS NOT NULL")
    urls = {row[0].strip().rstrip("/") for row in cursor.fetchall() if row[0]}
    conn.close()
    return urls


def validate_record(record: dict[str, Any], existing_urls: set[str]) -> tuple[bool, str]:
    if not record.get("name"):
        return False, "missing name"
    if not record.get("country"):
        return False, "missing country"
    if not record.get("degree_levels"):
        return False, "missing degree_levels"
    if not record.get("official_source_url"):
        return False, "missing official_source_url"
    
    url = record["official_source_url"].strip().rstrip("/")
    if not url.startswith("https://"):
        return False, "official_source_url must be HTTPS"
    
    if url in existing_urls:
        return False, "duplicate official_source_url"
    
    if not record.get("funding_type") and not record.get("funding"):
        return False, "missing funding_type"
    
    return True, "valid"


def process_country_results(country: str, results: dict[str, Any], existing_urls: set[str]) -> dict[str, Any]:
    candidates = results.get("new_scholarships", [])
    rejected_duplicates = results.get("rejected_duplicates", [])
    rejected_stale = results.get("rejected_stale", [])
    rejected_unreachable = results.get("rejected_unreachable", [])
    
    validated = []
    rejected = []
    
    for record in candidates:
        is_valid, reason = validate_record(record, existing_urls)
        if is_valid:
            validated.append(record)
        else:
            rejected.append({"name": record.get("name", "unknown"), "reason": reason})
    
    return {
        "country": country,
        "searched_sources": results.get("searched_sources", []),
        "candidates_found": len(candidates),
        "validated_new": len(validated),
        "rejected_validation": len(rejected),
        "rejected_duplicates": len(rejected_duplicates),
        "rejected_stale": len(rejected_stale),
        "rejected_unreachable": len(rejected_unreachable),
        "new_scholarships": validated,
        "rejected_details": rejected,
        "coverage_assessment": results.get("coverage_assessment", "unknown"),
    }


def main():
    existing_urls = load_existing_urls()
    print(f"Loaded {len(existing_urls)} existing official_source_urls")
    
    countries = ["Australia", "Austria", "Belgium", "Canada", "China"]
    report = {
        "generated_at": date.today().isoformat(),
        "total_existing": 303,
        "countries_processed": 0,
        "total_new_found": 0,
        "total_validated": 0,
        "total_rejected": 0,
        "countries": {},
    }
    
    for country in countries:
        result_path = Path(f"research_{country.lower()}.json")
        if result_path.exists():
            with open(result_path) as f:
                results = json.load(f)
            country_report = process_country_results(country, results, existing_urls)
            report["countries"][country] = country_report
            report["total_new_found"] += country_report["validated_new"]
            report["total_validated"] += country_report["validated_new"]
            report["total_rejected"] += country_report["rejected_validation"] + country_report["rejected_duplicates"] + country_report["rejected_stale"] + country_report["rejected_unreachable"]
            report["countries_processed"] += 1
            print(f"{country}: {country_report['validated_new']} new, {country_report['rejected_validation']} validation rejects")
        else:
            report["countries"][country] = {"status": "pending", "error": "research file not found"}
            print(f"{country}: research file not found")
    
    report["total_after_projection"] = report["total_existing"] + report["total_new_found"]
    
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved to {REPORT_PATH}")
    print(f"Total new scholarships (dry-run): {report['total_new_found']}")
    print(f"Total after projection: {report['total_after_projection']}")


if __name__ == "__main__":
    main()
