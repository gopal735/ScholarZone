"""Run the canonical verified scholarship ingestion catalogue."""

from pathlib import Path
import sys
import json
import subprocess
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


def load_master_snapshot_ids() -> dict[str, int]:
    """Load master snapshot from origin/master and return mapping of official_source_url -> master_id."""
    try:
        result = subprocess.run(
            ['git', 'show', 'origin/master:frontend/public/scholarships-snapshot.json'],
            capture_output=True,
            cwd=BACKEND_ROOT.parent,
            check=True
        )
        master_data = json.loads(result.stdout.decode('utf-8'))
    except subprocess.CalledProcessError:
        print("Warning: Could not load master snapshot from git")
        return {}
    
    master_by_url = {}
    for r in master_data.get('scholarships', []):
        url = r.get('official_source_url')
        if url:
            master_by_url[url] = r['id']
    
    print(f"Loaded master snapshot from origin/master: {len(master_by_url)} records with URLs")
    return master_by_url


def apply_master_ids(records: list, master_by_url: dict[str, int]) -> int:
    """Apply master IDs as preferred_id for records that exist in master snapshot."""
    updated = 0
    for record in records:
        url = record.official_source_url
        if url in master_by_url:
            master_id = master_by_url[url]
            if record.preferred_id != master_by_url[url]:
                record.preferred_id = master_by_url[url]
                updated += 1
    return updated


def load_master_recovered(json_path: Path, master_by_url: dict[str, int]) -> list:
    """Load master recovered scholarships from JSON file."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    records = []
    for item in data:
        def parse_date(v):
            if v is None:
                return None
            if isinstance(v, str):
                try:
                    return datetime.fromisoformat(v.replace('Z', '+00:00')).date()
                except ValueError:
                    return None
            return v
        
        def parse_datetime(v):
            if v is None:
                return None
            if isinstance(v, str):
                try:
                    return datetime.fromisoformat(v.replace('Z', '+00:00'))
                except ValueError:
                    return None
            return v
        
        original_id = item.get('original_id')
        record = ScholarshipIngestionRecord(
            name=item['name'],
            country=item['country'],
            degree_levels=item['degree_levels'],
            funding_type=item['funding_type'],
            deadline=item['deadline'],
            deadline_date=parse_date(item.get('deadline_date')),
            deadline_precision=item.get('deadline_precision', 'unknown'),
            application_period=item.get('application_period', ''),
            eligibility_summary=item.get('eligibility_summary', ''),
            coverage=item.get('coverage', []),
            required_documents=item.get('required_documents', []),
            official_source_url=item['official_source_url'],
            official_source=item.get('official_source', ''),
            is_verified=item.get('is_verified', False),
            english_requirement=item.get('english_requirement', 'See official source for English requirements.'),
            best_fit=item.get('best_fit', ''),
            notes=item.get('notes', ''),
            # Master recovered records don't have verified images; set to empty to pass evidence gate
            image_url='',
            image_source_url='',
            image_source_type='',
            image_verified_at=None,
            image_kind='program_image',
            image_alt_text='',
            preferred_id=original_id,  # PRESERVE ORIGINAL ID
        )
        records.append(record)
    
    return records


def main() -> None:
    init_database()
    
    # Load master snapshot IDs for legacy URL compatibility
    master_by_url = load_master_snapshot_ids()
    
    # Apply master IDs to VERIFIED and ADDITIONAL records
    verified_updated = apply_master_ids(list(VERIFIED_SCHOLARSHIPS), master_by_url)
    additional_updated = apply_master_ids(list(ADDITIONAL_VERIFIED_SCHOLARSHIPS), master_by_url)
    print(f"Applied master IDs: {verified_updated} VERIFIED, {additional_updated} ADDITIONAL records updated")
    
    with get_session_factory()() as session:
        previous_ids = {
            source_url: session.scalar(
                select(Scholarship.id).where(Scholarship.official_source_url == source_url)
            )
            for source_url in RESULT_URLS
        }
        # Build canonical catalogue: MASTER RECOVERED first (to reserve original IDs), then VERIFIED, then ADDITIONAL
        verified_urls = {s.official_source_url for s in VERIFIED_SCHOLARSHIPS}
        additional_filtered = [s for s in ADDITIONAL_VERIFIED_SCHOLARSHIPS if s.official_source_url not in verified_urls]
        
        # Load master recovered scholarships from JSON FIRST (to reserve original IDs)
        json_path = BACKEND_ROOT / 'data' / 'master_recovered_scholarships.json'
        master_recovered_filtered = []
        if json_path.exists():
            master_recovered = load_master_recovered(json_path, master_by_url)
            # Filter out records already in canonical catalogue
            canonical_urls = verified_urls  # Only VERIFIED at this point
            master_recovered_filtered = [r for r in master_recovered if r.official_source_url not in canonical_urls]
            print(f"Master recovered: {len(master_recovered_filtered)} new (reserving original IDs)")
        else:
            print("Master recovered JSON not found, skipping")
        
        # Build canonical catalogue: MASTER RECOVERED first, then VERIFIED, then ADDITIONAL
        additional_filtered = [s for s in ADDITIONAL_VERIFIED_SCHOLARSHIPS if s.official_source_url not in verified_urls]
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