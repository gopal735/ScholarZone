#!/usr/bin/env python3
"""
Ingest research findings into ScholarZone catalogue.

Processes research ledger JSONL files and converts to ScholarshipIngestionRecord
for database insertion via upsert_verified_scholarships.
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Add backend to path
BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.scholarship_ingestion import (
    ScholarshipIngestionRecord,
    upsert_verified_scholarships,
)
from app.database import get_session_factory, init_database


def parse_date(value: str | None) -> date | None:
    """Parse various date formats."""
    if not value:
        return None
    # Try multiple formats
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def map_funding_type(funding_str: str | None) -> str | None:
    """Map research funding type to catalogue funding label."""
    if not funding_str:
        return None
    funding_lower = funding_str.lower()
    if "fully funded" in funding_lower or "full tuition" in funding_lower or "full funding" in funding_lower:
        return "Fully Funded"
    elif "tuition waiver" in funding_lower or "tuition exemption" in funding_lower:
        return "Tuition Waiver"
    elif "partial" in funding_lower:
        return "Partial Funding"
    elif "stipend" in funding_lower and "tuition" not in funding_lower:
        return "Stipend"
    elif "need" in funding_lower and "met" in funding_lower:
        return "Need-Based Aid"
    elif "merit" in funding_lower:
        return "Merit-Based"
    return funding_str


def map_status(status_str: str | None) -> str | None:
    """Map research status to catalogue status."""
    if not status_str:
        return "open"
    status_lower = status_str.lower()
    if status_lower in ("open", "currently open", "accepting applications"):
        return "open"
    elif status_lower in ("upcoming", "future", "announced"):
        return "upcoming"
    elif status_lower in ("closing soon", "closing-soon"):
        return "closing-soon"
    elif status_lower in ("closed", "ended", "deadline passed"):
        return "closed"
    elif status_lower in ("limited", "mixed"):
        return "upcoming"
    return "open"


def extract_evidence_value(findings: dict, key: str) -> str | None:
    """Extract value from evidence findings dict."""
    if key in findings and isinstance(findings[key], dict):
        return findings[key].get("value")
    return None


def process_europe_gaps(filepath: Path) -> list[ScholarshipIngestionRecord]:
    """Process Europe gaps research ledger format."""
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse line {line_num}: {e}")
                continue
            
            title = entry.get("canonical_title", "")
            official_url = entry.get("official_source_url", "")
            findings = entry.get("evidence_backed_findings", {})
            
            if not title or not official_url:
                print(f"Warning: Missing required fields in line {line_num}")
                continue
            
            # Infer country from URL or title
            country = "Europe"  # default
            for c in ["Bulgaria", "Croatia", "Estonia", "Latvia", "Lithuania", "Romania", 
                      "Slovakia", "Slovenia", "Malta", "Luxembourg", "Iceland", "Cyprus"]:
                if c.lower() in title.lower() or c.lower() in official_url.lower():
                    country = c
                    break
            
            degree = extract_evidence_value(findings, "degree_levels") or "Bachelor's, Master's, PhD"
            
            # Determine funding type
            funding_cov = extract_evidence_value(findings, "funding_coverage") or ""
            funding_type = map_funding_type(funding_cov)
            # Ensure funding_type is within length limit
            if funding_type and len(funding_type) > 120:
                funding_type = funding_type[:117] + "..."
            if not funding_type:
                funding_type = "Partial Funding"
            
            # Status - mostly closed for 2026/27, some open
            status = "open"  # default
            deadline = extract_evidence_value(findings, "application_deadline") or extract_evidence_value(findings, "deadline") or ""
            deadline_date = parse_date(deadline)
            
            # Coverage
            coverage = [funding_cov] if funding_cov else []
            
            # Eligibility
            eligibility = []
            for k in ["eligibility_nationality", "eligible_countries", "eligible_applicants"]:
                val = extract_evidence_value(findings, k)
                if val:
                    eligibility.append(val)
            
            # Requirements
            requirements = []
            for k in ["application_process", "nomination_deadline", "application_deadlines"]:
                val = extract_evidence_value(findings, k)
                if val:
                    requirements.append(val)
            
            record = ScholarshipIngestionRecord(
                name=title,
                country=country,
                degree_levels=degree,
                funding_type=funding_type,
                official_source_url=official_url,
                is_verified=True,
                last_verified_date=date.today(),
                region="Europe",
                deadline=deadline,
                deadline_date=deadline_date,
                deadline_precision="exact" if deadline_date else "unknown",
                description=entry.get("notes", ""),
                eligibility=eligibility,
                coverage=coverage,
                requirements=requirements,
                english_requirement=extract_evidence_value(findings, "language_requirements"),
                program_type=extract_evidence_value(findings, "programme_type"),
            )
            records.append(record)
    
    return records


def process_north_america(filepath: Path) -> list[ScholarshipIngestionRecord]:
    """Process North America research ledger format."""
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse line {line_num}: {e}")
                continue
            
            title = entry.get("canonical_title", "")
            official_url = entry.get("official_source_url", "")
            findings = entry.get("evidence_backed_findings", {})
            
            # Skip discontinued
            status_val = extract_evidence_value(findings, "status") or ""
            if "discontinued" in status_val.lower():
                print(f"Skipping discontinued: {title}")
                continue
            
            if not title or not official_url:
                print(f"Warning: Missing required fields in line {line_num}")
                continue
            
            # Determine country
            country = "United States" if any(u in official_url for u in ["fulbright", "harvard", "stanford", "mit", "utoronto", "mcgill", "ualberta"]) else "Canada"
            if "vanier" in title.lower() or "banting" in title.lower() or "mcgill" in title.lower() or "ualberta" in title.lower():
                country = "Canada"
            
            degree = "Bachelor's, Master's, PhD"
            funding_type = map_funding_type(extract_evidence_value(findings, "funding") or "")
            if funding_type and len(funding_type) > 120:
                funding_type = funding_type[:117] + "..."
            if not funding_type:
                funding_type = "Partial Funding"
            
            deadline = extract_evidence_value(findings, "deadline") or extract_evidence_value(findings, "scholarship_deadline") or ""
            deadline_date = parse_date(deadline)
            
            status = map_status(extract_evidence_value(findings, "application_status"))
            
            coverage = []
            val = extract_evidence_value(findings, "funding") or extract_evidence_value(findings, "coverage") or ""
            if val:
                coverage.append(val)
            
            eligibility = []
            val = extract_evidence_value(findings, "eligibility") or extract_evidence_value(findings, "eligible_countries") or ""
            if val:
                eligibility.append(val)
            
            requirements = []
            for k in ["nomination_deadline", "admission_deadline", "scholarship_deadline", "application_forms"]:
                val = extract_evidence_value(findings, k)
                if val:
                    requirements.append(val)
            
            record = ScholarshipIngestionRecord(
                name=title,
                country=country,
                degree_levels=degree,
                funding_type=funding_type,
                official_source_url=official_url,
                is_verified=True,
                last_verified_date=date.today(),
                region="North America",
                deadline=deadline,
                deadline_date=deadline_date,
                deadline_precision="exact" if deadline_date else "unknown",
                description=entry.get("notes", ""),
                eligibility=eligibility,
                coverage=coverage,
                requirements=requirements,
                english_requirement=None,
                program_type=extract_evidence_value(findings, "programme_name") or extract_evidence_value(findings, "programme_type"),
            )
            records.append(record)
    
    return records


def process_top_tier_asia_pacific(filepath: Path) -> list[ScholarshipIngestionRecord]:
    """Process Top-Tier Asia-Pacific research ledger format."""
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse line {line_num}: {e}")
                continue
            
            title = entry.get("program_name", "")
            country = entry.get("country", "")
            official_url = entry.get("official_url", "")
            
            if not title or not country or not official_url:
                print(f"Warning: Missing required fields in line {line_num}")
                continue
            
            degree = entry.get("level", "Bachelor's, Master's, PhD")
            funding_type = map_funding_type(entry.get("funding_type"))
            if funding_type and len(funding_type) > 120:
                funding_type = funding_type[:117] + "..."
            if not funding_type:
                funding_type = "Partial Funding"
            status = map_status(entry.get("status"))
            
            deadline = entry.get("application_close_date", "")
            deadline_date = parse_date(deadline)
            
            record = ScholarshipIngestionRecord(
                name=title,
                country=country,
                degree_levels=degree,
                funding_type=funding_type,
                official_source_url=official_url,
                is_verified=True,
                last_verified_date=date.today(),
                region="Asia-Pacific",
                deadline=entry.get("coverage", ""),
                deadline_date=deadline_date,
                deadline_precision="exact" if deadline_date else "unknown",
                description=entry.get("notes", ""),
                eligibility=[entry.get("eligibility", "")] if entry.get("eligibility") else [],
                coverage=[entry.get("coverage", "")] if entry.get("coverage") else [],
                requirements=[],
                english_requirement=None,
                program_type=entry.get("funding_type"),
            )
            records.append(record)
    
    return records


def main():
    init_database()
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        all_records = []
        
        # Process Europe gaps
        eu_file = Path("backend/verification/research_ledger_europe_gaps.jsonl")
        if eu_file.exists():
            print("Processing Europe gaps...")
            eu_records = process_europe_gaps(eu_file)
            print(f"  Found {len(eu_records)} records")
            all_records.extend(eu_records)
        
        # Process North America
        na_file = Path("backend/verification/research_ledger_north_america.jsonl")
        if na_file.exists():
            print("Processing North America...")
            na_records = process_north_america(na_file)
            print(f"  Found {len(na_records)} records")
            all_records.extend(na_records)
        
        # Process Top-Tier Asia-Pacific
        ap_file = Path("backend/verification/research_ledger_top_tier_asia_pacific.jsonl")
        if ap_file.exists():
            print("Processing Top-Tier Asia-Pacific...")
            ap_records = process_top_tier_asia_pacific(ap_file)
            print(f"  Found {len(ap_records)} records")
            all_records.extend(ap_records)
        
        print(f"\nTotal records to ingest: {len(all_records)}")
        
        if all_records:
            created, updated = upsert_verified_scholarships(session, all_records)
            print(f"\nIngestion complete: {created} created, {updated} updated")
        else:
            print("No records to ingest")
        
    finally:
        session.close()


if __name__ == "__main__":
    main()