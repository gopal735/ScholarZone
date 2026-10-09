#!/usr/bin/env python3
"""
Generate a public-safe JSON snapshot from the local SQLite database.

Uses the canonical public visibility predicate:
- Exclude closed, archived, and quarantined records
- Do not gate catalogue inclusion on verification/image quality
- Serialize using the existing public response schema (ScholarshipDetailResponse fields)
- Never export admin notes, secrets, private session/user data, or internal review fields

Run from repository root: python generate_snapshot.py
"""

import sqlite3
import json
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any


def dict_from_row(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict[str, Any]:
    """Convert a sqlite3 row to a dict with proper type handling."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def normalize_list_field(value: Any) -> list[str]:
    """Normalize JSON list fields - accept string or list, return list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    if isinstance(value, str):
        return [value] if value.strip() else []
    return []


def normalize_date(value: Any) -> str | None:
    """Normalize date/datetime to ISO format string."""
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        if isinstance(value, datetime) and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, str):
        return value
    return str(value)


def generate_snapshot(db_path: str, output_path: str) -> dict[str, Any]:
    """Generate the public JSON snapshot from the local database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Calculate all counts from the actual database
    cursor.execute("SELECT COUNT(*) FROM scholarships")
    source_record_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM scholarships WHERE status = 'closed'")
    closed_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM scholarships WHERE is_archived = 1")
    archived_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM scholarships WHERE verification_status = 'quarantined'")
    quarantined_count = cursor.fetchone()[0]

    # Excluded union (accounting for overlaps)
    cursor.execute("""
        SELECT COUNT(*) FROM scholarships 
        WHERE status = 'closed' OR is_archived = 1 OR verification_status = 'quarantined'
    """)
    excluded_union = cursor.fetchone()[0]

    # Canonical public visibility predicate
    cursor.execute("""
        SELECT * FROM scholarships 
        WHERE status != 'closed' 
        AND is_archived = 0 
        AND verification_status != 'quarantined'
        ORDER BY id
    """)
    rows = cursor.fetchall()

    scholarships = []
    for row in rows:
        d = dict_from_row(cursor, row)

        # Build public-safe scholarship object matching ScholarshipDetailResponse schema
        scholarship = {
            "id": d["id"],
            "title": d["title"],
            "name": d["title"],  # alias for title
            "country": d["country"],
            "degree": d["degree"],
            "degree_levels": d["degree"],  # alias for degree
            "funding": d["funding"],
            "funding_type": d["funding"],  # alias for funding
            "deadline": d["deadline_display"] or d["deadline_date"],
            "deadline_date": normalize_date(d["deadline_date"]),
            "deadline_precision": d["deadline_precision"],
            "status": d["status"] if d["status"] in ("open", "upcoming", "closing-soon", "closed") else None,
            "verified": bool(d["is_verified"]),
            "last_verified_at": normalize_date(d["last_verified_at"]),
            "verification_status": d["verification_status"] or "uncertain",
            "official_source_url": d["official_source_url"],
            "updated_at": normalize_date(d["updated_at"]),
            "image_url": d["image_url"],
            "image_source_type": d["image_source_type"],
            "image_kind": d["image_kind"],
            # Detail-only fields
            "description": d["description"],
            "region": d["region"],
            "duration": d["duration"],
            "application_period": d["application_period"],
            "official_source": d["official_source"],
            "catalogue_url": d["catalogue_url"],
            "official_updates_url": d["official_updates_url"],
            "application_link": d["application_link"],
            "image_source_url": d["image_source_url"],
            "image_verified_at": normalize_date(d["image_verified_at"]),
            "image_alt_text": d["image_alt_text"],
            "eligibility": normalize_list_field(d["eligibility"]),
            "eligibility_summary": d["eligibility_summary"],
            "benefits": normalize_list_field(d["benefits"]),
            "coverage": normalize_list_field(d["coverage"]),
            "requirements": normalize_list_field(d["requirements"]),
            "documents": normalize_list_field(d["documents"]),
            "required_documents": normalize_list_field(d["documents"]),  # alias
            "english_requirement": d["english_requirement"],
            "application_method": normalize_list_field(d["application_method"]),
            "selection_notes": d["selection_notes"],
            "program_type": d["program_type"],
            "best_fit": d["best_fit"],
            "last_verified_date": normalize_date(d["last_verified_date"]),
            "notes": d["notes"],
        }
        scholarships.append(scholarship)

    # Compute stats matching ScholarshipStatsResponse
    total = len(scholarships)
    countries = len(set(s["country"] for s in scholarships if s["country"]))
    open_count = sum(1 for s in scholarships if s["status"] == "open")
    closing_soon = sum(1 for s in scholarships if s["status"] == "closing-soon")
    upcoming = sum(1 for s in scholarships if s["status"] == "upcoming")
    verified_active = sum(1 for s in scholarships if s["verification_status"] == "active")
    fully_funded = sum(1 for s in scholarships if "fully funded" in (s["funding"] or "").lower() and "partial" not in (s["funding"] or "").lower())
    with_image = sum(1 for s in scholarships if s["image_url"])
    with_official_source = sum(1 for s in scholarships if s["official_source"])

    stats = {
        "total": total,
        "countries": countries,
        "open": open_count,
        "closing_soon": closing_soon,
        "upcoming": upcoming,
        "verified_active": verified_active,
        "fully_funded": fully_funded,
        "with_image": with_image,
        "with_official_source": with_official_source,
    }

    # Build snapshot metadata
    snapshot = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source_database": Path(db_path).name,
            "source_record_count": source_record_count,
            "public_record_count": total,
            "excluded": {
                "closed": closed_count,
                "archived": archived_count,
                "quarantined": quarantined_count,
            },
            "excluded_union": excluded_union,
            "schema_version": "1.0",
            "visibility_predicate": "status != closed AND is_archived = false AND verification_status != quarantined",
        },
        "stats": stats,
        "scholarships": scholarships,
    }

    # Write JSON file
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    conn.close()
    return snapshot


if __name__ == "__main__":
    import sys
    
    # Default paths
    db_path = sys.argv[1] if len(sys.argv) > 1 else "backend/scholarzone.db"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "frontend/public/scholarships-snapshot.json"

    print(f"Generating snapshot from {db_path}...")
    snapshot = generate_snapshot(db_path, output_path)
    print(f"Generated {output_path}")
    print(f"  Public scholarships: {snapshot['meta']['public_record_count']}")
    print(f"  Stats: {snapshot['stats']}")