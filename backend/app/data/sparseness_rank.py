"""Rank scholarships by how much official information is actually missing.

Sparse records get the deeper multi-page research pass, so the driver can
prioritise effort where it changes the record most.
"""
from __future__ import annotations

import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select

from app.database import get_session_factory
from app.models import Scholarship

FACT_FIELDS = [
    "description",
    "region",
    "duration",
    "program_type",
    "application_period",
    "eligibility_summary",
    "eligibility",
    "benefits",
    "coverage",
    "requirements",
    "documents",
    "english_requirement",
    "application_method",
    "selection_notes",
    "best_fit",
    "notes",
    "deadline_display",
    "deadline_date",
    "catalogue_url",
    "official_updates_url",
    "application_link",
]


def sparseness(row: Scholarship) -> tuple[int, list[str]]:
    missing: list[str] = []
    for f in FACT_FIELDS:
        v = getattr(row, f, None)
        if v in (None, "", []):
            missing.append(f)
    return len(missing), missing


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    out = sys.argv[2] if len(sys.argv) > 2 else None

    factory = get_session_factory()
    session = factory()
    try:
        rows = session.scalars(
            select(Scholarship)
            .where(Scholarship.verification_status != "quarantined")
            .order_by(Scholarship.id)
        ).all()
        scored = []
        for row in rows:
            n, missing = sparseness(row)
            scored.append((n, row.id, row.title, row.official_source_url, missing))
        scored.sort(key=lambda t: (-t[0], t[1]))

        total = len(scored)
        perfect = sum(1 for s in scored if s[0] == 0)
        print(f"valid scholarships      : {total}")
        print(f"no missing fact fields  : {perfect} ({100*perfect/total:.1f}%)")
        print(f"mean missing fields     : {sum(s[0] for s in scored)/total:.1f} of {len(FACT_FIELDS)}")

        print(f"\n--- {limit} most sparse records (deep-research priority) ---")
        for n, sid, title, url, missing in scored[:limit]:
            print(f"  id={sid:<5d} missing {n:>2}/{len(FACT_FIELDS)}  {str(title)[:50]}")
            print(f"        {str(url)[:86]}")

        if out:
            payload = [
                {"id": sid, "missing": n, "title": title, "url": url, "fields": missing}
                for n, sid, title, url, missing in scored
            ]
            with open(out, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            print(f"\nfull ranking -> {out}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
