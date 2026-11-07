with open('frontend/src/pages/HomePage.jsx', 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

for i, line in enumerate(lines[:30]):
    print(f'{i+1}: {line.rstrip()}')