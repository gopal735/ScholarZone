#!/usr/bin/env python3
"""
Ingest world top-demand countries research findings into ScholarZone catalogue.
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
    return funding_str[:120] if len(funding_str) > 120 else funding_str


def map_status(status_str: str | None) -> str | None:
    """Map research status to catalogue status."""
    if not status_str:
        return "open"
    status_lower = status_str.lower()
    if status_lower in ("open", "currently open", "accepting applications"):
        return "open"
    elif status_lower in ("upcoming", "future", "announced", "opening"):
        return "upcoming"
    elif status_lower in ("closing soon", "closing-soon"):
        return "closing-soon"
    elif status_lower in ("closed", "ended", "deadline passed"):
        return "closed"
    elif status_lower in ("discontinued"):
        return "closed"  # Will be skipped
    elif status_lower in ("varies", "mixed"):
        return "upcoming"
    return "open"


def process_world_top_demand(filepath: Path) -> list[ScholarshipIngestionRecord]:
    """Process world top-demand research ledger format."""
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
            official_url = entry.get("official_source_url", "")
            
            if not title or not country or not official_url:
                print(f"Warning: Missing required fields in line {line_num}")
                continue
            
            # Skip discontinued
            status_val = entry.get("status", "")
            if "discontinued" in status_val.lower():
                print(f"Skipping discontinued: {title}")
                continue
            
            degree = entry.get("level", "Bachelor's, Master's, PhD")
            funding_type = map_funding_type(entry.get("funding_type"))
            if not funding_type:
                funding_type = "Partial Funding"
            
            status = map_status(entry.get("status"))
            if status == "closed":
                print(f"Skipping closed: {title}")
                continue
            
            deadline = entry.get("application_deadline", "")
            deadline_date = parse_date(deadline)
            
            record = ScholarshipIngestionRecord(
                name=title,
                country=country,
                degree_levels=degree,
                funding_type=funding_type,
                official_source_url=official_url,
                is_verified=True,
                last_verified_date=date.today(),
                region="World Top Demand",
                deadline=deadline,
                deadline_date=deadline_date,
                deadline_precision="exact" if deadline_date else "unknown",
                description=entry.get("notes", ""),
                eligibility=[entry.get("eligibility_criteria", "")] if entry.get("eligibility_criteria") else [],
                coverage=[entry.get("funding_amount", "")] if entry.get("funding_amount") else [],
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
        
        # Process world top-demand
        wtd_file = Path("backend/verification/research_ledger_world_top_demand.jsonl")
        if wtd_file.exists():
            print("Processing World Top-Demand...")
            wtd_records = process_world_top_demand(wtd_file)
            print(f"  Found {len(wtd_records)} records")
            all_records.extend(wtd_records)
        
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