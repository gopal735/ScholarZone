"""Report real enriched examples across the sparse and enriched spectrum."""
from __future__ import annotations

import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select

from app.database import get_session_factory
from app.models import Scholarship
from app.data.sparseness_rank import FACT_FIELDS

LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 20
OUT = r"C:\Users\GopaL\AppData\Local\Temp\kilo\sparse_examples.json"

FACT_COLS = [
    "eligibility", "benefits", "coverage", "requirements", "documents",
    "application_method", "english_requirement", "deadline_display",
    "duration", "description", "selection_notes", "best_fit",
]

factory = get_session_factory()
session = factory()
try:
    rows = session.scalars(
        select(Scholarship).where(Scholarship.verification_status != "quarantined")
    ).all()

    enriched = []
    for row in rows:
        empty = sum(1 for f in FACT_FIELDS if getattr(row, f, None) in (None, "", []))
        populated = [
            c for c in FACT_COLS if getattr(row, c, None) not in (None, "", [])
        ]
        if populated and empty >= 8:
            enriched.append((empty, row, populated))

    enriched.sort(key=lambda t: (-len(t[2]), t[0], t[1].id))
    sample = enriched[:LIMIT]

    print(f"enriched valid records (>=8 empty fields, >=1 populated fact col): {len(enriched)}")
    print("=" * 100)
    for empty, row, populated in sample:
        print(f"\nid={row.id}  empty={empty}/21  status={row.status}")
        print(f"  title   : {str(row.title)[:74]}")
        print(f"  official: {str(row.official_source_url)[:88]}")
        for col in populated[:3]:
            val = getattr(row, col)
            if isinstance(val, list):
                text = " | ".join(str(v) for v in val)[:120]
                count = f"({len(val)} items) "
            else:
                text = str(val)[:120]
                count = ""
            print(f"  {col:22s} {count}{text}")
        if row.image_verified_at:
            print(f"  image                  [{row.image_kind}] {str(row.image_url)[:62]}")
        else:
            print(f"  image                  none verified")

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(
            [{"id": r.id, "empty": e, "title": r.title, "fields": p} for e, r, p in sample],
            fh,
            indent=2,
        )
    print(f"\n-> {OUT}")
finally:
    session.close()
