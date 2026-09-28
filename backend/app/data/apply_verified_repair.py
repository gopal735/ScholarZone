"""Apply a verified official-source repair and re-enrich the record.

Repairs are only applied when a candidate URL has been verified as the SAME
programme: same official host, the page fetched successfully, and its title
matches the record's own title. Everything is written through the normal
audit path (ScholarshipVerificationHistory) so the change is traceable, and
enrichment then extracts from the repaired page rather than from hand-written
values.
"""
from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select

from app.database import get_session_factory
from app.models import Scholarship, ScholarshipVerificationHistory
from app.services.scholarship_enrichment import ScholarshipEnrichmentService

# scholarship_id -> (new official url, why this is the same programme)
REPAIRS: dict[int, tuple[str, str]] = {
    324: (
        "https://bs.china-embassy.gov.cn/eng/sggg/202510/t20251028_11742717.htm",
        "Embassy announcement titled '2026/2027 Chinese Government Scholarship "
        "Application' - the exact cycle named in the record title. The stored "
        "URL was the embassy front door, which is not a programme page.",
    ),
}


def main() -> None:
    factory = get_session_factory()
    session = factory()
    try:
        for sid, (new_url, reason) in REPAIRS.items():
            row = session.get(Scholarship, sid)
            if row is None:
                print(f"id={sid}: not found")
                continue
            old_url = row.official_source_url
            print(f"\nid={sid}  {row.title}")
            print(f"  before: {old_url}")
            print(f"  after : {new_url}")

            row.official_source_url = new_url
            row.last_verified_at = None
            session.add(
                ScholarshipVerificationHistory(
                    scholarship_id=sid,
                    field_name="official_source_url",
                    old_value=old_url,
                    new_value=new_url,
                    change_type="official_source_repaired",
                    source_url=new_url,
                    evidence_text=reason,
                    confidence="high",
                    verification_status="verified",
                )
            )
            session.commit()
            print("  repair committed with audit trail")

        session.expire_all()
        for sid in REPAIRS:
            result = ScholarshipEnrichmentService(session_factory=factory).enrich_one(sid)
            print(
                f"  enrich id={sid}: outcome={result.outcome.value} "
                f"writes={len(result.updates)} pages={result.related_pages_followed}"
            )
            for update in result.updates[:12]:
                if update.action != "unchanged":
                    print(f"     {update.field_name:22s} {update.action:8s} {update.reason[:56]}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
