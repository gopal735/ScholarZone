"""Archive stale scholarship records not in the canonical catalogue.

This script marks as archived any scholarship records in the database that are
not present in the current canonical catalogue (by official_source_url).
This ensures the public catalogue only contains active/upcoming opportunities
from the authoritative source.
"""

from pathlib import Path
import sys
import json


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select

from app.data.verified_scholarships import VERIFIED_SCHOLARSHIPS
from app.data.additional_scholarships import ADDITIONAL_VERIFIED_SCHOLARSHIPS
from app.database import get_session_factory, init_database
from app.models import Scholarship


def load_master_recovered_urls() -> set[str]:
    """Load official_source_urls from master recovered JSON."""
    json_path = BACKEND_ROOT / 'data' / 'master_recovered_scholarships.json'
    if not json_path.exists():
        return set()
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return {item['official_source_url'] for item in data if item.get('official_source_url')}


def main() -> int:
    init_database()

    # Build canonical catalogue URLs
    verified_urls = {s.official_source_url for s in VERIFIED_SCHOLARSHIPS}
    additional_urls = {s.official_source_url for s in ADDITIONAL_VERIFIED_SCHOLARSHIPS}
    master_recovered_urls = load_master_recovered_urls()
    canonical_urls = verified_urls.union(additional_urls).union(master_recovered_urls)

    print(f"Canonical catalogue URLs: {len(canonical_urls)} (verified: {len(verified_urls)}, additional: {len(additional_urls)}, master recovered: {len(master_recovered_urls)})")

    with get_session_factory()() as session:
        # Find all records in database
        all_records = session.scalars(select(Scholarship)).all()
        print(f"Total records in database: {len(all_records)}")

        # Find records not in canonical catalogue
        stale_records = [r for r in all_records if r.official_source_url not in canonical_urls]
        print(f"Stale records (not in canonical catalogue): {len(stale_records)}")

        if not stale_records:
            print("No stale records to archive.")
            return 0

        # Show what will be archived
        for record in stale_records[:20]:
            print(f"  - ID {record.id}: {record.title} (source: {record.official_source_url})")
        if len(stale_records) > 20:
            print(f"  ... and {len(stale_records) - 20} more")

        # Archive stale records
        archived_count = 0
        for record in stale_records:
            if not record.is_archived and record.status != "closed":
                record.is_archived = True
                archived_count += 1

        session.commit()
        print(f"Archived {archived_count} stale records.")

        # Verify
        remaining_public = session.scalars(
            select(Scholarship).where(
                Scholarship.status != "closed",
                Scholarship.is_archived.is_(False),
                Scholarship.verification_status != "quarantined",
            )
        ).all()
        print(f"Remaining public records: {len(remaining_public)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())