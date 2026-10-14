import json
import os
from collections import defaultdict

WAVE4_OUT = r"C:\Users\GopaL\AppData\Local\Temp\kilo\sz-wave4\backend\research\wave4\out"

# Read all output files
shard_files = sorted(os.listdir(WAVE4_OUT))
print(f"Total output files: {len(shard_files)}")

manifest = []
all_records = []
record_to_shards = defaultdict(list)

for fname in shard_files:
    fpath = os.path.join(WAVE4_OUT, fname)
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    shard_id = data.get('shard_id', fname.replace('.json', ''))
    topic = data.get('topic', 'unknown')
    records = data.get('records', [])
    
    # Count outcomes
    outcome_counts = defaultdict(int)
    for rec in records:
        outcome = rec.get('outcome', 'unknown')
        outcome_counts[outcome] += 1
        rec_id = rec.get('scholarship_id')
        record_to_shards[rec_id].append(shard_id)
        all_records.append({
            'shard_id': shard_id,
            'topic': topic,
            'scholarship_id': rec_id,
            'title': rec.get('title'),
            'outcome': outcome,
            'deadline_semantics': rec.get('deadline_semantics'),
            'deadline_date': rec.get('deadline_date'),
            'deadline_precision': rec.get('deadline_precision'),
            'deadline_display': rec.get('deadline_display'),
            'image_url': rec.get('image_url'),
            'confidence': rec.get('confidence'),
            'source_url': rec.get('source', {}).get('url') if isinstance(rec.get('source'), dict) else None,
        })
    
    manifest.append({
        'shard_id': shard_id,
        'topic': topic,
        'records': len(records),
        'outcome_counts': dict(outcome_counts),
        'output_path': fpath
    })

# Print manifest summary
print(f"\nTotal records across all shards: {len(all_records)}")
print(f"Deadline shards: {sum(1 for m in manifest if m['topic'] == 'deadline')}")
print(f"Logo shards: {sum(1 for m in manifest if m['topic'] == 'logo')}")
print(f"Deadline records: {sum(m['records'] for m in manifest if m['topic'] == 'deadline')}")
print(f"Logo records: {sum(m['records'] for m in manifest if m['topic'] == 'logo')}")

# Duplicate record IDs across shards
print("\n=== DUPLICATE RECORD IDs ACROSS SHARDS ===")
duplicates = {rid: shards for rid, shards in record_to_shards.items() if len(shards) > 1}
for rid, shards in sorted(duplicates.items()):
    print(f"  Record {rid}: {shards}")

# Outcome summary
outcome_summary = defaultdict(int)
for rec in all_records:
    outcome_summary[rec['outcome']] += 1
print("\n=== OUTCOME SUMMARY ===")
for outcome, count in sorted(outcome_summary.items(), key=lambda x: -x[1]):
    print(f"  {outcome}: {count}")

# Deadline semantics summary
deadline_recs = [r for r in all_records if r['topic'] == 'deadline']
semantics_summary = defaultdict(int)
for rec in deadline_recs:
    semantics_summary[rec['deadline_semantics']] += 1
print("\n=== DEADLINE SEMANTICS SUMMARY ===")
for sem, count in sorted(semantics_summary.items(), key=lambda x: -x[1]):
    print(f"  {sem}: {count}")

# Deadline_date fills
filled = sum(1 for r in deadline_recs if r['deadline_date'])
print(f"\nDeadline records with deadline_date filled: {filled} / {len(deadline_recs)}")

# Logo records with image_url
logo_recs = [r for r in all_records if r['topic'] == 'logo']
logo_filled = sum(1 for r in logo_recs if r['image_url'])
print(f"Logo records with image_url: {logo_filled} / {len(logo_recs)}")

# Save manifest
with open(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\wave4_manifest.json", 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

with open(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\wave4_all_records.json", 'w', encoding='utf-8') as f:
    json.dump(all_records, f, indent=2, ensure_ascii=False)

print("\nManifest saved to wave4_manifest.json and wave4_all_records.json")