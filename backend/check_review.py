import json
r = json.load(open('image_discovery_results.json', 'r', encoding='utf-8'))
review = [x for x in r if x.get('decision') == 'human_review']
for x in review:
    print(f"ID:{x['scholarship_id']} | {x['scholarship_title'][:60]}")
    print(f"  Source: {x.get('official_source_url', '')[:80]}")
    print(f"  Best URL: {x.get('best_candidate_url', '')}")
    print(f"  Page: {x.get('best_candidate_page', '')}")
    print(f"  Relevance: {x.get('program_relevance', '')}")
    print(f"  Confidence: {x.get('confidence', '')}")
    print(f"  Reason: {x.get('human_review_reason', '')}")
    print(f"  Rejection: {x.get('rejection_reasons', [])}")
    print()
