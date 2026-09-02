"""Import additional verified scholarships into the database.

Run this script to add all newly verified scholarships from the
additional_scholarships module to the database.
"""

from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.data.additional_scholarships import ADDITIONAL_VERIFIED_SCHOLARSHIPS  # noqa: E402
from app.database import get_session_factory, init_database  # noqa: E402
from app.services.scholarship_ingestion import upsert_verified_scholarships  # noqa: E402


def main() -> None:
    init_database()
    print(f"Importing {len(ADDITIONAL_VERIFIED_SCHOLARSHIPS)} additional verified scholarships...")

    with get_session_factory()() as session:
        created_count, updated_count = upsert_verified_scholarships(session, ADDITIONAL_VERIFIED_SCHOLARSHIPS)

    print(f"Created {created_count} new scholarship record(s); updated {updated_count} existing record(s).")

    # Summary by country
    from collections import Counter
    country_counts = Counter(r.country for r in ADDITIONAL_VERIFIED_SCHOLARSHIPS)
    print("\nBreakdown by country:")
    for country, count in sorted(country_counts.items()):
        print(f"  {country}: {count} scholarships")


if __name__ == "__main__":
    main()
