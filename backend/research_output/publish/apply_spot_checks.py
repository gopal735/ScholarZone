"""Fold the lead auditor's own live spot-checks into the merged classification.

Provisional records are only upgraded when the lead auditor fetched the
official page directly. Read-only against the sources; writes only the merged
classification artifact.
"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
TARGET = BASE / "backend/research_output/publish/intake_classification_2026-10-11.json"

spot = {
    49: {
        "classification": "temporarily_closed_awaiting_announcement",
        "official_evidence_urls": [
            "https://www.sydney.edu.au/scholarships/d/farrand-scholarship-in-agricultural-science--international-.html",
            "https://www.sydney.edu.au/science/schools/school-of-life-and-environmental-sciences.html",
        ],
        "page_evidence": "Official page (fetched 2026-10-11): highlights list 'Close date: 01 December 2025' and 'Open date: N/A'. Scholarship established 2023, 'A $20,000 scholarship ... studying Bachelor of Agricultural Science'; 'No application is required, as all eligible students who have secured an unconditional offer of admission will be automatically considered.' No subsequent round announced and no open date published.",
        "next_deadline_or_window": None,
        "funding_on_page": "AUD 20,000 per annum, up to 3 years (tuition offset; automatic consideration)",
        "confidence": 0.8,
        "last_checked_date": "2026-10-11",
    },
    203: {
        "classification": "recurring_next_intake_expected",
        "official_evidence_urls": [
            "https://www.flinders.edu.au/scholarships/flinders-university-international-research-scholarship",
            "https://www.flinders.edu.au/content/dam/documents/scholarships/fiprs-conditions-award-2027.pdf",
        ],
        "page_evidence": "Official page (fetched 2026-10-11) shows the 2026 round ('Opening date 30-04-2026', 'Closing date 18-06-2026', 'Applications close Thursday 18 June 2026') but its own application documents are all the 2027 cycle: '2027 hdr-scholarships-international-fact-sheet.pdf', 'fiprs-conditions-award-2027.pdf', 'international publication-cover-sheet-main 2027.pdf', 'agrtpsiFIPRS-referee-report-2027 PDF.pdf'. The page states 'A limited number of FIPRS are available each year' and the living allowance is 'indexed annually'. Round closed 18 June 2026; next cycle expected in 2027.",
        "next_deadline_or_window": None,
        "funding_on_page": "AUD 36,061 per year (2026 rate, tax free) plus international tuition fees, up to 3.5 years, establishment allowance up to AUD 1,485",
        "confidence": 0.85,
        "last_checked_date": "2026-10-11",
    },
    647: {
        "classification": "recurring_next_intake_expected",
        "official_evidence_urls": [
            "https://sgs.upm.edu.my/financial_assistance_scholarships/scholarship_financial_assistance_upm/international_graduate_student_scholarship_igss-1402",
        ],
        "page_evidence": "Official UPM School of Graduate Studies page (fetched 2026-10-11): 'the International Graduate Student Scholarship (IGSS) is now open for application for the First Semester 2026/2027 starting from 01 - 31 August 2026' - a standing, semester-based scheme whose announcement is the current one. Award value 'a 30-50% tuition fee waiver', duration up to 3 years subject to annual review. The 01-31 August 2026 window has passed; the scheme is published anew each intake (cf. the recurring GRF/GRA/GTA schemes listed on the same page).",
        "next_deadline_or_window": None,
        "funding_on_page": "30-50% tuition fee waiver, up to 3 years (6th semester)",
        "confidence": 0.7,
        "last_checked_date": "2026-10-11",
    },
}

data = json.loads(TARGET.read_text(encoding="utf-8"))
counts_before = data["_audit"]["classification_counts"].copy()
present = {r["id"] for r in data["records"]}
inventory = json.loads(
    (BASE / "backend/research_output/publish/intake_audit_2026-10-11.json").read_text(encoding="utf-8")
)["closed_records"]

added = []
for rid, result in spot.items():
    if rid in present:
        for record in data["records"]:
            if record["id"] == rid:
                record.update(result)
        continue
    # The chunk agent for this record had not returned, so it exists only in
    # the inventory; add it with its local evidence carried over.
    inv = next(r for r in inventory if r["id"] == rid)
    merged = {
        "id": rid,
        "title": inv["title"],
        "country": inv["country"],
        "degree": inv["degree"],
        "funding": inv["funding"],
        "funding_amount": inv["funding_amount"],
        "funding_currency": inv["funding_currency"],
        "funding_period": inv["funding_period"],
        "recorded_deadline": inv["deadline_date"],
        "days_since_deadline": inv["days_since_deadline"],
        "public_status": inv["public_status"],
        "db_status": inv["db_status"],
        "db_archived": inv["db_archived"],
        "db_verification_status": inv["db_verification_status"],
        "official_source_url": inv["official_source_url"],
    }
    merged.update(result)
    data["records"].append(merged)
    added.append(rid)

missing = [rid for rid in data["_audit"]["missing"] if rid not in spot]
data["_audit"]["missing"] = missing

from collections import Counter

counts = dict(Counter(r["classification"] for r in data["records"]))
data["_audit"]["classification_counts"] = counts
data["_audit"]["lead_spot_checks"] = sorted(spot)
data["_audit"]["records_classified"] = len(data["records"])
data["_audit"]["counts_before_lead_spot_checks"] = counts_before
data["records"].sort(key=lambda r: r["id"])
TARGET.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("updated:", sorted(spot), "| added:", added)
print("counts before:", counts_before)
print("counts after:", counts)
print("still missing:", missing)
