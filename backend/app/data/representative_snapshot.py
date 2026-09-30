"""Capture a BEFORE/AFTER snapshot of representative scholarship records.

Usage:
  python representative_snapshot.py before
  python representative_snapshot.py after
"""
from __future__ import annotations

import json
import sys
from urllib.parse import urlparse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship

# One record per archetype the task asks to demonstrate.
REPRESENTATIVE = {
    "fully_populated": 7,     # Swiss Gov ESKAS - many fields populated
    "sparse": 69,             # Cambridge Trust - few fields
    "no_image": 3,            # DAAD - no verified image
    "image_backed": 14,       # ETH Zurich - has verified program image
    "multiple_source": 6,     # Campus France - several official URLs
    "government": 12,         # MEXT / Japanese govt
    "university": 21,         # DAAD study scholarship (university-level)
    "international": 13,      # POSCO foundation, international programme
}

FIELDS = [
    "title", "official_source", "country", "region", "degree", "program_type",
    "description", "duration", "application_period", "deadline_display",
    "deadline_date", "deadline_precision", "status", "eligibility_summary",
    "eligibility", "benefits", "coverage", "requirements", "documents",
    "english_requirement", "application_method", "selection_notes", "best_fit",
    "notes", "application_link", "official_source_url", "catalogue_url",
    "official_updates_url", "image_url", "image_source_url",
    "image_source_type", "image_kind", "image_alt_text", "image_verified_at",
    "last_verified_at",
]


def snapshot() -> dict:
    engine = create_engine("sqlite:///scholarzone.db")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    out: dict[str, dict] = {}
    for label, sid in REPRESENTATIVE.items():
        row = session.get(Scholarship, sid)
        if row is None:
            out[label] = {"id": sid, "missing": True}
            continue
        data = {}
        for f in FIELDS:
            v = getattr(row, f, None)
            if isinstance(v, list):
                v = [str(x) for x in v]
            data[f] = v
        data["_official_domain"] = urlparse(row.official_source_url or "").netloc
        out[label] = data
    session.close()
    return out


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "before"
    snap = snapshot()
    path = f"C:/Users/GopaL/AppData/Local/Temp/kilo/rep_{mode}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, indent=2, default=str)

    print(f"{'RECORD':<18} {'ID':>5}  {'DOMAIN':<28} FILDS-POPULATED  IMAGES")
    for label, data in snap.items():
        populated = sum(
            1 for k, v in data.items()
            if k not in ("_official_domain", "id", "missing") and v not in (None, "", [], {})
        )
        img = "yes" if data.get("image_url") else "no"
        print(f"{label:<18} {data.get('id','-'):>5}  {str(data.get('_official_domain'))[:28]:<28} {populated:>3}/{len(FIELDS)}      {img}")
    print(f"\nsnapshot -> {path}")
