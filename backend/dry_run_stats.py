import json
from datetime import datetime
from collections import Counter

r = json.load(open('image_discovery_results.json', 'r', encoding='utf-8'))

total = len(r)
approved = sum(1 for x in r if x.get('decision') == 'approved')
review = sum(1 for x in r if x.get('decision') == 'human_review')
rejected = sum(1 for x in r if x.get('decision') == 'rejected')
no_candidates = sum(1 for x in r if x.get('candidates_found', 0) == 0)

print(f'Total processed: {total}')
print(f'APPROVED (HIGH): {approved}')
print(f'HUMAN_REVIEW (MEDIUM): {review}')
print(f'REJECTED (LOW): {rejected}')
print(f'No candidates found: {no_candidates}')
print()

# Source type breakdown
source_types = Counter(x.get('source_type') for x in r)
print('Source types:')
for st, count in source_types.most_common():
    print(f'  {st}: {count}')

print()
# Resolution types
res_types = Counter(x.get('source_resolution_type') for x in r)
print('Resolution types:')
for rt, count in res_types.most_common():
    print(f'  {rt}: {count}')

print()
# Countries
countries = Counter(x.get('country') for x in r)
print('Countries:')
for c, count in countries.most_common(10):
    print(f'  {c}: {count}')

print()
# Rejection reasons
rej_reasons = Counter()
for x in r:
    for reason in x.get('rejection_reasons', []):
        rej_reasons[reason] += 1
print('Top rejection reasons:')
for reason, count in rej_reasons.most_common(10):
    print(f'  {reason}: {count}')
