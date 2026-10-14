import json
r = json.load(open('image_discovery_results.json', 'r', encoding='utf-8'))
review = [x for x in r if x.get('decision') == 'human_review']
for x in review:
    print(f"ID:{x['scholarship_id']} {x['scholarship_title'][:50]}")
    print(f"  URL: {x.get('best_candidate_url', '')}")
    print(f"  Reason: {x.get('human_review_reason', '')}")

approved = [x for x in r if x.get('decision') == 'approved']
print(f"\nApproved: {len(approved)}")
for x in approved:
    print(f"ID:{x['scholarship_id']} {x['scholarship_title'][:50]}")
    print(f"  URL: {x.get('best_candidate_url', '')}")
