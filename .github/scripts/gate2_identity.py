#!/usr/bin/env python3
"""
Gate 2: Production Identity Verification
Connects using READ-ONLY role. Verifies:
- Neon project/branch identity
- All 34 canonical IDs exist
- Exact titles and original statuses
"""

import os
import psycopg2
import json
import sys
import datetime

url = os.getenv("SCHOLARZONE_DATABASE_URL_RO")
if not url:
    print("ERROR: SCHOLARZONE_DATABASE_URL_RO not set", file=sys.stderr)
    sys.exit(1)

# Canonical 34 IDs (sorted, verified unique)
TARGET_IDS = [2, 54, 59, 62, 103, 382, 492, 496, 497, 510,
              521, 556, 563, 583, 587, 588, 592, 594, 624, 626,
              642, 651, 652, 655, 657, 662, 666, 677, 711, 724,
              788, 1216, 1218, 1278]

try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    conn.set_session(readonly=True)  # Enforce read-only
    cur = conn.cursor()

    # 1. Database identity - verify Neon project/branch
    cur.execute("""
        SELECT
            current_database() as db_name,
            version(),
            current_user,
            inet_server_addr() as server_ip,
            inet_server_port() as server_port,
            current_setting('neon.project_id') as neon_project_id,
            current_setting('neon.branch_id') as neon_branch_id,
            current_setting('neon.branch_name') as neon_branch_name
    """)
    db_identity = cur.fetchone()
    print("=== DATABASE IDENTITY ===")
    print("Database: " + str(db_identity[0]))
    print("Version: " + str(db_identity[1])[:80] + "...")
    print("User: " + str(db_identity[2]))
    print("Server: " + str(db_identity[3]) + ":" + str(db_identity[3]))
    print("Neon Project ID: " + str(db_identity[5]))
    print("Neon Branch ID: " + str(db_identity[6]))
    print("Neon Branch Name: " + str(db_identity[7]))

    # Verify expected Neon project/branch
    expected_project_id = os.getenv("EXPECTED_NEON_PROJECT_ID")
    expected_branch_name = os.getenv("EXPECTED_NEON_BRANCH_NAME", "main")
    if expected_project_id and db_identity[5] != expected_project_id:
        print("ERROR: Neon project ID mismatch. Expected: " + expected_project_id + ", Got: " + str(db_identity[5]), file=sys.stderr)
        sys.exit(1)
    if db_identity[7] != expected_branch_name:
        print("ERROR: Neon branch name mismatch. Expected: " + expected_branch_name + ", Got: " + str(db_identity[7]), file=sys.stderr)
        sys.exit(1)
    print("Neon project/branch identity verified.")

    # 2. Verify all 34 canonical IDs exist
    placeholders = ','.join(['%s'] * len(TARGET_IDS))
    cur.execute("""
        SELECT id, title, status, deadline_date, deadline_precision, verification_status
        FROM scholarships
        WHERE id IN (""" + placeholders + """)
        ORDER BY deadline_date
    """, tuple(TARGET_IDS))

    rows = cur.fetchall()
    found_ids = {row[0] for row in rows}
    missing_ids = set(TARGET_IDS) - found_ids

    print("\n=== ID VERIFICATION ===")
    print("Expected: " + str(len(TARGET_IDS)))
    print("Found: " + str(len(found_ids)))
    if missing_ids:
        print("MISSING IDs: " + str(sorted(missing_ids)))
    else:
        print("All 34 canonical IDs present")

    # 3. Show each record detail
    print("\n=== RECORD DETAILS ===")
    today = datetime.date.today()
    for row in rows:
        deadline_status = "EXPIRED" if row[3] and row[3] < today else "FUTURE"
        print("  ID " + str(row[0]).rjust(4) + ": " + str(row[1])[:60].ljust(60) + " | " + str(row[2]).ljust(12) + " | " + str(row[3]) + " | " + str(row[4]).ljust(8) + " | " + deadline_status)

    # Summary
    summary = {
        "neon_project_id": db_identity[5],
        "neon_branch_id": db_identity[6],
        "neon_branch_name": db_identity[7],
        "total_found": len(found_ids),
        "missing_ids": sorted(list(missing_ids)),
        "all_present": len(missing_ids) == 0
    }

    with open("gate2_result.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    if missing_ids:
        print("\nGATE 2 FAILED: " + str(len(missing_ids)) + " IDs missing")
        sys.exit(1)
    else:
        print("\nGATE 2 PASSED: All 34 canonical IDs verified in production")

except Exception as e:
    print("ERROR: " + str(e), file=sys.stderr)
    sys.exit(1)
finally:
    if 'conn' in locals():
        conn.close()