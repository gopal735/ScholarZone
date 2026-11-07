with open('frontend/src/pages/HomePage.jsx.master3', 'r', encoding='utf-8') as f:
    content = f.read()

print('HERO_HEADLINE_WORDS defined:', 'const HERO_HEADLINE_WORDS' in content)
print('FLAGSHIP_PROGRAMMES present:', 'FLAGSHIP_PROGRAMMES' in content)
print('hero-learning:', 'hero-learning' in content)
print('hero-guide:', 'hero-guide' in content)
print('hero-guide (className):', 'hero-guide' in content)

idx = content.find('const EUROPE_COUNTRIES')
print(f'EUROPE_COUNTRIES at: {idx}')

idx2 = content.find('const HERO_HEADLINE_WORDS')
print(f'HERO_HEADLINE_WORDS defined: {idx2 != -1}')