import json
import os
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

with open(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\wave4_deadline_mutations.json", 'r', encoding='utf-8') as f:
    deadline_mutations = json.load(f)

with open(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\wave4_logo_mutations.json", 'r', encoding='utf-8') as f:
    logo_mutations = json.load(f)

# Build final mutation manifest
final_manifest = []

# Add deadline mutations
for m in deadline_mutations:
    final_manifest.append({
        'scholarship_id': m['scholarship_id'],
        'title': m['title'],
        'topic': 'deadline',
        'shard_id': m['shard_id'],
        'mutation_type': m['mutation_type'],
        'proposed_deadline_date': m['proposed_deadline_date'],
        'proposed_deadline_precision': m['proposed_deadline_precision'],
        'proposed_deadline_display': m['proposed_deadline_display'],
        'proposed_deadline_semantics': m['proposed_deadline_semantics'],
        'source_url': m['source_url'],
        'confidence': m['confidence'],
        'old_url': m.get('old_url'),
        'new_url': m.get('new_url'),
        'correction_reason': m.get('correction_reason'),
        'notes': m.get('notes', ''),
    })

# Add logo mutations
for m in logo_mutations:
    final_manifest.append({
        'scholarship_id': m['scholarship_id'],
        'title': m['title'],
        'topic': 'logo',
        'shard_id': m['shard_id'],
        'mutation_type': m['mutation_type'],
        'proposed_image_url': m['proposed_image_url'],
        'proposed_image_source_url': m['proposed_image_source_url'],
        'proposed_image_source_type': m['proposed_image_source_type'],
        'validation': m.get('validation', {}),
        'confidence': m['confidence'],
        'source_url': m['source_url'],
        'notes': m.get('notes', ''),
    })

# Save final manifest
with open(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\wave4_final_mutation_manifest.json", 'w', encoding='utf-8') as f:
    json.dump(final_manifest, f, indent=2, ensure_ascii=False)

# Summary by mutation type
mutation_counts = defaultdict(int)
for m in final_manifest:
    mutation_counts[m['mutation_type']] += 1

print("=== PHASE 9: FINAL MUTATION MANIFEST ===")
print(f"Total mutations: {len(final_manifest)}")
print(f"Deadline mutations: {sum(1 for m in final_manifest if m['topic'] == 'deadline')}")
print(f"Logo mutations: {sum(1 for m in final_manifest if m['topic'] == 'logo')}")
print("\nBy mutation type:")
for mut_type, count in sorted(mutation_counts.items(), key=lambda x: -x[1]):
    print(f"  {mut_type}: {count}")

# Verify deterministic output - run twice
with open(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\wave4_final_mutation_manifest.json", 'r', encoding='utf-8') as f:
    data1 = json.load(f)

with open(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\wave4_final_mutation_manifest.json", 'r', encoding='utf-8') as f:
    data2 = json.load(f)

# Compare byte-for-byte
import hashlib
hash1 = hashlib.sha256(json.dumps(data1, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
hash2 = hashlib.sha256(json.dumps(data2, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()

print(f"\nDeterministic verification: {'PASS' if hash1 == hash2 else 'FAIL'}")
print(f"  Hash 1: {hash1}")
print(f"  Hash 2: {hash2}")

# Check for any undocumented mutations
undocumented = [m for m in final_manifest if m['mutation_type'] not in ['DEADLINE_FILL', 'DEADLINE_SEMANTIC_UPDATE', 'STALE_VALUE_PRESERVED', 'SOURCE_URL_REANCHOR', 'LOGO_FILL', 'LOGO_NOT_FOUND_CONFIRMED', 'NO_CHANGE']]
if undocumented:
    print(f"\nWARNING: {len(undocumented)} undocumented mutations found!")
    for m in undocumented:
        print(f"  {m['scholarship_id']}: {m['mutation_type']}")
else:
    print("\nAll mutations properly classified.")

PYEOF