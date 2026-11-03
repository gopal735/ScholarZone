#!/usr/bin/env python3
"""
Purge Manifest Generator
Generates a manifest of the 34 expired cycle records to be purged.
"""

import os
import json
import psycopg2
import sys
import datetime

# Canonical 34 target IDs (sorted, verified unique)
TARGET_IDS = [2, 54, 59, 62, 103, 382, 492, 496, 497, 510,
              521, 556, 563, 583, 587, 588, 592, 594, 624, 626,
              642, 651, 652, 655, 657, 662, 666, 677, 711, 724,
              788, 1216, 1218, 1278]

def generate_purge_manifest(database_url):
    """Generate a purge manifest for the 34 target IDs."""
    
    manifest = {
        "manifest_version": "1.0",
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "purge_reason": "Expired 2026 application cycles - all 34 cycles have passed their application deadlines",
        "total_records": 34,
        "target_ids": TARGET_IDS,
        "records": []
    }
    
    try:
        conn = psycopg2.connect(os.getenv("SCHOLARZONE_DATABASE_URL_RO"))
        conn.autocommit = True
        conn.set_session(readonly=True)
        cur = conn.cursor()
        
        placeholders = ','.join(['%s'] * len(TARGET_IDS))
        cur.execute(f"""
            SELECT 
                id, title, country, degree, funding, funding_type,
                deadline_date, deadline_display, deadline_precision,
                status, fully_funded, funding_amount, funding_currency,
                funding_period, tuition_coverage, living_cost_coverage,
                travel_coverage, accommodation, insurance, insurance_coverage,
                duration, conditions, funding_details, official_source,
                official_source_url, official_details, applicant_utility,
                programme_verification, auto_delete_candidate_since,
                deletion_protected, verification_status, last_verified_at,
                verified_by, verification_notes, next_verification_due,
                is_archived, archived_at, archived_reason,
                created_at, updated_at
            FROM scholarships
            WHERE id IN ({','.join(['%s'] * len(TARGET_IDS))})
            ORDER BY deadline_date
        """, tuple(TARGET_IDS))
        
        rows = cur.fetchall()
        
        for row in rows:
            record = {
                "id": row[0],
                "title": row[1],
                "country": row[2],
                "degree": row[3],
                "funding": row[4],
                "funding_type": row[5],
                "deadline_date": str(row[6]) if row[6] else None,
                "deadline_display": row[7],
                "deadline_precision": row[8],
                "status": row[9],
                "fully_funded": row[10],
                "funding_amount": str(row[11]) if row[11] else None,
                "funding_currency": row[12],
                "funding_period": row[13],
                "tuition_coverage": row[14],
                "living_cost_coverage": row[15],
                "travel_coverage": row[16],
                "accommodation": row[17],
                "insurance": row[17],
                "insurance_coverage": row[18],
                "duration": row[19],
                "conditions": row[20],
                "funding_details": row[21],
                "official_source": row[22],
                "official_source_url": row[23],
                "official_details": row[24],
                "applicant_utility": row[25],
                "programme_verification": row[26],
                "auto_delete_candidate_since": str(row[27]) if row[27] else None,
                "deletion_protected": row[28],
                "verification_status": row[29],
                "last_verified_at": str(row[30]) if row[30] else None,
                "verified_by": row[31],
                "verification_notes": row[32],
                "next_verification_due": str(row[33]) if row[33] else None,
                "is_archived": row[34],
                "archived_at": str(row[35]) if row[35] else None,
                "archived_reason": row[36],
                "created_at": str(row[37]) if row[37] else None,
                "updated_at": str(row[38]) if row[38] else None
            }
            manifest["records"].append(record)
        
        conn.close()
        
        # Write manifest
        with open("purge_manifest.json", "w") as f:
            json.dump(manifest, f, indent=2, default=str)
        
        print(f"Purge manifest generated: {len(manifest['records'])} records")
        return manifest
        
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    database_url = os.getenv("SCHOLARZONE_DATABASE_URL_RO")
    if not database_url:
        print("ERROR: SCHOLARZONE_DATABASE_URL_RO not set", file=sys.stderr)
        sys.exit(1)
    
    print("Generating purge manifest...")
    manifest = generate_purge_manifest(os.getenv("SCHOLARZONE_DATABASE_URL_RO"))
    
    print(f"\nPurge manifest generated successfully!")
    print(f"Total records: {manifest['total_records']}")
    print(f"Target IDs: {manifest['target_ids']}")
    
    # Verify all 34 IDs present
    record_ids = {r["id"] for r in manifest["records"]}
    expected_ids = set(TARGET_IDS)
    missing = set(TARGET_IDS) - record_ids
    extra = record_ids - set(TARGET_IDS)
    
    if missing:
        print(f"WARNING: Missing IDs: {sorted(missing)}")
    if extra:
        print(f"WARNING: Extra IDs: {sorted(extra)}")
    
    if not missing and not extra:
        print("✅ All 34 canonical IDs present in manifest")


if __name__ == "__main__":
    import os
    import psycopg2
    import json
    import sys
    import datetime
    main()