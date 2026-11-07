with open('frontend/src/pages/HomePage.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 1646 (index 1645) - missing closing >
lines[1645] = lines[1645].replace('</aside', '</aside>')

with open('frontend/src/pages/HomePage.jsx', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("Fixed line 1646")