import subprocess
import json

# Get base commit snapshot
result = subprocess.run(['git', 'show', '606e233:frontend/public/scholarships-snapshot.json'], 
                       capture_output=True, text=True, cwd=r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone')
if result.returncode == 0:
    snapshot = json.loads(result.stdout)
    print(f"Base commit snapshot meta source_record_count: {snapshot['meta']['source_record_count']}")
    print(f"Base commit snapshot meta public_record_count: {snapshot['meta']['public_record_count']}")
    print(f"Base commit snapshot stats total: {snapshot['stats']['total']}")
    print(f"Base commit actual scholarships: {len(snapshot['scholarships'])}")
    base_ids = set(s['id'] for s in snapshot['scholarships'])
    print(f"Base commit ID range: {min(base_ids)} - {max(base_ids)}")
    print(f"Base commit IDs count: {len(base_ids)}")
else:
    print(f"Error: {result.stderr}")

# Also check current commit snapshot for comparison
result2 = subprocess.run(['git', 'show', 'HEAD:frontend/public/scholarships-snapshot.json'], 
                        capture_output=True, text=True, cwd=r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone')
if result2.returncode == 0:
    snapshot2 = json.loads(result2.stdout)
    print(f"\nHEAD snapshot meta source_record_count: {snapshot2['meta']['source_record_count']}")
    print(f"HEAD snapshot stats total: {snapshot2['stats']['total']}")
    print(f"HEAD actual scholarships: {len(snapshot2['scholarships'])}")
    head_ids = set(s['id'] for s in snapshot2['scholarships'])
    print(f"HEAD ID range: {min(head_ids)} - {max(head_ids)}")
    print(f"HEAD IDs count: {len(head_ids)}")
else:
    print(f"HEAD Error: {result2.stderr}")

# Compare
if 'base_ids' in locals() and 'head_ids' in locals():
    added = head_ids - base_ids
    removed = base_ids - head_ids
    print(f"\nAdded IDs: {len(added)} -> {sorted(added)}")
    print(f"Removed IDs: {len(removed)} -> {sorted(removed)}")