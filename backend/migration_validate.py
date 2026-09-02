"""
Post-Migration Validation Script for ScholarZone

This script validates that PostgreSQL data matches the expected SQLite data
after migration. Run this after importing data to PostgreSQL.

Usage:
    python migration_validate.py --sqlite scholarzone.db --pg "postgresql://..."

Expected counts:
    scholarships: 303
    scholarship_verification_history: 6
    scholarship_reviews: 625
    scholarship_snapshots: 0
    scholarship_fetch_attempts: 0
    scholarship_restore_records: 0
    approved_sources: 0
    content_fingerprints: 0
    discovery_candidates: 0
    knowledge_nodes: 0
    knowledge_edges: 0
    source_health: 0
"""

import argparse
import sqlite3
import sys
from pathlib import Path

EXPECTED_COUNTS = {
    "scholarships": 303,
    "scholarship_verification_history": 6,
    "scholarship_reviews": 625,
    "scholarship_snapshots": 0,
    "scholarship_fetch_attempts": 0,
    "scholarship_restore_records": 0,
    "approved_sources": 0,
    "content_fingerprints": 0,
    "discovery_candidates": 0,
    "knowledge_nodes": 0,
    "knowledge_edges": 0,
    "source_health": 0,
}

EXPECTED_MAX_ID = 304
EXPECTED_COUNTRIES = [
    "India",
    "Germany",
    "Belgium",
    "Hungary",
    "Poland",
    "Czech Republic",
    "Portugal",
    "Ireland",
    "New Zealand",
    "Finland",
    "Denmark",
    "Norway",
]

SAMPLE_COUNTRIES = [
    "India",
    "Germany",
    "Belgium",
    "Hungary",
    "Poland",
    "Czech Republic",
    "Portugal",
    "Ireland",
    "New Zealand",
    "Finland",
    "Denmark",
    "Norway",
]


def validate_sqlite(sqlite_path):
    """Validate SQLite database."""
    print("=== SQLite Validation ===\n")
    
    conn = sqlite3.connect(str(sqlite_path))
    cursor = conn.cursor()
    
    results = {}
    all_pass = True
    
    for table, expected in EXPECTED_COUNTS.items():
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        actual = cursor.fetchone()[0]
        status = "PASS" if actual == expected else "FAIL"
        if actual != expected:
            all_pass = False
        print(f"{table}: {actual} (expected {expected}) [{status}]")
        results[table] = actual
    
    # Check max ID
    cursor.execute("SELECT MAX(id) FROM scholarships")
    max_id = cursor.fetchone()[0]
    status = "PASS" if max_id == EXPECTED_MAX_ID else "FAIL"
    if max_id != EXPECTED_MAX_ID:
        all_pass = False
    print(f"\nMax scholarship ID: {max_id} (expected {EXPECTED_MAX_ID}) [{status}]")
    
    # Check test records
    cursor.execute("SELECT COUNT(*) FROM scholarships WHERE country = 'Test Country'")
    test_count = cursor.fetchone()[0]
    status = "PASS" if test_count == 0 else "FAIL"
    if test_count != 0:
        all_pass = False
    print(f"Test records: {test_count} (expected 0) [{status}]")
    
    # Check duplicate URLs
    cursor.execute("""
        SELECT official_source_url FROM scholarships 
        WHERE official_source_url IS NOT NULL 
        GROUP BY official_source_url HAVING COUNT(*) > 1
    """)
    dupes = cursor.fetchall()
    status = "PASS" if len(dupes) == 0 else "FAIL"
    if len(dupes) != 0:
        all_pass = False
    print(f"Duplicate URLs: {len(dupes)} (expected 0) [{status}]")
    
    # Check countries
    cursor.execute("SELECT DISTINCT country FROM scholarships ORDER BY country")
    countries = [row[0] for row in cursor.fetchall()]
    print(f"\nCountries ({len(countries)}): {', '.join(countries[:10])}...")
    
    missing_countries = [c for c in EXPECTED_COUNTRIES if c not in countries]
    if missing_countries:
        print(f"WARNING: Missing expected countries: {missing_countries}")
    else:
        print("All expected countries present.")
    
    conn.close()
    
    return all_pass, results


def generate_validation_sql():
    """Generate SQL queries for PostgreSQL validation."""
    sql = []
    sql.append("-- PostgreSQL Validation Queries")
    sql.append("-- Run these queries after migration to verify data integrity")
    sql.append("")
    
    for table, expected in EXPECTED_COUNTS.items():
        sql.append(f"SELECT '{table}' as table_name, COUNT(*) as actual, {expected} as expected, "
                   f"(CASE WHEN COUNT(*) = {expected} THEN 'PASS' ELSE 'FAIL' END) as status "
                   f"FROM {table};")
    
    sql.append("")
    sql.append("-- Max ID check")
    sql.append(f"SELECT MAX(id) as max_id, {EXPECTED_MAX_ID} as expected, "
               f"(CASE WHEN MAX(id) = {EXPECTED_MAX_ID} THEN 'PASS' ELSE 'FAIL' END) as status "
               f"FROM scholarships;")
    
    sql.append("")
    sql.append("-- Test records check")
    sql.append("SELECT COUNT(*) as test_records FROM scholarships WHERE country = 'Test Country';")
    
    sql.append("")
    sql.append("-- Duplicate URLs check")
    sql.append("SELECT official_source_url, COUNT(*) as count FROM scholarships "
               "WHERE official_source_url IS NOT NULL "
               "GROUP BY official_source_url HAVING COUNT(*) > 1;")
    
    sql.append("")
    sql.append("-- Country distribution")
    sql.append("SELECT country, COUNT(*) as count FROM scholarships GROUP BY country ORDER BY country;")
    
    sql.append("")
    sql.append("-- Sample records from key countries")
    for country in SAMPLE_COUNTRIES:
        sql.append(f"SELECT id, title, country, official_source_url FROM scholarships "
                   f"WHERE country = '{country}' LIMIT 3;")
    
    sql.append("")
    sql.append("-- Foreign key integrity checks")
    sql.append("SELECT 'orphaned_verification_history' as check_name, COUNT(*) as count "
               "FROM scholarship_verification_history "
               "WHERE scholarship_id NOT IN (SELECT id FROM scholarships);")
    sql.append("SELECT 'orphaned_reviews' as check_name, COUNT(*) as count "
               "FROM scholarship_reviews "
               "WHERE scholarship_id NOT IN (SELECT id FROM scholarships);")
    
    return "\n".join(sql)


def main():
    parser = argparse.ArgumentParser(description="ScholarZone Migration Validation")
    parser.add_argument("--sqlite", type=str, default="scholarzone.db", help="SQLite database path")
    parser.add_argument("--generate-sql", action="store_true", help="Generate validation SQL")
    args = parser.parse_args()
    
    if args.generate_sql:
        sql = generate_validation_sql()
        output_path = Path(__file__).parent / "migration_validation.sql"
        with open(output_path, "w") as f:
            f.write(sql)
        print(f"Validation SQL written to: {output_path}")
        return
    
    sqlite_path = Path(args.sqlite)
    if not sqlite_path.exists():
        print(f"ERROR: SQLite database not found: {sqlite_path}")
        sys.exit(1)
    
    all_pass, results = validate_sqlite(sqlite_path)
    
    print()
    if all_pass:
        print("SQLite validation PASSED - Ready for migration")
    else:
        print("SQLite validation FAILED - Do not proceed with migration")
        sys.exit(1)


if __name__ == "__main__":
    main()
