"""Print the stored record for the given ids, so it can be compared with the live page."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = {int(k): v for k, v in json.loads((HERE / "live_raw.json").read_text(encoding="utf-8")).items()}

FIELDS = [
    "title",
    "official_source",
    "official_source_url",
    "catalogue_url",
    "application_link",
    "official_updates_url",
    "degree",
    "funding",
    "funding_amount",
    "funding_currency",
    "funding_period",
    "tuition_coverage",
    "living_cost_coverage",
    "travel_coverage",
    "fully_funded",
    "deadline_display",
    "deadline_date",
    "deadline_precision",
    "application_period",
    "duration",
    "status",
    "verification_status",
    "last_verified_at",
    "verified_by",
    "program_type",
    "region",
    "english_requirement",
    "image_url",
    "image_kind",
    "image_evaluation_status",
]

LISTS = ["benefits", "coverage", "documents", "requirements", "eligibility", "application_method"]

for raw_id in sys.argv[1:]:
    row = RAW.get(int(raw_id))
    print("=" * 100)
    if row is None:
        print("unknown id", raw_id)
        continue
    print("ID", row["id"])
    for f in FIELDS:
        if f in row:
            print(f"  {f:24} {json.dumps(row[f], ensure_ascii=False)[:400]}")
    for f in LISTS:
        v = row.get(f)
        if v is None:
            print(f"  {f:24} None")
        elif isinstance(v, str):
            print(f"  {f:24} (str) {v[:300]}")
        else:
            print(f"  {f:24} (list of {len(v)})")
            for item in v[:8]:
                print(f"      - {str(item)[:220]}")
    for f in ("official_details", "applicant_utility", "programme_verification"):
        print(f"  {f}:")
        print("      " + json.dumps(row.get(f), ensure_ascii=False)[:1400])
    print("  description:", (row.get("description") or "")[:400])
    print("  eligibility_summary:", (row.get("eligibility_summary") or "")[:500])
    print("  notes:", (row.get("notes") or "")[:400])
    print("  verification_notes:", (row.get("verification_notes") or "")[:800])