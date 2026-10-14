import json
with open(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\dry_run_after_report.json', 'r') as f:
    data = json.load(f)
approved = [s for s in data if s.get('decision') == 'approved']
print(f'Approved in after_report: {len(approved)}')
for s in approved:
    sid = s["scholarship_id"]
    title = s["scholarship_title"]
    best = s.get("best_candidate_url")
    print(f'ID {sid}: {title} - {best}')
