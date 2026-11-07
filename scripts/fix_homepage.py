import re

# Read the current file
with open('frontend/src/pages/HomePage.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove FLAGSHIP_PROGRAMMES block (from "const FLAGSHIP_PROGRAMMES = [" to "]" before "const FUNDING_MATRIX")
pattern = r'const FLAGSHIP_PROGRAMMES = \[.*?\]\n\nconst FUNDING_MATRIX = \['
replacement = '// FLAGSHIP_PROGRAMMES removed - using dynamic data from snapshot instead\n\nconst FUNDING_MATRIX = ['
content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# Also remove HERO_HEADLINE_WORDS
content = re.sub(r'const HERO_HEADLINE_WORDS = .*?\n', '', content)

# Write back
with open('frontend/src/pages/HomePage.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")