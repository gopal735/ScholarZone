"""Build wave-1 research shards for the 50-agent live re-verification run.

Each shard is a self-contained assignment: the current DB state of ~10 records
plus the focus areas that need live official re-verification.
"""
import json
import os
import sqlite3
from urllib.parse import urlsplit

ROOT = r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone"
DB = os.path.join(ROOT, "backend", "scholarzone.db")
OUT = os.path.join(ROOT, "research", "wave1", "shards")
os.makedirs(OUT, exist_ok=True)

SHARDS = 50
TODAY = "2026-10-04"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT id,title,country,degree,funding,status,deadline_date,deadline_display,"
    "deadline_precision,official_source,official_source_url,application_link,region,"
    "program_type,verification_status,is_verified,last_verified_date,image_url,"
    "image_source_url,image_source_type,image_kind,image_verified_at,image_alt_text,funding_amount,"
    "funding_currency,fully_funded FROM scholarships ORDER BY id"
).fetchall()


def host_of(url):
    if not url:
        return None
    try:
        h = urlsplit(url if "//" in url else "https://" + url).netloc.lower()
        return h[4:] if h.startswith("www.") else h or None
    except ValueError:
        return None


def focus_for(r):
    """What this record most needs from a live official re-check."""
    f = []
    if not r["image_url"]:
        f.append("NO_IMAGE_AT_ALL")
    elif r["image_kind"] not in ("official_logo", "official_government", "official_university"):
        f.append("STORED_IMAGE_IS_A_PHOTO_OR_BANNER_NOT_THE_OFFICIAL_LOGO")
    if r["verification_status"] != "active":
        f.append(f"VERIFICATION_STATUS_IS_{str(r['verification_status']).upper()}")
    if not r["deadline_date"]:
        f.append("NO_EXACT_DEADLINE_DATE")
    if r["deadline_precision"] in ("unknown", "application_dead"):
        f.append(f"DEADLINE_PRECISION_IS_{str(r['deadline_precision']).upper()}")
    if not r["region"]:
        f.append("REGION_MISSING")
    if not r["funding_amount"]:
        f.append("NO_FUNDING_AMOUNT")
    if not r["last_verified_date"] or str(r["last_verified_date"]) < "2026-09-01":
        f.append("NOT_REVERIFIED_SINCE_SEPTEMBER")
    if not f:
        f.append("FULL_REFRESH_ALL_FIELDS")
    return f


records = []
for r in rows:
    records.append(
        {
            "target_id": r["id"],
            "current_title": r["title"],
            "official_source": r["official_source"],
            "current_official_source_url": r["official_source_url"],
            "current_application_link": r["application_link"],
            "official_host": host_of(r["official_source_url"]),
            "country": r["country"],
            "degree": r["degree"],
            "funding": r["funding"],
            "region": r["region"],
            "program_type": r["program_type"],
            "status": r["status"],
            "deadline_date": r["deadline_date"],
            "deadline_display": r["deadline_display"],
            "deadline_precision": r["deadline_precision"],
            "verification_status": r["verification_status"],
            "last_verified_date": r["last_verified_date"],
            "current_image_url": r["image_url"],
            "current_image_kind": r["image_kind"],
            "current_image_source_type": r["image_source_type"],
            "current_image_source_url": r["image_source_url"],
            "current_image_alt_text": r["image_alt_text"],
            "current_funding_amount": r["funding_amount"],
            "current_funding_currency": r["funding_currency"],
            "research_focus": focus_for(r),
        }
    )

per = (len(records) + SHARDS - 1) // SHARDS
bounds = []
start = 0
for i in range(SHARDS):
    bounds.append(start)
    start += len(records) // SHARDS + (1 if i < len(records) % SHARDS else 0)
bounds.append(len(records))
manifest = []
for i in range(SHARDS):
    chunk = records[bounds[i] : bounds[i + 1]]
    if not chunk:
        continue
    n = i + 1
    payload = {
        "shard": f"w1-{n:02d}",
        "agent_id": f"w1_{n:02d}",
        "today": TODAY,
        "record_count": len(chunk),
        "records": chunk,
    }
    path = os.path.join(OUT, f"w1-{n:02d}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    manifest.append(
        {
            "shard": payload["shard"],
            "file": os.path.relpath(path, ROOT).replace("\\", "/"),
            "count": len(chunk),
            "ids": [c["target_id"] for c in chunk],
        }
    )

with open(os.path.join(OUT, "MANIFEST.json"), "w", encoding="utf-8") as fh:
    json.dump({"shards": len(manifest), "records": len(records), "items": manifest}, fh, indent=2)

print("records:", len(records), "shards:", len(manifest), "per shard:", per)
print("first shard ids:", manifest[0]["ids"])
print("last shard ids:", manifest[-1]["ids"])