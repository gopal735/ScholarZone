import json

# Load merge report
with open(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\research\premium_card\merge_report.json') as f:
    report = json.load(f)

print(f"Research records: {report['research_records']}")
print(f"Matched: {report['matched']}")
print(f"Unmatched: {report['unmatched']}")
print(f"Duplicate IDs: {report['duplicate_ids']}")
print(f"Proposed fields: {len(report.get('proposed_fields', []))}")
print(f"Conflicts: {len(report.get('conflicts', []))}")
print(f"Rejected fields: {len(report.get('rejected_fields', []))}")

# Analyze conflicts by scholarship ID
print("\n=== CONFLICTS BY SCHOLARSHIP ID ===")
conflicts_by_id = {}
for c in report.get('conflicts', []):
    # Find which scholarship this belongs to
    for pair in report.get('matched_pairs', []):
        for pc in pair.get('conflicts', []):
            if pc.get('field') == c.get('field') and pc.get('old_value') == c.get('old_value') and pc.get('new_value') == c.get('new_value'):
                sch_id = pair.get('scholarship_id')
                if sch_id not in conflicts_by_id:
                    conflicts_by_id[sch_id] = []
                conflicts_by_id[sch_id].append(c)
                break

for sch_id, conflicts in conflicts_by_id.items():
    print(f"\nScholarship ID {sch_id}: {len(conflicts)} conflicts")
    for c in conflicts:
        print(f"  Field: {c['field']}")
        print(f"    Old: {c['old_value']}")
        print(f"    New: {c['new_value']}")
        print(f"    Source: {c.get('source_url')}")

# Analyze rejected fields
print("\n=== REJECTED FIELDS ===")
rejected_by_reason = {}
for r in report.get('rejected_fields', []):
    reason = r.get('reason', 'unknown')
    if reason not in rejected_by_reason:
        rejected_by_reason[reason] = []
    rejected_by_reason[reason].append(r)

for reason, items in rejected_by_reason.items():
    print(f"\nReason: {reason} ({len(items)} items)")
    for r in items[:5]:  # Show first 5
        print(f"  Field: {r.get('field')}, Old: {r.get('old_value')}, New: {r.get('new_value')}, Required: {r.get('required')}, Actual: {r.get('actual')}")
    if len(items) > 5:
        print(f"  ... and {len(items) - 5} more")

# Analyze proposed fields by scholarship ID
print("\n=== PROPOSED FIELDS BY SCHOLARSHIP ID ===")
proposed_by_id = {}
for p in report.get('proposed_fields', []):
    for pair in report.get('matched_pairs', []):
        for pp in pair.get('proposed_fields', []):
            if pp.get('field') == p.get('field') and pp.get('old_value') == p.get('old_value') and pp.get('new_value') == p.get('new_value'):
                sch_id = pair.get('scholarship_id')
                if sch_id not in proposed_by_id:
                    proposed_by_id[sch_id] = []
                proposed_by_id[sch_id].append(p)
                break

for sch_id, fields in proposed_by_id.items():
    print(f"\nScholarship ID {sch_id}: {len(fields)} proposed fields")
    for f in fields:
        print(f"  {f['field']}: {f['old_value']} -> {f['new_value']}")

# Check unmatched records
print("\n=== UNMATCHED RECORDS ===")
unmatched_count = 0
for pair in report.get('matched_pairs', []):
    if pair.get('match_type') == 'unmatched':
        unmatched_count += 1

# Actually, the report doesn't have unmatched in matched_pairs. Let me check research_index
# The unmatched count comes from the reconciliation process