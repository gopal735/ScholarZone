import json
import os
import sys
from collections import defaultdict

# Set stdout encoding
sys.stdout.reconfigure(encoding='utf-8')

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
            unique_outcomes = set(o[1] for o in outcomes)
            if len(unique_outcomes) > 1:
                print(f"  Record {rec_id} has conflicting outcomes: {outcomes}")

# Analyze deadline records with deadline_date
print("\n=== DEADLINE RECORDS WITH deadline_date ===")
for rec in all_records:
    if rec['topic'] == 'deadline' and rec['deadline_date']:
        title = rec['title'][:60].encode('ascii', 'replace').decode('ascii')
        print(f"  {rec['scholarship_id']}: {title} -> {rec['deadline_date']} ({rec['deadline_semantics']})")

# Source URL corrections (404s, wrong pages)
print("\n=== SOURCE URL CORRECTIONS NEEDED ===")
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
            reason = r.get('reason', '').lower()
            if '404' in reason or 'wrong' in reason or 'not the live' in reason or 'superseded' in reason or 'stale' in reason or 'error page' in reason:
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
        title = rec['title'][:60].encode('ascii', 'replace').decode('ascii')
        print(f"  {rec['scholarship_id']}: {title}")
        dd = rec['deadline_display'][:100] if rec['deadline_display'] else 'N/A'
        print(f"    deadline_display: {dd.encode('ascii', 'replace').decode('ascii')}")

# Check conflicting records
print("\n=== CONFLICTING RECORDS ===")
for rec in all_records:
    if rec['outcome'] == 'conflicting':
        title = rec['title'][:60].encode('ascii', 'replace').decode('ascii')
        print(f"  {rec['scholarship_id']}: {title}")
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
print(f"\nMissing deadline shards: {sorted(set(all_expected_dl) - actual_shards)}")
print(f"Missing logo shards: {sorted(set(all_expected_lg) - actual_shards)}")

# Outcome counts by topic
print("\n=== OUTCOME BY TOPIC ===")
for topic in ['deadline', 'logo']:
    topic_recs = [r for r in all_records if r['topic'] == topic]
    outcome_counts = defaultdict(int)
    for r in topic_recs:
        outcome_counts[r['outcome']] += 1
    print(f"  {topic}: {dict(outcome_counts)}")

# Deadline semantics counts
print("\n=== DEADLINE SEMANTICS DISTRIBUTION ===")
deadline_recs = [r for r in all_records if r['topic'] == 'deadline']
sem_counts = defaultdict(int)
for r in deadline_recs:
    sem_counts[r.get('deadline_semantics', 'NONE')] += 1
for sem, count in sorted(sem_counts.items(), key=lambda x: -x[1]):
    print(f"  {sem}: {count}")

# Logo confidence distribution
print("\n=== LOGO CONFIDENCE DISTRIBUTION ===")
logo_recs = [r for r in all_records if r['topic'] == 'logo']
conf_counts = defaultdict(int)
for r in logo_recs:
    conf_counts[r.get('confidence', 'NONE')] += 1
for conf, count in sorted(conf_counts.items(), key=lambda x: -x[1]):
    print(f"  {conf}: {count}")

# Duplicate image_url across scholarships from same provider
print("\n=== DUPLICATE image_url ANALYSIS ===")
url_to_records = defaultdict(list)
for r in logo_recs:
    if r.get('image_url'):
        url_to_records[r['image_url']].append(r['scholarship_id'])

for url, recs in url_to_records.items():
    if len(recs) > 1:
        # Check if same provider
        providers = set()
        for rec in logo_recs:
            if rec['scholarship_id'] in recs:
                src = rec.get('source', {})
                if isinstance(src, dict):
                    providers.add(src.get('publisher', 'UNKNOWN'))
        print(f"  URL shared by {len(recs)} records: {recs}")
        print(f"    Providers: {providers}")
        print(f"    URL: {url[:80]}")