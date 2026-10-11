"""Phase 1 (audit only, read-only): intake-status inventory.

Produces the per-record evidence table for every closed/expired published
record, from:
  - the committed public snapshot (the live artifact's source),
  - the copied local database (read only),
  - the copied research corpus (read only).

Nothing writes to either source. The output is the classification worksheet
the official-source verification pass fills in.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
SNAPSHOT = BASE / "frontend/public/scholarships-snapshot.json"
DATABASE = BASE / "backend/scholarzone.db"
CORPUS = BASE / "backend/config/programme_details.json"

snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
records = snapshot["scholarships"]
meta = snapshot["meta"]

conn = sqlite3.connect(DATABASE)
conn.row_factory = sqlite3.Row
corpus = {r["id"]: r for r in json.loads(CORPUS.read_text(encoding="utf-8"))["records"]}


def http_urls(values):
    return [u for u in (values or []) if isinstance(u, str) and u.startswith(("http://", "https://"))]


today = date.today()
rows = []
for record in records:
    row = conn.execute("SELECT * FROM scholarships WHERE id = ?", (record["id"],)).fetchone()
    crow = corpus.get(record["id"]) or {}
    official = crow.get("official") or {}
    verification = crow.get("verification") or {}

    deadline = record.get("deadline_date")
    if deadline:
        try:
            deadline_day = date.fromisoformat(str(deadline).split("T", 1)[0].split(" ", 1)[0])
        except ValueError:
            deadline_day = None
    else:
        deadline_day = None

    # Official-page facts the research already read, so the verification pass
    # starts from the best local evidence instead of from nothing.
    status_note = official.get("status_note")
    deadline_display_official = official.get("deadline_central_display")
    urls = sorted(
        set(
            http_urls(official.get("official_source_urls"))
            + ([official["official_source_url"]] if official.get("official_source_url") else [])
            + http_urls(verification.get("source_citations"))
        )
    )

    rows.append(
        {
            "id": record["id"],
            "title": record.get("title"),
            "country": record.get("country"),
            "degree": record.get("degree"),
            "funding": record.get("funding"),
            "funding_amount": record.get("funding_amount"),
            "funding_currency": record.get("funding_currency"),
            "funding_period": record.get("funding_period"),
            "public_status": record.get("status"),
            "db_status": row["status"] if row else None,
            "db_archived": bool(row["is_archived"]) if row else None,
            "db_verification_status": row["verification_status"] if row else None,
            "deadline_date": deadline,
            "days_since_deadline": (today - deadline_day).days if deadline_day else None,
            "deadline_display": record.get("deadline"),
            "official_deadline_display": deadline_display_official,
            "official_status_note": status_note,
            "official_source": record.get("official_source"),
            "official_source_url": record.get("official_source_url"),
            "official_urls": urls,
            "verified": record.get("verified"),
            "last_verified_date": record.get("last_verified_date"),
            "in_corpus": bool(crow),
            "corpus_keys": len(official),
        }
    )

closed = [r for r in rows if r["public_status"] == "closed"]
live = [r for r in rows if r["public_status"] in ("open", "closing-soon", "upcoming")]
other = [r for r in rows if r["public_status"] not in ("closed", "open", "closing-soon", "upcoming")]

out = {
    "_audit": {
        "date": today.isoformat(),
        "snapshot_generated_at": meta.get("generated_at"),
        "snapshot_public_record_count": meta.get("public_record_count"),
        "snapshot_status_derived_at": meta.get("status_derived_at"),
        "closed_count": len(closed),
        "live_count": len(live),
        "other_status_count": len(other),
        "database_path": str(DATABASE),
        "corpus_path": str(CORPUS),
        "mode": "read-only audit; no database, snapshot or corpus writes",
    },
    "closed_records": sorted(closed, key=lambda r: r["id"]),
    "live_records": sorted(live, key=lambda r: r["id"]),
    "other_status_records": sorted(other, key=lambda r: r["id"]),
}
output = BASE / "backend/research_output/publish/intake_audit_2026-10-11.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

# Console summary
buckets = {}
for r in closed:
    d = r["days_since_deadline"]
    if d is None:
        key = "no deadline"
    elif d <= 90:
        key = "expired <=90d"
    elif d <= 365:
        key = "expired 91-365d"
    elif d <= 730:
        key = "expired 1-2y"
    else:
        key = "expired >2y"
    buckets[key] = buckets.get(key, 0) + 1
print("closed records:", len(closed))
for k, v in sorted(buckets.items()):
    print(f"  {k}: {v}")
with_note = [r["id"] for r in closed if r["official_status_note"]]
print("closed records carrying a corpus status_note:", len(with_note), with_note[:15])
print("written:", output)
conn.close()
