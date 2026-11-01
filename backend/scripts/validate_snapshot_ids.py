"""Validate exact equality of scholarship IDs across snapshot, sitemap, and ledger.

This script ensures that the three canonical sources of public scholarship IDs
are perfectly in sync:
  - snapshot IDs: frontend/public/scholarships-snapshot.json
  - sitemap IDs: frontend/public/sitemap.xml
  - ledger IDs: database query using public_visibility_conditions()

Any mismatch fails the CI build.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import get_session_factory, init_database
from app.models import Scholarship
from app.repositories.scholarships import public_visibility_conditions


REPO_ROOT = BACKEND_ROOT.parent
SNAPSHOT_PATH = REPO_ROOT / "frontend" / "public" / "scholarships-snapshot.json"
SITEMAP_PATH = REPO_ROOT / "frontend" / "public" / "sitemap.xml"


DATE_FIELDS = {
    "deadline_date",
    "last_verified_at",
    "last_verified_date",
    "next_verification_due",
    "archived_at",
    "auto_delete_candidate_since",
    "image_verified_at",
    "image_evaluated_at",
    "updated_at",
    "created_at",
    "reviewed_at",
    "fetched_at",
}


def _parse_date(value: Any) -> date | None:
    """Parse ISO date string to Python date object."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.replace("Z", "+00:00").split("T")[0])
        except ValueError:
            return None
    return None


def load_snapshot_ids() -> set[int]:
    """Extract scholarship IDs from the snapshot JSON."""
    if not SNAPSHOT_PATH.exists():
        raise FileNotFoundError(f"Snapshot not found at {SNAPSHOT_PATH}")
    with SNAPSHOT_PATH.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return {item["id"] for item in data.get("scholarships", [])}


def load_snapshot_scholarships() -> list[dict[str, Any]]:
    """Load full scholarship records from the snapshot JSON."""
    if not SNAPSHOT_PATH.exists():
        raise FileNotFoundError(f"Snapshot not found at {SNAPSHOT_PATH}")
    with SNAPSHOT_PATH.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data.get("scholarships", [])


def load_sitemap_ids() -> set[int]:
    """Extract scholarship IDs from the sitemap XML."""
    if not SITEMAP_PATH.exists():
        raise FileNotFoundError(f"Sitemap not found at {SITEMAP_PATH}")
    content = SITEMAP_PATH.read_text(encoding="utf-8")
    pattern = r"/scholarships/(\d+)"
    return {int(match) for match in re.findall(pattern, content)}


def seed_database_from_snapshot() -> None:
    """Initialize database and seed it with snapshot data."""
    init_database()
    factory = get_session_factory()
    with factory() as session:
        existing = session.execute(select(Scholarship.id)).scalars().all()
        if existing:
            return
        scholarships = load_snapshot_scholarships()
        # Get valid column names from the model
        valid_columns = {c.name for c in Scholarship.__table__.columns}
        for item in scholarships:
            record = Scholarship()
            for key, value in item.items():
                if key in valid_columns and hasattr(record, key):
                    if key in DATE_FIELDS:
                        value = _parse_date(value)
                    setattr(record, key, value)
            session.add(record)
        session.commit()


def load_ledger_ids() -> set[int]:
    """Extract scholarship IDs from the database using the canonical public predicate."""
    seed_database_from_snapshot()
    factory = get_session_factory()
    with factory() as session:
        stmt = select(Scholarship.id).where(*public_visibility_conditions())
        return {row[0] for row in session.execute(stmt).all()}


def main() -> int:
    snapshot_ids = load_snapshot_ids()
    sitemap_ids = load_sitemap_ids()
    ledger_ids = load_ledger_ids()

    print(f"Snapshot IDs: {len(snapshot_ids)}")
    print(f"Sitemap IDs:  {len(sitemap_ids)}")
    print(f"Ledger IDs:   {len(ledger_ids)}")

    if snapshot_ids != sitemap_ids:
        missing_in_sitemap = snapshot_ids - sitemap_ids
        extra_in_sitemap = sitemap_ids - snapshot_ids
        print("MISMATCH: snapshot != sitemap", file=sys.stderr)
        if missing_in_sitemap:
            print(f"  Missing in sitemap: {sorted(missing_in_sitemap)}", file=sys.stderr)
        if extra_in_sitemap:
            print(f"  Extra in sitemap:   {sorted(extra_in_sitemap)}", file=sys.stderr)
        return 1

    if snapshot_ids != ledger_ids:
        missing_in_ledger = snapshot_ids - ledger_ids
        extra_in_ledger = ledger_ids - snapshot_ids
        print("MISMATCH: snapshot != ledger", file=sys.stderr)
        if missing_in_ledger:
            print(f"  Missing in ledger: {sorted(missing_in_ledger)}", file=sys.stderr)
        if extra_in_ledger:
            print(f"  Extra in ledger:   {sorted(extra_in_ledger)}", file=sys.stderr)
        return 1

    if sitemap_ids != ledger_ids:
        missing_in_ledger = sitemap_ids - ledger_ids
        extra_in_ledger = ledger_ids - sitemap_ids
        print("MISMATCH: sitemap != ledger", file=sys.stderr)
        if missing_in_ledger:
            print(f"  Missing in ledger: {sorted(missing_in_ledger)}", file=sys.stderr)
        if extra_in_ledger:
            print(f"  Extra in ledger:   {sorted(extra_in_ledger)}", file=sys.stderr)
        return 1

    print("OK: snapshot == sitemap == ledger")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())