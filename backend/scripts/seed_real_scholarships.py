"""Run the canonical verified scholarship ingestion catalogue."""

from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.data.verified_scholarships import (  # noqa: E402
    EIFFEL_OFFICIAL_SOURCE_URL,
    SWISS_ESKAS_OFFICIAL_SOURCE_URL,
    VERIFIED_SCHOLARSHIPS,
)
from app.database import get_session_factory, init_database  # noqa: E402
from app.models import Scholarship  # noqa: E402
from app.services.scholarship_ingestion import upsert_verified_scholarships  # noqa: E402


RESULT_URLS = (EIFFEL_OFFICIAL_SOURCE_URL, SWISS_ESKAS_OFFICIAL_SOURCE_URL)


def main() -> None:
    init_database()
    with get_session_factory()() as session:
        previous_ids = {
            source_url: session.scalar(
                select(Scholarship.id).where(Scholarship.official_source_url == source_url)
            )
            for source_url in RESULT_URLS
        }
        created_count, updated_count = upsert_verified_scholarships(session, VERIFIED_SCHOLARSHIPS)
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
