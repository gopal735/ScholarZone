import json

# Read base snapshot with UTF-16 encoding
with open(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\base_snapshot.json', 'r', encoding='utf-16') as f:
    snapshot = json.load(f)

print(f"Base commit snapshot meta source_record_count: {snapshot['meta']['source_record_count']}")
print(f"Base commit snapshot meta public_record_count: {snapshot['meta']['public_record_count']}")
print(f"Base commit snapshot stats total: {snapshot['stats']['total']}")
print(f"Base commit actual scholarships: {len(snapshot['scholarships'])}")
base_ids = set(s['id'] for s in snapshot['scholarships'])
print(f"Base commit ID range: {min(base_ids)} - {max(base_ids)}")
print(f"Base commit IDs count: {len(base_ids)}")

# Read current snapshot
with open(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\frontend\public\scholarships-snapshot.json', 'r', encoding='utf-8') as f:
    snapshot2 = json.load(f)

print(f"\nHEAD snapshot meta source_record_count: {snapshot2['meta']['source_record_count']}")
print(f"HEAD snapshot stats total: {snapshot2['stats']['total']}")
print(f"HEAD actual scholarships: {len(snapshot2['scholarships'])}")
head_ids = set(s['id'] for s in snapshot2['scholarships'])
print(f"HEAD ID range: {min(head_ids)} - {max(head_ids)}")
print(f"HEAD IDs count: {len(head_ids)}")

# Compare
added = head_ids - base_ids
removed = base_ids - head_ids
print(f"\nAdded IDs: {len(added)} -> {sorted(added)}")
print(f"Removed IDs: {len(removed)} -> {sorted(removed)}")

# Check stats differences
print(f"\nBase stats: {snapshot['stats']}")
print(f"HEAD stats: {snapshot2['stats']}")