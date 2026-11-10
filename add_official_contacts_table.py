#!/usr/bin/env python3
"""
Add official_contacts table migration for supervisor discovery.
This is an additive migration - only adds new table, doesn't modify existing ones.
"""

import sqlite3

def add_official_contact_table(db_path: str = "backend/scholarzone.db"):
    """Add the official_contacts table to SQLite."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if table already exists
    cursor.execute("""
        SELECT name FROM sqlite_master WHERE type='table' AND name='official_contacts'
    """)
    if cursor.fetchone():
        print("official_contacts table already exists")
        conn.close()
        return
    
    # Create the table
    cursor.execute("""
        CREATE TABLE official_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scholarship_id INTEGER NOT NULL REFERENCES scholarships(id) ON DELETE CASCADE,
            institution_name TEXT NOT NULL,
            department_name TEXT,
            programme_name TEXT,
            contact_type TEXT NOT NULL DEFAULT 'programme_office',
            contact_role TEXT,
            published_contact_name TEXT,
            official_email TEXT,
            email_verified BOOLEAN NOT NULL DEFAULT 0,
            official_contact_url TEXT NOT NULL,
            evidence_source_url TEXT NOT NULL,
            evidence_source_type TEXT NOT NULL,
            evidence_summary TEXT,
            retrieved_at TIMESTAMP NOT NULL,
            verified_at TIMESTAMP,
            verification_status TEXT NOT NULL DEFAULT 'unverified',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX ix_official_contacts_scholarship_id ON official_contacts(scholarship_id)")
    cursor.execute("CREATE INDEX ix_official_contacts_institution ON official_contacts(institution_name)")
    cursor.execute("CREATE INDEX ix_official_contacts_verification ON official_contacts(verification_status)")
    cursor.execute("CREATE UNIQUE INDEX uq_official_contact_scholarship_url ON official_contacts(scholarship_id, official_contact_url)")
    
    conn.commit()
    
    # Verify
    cursor.execute("PRAGMA table_info(official_contacts)")
    columns = cursor.fetchall()
    print("official_contacts table created with columns:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    add_official_contact_table()