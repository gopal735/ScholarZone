#!/usr/bin/env python3
"""
Gate 3: Production Dependencies Verification
Connects using READ-ONLY role. Verifies:
- ALL foreign keys referencing scholarships.id (dynamic discovery)
- ON DELETE behavior for each FK
- CASCADE risks
- Exact references to all 34 target IDs
"""

import os
import psycopg2
import json
import sys

url = os.getenv("SCHOLARZONE_DATABASE_URL_RO")
if not url:
    print("ERROR: SCHOLARZONE_DATABASE_URL_RO not set", file=sys.stderr)
    sys.exit(1)

TARGET_IDS = [2, 54, 59, 62, 103, 382, 492, 496, 497, 510,
              521, 556, 563, 583, 587, 588, 592, 594, 624, 626,
              642, 651, 652, 655, 657, 662, 666, 677, 711, 724,
              788, 1216, 1218, 1278]

try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    conn.set_session(readonly=True)
    cur = conn.cursor()

    # 1. Discover ALL foreign keys referencing scholarships.id dynamically
    cur.execute("""
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS referenced_table,
            ccu.column_name AS referenced_column,
            rc.delete_rule AS on_delete_action,
            rc.update_rule AS on_update_action
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
        JOIN information_schema.referential_constraints rc
          ON rc.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_name = 'scholarships'
          AND ccu.column_name = 'id'
        ORDER BY tc.table_name, kcu.column_name
    """)
    fk_metadata = cur.fetchall()

    print("=== FOREIGN KEY METADATA (DYNAMIC DISCOVERY) ===")
    for row in fk_metadata:
        print("  " + str(row[0]) + "." + str(row[1]) + " -> " + str(row[2]) + "." + str(row[3]) + " | ON DELETE: " + str(row[4]) + " | ON UPDATE: " + str(row[5]))

    # 2. Check for CASCADE on any FK to scholarships
    cur.execute("""
        SELECT
            tc.table_name,
            kcu.column_name,
            rc.delete_rule
        FROM information_schema.referential_constraints rc
        JOIN information_schema.table_constraints tc ON rc.constraint_name = tc.constraint_name
        JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = rc.unique_constraint_name
        JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
        WHERE rc.delete_rule = 'CASCADE'
          AND tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_name = 'scholarships'
          AND ccu.column_name = 'id'
    """)
    cascade_fks = cur.fetchall()
    cascade_count = len(cascade_fks)
    print("\n=== CASCADE CHECK ===")
    if cascade_count > 0:
        print("FKs with ON DELETE CASCADE:")
        for row in cascade_fks:
            print("  " + str(row[0]) + "." + str(row[1]) + " -> ON DELETE " + str(row[2]))
    else:
        print("FKs with ON DELETE CASCADE: 0")

    # 3. Reference counts for target IDs across ALL referencing tables
    # First, get all tables/columns that reference scholarships
    cur.execute("""
        SELECT DISTINCT tc.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_name = 'scholarships'
          AND ccu.column_name = 'id'
    """)
    ref_tables = cur.fetchall()

    print("\n=== REFERENCE COUNTS TO TARGET IDs (ALL REFERENCING TABLES) ===")
    target_ids_tuple = tuple([2, 54, 59, 62, 103, 382, 492, 496, 497, 510,
                              521, 556, 563, 583, 587, 588, 592, 594, 624, 626,
                              642, 651, 652, 655, 657, 662, 666, 677, 711, 724,
                              788, 1216, 1218, 1278])

    total_refs = 0
    ref_details = {}
    for table, column in ref_tables:
        try:
            cur.execute("SELECT COUNT(*) FROM " + table + " WHERE " + column + " = ANY(%s)", (target_ids_tuple,))
            count = cur.fetchone()[0]
            ref_details[table] = count
            total_refs += count
            status = "OK" if count == 0 else "WARNING"
            print("  " + table + "." + column + ": " + str(count) + " " + status)
        except Exception as e:
            print("  " + table + ": ERROR - " + str(e))
            ref_details[table] = "ERROR: " + str(e)

    print("\nTotal references to 34 target IDs: " + str(total_refs))

    # 6. Summary
    summary = {
        "fk_metadata": [{"table": r[0], "column": r[1], "ref_table": r[2], "ref_column": r[3], "on_delete": r[4], "on_update": r[5]} for r in fk_metadata],
        "cascade_fk_count": len(cascade_fks),
        "cascade_details": [{"table": r[0], "column": r[1], "on_delete": r[2]} for r in cascade_fks],
        "reference_counts": ref_details,
        "total_references_to_targets": total_refs,
        "safe_to_delete": len(cascade_fks) == 0 and total_refs == 0
    }

    with open("gate3_result.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    if len(cascade_fks) > 0:
        print("\nGATE 3 FAILED: " + str(len(cascade_fks)) + " FKs with ON DELETE CASCADE")
        sys.exit(1)
    elif total_refs > 0:
        print("\nGATE 3 WARNING: " + str(total_refs) + " references to target IDs (review needed)")
    else:
        print("\nGATE 3 PASSED: No CASCADE, zero references to 34 target IDs")

except Exception as e:
    print("ERROR: " + str(e), file=sys.stderr)
    sys.exit(1)
finally:
    if 'conn' in locals():
        conn.close()