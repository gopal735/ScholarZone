"""Apply a lifecycle correction proven by an official source statement.

A status of "open" on a programme that has stopped accepting applications is
the most damaging kind of stale fact on the site: it invites a student to a
dead end. This applies a correction only where the provider states the change
in its own words, records the exact quotation, and keeps the programme's
history intact rather than deleting it.

The successor programme is named in the record's notes so the student is sent
to the live route, and the old deadline wording is preserved - it remains
historically true for the final competition.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.database import get_session_factory
from app.models import Scholarship, ScholarshipVerificationHistory

APPLY = "--apply" in sys.argv

#: scholarship_id -> the correction, with the provider's own wording.
CORRECTIONS: dict[int, dict[str, object]] = {
    38: {
        "status": "closed",
        "notes": (
            "No longer accepting applications. The Government of Canada "
            "harmonised the Vanier CGS into the Canada Graduate Research "
            "Scholarship - Doctoral (CGRS D) programme; new doctoral "
            "competitions are run by CIHR, NSERC and SSHRC through the "
            "Canadian Research Training Awards Suite. Applicants must still be "
            "nominated by a Canadian institution. The Vanier site remains the "
            "official record of the legacy programme."
        ),
        "official_updates_url": "https://nserc-crsng.canada.ca/en/funding-opportunity/canada-graduate-research-scholarship-doctoral-program",
        "quote": (
            "We are no longer accepting applications for the Vanier Canada "
            "Graduate Scholarships. Please refer to the Canada Graduate "
            "Research Scholarship - Doctoral program web page for information "
            "regarding the new harmonized program."
        ),
        "source": "https://vanier.gc.ca/en/home-accueil.html",
    },
}


def main() -> int:
    factory = get_session_factory()
    session = factory()
    try:
        for sid, fix in CORRECTIONS.items():
            row = session.get(Scholarship, sid)
            if row is None:
                print(f"id={sid}: not found")
                continue
            print(f"\nid={sid}  {row.title}")
            print(f"  before: status={row.status}")
            for field in ("status", "notes", "official_updates_url"):
                if field in fix:
                    print(f"  {field}: {str(getattr(row, field))[:70]}")
                    print(f"  {'->':>8} {str(fix[field])[:70]}")
            if not APPLY:
                continue
            for field in ("status", "notes", "official_updates_url"):
                if field in fix:
                    session.add(
                        ScholarshipVerificationHistory(
                            scholarship_id=sid,
                            field_name=field,
                            old_value=str(getattr(row, field) or ""),
                            new_value=str(fix[field]),
                            change_type="modified",
                            source_url=str(fix["source"]),
                            evidence_text=f'Provider states: "{fix["quote"]}"',
                            confidence="high",
                            verification_status="active",
                        )
                    )
                    setattr(row, field, fix[field])
            row.last_verified_at = datetime.now(timezone.utc)
            session.commit()
            print("  APPLIED with audit trail")
        if not APPLY:
            print("\ndry run: no changes written (pass --apply to persist)")
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
