"""Classify enrichment outcomes and sample real proposed values for review."""
from __future__ import annotations

import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PATH = r"C:\Users\GopaL\AppData\Local\Temp\kilo\enrich_dryrun_full.txt"
# PowerShell Tee-Object writes UTF-16LE by default; honour the BOM if present.
raw = open(PATH, "rb").read()
if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
    text = raw.decode("utf-16", errors="replace")
else:
    text = raw.decode("utf-8", errors="replace")
lines = text.splitlines()

outcomes = Counter()
errors = Counter()
enriched = []

cur = None
for line in lines:
    m = re.match(r"^\[\s*\d+/\d+\]\s*(\*?)\s*id=(\d+)\s+(\S+)", line)
    if m:
        flag, sid, outcome = m.group(1), m.group(2), m.group(3)
        outcomes[outcome] += 1
        cur = {"id": sid, "outcome": outcome, "changes": flag == "*"}
        if flag == "*":
            enriched.append(cur)
        continue
    m = re.match(r"^\s*error:\s*(\w+):\s*(.*)$", line)
    if m and cur is not None:
        errors[f"{m.group(1)}"] += 1
        cur["error"] = f"{m.group(1)}: {m.group(2)}"
        continue

total = sum(outcomes.values())
print(f"TOTAL RECORDS: {total}\n")
print("=== OUTCOME BREAKDOWN ===")
for k, v in outcomes.most_common():
    print(f"  {k:<24s} {v:4d}  ({100*v/total:5.1f}%)")

print(f"\n=== SOURCE FAILURE CLASSIFICATION ({sum(errors.values())}) ===")
for k, v in errors.most_common():
    print(f"  {k:<20s} {v:4d}")

print(f"\n=== ENRICHED RECORDS: {len(enriched)} ===")

# Pull sample added values per field to eyeball quality
print("\n=== SAMPLE ADDED VALUES BY FIELD (quality eyeball) ===")
current_field = None
samples: dict[str, list[str]] = {}
for i, line in enumerate(lines):
    m = re.match(r"^\s+\[\s*(merged|fill|replace)\s*\]\s+(\w+)\s+(.*)$", line)
    if m:
        current_field = m.group(2)
        # next line holds the '+ ...' sample
        if i + 1 < len(lines):
            nxt = lines[i + 1].strip()
            if nxt.startswith("+"):
                samples.setdefault(current_field, []).append(nxt[1:].strip())
for field, vals in samples.items():
    print(f"\n--- {field} ({len(vals)} shown) ---")
    for v in vals[:8]:
        print(f"    {v[:150]}")
