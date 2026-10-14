import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\research\wave4\wave4_final_mutation_manifest.json", 'r', encoding='utf-8') as f:
    data = json.load(f)

# Fix the three records
fixed = 0
for m in data:
    if m['scholarship_id'] == 412 and m['topic'] == 'deadline':
        print(f"Fixing record 412: {m['mutation_type']} -> STALE_VALUE_PRESERVED")
        m['mutation_type'] = 'STALE_VALUE_PRESERVED'
        m['proposed_deadline_date'] = None
        # Keep the precision as EXACT (the semantics of the original date)
        # Update notes to clarify expired_mismatch
        m['notes'] = m['notes'] + " RECLASSIFIED per merge gate: deadline 2026-05-08 is past evaluation date 2026-10-06; reclassified from DEADLINE_FILL to STALE_VALUE_PRESERVED per contract. Stale date preserved in proposed_deadline_display."
        fixed += 1
    elif m['scholarship_id'] == 414 and m['topic'] == 'deadline':
        print(f"Fixing record 414: {m['mutation_type']} -> STALE_VALUE_PRESERVED")
        m['mutation_type'] = 'STALE_VALUE_PRESERVED'
        m['proposed_deadline_date'] = None
        m['notes'] = m['notes'] + " RECLASSIFIED per merge gate: deadline 2026-07-09 is past evaluation date 2026-10-06; reclassified from DEADLINE_FILL to STALE_VALUE_PRESERVED per contract. Stale date preserved in proposed_deadline_display."
        fixed += 1
    elif m['scholarship_id'] == 600 and m['topic'] == 'deadline':
        print(f"Fixing record 600: {m['mutation_type']} -> STALE_VALUE_PRESERVED")
        m['mutation_type'] = 'STALE_VALUE_PRESERVED'
        m['proposed_deadline_date'] = None
        m['notes'] = m['notes'] + " RECLASSIFIED per merge gate: deadline 2026-10-05 is past evaluation date 2026-10-06; reclassified from DEADLINE_FILL to STALE_VALUE_PRESERVED per contract. Stale date preserved in proposed_deadline_display."
        fixed += 1

print(f"\nFixed {fixed} records")

# Save the fixed manifest
with open(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\research\wave4\wave4_final_mutation_manifest.json", 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Manifest saved")