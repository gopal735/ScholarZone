import re

with open('frontend/src/pages/HomePage.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Check for FLAGSHIP_PROGRAMMES reference
matches = list(re.finditer(r'FLAGSHIP_PROGRAMMES', content))
print(f'FLAGSHIP_PROGRAMMES occurrences: {len(matches)}')

# Check for hero-guide
if 'hero-guide' in content:
    print('hero-guide present')
else:
    print('hero-guide NOT present')

# Check for hero-learning
if 'hero-learning' in content:
    print('hero-learning present')
else:
    print('hero-learning NOT present')

# Check brace balance
open_braces = content.count('{')
close_braces = content.count('}')
print(f'Brace balance: {content.count("{") - content.count("}")}')

# Check if file ends properly
print(f'File length: {len(content)} chars')
print(f'Last 200 chars: {content[-200:]}')