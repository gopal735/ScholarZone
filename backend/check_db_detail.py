import sqlite3

def check_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    
    # Check image-related fields
    cursor.execute('SELECT COUNT(*) FROM scholarships WHERE image_url IS NOT NULL AND image_url != ""')
    print(f'Scholarships with image_url: {cursor.fetchone()[0]}')
    
    cursor.execute('SELECT COUNT(*) FROM scholarships WHERE image_verified_at IS NOT NULL')
    print(f'Scholarships with image_verified_at: {cursor.fetchone()[0]}')
    
    cursor.execute('SELECT image_source_type, COUNT(*) FROM scholarships GROUP BY image_source_type')
    for row in cursor.fetchall():
        print(f'  image_source_type={row[0]}: {row[1]}')
    
    # Check for duplicate IDs
    cursor.execute('SELECT id, COUNT(*) FROM scholarships GROUP BY id HAVING COUNT(*) > 1')
    dupes = cursor.fetchall()
    print(f'Duplicate scholarship IDs: {len(dupes)}')
    
    # Check foreign keys - application_records -> scholarships
    if 'application_records' in tables:
        cursor.execute('SELECT COUNT(*) FROM application_records')
        print(f'Application records: {cursor.fetchone()[0]}')
    else:
        print('Application records: TABLE MISSING')
    
    if 'saved_scholarships' in tables:
        cursor.execute('SELECT COUNT(*) FROM saved_scholarships')
        print(f'Saved scholarships: {cursor.fetchone()[0]}')
    else:
        print('Saved scholarships: TABLE MISSING')
    
    # Check maintenance data
    cursor.execute('SELECT COUNT(*) FROM maintenance_runs')
    print(f'Maintenance runs: {cursor.fetchone()[0]}')
    
    cursor.execute('SELECT * FROM maintenance_cursors')
    for row in cursor.fetchall():
        print(f'  Maintenance cursor: {row}')
    
    conn.close()

print("=== scholarzone.db (latest) ===")
check_db('scholarzone.db')

print("\n=== scholarzone.pre_integrity_repair_20261005_143934.db ===")
check_db('scholarzone.pre_integrity_repair_20261005_143934.db')

print("\n=== wave13_local.db ===")
check_db('wave13_local.db')

print("\n=== scholarzone.pre_wave13_master_20261004_201056.db ===")
check_db('scholarzone.pre_wave13_master_20261004_201056.db')