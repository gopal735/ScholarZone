import json
with open('reports/bulk_image_dry_run_20260905_101221.json', encoding='utf-8') as f:
    data = json.load(f)

source_types = {}
for r in data:
    st = r.get('source_type')
    if st:
        source_types[st] = source_types.get(st, 0) + 1

print('Source types:', source_types)

human_review = [r for r in data if r['decision'] == 'human_review']
print('\nHUMAN_REVIEW scholarships:')
for r in human_review:
    print('  ID', r['scholarship_id'], ':', r['scholarship_title'][:50])
    print('    Source:', r['official_source_url'])
    print('    Image:', r['best_candidate_url'])
    print('    Reason:', r['human_review_reason'])

uni_scholarships = [r for r in data if r.get('source_type') == 'official_university']
print('\nOfficial university scholarships:', len(uni_scholarships))
for r in uni_scholarships:
    print('  ID', r['scholarship_id'], ':', r['scholarship_title'][:50], '|', r['official_source_url'])

# Find scholarships with accessible official sources but 0 candidates
accessible_zero = [r for r in data if r['candidates_found'] == 0 and 'inaccessible' not in r['source_resolution_type'].lower()]
print('\nAccessible source, 0 candidates:', len(accessible_zero))
for r in accessible_zero[:10]:
    print('  ID', r['scholarship_id'], ':', r['scholarship_title'][:50], '|', r['official_source_url'])
