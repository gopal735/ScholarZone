"""Find duplicate URLs in the scholarships file."""
import re
from collections import Counter

with open('app/data/additional_scholarships.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all URLs
urls = re.findall(r'official_source_url="(https://[^"]+)"', content)
duplicates = {url: count for url, count in Counter(urls).items() if count > 1}

print('Duplicate URLs found:')
for url, count in sorted(duplicates.items()):
    print(f'  ({count}x) {url}')
