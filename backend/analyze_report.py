"""Extract matched_pairs and other key info from merge_report.json."""
import json

REPORT_PATH = r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\research\premium_card\merge_report.json"

with open(REPORT_PATH, encoding="utf-8") as f:
    report = json.load(f)

print(f"Report keys: {list(report.keys())}")
print(f"research_records: {report.get('research_records')}")
print(f"matched: {report.get('matched')}")
print(f"unmatched: {report.get('unmatched')}")
print(f"duplicate_ids: {report.get('duplicate_ids')}")
print(f"total proposed_fields: {len(report.get('proposed_fields', []))}")
print(f"total conflicts: {len(report.get('conflicts', []))}")
print(f"total rejected_fields: {len(report.get('rejected_fields', []))}")

print("\n=== MATCHED PAIRS ===")
for pair in report.get("matched_pairs", []):
    print(f"  Research ID: {pair['research_id']}")
    print(f"  Research Title: {pair['research_title']}")
    print(f"  Scholarship ID: {pair['scholarship_id']}")
    print(f"  Scholarship Title: {pair['scholarship_title']}")
    print(f"  Match Type: {pair['match_type']}")
    print(f"  Confidence: {pair['confidence']}")
    print(f"  Proposed Fields: {len(pair.get('proposed_fields', []))}")
    print(f"  Conflicts: {len(pair.get('conflicts', []))}")
    print(f"  Rejected Fields: {len(pair.get('rejected_fields', []))}")
    print()

# Also look at rejected fields to understand the evidence issue
print("\n=== REJECTED FIELD SUMMARY (first 30) ===")
rejected = report.get("rejected_fields", [])
for r in rejected[:30]:
    print(f"  field={r.get('field')}, reason={r.get('reason')}, required={r.get('required')}, actual={r.get('actual')}")

# Count rejection reasons
from collections import Counter
reasons = Counter(r.get('reason') for r in rejected)
print(f"\n=== Rejection reason counts ===")
for reason, count in reasons.most_common():
    print(f"  {reason}: {count}")

# Count conflicts
conflicts = report.get("conflicts", [])
print(f"\n=== Conflict summary (first 20) ===")
for c in conflicts[:20]:
    print(f"  field={c.get('field')}, old={str(c.get('old_value'))[:50]}, new={str(c.get('new_value'))[:50]}")
