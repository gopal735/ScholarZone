"""Print the cached plain-text rendering of an already-fetched official page."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = json.loads((HERE / "fetch_cache.json").read_text(encoding="utf-8"))
TEXTDIR = HERE / "fetch_text"

needle = sys.argv[1]
width = int(sys.argv[2]) if len(sys.argv) > 2 else 4000

hits = [u for u in CACHE if needle in u]
for u in hits:
    e = CACHE[u]
    print("=" * 100)
    print("URL    :", u)
    print("STATUS :", e.get("status_code"), "->", e.get("final_url"))
    print("RESULT :", "OK" if e.get("success") else f"ERR {e.get('error_type')}")
    f = e.get("text_file")
    if f and (TEXTDIR / f).exists():
        text = (TEXTDIR / f).read_text(encoding="utf-8")
        print("-" * 100)
        print(text[:width])
        if len(text) > width:
            print(f"... [{len(text) - width} more chars]")