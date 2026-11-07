with open('frontend/src/pages/HomePage.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Check around line 1648
for i, line in enumerate(lines[1640:1655], 1641):
    line_clean = line.rstrip().encode('ascii', 'replace').decode('ascii')
    print(f'{i}: {line_clean}')