import json
with open('dry_run_after_report.json') as f:
    r = json.load(f)
print('Approved count:', len(r['approved_details']))
print('Human review count:', len(r['human_review_details']))
for a in r['approved_details']:
    print(f"  #{a['scholarship_id']}: {a['scholarship_title'][:50]}")
for h in r['human_review_details']:
    print(f"  HR #{h['scholarship_id']}: {h['scholarship_title'][:50]}")
