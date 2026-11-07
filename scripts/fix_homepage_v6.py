with open('frontend/src/pages/HomePage.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 312 - split the two statements
# Line 312 (0-indexed 311) should be split
new_lines = []
for i, line in enumerate(lines):
    if i == 311:  # Line 312 (1-indexed)
        # Split the line
        new_lines.append("        verified: s.verification_status === 'active',\n")
        new_lines.append("        image_url: s.image_url,\n")
    else:
        new_lines.append(line)

with open('frontend/src/pages/HomePage.jsx', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("Fixed line 312")