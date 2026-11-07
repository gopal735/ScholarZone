with open('frontend/src/pages/HomePage.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Add Fragment to React import
content = content.replace(
    "import { useEffect, useMemo, useRef, useState } from 'react'",
    "import { Fragment, useEffect, useMemo, useRef, useState } from 'react'"
)

with open('frontend/src/pages/HomePage.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Added Fragment import")