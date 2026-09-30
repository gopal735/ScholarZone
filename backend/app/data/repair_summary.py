"""Summarise a source-repair run JSON."""
from __future__ import annotations

import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

path = sys.argv[1]
d = json.load(open(path, encoding="utf-8"))
print("MODE:", d.get("mode"))
print("COUNTS:", json.dumps(d["counts"], indent=2))

rows = d["rows"]
rep = [r for r in rows if r["quality"] in ("repaired_authoritative", "redirected_to_authoritative")]
unres = [r for r in rows if r["quality"] == "unresolved"]
print(f"\nrepaired+redirected: {len(rep)}   unresolved: {len(unres)}")

print("\n--- repairs (first 10) ---")
for r in rep[:10]:
    print(f"  id={r['id']:<5d} {str(r['from'])[:54]}")
    print(f"        -> {str(r['to'])[:80]}")
    print(f"        {r['reason'][:78]}")

print("\n--- unresolved (first 6) ---")
for r in unres[:6]:
    print(f"  id={r['id']:<5d} {str(r['from'])[:62]}")
    print(f"        {r['reason'][:86]}")
