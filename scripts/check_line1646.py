with open('frontend/src/pages/HomePage.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines[1640:1660], 1641):
    line_clean = line.rstrip().encode('ascii', 'replace').decode('ascii')
    print(f'{i}: {line_clean}')