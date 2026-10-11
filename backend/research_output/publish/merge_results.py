"""Merge the per-agent intake-verification results into one audit table."""
import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
RESULTS = BASE / "backend/research_output/publish/results"
INVENTORY = BASE / "backend/research_output/publish/intake_audit_2026-10-11.json"

inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in inventory["closed_records"]}

merged = {}
missing = []
for path in sorted(RESULTS.glob("agent_*.json")):
    payload = json.loads(path.read_text(encoding="utf-8"))
    for record in payload.get("records", []):
        rid = record.get("id")
        if rid in merged:
            raise SystemExit(f"duplicate result for id {rid} in {path.name}")
        if rid not in by_id:
            raise SystemExit(f"result id {rid} is not a closed record in the inventory")
        merged[rid] = record

covered = set(merged)
expected = set(by_id)
missing = sorted(expected - covered, key=int)
extra = sorted(covered - expected, key=int)

counts = Counter(r["classification"] for r in merged.values())
print("records classified:", len(merged), "/", len(expected))
print("classification counts:", dict(counts))
print("missing:", missing)
print("extra:", extra)

rows = []
for rid in sorted(merged):
    inv = by_id[rid]
    res = merged[rid]
    rows.append(
        {
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
            "classification": res["classification"],
            "official_evidence_urls": res.get("official_evidence_urls") or [],
            "page_evidence": res.get("page_evidence"),
            "next_deadline_or_window": res.get("next_deadline_or_window"),
            "funding_on_page": res.get("funding_on_page"),
            "department_or_programme": res.get("department_or_programme"),
            "logo_or_image_url": res.get("logo_or_image_url"),
            "confidence": res.get("confidence"),
            "last_checked_date": res.get("last_checked_date"),
        }
    )

out = {
    "_audit": {
        "date": "2026-10-11",
        "source": "intake_audit_2026-10-11.json + results/agent_*.json",
        "records_in_inventory": len(expected),
        "records_classified": len(merged),
        "classification_counts": dict(counts),
        "missing": missing,
        "extra": extra,
        "mode": "read-only audit; no database, snapshot, corpus or code writes",
    },
    "records": rows,
}
target = BASE / "backend/research_output/publish/intake_classification_2026-10-11.json"
target.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("written:", target)
