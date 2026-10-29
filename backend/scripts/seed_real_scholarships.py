"""Run the canonical verified scholarship ingestion catalogue."""

from pathlib import Path
import sys
import subprocess
import json
from datetime import date, datetime


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
from app.services.scholarship_ingestion import ScholarshipIngestionRecord, upsert_verified_scholarships  # noqa: E402


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


def load_master_recovered(json_path: Path, master_by_url: dict[str, int], verified_urls: set, additional_urls: set) -> list:
    """Load master recovered scholarships from JSON file."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = []
    for item in data:
        def parse_date(v):
            if v is None:
                return None
            if isinstance(v, str):
                try:
                    return datetime.fromisoformat(v.replace("Z", "+00:00")).date()
                except ValueError:
                    return None
            return v

        def parse_datetime(v):
            if v is None:
                return None
            if isinstance(v, str):
                try:
                    return datetime.fromisoformat(v.replace("Z", "+00:00"))
                except ValueError:
                    return None
            return v

        original_id = item.get("original_id")
        url = item.get("official_source_url")
        # Skip if already in VERIFIED or ADDITIONAL
        if url in verified_urls or url in additional_urls:
            continue
        record = ScholarshipIngestionRecord(
            name=item["name"],
            country=item["country"],
            degree_levels=item["degree_levels"],
            funding_type=item["funding_type"],
            deadline=item["deadline"],
            deadline_date=parse_date(item.get("deadline_date")),
            deadline_precision=item.get("deadline_precision", "unknown"),
            application_period=item.get("application_period", ""),
            eligibility_summary=item.get("eligibility_summary", ""),
            coverage=item.get("coverage", []),
            required_documents=item.get("required_documents", []),
            official_source_url=item["official_source_url"],
            official_source=item.get("official_source", ""),
            is_verified=item.get("is_verified", False),
            english_requirement=item.get("english_requirement", "See official source for English requirements."),
            best_fit=item.get("best_fit", ""),
            notes=item.get("notes", ""),
            # Master recovered records don't have verified images; set to empty to pass evidence gate
            image_url="",
            image_source_url="",
            image_source_type="",
            image_verified_at=None,
            image_kind="program_image",
            image_alt_text="",
            # Use original_id as preferred_id to preserve master snapshot IDs
            preferred_id=item.get("original_id"),
        )
        records.append(record)

    return records


def main() -> None:
    # Load master ID map for backward compatibility
    master_id_map = _load_master_id_map()
    if master_id_map:
        print(f"Loaded {len(master_id_map)} master IDs for backward compatibility")

    init_database()
    with get_session_factory()() as session:
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
        additional_urls = {s.official_source_url for s in ADDITIONAL_VERIFIED_SCHOLARSHIPS}
        additional_filtered = [s for s in ADDITIONAL_VERIFIED_SCHOLARSHIPS if s.official_source_url not in verified_urls]

        # Load master recovered scholarships from JSON FIRST (to reserve original IDs)
        json_path = BACKEND_ROOT / "data" / "master_recovered_scholarships.json"
        master_recovered_filtered = []
        if json_path.exists():
            master_recovered = load_master_recovered(json_path, master_id_map, verified_urls, additional_urls)
            # Filter out records already in canonical catalogue
            canonical_urls = verified_urls | {s.official_source_url for s in ADDITIONAL_VERIFIED_SCHOLARSHIPS}
            master_recovered_filtered = [r for r in master_recovered if r.official_source_url not in canonical_urls]
            print(f"Master recovered: {len(master_recovered_filtered)} new (reserving original IDs)")
        else:
            print("Master recovered JSON not found, skipping")

        # Apply master IDs to VERIFIED and ADDITIONAL records
        verified_updated = 0
        additional_updated = 0
        for s in VERIFIED_SCHOLARSHIPS:
            if s.official_source_url in master_id_map:
                preferred = master_id_map[s.official_source_url]
                if preferred not in {2, 3}:  # Reserved IDs
                    s.preferred_id = master_id_map[s.official_source_url]
                    verified_updated += 1
        for s in ADDITIONAL_VERIFIED_SCHOLARSHIPS:
            if s.official_source_url in master_id_map:
                preferred = master_id_map[s.official_source_url]
                if preferred not in {2, 3}:
                    s.preferred_id = master_id_map[s.official_source_url]
                    additional_updated += 1
        print(f"Applied master IDs: {verified_updated} VERIFIED, {additional_updated} ADDITIONAL records updated")

        # Build canonical catalogue: MASTER RECOVERED first (to reserve original IDs), then VERIFIED, then ADDITIONAL
        additional_filtered = [s for s in ADDITIONAL_VERIFIED_SCHOLARSHIPS if s.official_source_url not in {s.official_source_url for s in VERIFIED_SCHOLARSHIPS}]
        canonical_catalogue = master_recovered_filtered + list(VERIFIED_SCHOLARSHIPS) + additional_filtered

        print(f"Canonical catalogue: {len(master_recovered_filtered)} RECOVERED + {len(VERIFIED_SCHOLARSHIPS)} VERIFIED + {len(additional_filtered)} ADDITIONAL = {len(canonical_catalogue)} total")

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