import json
import os
from collections import defaultdict

with open(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\wave4_all_records.json", 'r', encoding='utf-8') as f:
    all_records = json.load(f)

# Check for same-topic duplicates
print("=== SAME-TOPIC DUPLICATES ===")
topic_shard_recs = defaultdict(lambda: defaultdict(list))
for rec in all_records:
    topic_shard_recs[rec['topic']][rec['scholarship_id']].append(rec['shard_id'])

for topic in ['deadline', 'logo']:
    print(f"\n--- {topic} ---")
    for rec_id, shards in topic_shard_recs[topic].items():
        if len(shards) > 1:
            print(f"  Record {rec_id}: {shards}")

# Check conflicting outcomes for same record across shards (same topic)
print("\n=== CONFLICTING OUTCOMES (same topic) ===")
for topic in ['deadline', 'logo']:
    print(f"\n--- {topic} ---")
    for rec_id, shards in topic_shard_recs[topic].items():
        if len(shards) > 1:
            outcomes = []
            for rec in all_records:
                if rec['scholarship_id'] == rec_id and rec['topic'] == topic:
                    outcomes.append((rec['shard_id'], rec['outcome'], rec.get('deadline_semantics'), rec.get('deadline_date')))
            # Check if outcomes differ
            unique_outcomes = set(o[1] for o in outcomes)
            if len(unique_outcomes) > 1:
                print(f"  Record {rec_id} has conflicting outcomes: {outcomes}")

# Analyze deadline records with deadline_date
print("\n=== DEADLINE RECORDS WITH deadline_date ===")
for rec in all_records:
    if rec['topic'] == 'deadline' and rec['deadline_date']:
        print(f"  {rec['scholarship_id']}: {rec['title'][:60]} -> {rec['deadline_date']} ({rec['deadline_semantics']}, {rec['confidence']})")

# Analyze logo records with image_url
print("\n=== LOGO RECORDS WITH image_url ===")
for rec in all_records:
    if rec['topic'] == 'logo' and rec['image_url']:
        print(f"  {rec['scholarship_id']}: {rec['title'][:60]} -> {rec['image_url'][:80]} ({rec['confidence']})")

# Source URL corrections (404s, wrong pages)
print("\n=== SOURCE URL CORRECTIONS NEEDED ===")
# We need to read the full records to see rejected_sources
WAVE4_OUT = r"C:\Users\GopaL\AppData\Local\Temp\kilo\sz-wave4\backend\research\wave4\out"
shard_files = sorted(os.listdir(WAVE4_OUT))

corrections = []
for fname in shard_files:
    fpath = os.path.join(WAVE4_OUT, fname)
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    for rec in data.get('records', []):
        rejected = rec.get('rejected_sources', [])
        for r in rejected:
            if '404' in r.get('reason', '') or 'wrong' in r.get('reason', '').lower() or 'not the live' in r.get('reason', '').lower() or 'superseded' in r.get('reason', '').lower():
                corrections.append({
                    'scholarship_id': rec['scholarship_id'],
                    'shard_id': data.get('shard_id'),
                    'old_url': r['url'],
                    'reason': r['reason'],
                    'new_url': rec.get('source', {}).get('url') if isinstance(rec.get('source'), dict) else None
                })

for c in corrections:
    print(f"  Record {c['scholarship_id']} ({c['shard_id']}): {c['old_url']} -> {c['new_url']}")
    print(f"    Reason: {c['reason']}")

print(f"\nTotal corrections: {len(corrections)}")

# Check for expired_mismatch details
print("\n=== EXPIRED_MISMATCH DETAILS ===")
for rec in all_records:
    if rec['outcome'] == 'expired_mismatch':
        print(f"  {rec['scholarship_id']}: {rec['title'][:60]}")
        print(f"    deadline_display: {rec['deadline_display'][:100]}")

# Check conflicting records
print("\n=== CONFLICTING RECORDS ===")
for rec in all_records:
    if rec['outcome'] == 'conflicting':
        print(f"  {rec['scholarship_id']}: {rec['title'][:60]}")
        print(f"    semantics: {rec['deadline_semantics']}")

# Count records per shard
print("\n=== RECORDS PER SHARD ===")
shard_counts = defaultdict(int)
for rec in all_records:
    shard_counts[rec['shard_id']] += 1
for shard, count in sorted(shard_counts.items()):
    print(f"  {shard}: {count}")

# Missing shards
all_expected_dl = [f"DL-{i:03d}" for i in range(1, 61)]
all_expected_lg = [f"LG-{i:03d}" for i in range(1, 41)]
actual_shards = set(shard_counts.keys())
print(f"\nMissing deadline shards: {set(all_expected_dl) - actual_shards}")
print(f"Missing logo shards: {set(all_expected_lg) - actual_shards}")