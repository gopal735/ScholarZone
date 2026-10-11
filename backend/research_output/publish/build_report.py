"""Build the Phase-2 audit report (sections A-F) from the merged classification.

Read-only against every source. Emits the reviewable report the reviewer
approves or rejects before any change is proposed.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
CLASSIFICATION = BASE / "backend/research_output/publish/intake_classification_2026-10-11.json"
INVENTORY = BASE / "backend/research_output/publish/intake_audit_2026-10-11.json"

data = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
records = data["records"]
pending = data["_audit"]["missing"]

BUCKET_ORDER = [
    "upcoming_or_current_intake",
    "recurring_next_intake_expected",
    "temporarily_closed_awaiting_announcement",
    "genuinely_discontinued",
    "uncertain",
]
BUCKET_LABEL = {
    "upcoming_or_current_intake": "Upcoming/current intake",
    "recurring_next_intake_expected": "Recurring, next intake expected",
    "temporarily_closed_awaiting_announcement": "Temporarily closed, awaiting announcement",
    "genuinely_discontinued": "Genuinely discontinued",
    "uncertain": "Uncertain (no readable official status)",
}

by_bucket = defaultdict(list)
for record in records:
    by_bucket[record["classification"]].append(record)

counts = {bucket: len(by_bucket.get(bucket, [])) for bucket in BUCKET_ORDER}
counts["pending_verification"] = len(pending)

print("=" * 100)
print("SECTION A — counts by classification")
print("=" * 100)
for bucket in BUCKET_ORDER:
    print(f"{BUCKET_LABEL[bucket]:52s} {counts[bucket]:4d}")
print(f"{'Pending verification (agent still running)':52s} {counts['pending_verification']:4d}")
print(f"{'TOTAL closed/expired records under audit':52s} {len(records) + len(pending):4d}")

for bucket in BUCKET_ORDER:
    print()
    print("=" * 100)
    print(f"SECTION A detail — {BUCKET_LABEL[bucket]}")
    print("=" * 100)
    for record in by_bucket.get(bucket, []):
        print(
            f"id={record['id']:>4} | deadline {str(record['recorded_deadline']):>10} "
            f"({record['days_since_deadline']:>4}d) | conf={record['confidence']} | "
            f"{record['title'][:58]}"
        )
        if bucket in ("genuinely_discontinued", "uncertain"):
            for url in record["official_evidence_urls"][:2]:
                print(f"        evidence: {url[:100]}")
            quote = (record["page_evidence"] or "")[:200]
            print(f"        quote: {quote}")
        elif bucket in ("recurring_next_intake_expected", "temporarily_closed_awaiting_announcement"):
            window = record.get("next_deadline_or_window")
            print(f"        next window: {window}")

if pending:
    print()
    print("=" * 100)
    print("SECTION A detail — still pending verification")
    print("=" * 100)
    for rid in pending:
        inv = next(r for r in inventory["closed_records"] if r["id"] == rid)
        print(f"id={rid:>4} | deadline {str(inv['deadline_date']):>10} | {inv['title'][:60]} | {inv['official_source_url']}")

print()
print("written report data: intake_classification_2026-10-11.json (+ sections above)")
