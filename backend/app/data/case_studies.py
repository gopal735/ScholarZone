"""Report 20 real sparse-record case studies with final image outcomes."""
from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select

from app.data.sparseness_rank import FACT_FIELDS
from app.database import get_session_factory
from app.models import Scholarship
from app.services.image_evaluation_status import ImageEvaluationStatus

LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 20

factory = get_session_factory()
session = factory()
try:
    rows = list(
        session.scalars(
            select(Scholarship).where(Scholarship.verification_status != "quarantined")
        )
    )

    scored = []
    for row in rows:
        empty = sum(1 for f in FACT_FIELDS if getattr(row, f, None) in (None, "", []))
        scored.append((empty, row))
    scored.sort(key=lambda t: (-t[0], t[1].id))

    # Sparsest records that nonetheless hold real official facts. Sorting by
    # descending empty count is the point: these are the information-poor
    # records the deep pass was meant to help.
    picked = []
    for empty, row in scored:
        populated = [f for f in FACT_FIELDS if getattr(row, f, None) not in (None, "", [])]
        if populated:
            picked.append((empty, row, populated))
        if len(picked) >= LIMIT:
            break

    print(f"20 SPARSE-RECORD CASE STUDIES (sparsest records with official facts)")
    print("=" * 96)
    for n, (empty, row, populated) in enumerate(picked, 1):
        print(f"\n[{n}] id={row.id}  empty={empty}/21  status={row.status}")
        print(f"    title    : {str(row.title)[:88]}")
        print(f"    official : {str(row.official_source_url)[:88]}")
        print(f"    deadline : {row.deadline_date or 'none published'}")
        outcome = (
            ImageEvaluationStatus.VERIFIED
            if row.image_verified_at and not row.image_evaluation_status
            else (row.image_evaluation_status or "unevaluated")
        )
        if row.image_verified_at:
            prov = all(
                [
                    row.image_url,
                    row.image_source_url,
                    row.image_source_type,
                    row.image_alt_text,
                    row.image_verified_at,
                ]
            )
            print(
                f"    image    : [{row.image_kind}] {str(row.image_url)[:58]}"
                f" provenance={'complete' if prov else 'INCOMPLETE'}"
            )
        else:
            print(f"    image    : {outcome}")
        show = [
            f
            for f in ("eligibility", "benefits", "coverage", "requirements",
                      "documents", "application_method", "english_requirement",
                      "duration", "deadline_display", "description",
                      "selection_notes", "best_fit", "application_period")
            if getattr(row, f, None) not in (None, "", [])
        ]
        print(f"    populated: {', '.join(show) if show else 'none'}")
        for col in show[:2]:
            val = getattr(row, col)
            if isinstance(val, list):
                text = f"({len(val)}) " + " | ".join(str(v) for v in val)[:88]
            else:
                text = str(val)[:94]
            print(f"       {col:20s} {text}")
finally:
    session.close()
