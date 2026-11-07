with open('frontend/src/pages/HomePage.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 1644 (index 1643) - missing closing >
lines[1643] = lines[1643].replace('</aside', '</aside>')

with open('frontend/src/pages/HomePage.jsx', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("Fixed line 1644")