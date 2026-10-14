import json
r = json.load(open('image_discovery_results.json', 'r', encoding='utf-8'))
print(f'Total processed: {len(r)}')
approved = [x for x in r if x.get('decision') == 'approved']
review = [x for x in r if x.get('decision') == 'human_review']
rejected = [x for x in r if x.get('decision') == 'rejected']
print(f'Approved: {len(approved)}')
print(f'Human Review: {len(review)}')
print(f'Rejected: {len(rejected)}')
print()
print('HUMAN_REVIEW candidates:')
for x in review:
    print(f"  ID {x['scholarship_id']}: {x['scholarship_title'][:50]} | {x.get('best_candidate_url', '')[:60]}")
