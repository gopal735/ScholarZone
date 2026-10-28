"""Run the canonical verified scholarship ingestion catalogue."""

from pathlib import Path
import sys
import subprocess
import json


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.data.verified_scholarships import (
    EIFFEL_OFFICIAL_SOURCE_URL,
    SWISS_ESKAS_OFFICIAL_SOURCE_URL,
    VERIFIED_SCHOLARSHIPS,
)
from app.data.additional_scholarships import (
    ADDITIONAL_VERIFIED_SCHOLARSHIPS,
)  # noqa: E402
from app.database import get_session_factory, init_database  # noqa: E402
from app.models import Scholarship  # noqa: E402
from app.services.scholarship_ingestion import upsert_verified_scholarships  # noqa: E402


RESULT_URLS = (EIFFEL_OFFICIAL_SOURCE_URL, SWISS_ESKAS_OFFICIAL_SOURCE_URL)


def _load_master_id_map() -> dict[str, int]:
    """Fetch the master snapshot from origin/master and return URL->ID mapping."""
    try:
        result = subprocess.run(
            ["git", "show", "origin/master:frontend/public/scholarships-snapshot.json"],
            capture_output=True,
            cwd=BACKEND_ROOT.parent,
            timeout=30,
        )
        if result.returncode != 0:
            print(f"Warning: Could not fetch master snapshot: {result.stderr.decode('utf-8', errors='replace')}")
            return {}
        master_data = json.loads(result.stdout.decode("utf-8"))
        return {
            s["official_source_url"]: s["id"]
            for s in master_data["scholarships"]
            if s.get("official_source_url")
        }
    except Exception as e:
        print(f"Warning: Failed to load master ID map: {e}")
        return {}


def main() -> None:
    # Load master ID map for backward compatibility
    master_id_map = _load_master_id_map()
    if master_id_map:
        print(f"Loaded {len(master_id_map)} master IDs for backward compatibility")

    init_database()
    with get_session_factory()() as session:
        # Legacy bootstrap records are now included in the canonical catalogue
        # via VERIFIED_SCHOLARSHIPS (which includes them with stable IDs)
        # No separate seed_scholarships() call needed.

        # Debug: check what's in the database initially (should be empty)
        from sqlalchemy import select
        existing_ids = session.scalars(select(Scholarship.id)).all()
        print(f"DEBUG: IDs in DB initially: {sorted(existing_ids)}")

        previous_ids = {
            source_url: session.scalar(
                select(Scholarship.id).where(Scholarship.official_source_url == source_url)
            )
            for source_url in RESULT_URLS
        }
        # Build canonical catalogue: VERIFIED first (takes precedence), then ADDITIONAL
        verified_urls = {s.official_source_url for s in VERIFIED_SCHOLARSHIPS}
        additional_filtered = [s for s in ADDITIONAL_VERIFIED_SCHOLARSHIPS if s.official_source_url not in verified_urls]
        canonical_catalogue = list(VERIFIED_SCHOLARSHIPS) + additional_filtered

# Set legacy_id from master snapshot for backward URL compatibility
        reserved_ids = {2, 3}  # Legacy bootstrap IDs (ICCR, DAAD)
        for record in canonical_catalogue:
            if master_id_map and record.official_source_url in master_id_map:
                preferred = master_id_map[record.official_source_url]
                if preferred not in reserved_ids:
                    record.legacy_id = master_id_map[record.official_source_url]

        print(f"Canonical catalogue: {len(VERIFIED_SCHOLARSHIPS)} VERIFIED + {len(additional_filtered)} ADDITIONAL (filtered) = {len(canonical_catalogue)} total")

        created_count, updated_count = upsert_verified_scholarships(session, canonical_catalogue)
        resulting_rows = session.scalars(
            select(Scholarship)
            .where(Scholarship.official_source_url.in_(RESULT_URLS))
            .order_by(Scholarship.id)
        ).all()

        print(f"Created {created_count} scholarship record(s); updated {updated_count} record(s).")
        for scholarship in resulting_rows:
            print(
                {
                    "action": "UPDATED" if previous_ids[scholarship.official_source_url] else "CREATED",
                    "id": scholarship.id,
                    "name": scholarship.title,
                    "country": scholarship.country,
                    "official_source_url": scholarship.official_source_url,
                    "is_verified": scholarship.is_verified,
                }
            )


if __name__ == "__main__":
    main()