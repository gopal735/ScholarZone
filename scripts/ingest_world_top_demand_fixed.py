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


# Map scholarship names to official URLs
SCHOLARSHIP_URLS = {
    "DAAD-EPOS": "https://www.daad.de/epos",
    "Erasmus Mundus": "https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters",
    "Eiffel": "https://www.campusfrance.org/en/france-excellence-eiffel-scholarship-program",
    "NL Scholarship": "https://www.studyinnl.org/finances/nl-scholarship",
    "SI Global Professionals": "https://si.se/en/apply/scholarships/swedish-institute-scholarships-for-global-professionals/",
    "Swiss Excellence": "https://www.sbfi.admin.ch/en/swiss-government-excellence-scholarships",
    "MAECI": "https://www.esteri.it/en/servizi-opportunita/opportunita/borse-di-studio/per-cittadini-stranieri/borsestudio_stranieri",
    "Invest Your Talent": "https://investyourtalentapplication.esteri.it/SitoIYT/EN/invest-your-talent-in-italy",
    "MAEC-AECID": "https://www.aecid.es/",
    "VLIR-UOS": "https://www.vliruos.be/get-funded/study-scholarships",
    "Ernst Mach Worldwide": "https://oead.at/en/study-research-teaching/overview-grants-and-scholarships/ernst-mach-grant",
    "Ernst Mach FH": "https://oead.at/en/study-research-teaching/overview-grants-and-scholarships/ernst-mach-grant",
    "Ernst Mach ASEA": "https://oead.at/en/study-research-teaching/overview-grants-and-scholarships/ernst-mach-grant",
    "Fulbright Foreign Student": "https://foreign.fulbrightonline.org/",
    "CGRS-D": "https://www.nserc-crsng.gc.ca/Students-Etudiants/PG-CS/CGRS-D-BRCD_eng.asp",
    "CPRA": "https://www.nserc-crsng.gc.ca/Students-Etudiants/PD-PD/CPRA-BRPC_eng.asp",
    "Pearson": "https://future.utoronto.ca/pearson-scholarships",
    "McGill": "https://www.mcgill.ca/studentaid/scholarships-aid/future-undergrads/entrance-scholarships",
    "Destination Australia": "https://www.education.gov.au/destination-australia",
    "ANU": "https://study.anu.edu.au/scholarships",
    "Melbourne": "https://scholarships.unimelb.edu.au/",
    "UNSW": "https://www.scholarships.unsw.edu.au/",
    "UWA": "https://www.uwa.edu.au/study/scholarships-and-fees/scholarships/international-scholarships/global-excellence-scholarship",
    "JICA": "https://www.jica.go.jp/english/our_work/types_of_assistance/tech_acceptance/training/index.html",
    "ADB-Japan": "https://www.adb.org/scholarship/adb-japan-scholarship-program",
    "UTokyo": "https://www.u-tokyo.ac.jp/en/admission/scholarship.html",
    "Kyoto": "https://www.kyoto-u.ac.jp/en/education-campus/scholarship",
    "Tokyo Tech": "https://www.titech.ac.jp/english/enrolled/scholarships",
    "SNU": "https://en.snu.ac.kr/admission/scholarship",
    "KAIST": "https://admission.kaist.ac.kr/scholarship/",
    "POSTECH": "https://admission.postech.ac.kr/scholarship/",
    "A*STAR AGS": "https://www.a-star.edu.sg/Scholarships/For-Graduate-Studies/ASTAR-Graduate-Scholarship",
    "SINGA": "https://www.singa.a-star.edu.sg/",
    "NUS": "https://nus.edu.sg/scholarships/",
    "NTU": "https://www.ntu.edu.sg/admissions/graduate/financialmatters/scholarships",
    "Manaaki": "https://www.nzscholarships.govt.nz/",
    "Auckland/Otago": "https://international.auckland.ac.nz/study/scholarships",
    "HKSAR Fund": "https://www.edb.gov.hk/en/edu-system/postsecondary/local-higher-edu/publicly-funded-programmes/scholarship.html",
    "HKU": "https://admissions.hku.hk/fees-and-scholarships/scholarships",
    "CUHK": "https://admission.cuhk.edu.hk/fees-financing-your-studies/scholarships/",
    "HKUST": "https://join.hkust.edu.hk/admissions/scholarships",
}


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


def process_world_top_demand(filepath: Path) -> list[ScholarshipIngestionRecord]:
    """Process world top-demand research ledger format."""
    records = []
    seen_urls = set()
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
            
            scholarship_name = entry.get("scholarship", "")
            country = entry.get("country", "")
            
            if not scholarship_name or not country:
                print(f"Warning: Missing required fields in line {line_num}")
                continue
            
            # Get official URL
            official_url = SCHOLARSHIP_URLS.get(scholarship_name)
            if not official_url:
                print(f"Warning: No official URL for {scholarship_name} in line {line_num}")
                continue
            
            # Handle duplicate URLs by adding fragment identifier
            if official_url in seen_urls:
                official_url = f"{official_url}#{scholarship_name.lower().replace(' ', '-')}"
            seen_urls.add(SCHOLARSHIP_URLS.get(scholarship_name, official_url))
            
            degree = entry.get("level", "Bachelor's, Master's, PhD")
            funding_amount = entry.get("funding_amount", "")
            funding_type = map_funding_type(funding_amount)
            if not funding_type:
                funding_type = "Partial Funding"
            
            deadline = entry.get("application_deadline", "")
            deadline_date = parse_date(deadline) if "-" in deadline and len(deadline) >= 10 else None
            
            # Default to "upcoming" for most, "open" for well-known ongoing programmes
            status = "upcoming"
            if scholarship_name in ["DAAD-EPOS", "Erasmus Mundus", "Eiffel", "NL Scholarship", "Swiss Excellence", 
                                    "Fulbright Foreign Student", "Pearson", "McGill", "ANU", "Melbourne", "UNSW", "UWA",
                                    "UTokyo", "Kyoto", "Tokyo Tech", "SNU", "KAIST", "POSTECH", 
                                    "A*STAR AGS", "SINGA", "NUS", "NTU"]:
                status = "open"
            
            record = ScholarshipIngestionRecord(
                name=scholarship_name,
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
                description="",
                eligibility=[],
                coverage=[funding_amount] if funding_amount else [],
                requirements=[],
                english_requirement=None,
                program_type=None,
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
        wtd_file = Path("backend/verification/research_ledger_world_top_demand_fixed.jsonl")
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