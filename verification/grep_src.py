"""Search the cached plain-text renderings for a phrase, with context.

Evidence extraction only: it prints what the official page says so the decision
is made against the page text rather than against memory.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = json.loads((HERE / "fetch_cache.json").read_text(encoding="utf-8"))
TEXTDIR = HERE / "fetch_text"

if len(sys.argv) < 2:
    raise SystemExit("usage: grep.py <regex> [needle-in-url] [context] [max-hits]")

pattern = re.compile(sys.argv[1], re.I)
url_needle = sys.argv[2] if len(sys.argv) > 2 else ""
ctx = int(sys.argv[3]) if len(sys.argv) > 3 else 160
maxhits = int(sys.argv[4]) if len(sys.argv) > 4 else 6

for url, entry in CACHE.items():
    if url_needle and url_needle not in url:
        continue
    f = entry.get("text_file")
    if not f or not (TEXTDIR / f).exists():
        continue
    text = (TEXTDIR / f).read_text(encoding="utf-8")
    lines = text.split("\n")
    hits = 0
    for i, line in enumerate(lines):
        if pattern.search(line):
            hits += 1
            if hits > maxhits:
                print(f"  ... more matches in {url}")
                break
            lo, hi = max(0, i - 1), min(len(lines), i + 2)
            print(f"--- {url}")
            for j in range(lo, hi):
                mark = ">" if j == i else " "
                print(f" {mark} {lines[j][:ctx * 3]}")