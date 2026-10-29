"""Rebuild the public scholarship snapshot from the local verified database.

Why this exists
---------------
The deployed API is down because its Neon Free project exceeded its monthly
transfer quota. The catalogue must stay browsable while that is resolved, and
the product should not silently offer a page that only works when somebody has
paid a bill.

The output is ``frontend/public/scholarships-snapshot.json``. It is the same
shape the frontend's static service already reads — ``meta``, ``stats`` and
``scholarships`` — so nothing on the client changes when the file appears.

The rules this script follows
-----------------------------
* Only rows that pass the **canonical public predicate** are written. The
  predicate is imported from the application, never re-implemented here, so
  this snapshot and the live directory can never disagree about who is
  visible.

* Closed, archived and quarantined records are excluded. Records whose
  deadline has passed are NOT excluded — they remain visible with their
  expired deadlines displayed honestly, per the public visibility contract.

* Internal review fields are never written. ``verification_notes``,
  ``reviewed_by``, quarantine reasons and supervisor review state stay in the
  database. What is written is the public contract only.

* Research enrichment (professor and email data) is **not** copied. That data
  is out of scope for this snapshot, so an unverified professor cannot be
  promoted by appearing in a public file — the file is simply not a source
  for it.

Run
---
    backend/.venv/Scripts/python.exe backend/scripts/build_public_snapshot.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

# Running as a script puts this file's directory on sys.path, not the backend
# root, so the app package would not import without help. Inserting the parent
# of the script's own directory (the backend root) fixes that regardless of
# the caller's working directory.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import get_session_factory  # noqa: E402
from app.models import Scholarship  # noqa: E402
from app.repositories.scholarships import (  # noqa: E402
    public_visibility_conditions,
)

REPO_ROOT = BACKEND_ROOT.parent
DEFAULT_OUTPUT = REPO_ROOT / "frontend" / "public" / "scholarships-snapshot.json"

#: The columns that form the public contract, in the order the frontend's
#: snapshot reader expects. Anything not listed here is not written — which
#: is how "no internal fields" is enforced rather than promised.
PUBLIC_COLUMNS: tuple[str, ...] = (
    "id",
    "title",
    "country",
    "degree",
    "funding",
    "description",
    "deadline_date",
    "deadline_display",
    "deadline_precision",
    "status",
    "verification_status",
    "last_verified_at",
    "last_verified_date",
    "official_source",
    "official_source_url",
    "application_link",
    "eligibility",
    "benefits",
    "requirements",
    "documents",
    "region",
    "duration",
    "application_period",
    "catalogue_url",
    "official_updates_url",
    "selection_notes",
    "program_type",
    "image_url",
    "image_source_url",
    "image_source_type",
    "image_kind",
    "image_verified_at",
    "image_alt_text",
    "fully_funded",
    "funding_amount",
    "funding_currency",
    "funding_period",
    "tuition_coverage",
    "living_cost_coverage",
    "travel_coverage",
    "eligibility_summary",
    "english_requirement",
    "application_method",
    "best_fit",
    "notes",
    "next_verification_due",
    "updated_at",
)

#: Research enrichment tables. Listed so the exclusion is explicit and a
#: future change cannot quietly start copying them by adding a column.
RESEARCH_TABLES: tuple[str, ...] = (
    "supervisors",
    "supervisor_reviews",
    "supervisor_candidates",
    "professors",
)


def _jsonable(value: Any) -> Any:
    """Render a value as JSON without a schema file.

    Dates become ISO strings because ``date`` is not JSON-serialisable, and
    everything else falls through unchanged. None stays None rather than
    becoming the string "None".
    """
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _record_to_public_dict(record: Scholarship) -> dict[str, Any]:
    """Project one row onto the public contract.

    The projection is by allow-list: a column that is not in
    ``PUBLIC_COLUMNS`` cannot reach the file even if the model gains it
    later. That is deliberate — a block-list would let the next column
    added to the model leak straight into a public asset.
    """
    row: dict[str, Any] = {}
    for column in PUBLIC_COLUMNS:
        value = getattr(record, column, None)
        # ``deadline_display`` is the column the frontend reads as the
        # human deadline; the snapshot writes it under both names so a
        # reader expecting either works.
        if column == "deadline_display":
            row["deadline"] = _jsonable(value)
        row[column] = _jsonable(value)

    # ``funding_type`` mirrors the dominant term so the client's funding
    # filter has a stable value to match on. It is derived, not stored, and
    # it is derived through the taxonomy so the two cannot drift.
    from app.services.taxonomy import canonical_funding_label

    row["funding_type"] = canonical_funding_label(record.funding)
    row["name"] = record.title
    return row


def _compute_stats(records: list[Scholarship]) -> dict[str, int]:
    """The public figures the snapshot header reports.

    Counted from the records actually written, not from the database, so the
    header can never claim a number the file does not contain.
    """
    today = date.today()
    countries = {record.country for record in records if record.country}

    closing_soon = 0
    upcoming = 0
    open_count = 0
    fully_funded = 0
    with_image = 0
    with_source = 0

    for record in records:
        if record.status == "open":
            open_count += 1
        target = record.deadline_date
        if target is not None:
            days = (target - today).days
            if days < 0:
                # Past deadline - do not count in deadline-specific stats,
                # but continue to count funding, image, source independently
                pass
            elif days <= 60:
                closing_soon += 1
            else:
                upcoming += 1
        if record.fully_funded:
            fully_funded += 1
        if record.image_url:
            with_image += 1
        if record.official_source_url:
            with_source += 1

    return {
        "total": len(records),
        "countries": len(countries),
        "open": open_count,
        "closing_soon": closing_soon,
        "upcoming": upcoming,
        "verified_active": sum(
            1 for r in records if r.verification_status == "active"
        ),
        "fully_funded": fully_funded,
        "with_image": with_image,
        "with_official_source": with_source,
    }


def build_payload(session: Session) -> dict[str, Any]:
    """The complete snapshot payload."""
    conditions = public_visibility_conditions()

    all_count = session.scalar(select(func.count()).select_from(Scholarship))
    closed_count = session.scalar(
        select(func.count())
        .select_from(Scholarship)
        .where(Scholarship.status == "closed")
    )
    archived_count = session.scalar(
        select(func.count())
        .select_from(Scholarship)
        .where(Scholarship.is_archived.is_(True))
    )
    quarantined_count = session.scalar(
        select(func.count())
        .select_from(Scholarship)
        .where(Scholarship.verification_status == "quarantined")
    )

    # The public predicate is the authority. Everything below counts what
    # it excluded so the header can say so, rather than the script
    # deciding who is visible a second time.
    records = list(
        session.scalars(
            select(Scholarship).where(*conditions).order_by(Scholarship.id)
        )
    )

    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_database": "scholarzone.db",
            "source_record_count": all_count or 0,
            "public_record_count": len(records),
            "excluded": {
                "closed": closed_count or 0,
                "archived": archived_count or 0,
                "quarantined": quarantined_count or 0,
            },
            #: The research tables this file deliberately does not read.
            #: Recorded so the omission is visible in the artefact.
            "research_tables_excluded": list(RESEARCH_TABLES),
        },
        "stats": _compute_stats(records),
        "scholarships": [_record_to_public_dict(record) for record in records],
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Where to write the snapshot (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Write nothing; report what would be written.",
    )
    args = parser.parse_args()

    factory = get_session_factory()
    with factory() as session:
        payload = build_payload(session)

    records = payload["scholarships"]
    meta = payload["meta"]

    print(f"database records:   {meta['source_record_count']}")
    print(f"public records:     {meta['public_record_count']}")
    print(f"  closed:           {meta['excluded']['closed']}")
    print(f"  archived:         {meta['excluded']['archived']}")
    print(f"  quarantined:      {meta['excluded']['quarantined']}")
    print(f"research tables:    excluded ({', '.join(RESEARCH_TABLES)})")

    if not records:
        # A snapshot with zero records is not a fallback, it is a false
        # promise of one. Fail loudly rather than shipping an empty file
        # that would read as "there are no scholarships".
        print("refusing to write an empty snapshot", file=sys.stderr)
        return 1

    if args.check:
        print(f"would write {len(records)} records to {args.output}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Written to a temp file and moved into place so an interrupted run
    # cannot leave a truncated JSON file that the frontend will cache.
    temporary = args.output.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1, separators=(",", ":"))
    temporary.replace(args.output)
    print(f"wrote {args.output} ({args.output.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
