import json
with open(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\dry_run_latest.json', 'r') as f:
    data = json.load(f)
print(f'Total scholarships: {len(data)}')
approved = [s for s in data if s.get('decision') == 'approved']
print(f'Approved: {len(approved)}')
human_review = [s for s in data if s.get('decision') == 'human_review']
print(f'Human review: {len(human_review)}')
rejected = [s for s in data if s.get('decision') == 'rejected']
print(f'Rejected: {len(rejected)}')
print()
for s in approved:
    sid = s["scholarship_id"]
    title = s["scholarship_title"]
    best = s.get("best_candidate_url")
    conf = s.get("confidence")
    reasons = s.get("rejection_reasons")
    print(f'ID {sid}: {title}')
    print(f'  Best candidate: {best}')
    print(f'  Confidence: {conf}')
    print(f'  Rejection reasons: {reasons}')
    print()
