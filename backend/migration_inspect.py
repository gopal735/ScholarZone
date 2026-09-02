"""List all tables and their schemas in the SQLite database."""

import sqlite3
import json

conn = sqlite3.connect("scholarzone.db")
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row[0] for row in cursor.fetchall()]

print("=== TABLES ===")
for table in tables:
    print(f"\n--- {table} ---")
    
    # Get schema
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE name='{table}'")
    schema = cursor.fetchone()
    if schema and schema[0]:
        print(f"Schema: {schema[0][:200]}...")
    
    # Get column info
    cursor.execute(f"PRAGMA table_info({table})")
    columns = cursor.fetchall()
    print(f"Columns ({len(columns)}): {[col[1] for col in columns]}")
    
    # Get row count
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"Row count: {count}")
    
    # Get foreign keys
    cursor.execute(f"PRAGMA foreign_key_list({table})")
    fks = cursor.fetchall()
    if fks:
        print(f"Foreign keys: {[(fk[2], fk[3], fk[4]) for fk in fks]}")

conn.close()
