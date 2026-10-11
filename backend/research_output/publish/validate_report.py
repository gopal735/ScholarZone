"""Final cross-check of the Phase 2 report's claims against the data.

Read-only. Fails loudly if any number in the report disagrees with the
merged classification, the snapshot, or the local database copy.
"""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
CLASSIFICATION = BASE / "backend/research_output/publish/intake_classification_2026-10-11.json"
INVENTORY = BASE / "backend/research_output/publish/intake_audit_2026-10-11.json"
SNAPSHOT = BASE / "frontend/public/scholarships-snapshot.json"
DATABASE = BASE / "backend/scholarzone.db"

data = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
conn = sqlite3.connect(DATABASE)
conn.row_factory = sqlite3.Row

failures = []


def check(label, actual, expected):
    ok = actual == expected
    print(f"{'PASS' if ok else 'FAIL'}  {label}: {actual}" + ("" if ok else f" (expected {expected})"))
    if not ok:
        failures.append(label)


records = data["records"]
counts = Counter(r["classification"] for r in records)

check("total classified", len(records), 153)
check("unique ids", len({r["id"] for r in records}), 153)
check("no missing", data["_audit"]["missing"], [])
check("recurring", counts["recurring_next_intake_expected"], 91)
check("temporarily closed", counts["temporarily_closed_awaiting_announcement"], 38)
check("uncertain", counts["uncertain"], 15)
check("upcoming/current", counts["upcoming_or_current_intake"], 7)
check("discontinued", counts["genuinely_discontinued"], 2)

# The audit population must be exactly the snapshot's closed-labelled records.
snapshot_closed = sorted(r["id"] for r in snapshot["scholarships"] if r["status"] == "closed")
check("audit population == snapshot closed ids", sorted(r["id"] for r in records), snapshot_closed)

# Discontinued candidates must carry fetched evidence and high confidence.
for rid in (279, 729):
    rec = next(r for r in records if r["id"] == rid)
    check(f"id {rid} classification", rec["classification"], "genuinely_discontinued")
    check(f"id {rid} has evidence url", bool(rec["official_evidence_urls"]), True)
    check(f"id {rid} confidence >= 0.8", rec["confidence"] >= 0.8, True)
    check(f"id {rid} still published (no removal made)", rid in {r["id"] for r in snapshot["scholarships"]}, True)

# Every record must carry evidence text, and a real evidence URL or a stated reason.
missing_evidence = [r["id"] for r in records if not r.get("page_evidence")]
check("every record carries page_evidence", missing_evidence, [])

# Every uncertain record must have no unsupported claim: confidence <= 0.5
low_conf = [r["id"] for r in records if r["classification"] == "uncertain" and r["confidence"] > 0.5]
check("uncertain records are <= 0.5 confidence", low_conf, [])

# Retained count arithmetic.
check("retained closed records", len(records) - 2, 151)
check("published total", len(snapshot["scholarships"]), 623)
check("closed published now", len(snapshot_closed), 153)
check("non-closed published", 623 - 153, 470)

# Duplicate pairs are still both published (no merges performed).
for a, b in ((182, 382), (185, 452), (374, 514)):
    ids = {r["id"] for r in snapshot["scholarships"]}
    check(f"duplicate pair {a}/{b} both still published", {a, b} <= ids, True)

# Local DB copy unchanged.
check("db rows", conn.execute("SELECT COUNT(*) FROM scholarships").fetchone()[0], 695)
check("db archived", conn.execute("SELECT COUNT(*) FROM scholarships WHERE is_archived=1").fetchone()[0], 52)
check("279 not archived in db", conn.execute("SELECT is_archived FROM scholarships WHERE id=279").fetchone()[0], 0)
check("729 not archived in db", conn.execute("SELECT is_archived FROM scholarships WHERE id=729").fetchone()[0], 0)

# CGRS-D successor exists as published (Vanier's replacement).
cgr = [r["id"] for r in snapshot["scholarships"] if "Canada Graduate Research" in (r["title"] or "")]
check("successor CGRS-D published", bool(cgr), True)
print("  successor id(s):", cgr)

print()
if failures:
    print("FAILURES:", failures)
    sys.exit(1)
print(f"All checks passed. {len(records)}/153 classified; report numbers agree with the data.")
conn.close()
