"""
Purge Manifest Generator

Generates a manifest of the 34 expired cycle records to be purged.
Uses the canonical target IDs and read-only database connection.
"""

import json
import sys
from datetime import datetime
from typing import Optional

from .manifest import CANONICAL_TARGET_IDS, TARGET_ID_SET
from .database import DatabaseAccessor, create_accessor
from .config import DatabaseConfig, PreflightConfig, load_config


def generate_purge_manifest(accessor: DatabaseAccessor, target_ids: list[int]) -> dict:
    """Generate a purge manifest for the target IDs."""
    manifest = {
        "manifest_version": "1.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "purge_reason": "Expired 2026 application cycles - all 34 cycles have passed their application deadlines",
        "total_records": len(target_ids),
        "target_ids": target_ids,
        "records": []
    }

    with accessor.connect_readonly() as conn:
        records = accessor.get_target_records(conn, target_ids)

        for row in records:
            record = {
                "id": row["id"],
                "title": row["title"],
                "country": row["country"],
                "degree": row.get("degree"),
                "funding": row.get("funding"),
                "funding_type": row.get("funding_type"),
                "deadline_date": str(row["deadline_date"]) if row.get("deadline_date") else None,
                "deadline_display": row.get("deadline_display"),
                "deadline_precision": row.get("deadline_precision"),
                "status": row.get("status"),
                "fully_funded": row.get("fully_funded"),
                "funding_amount": str(row["funding_amount"]) if row.get("funding_amount") else None,
                "funding_currency": row.get("funding_currency"),
                "funding_period": row.get("funding_period"),
                "tuition_coverage": row.get("tuition_coverage"),
                "living_cost_coverage": row.get("living_cost_coverage"),
                "travel_coverage": row.get("travel_coverage"),
                "accommodation": row.get("accommodation"),
                "insurance": row.get("insurance"),
                "insurance_coverage": row.get("insurance_coverage"),
                "duration": row.get("duration"),
                "conditions": row.get("conditions"),
                "funding_details": row.get("funding_details"),
                "official_source": row.get("official_source"),
                "official_source_url": row.get("official_source_url"),
                "official_details": row.get("official_details"),
                "applicant_utility": row.get("applicant_utility"),
                "programme_verification": row.get("programme_verification"),
                "auto_delete_candidate_since": str(row["auto_delete_candidate_since"]) if row.get("auto_delete_candidate_since") else None,
                "deletion_protected": row.get("deletion_protected"),
                "verification_status": row.get("verification_status"),
                "last_verified_at": str(row["last_verified_at"]) if row.get("last_verified_at") else None,
                "verified_by": row.get("verified_by"),
                "verification_notes": row.get("verification_notes"),
                "next_verification_due": str(row["next_verification_due"]) if row.get("next_verification_due") else None,
                "is_archived": row.get("is_archived"),
                "archived_at": str(row["archived_at"]) if row.get("archived_at") else None,
                "archived_reason": row.get("archived_reason"),
                "created_at": str(row["created_at"]) if row.get("created_at") else None,
                "updated_at": str(row["updated_at"]) if row.get("updated_at") else None,
            }
            manifest["records"].append(record)

    return manifest


def main() -> int:
    """CLI entry point for purge manifest generation."""
    print("Generating purge manifest...")
    print(f"Target IDs: {CANONICAL_TARGET_IDS}")
    print(f"Count: {len(CANONICAL_TARGET_IDS)}")
    print()

    try:
        config = load_config(gates_to_run={"gate2"})  # Uses readonly connection like gate2
        accessor = create_accessor(config.database)
    except ValueError as e:
        print(f"CONFIGURATION ERROR: {e}", file=sys.stderr)
        return 1

    manifest = generate_purge_manifest(accessor, CANONICAL_TARGET_IDS)

    # Write manifest
    with open("purge_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    print(f"\nPurge manifest generated successfully!")
    print(f"Total records: {manifest['total_records']}")
    print(f"Target IDs: {manifest['target_ids']}")

    # Verify all 34 IDs present
    record_ids = {r["id"] for r in manifest["records"]}
    expected_ids = set(CANONICAL_TARGET_IDS)
    missing = expected_ids - record_ids
    extra = record_ids - expected_ids

    if missing:
        print(f"WARNING: Missing IDs: {sorted(missing)}")
    if extra:
        print(f"WARNING: Extra IDs: {sorted(extra)}")

    if not missing and not extra:
        print("✅ All 34 canonical IDs present in manifest")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())