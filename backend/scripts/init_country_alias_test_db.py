#!/usr/bin/env python3
"""
Initialize test database for country alias integration tests.

Seeds the database with test records covering various country aliases
to verify PostgreSQL TRANSLATE-based ASCII folding works correctly.
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def init_country_alias_test_db():
    """Seed the database with test records for country alias testing."""
    # Import after setting environment variables to ensure correct database URL resolution
    from app.database import get_session_factory, init_database
    from app.models import Scholarship
    from sqlalchemy import text
    from datetime import date
    
    # Initialize database schema first
    print("Initializing database schema...")
    init_database()
    print("Database schema initialized.")
    
    session_factory = get_session_factory()
    session = session_factory()
    
    with session:
        # Clear existing test data
        session.execute(
            text("DELETE FROM scholarships WHERE official_source_url LIKE 'https://test.country.alias/%'")
        )
        session.execute(
            text("DELETE FROM scholarships WHERE official_source_url LIKE 'https://test.deadline/%'")
        )
        session.commit()
        
        # Test records covering various country aliases
        test_records = [
            # Türkiye aliases (diacritic handling)
            {
                "name": "Test Turkey Diacritic 1",
                "country": "Türkiye",
                "degree_levels": "Master",
                "funding_type": "Fully Funded",
                "official_source_url": "https://test.country.alias/turkiye-diacritic-1",
                "deadline_date": None,
                "deadline_precision": "none",
                "status": "open",
                "verification_status": "active",
                "fully_funded": True,
            },
            {
                "name": "Test Turkey ASCII 1",
                "country": "Turkiye",
                "degree_levels": "PhD",
                "funding_type": "Stipend",
                "official_source_url": "https://test.country.alias/turkiye-ascii-1",
                "deadline_date": None,
                "deadline_precision": "none",
                "status": "open",
                "verification_status": "active",
                "fully_funded": False,
            },
            {
                "name": "Test Turkey Canonical 1",
                "country": "Turkey",
                "degree_levels": "Master",
                "funding_type": "Tuition Fee Waiver",
                "official_source_url": "https://test.country.alias/turkey-canonical-1",
                "deadline_date": None,
                "deadline_precision": "none",
                "status": "open",
                "verification_status": "active",
                "fully_funded": False,
            },
            
            # USA aliases
            {
                "name": "Test USA Abbrev 1",
                "country": "USA",
                "degree_levels": "Bachelor",
                "funding_type": "Fully Funded",
                "official_source_url": "https://test.country.alias/usa-abbrev-1",
                "deadline_date": None,
                "deadline_precision": "none",
                "status": "open",
                "verification_status": "active",
                "fully_funded": True,
            },
            {
                "name": "Test US Abbrev 1",
                "country": "US",
                "degree_levels": "Master",
                "funding_type": "Stipend",
                "official_source_url": "https://test.country.alias/us-abbrev-1",
                "deadline_date": None,
                "deadline_precision": "none",
                "status": "open",
                "verification_status": "active",
                "fully_funded": False,
            },
            {
                "name": "Test USA Canonical 1",
                "country": "United States",
                "degree_levels": "PhD",
                "funding_type": "Fully Funded",
                "official_source_url": "https://test.country.alias/usa-canonical-1",
                "deadline_date": None,
                "deadline_precision": "none",
                "status": "open",
                "verification_status": "active",
                "fully_funded": True,
            },
            
            # UK aliases
            {
                "name": "Test UK Abbrev 1",
                "country": "UK",
                "degree_levels": "Master",
                "funding_type": "Fully Funded",
                "official_source_url": "https://test.country.alias/uk-abbrev-1",
                "deadline_date": None,
                "deadline_precision": "none",
                "status": "open",
                "verification_status": "active",
                "fully_funded": True,
            },
            {
                "name": "Test UK Canonical 1",
                "country": "United Kingdom",
                "degree_levels": "Bachelor",
                "funding_type": "Tuition Fee Waiver",
                "official_source_url": "https://test.country.alias/uk-canonical-1",
                "deadline_date": None,
                "deadline_precision": "none",
                "status": "open",
                "verification_status": "active",
                "fully_funded": False,
            },
            
            # Côte d'Ivoire (diacritic test)
            {
                "name": "Test Cote d'Ivoire Diacritic",
                "country": "Côte d'Ivoire",
                "degree_levels": "Master",
                "funding_type": "Fully Funded",
                "official_source_url": "https://test.country.alias/cote-ivoire-diacritic-1",
                "deadline_date": None,
                "deadline_precision": "none",
                "status": "open",
                "verification_status": "active",
                "fully_funded": True,
            },
            
            # São Tomé and Príncipe (diacritic test)
            {
                "name": "Test Sao Tome Diacritic",
                "country": "São Tomé and Príncipe",
                "degree_levels": "PhD",
                "funding_type": "Stipend",
                "official_source_url": "https://test.country.alias/sao-tome-diacritic-1",
                "deadline_date": None,
                "deadline_precision": "none",
                "status": "open",
                "verification_status": "active",
                "fully_funded": False,
            },
            
            # Vietnam / Viet Nam
            {
                "name": "Test Vietnam Canonical",
                "country": "Vietnam",
                "degree_levels": "Master",
                "funding_type": "Fully Funded",
                "official_source_url": "https://test.country.alias/vietnam-canonical-1",
                "deadline_date": None,
                "deadline_precision": "none",
                "status": "open",
                "verification_status": "active",
                "fully_funded": True,
            },
            {
                "name": "Test Viet Nam Alias",
                "country": "Viet Nam",
                "degree_levels": "PhD",
                "funding_type": "Stipend",
                "official_source_url": "https://test.country.alias/vietnam-alias-1",
                "deadline_date": None,
                "deadline_precision": "none",
                "status": "open",
                "verification_status": "active",
                "fully_funded": False,
            },
            
            # Control: non-matching country (Germany)
            {
                "name": "Test Germany Control",
                "country": "Germany",
                "degree_levels": "Master",
                "funding_type": "Fully Funded",
                "official_source_url": "https://test.country.alias/germany-control-1",
                "deadline_date": None,
                "deadline_precision": "none",
                "status": "open",
                "verification_status": "active",
                "fully_funded": True,
            },
            
            # Deadline test records
            {
                "name": "Test Deadline Exact",
                "country": "Test Country",
                "degree_levels": "Master",
                "funding_type": "Fully Funded",
                "official_source_url": "https://test.deadline/exact-1",
                "deadline_date": date(2027, 12, 15),
                "deadline_precision": "exact",
                "status": "open",
                "verification_status": "active",
                "fully_funded": True,
            },
        ]
        
        for record_data in test_records:
            sch = Scholarship(
                title=record_data["name"],
                country=record_data["country"],
                degree=record_data["degree_levels"],
                funding=record_data["funding_type"],
                official_source_url=record_data["official_source_url"],
                deadline_date=record_data.get("deadline_date"),
                deadline_precision=record_data.get("deadline_precision", "none"),
                status=record_data.get("status", "open"),
                verification_status=record_data.get("verification_status", "active"),
                fully_funded=record_data.get("fully_funded", False),
                created_at=None,
                updated_at=None,
            )
            session.add(sch)
        session.commit()
        
        # Verify inserted records
        test_urls = [r["official_source_url"] for r in test_records]
        result = session.execute(
            text("SELECT id, country, deadline_date FROM scholarships WHERE official_source_url = ANY(:urls)"),
            {"urls": test_urls}
        )
        inserted = result.fetchall()
        print(f"Inserted {len(inserted)} test records:")
        for row in inserted:
            print(f"  ID={row[0]}, country={row[1]}, deadline={row[2]}")


if __name__ == "__main__":
    # Set test environment BEFORE importing database module
    # This must happen before database module is imported
    os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
    os.environ["SCHOLARZONE_DATABASE_URL"] = os.environ.get(
        "SCHOLARZONE_DATABASE_URL",
        "postgresql://test:test@localhost:5439/country_alias_test?sslmode=disable"
    )
    
    # Verify we're using a test database with strict URL validation
    db_url = os.environ["SCHOLARZONE_DATABASE_URL"]
    
    # Strict URL validation - parse and verify each component
    from sqlalchemy.engine.url import make_url
    from urllib.parse import parse_qs
    
    url = make_url(db_url)
    
    if url.get_backend_name() != "postgresql":
        raise RuntimeError(
            f"SAFETY VIOLATION: This script must only run against PostgreSQL. "
            f"Current dialect: {url.get_backend_name()}"
        )
    
    if url.host != "localhost":
        raise RuntimeError(
            f"SAFETY VIOLATION: This script must only run against localhost. "
            f"Current host: {url.host}"
        )
    
    if url.port != 5439:
        raise RuntimeError(
            f"SAFETY VIOLATION: This script must only run on port 5439. "
            f"Current port: {url.port}"
        )
    
    if url.database != "country_alias_test":
        raise RuntimeError(
            f"SAFETY VIOLATION: This script must only run against country_alias_test database. "
            f"Current database: {url.database}"
        )
    
    if url.username != "test":
        raise RuntimeError(
            f"SAFETY VIOLATION: This script must only run with username 'test'. "
            f"Current username: {url.username}"
        )
    
    # Check sslmode query parameter
    query_string = str(url.query)
    from urllib.parse import parse_qs
    query = parse_qs(query_string)
    sslmode = query.get("sslmode", [None])[0]
    if sslmode != "disable":
        raise RuntimeError(
            f"SAFETY VIOLATION: This script must only run with sslmode=disable. "
            f"Current sslmode: {sslmode}"
        )
    
    print("All database safety checks passed.")
    
    # Clear cached database connections
    from app.database import reset_database_connections
    reset_database_connections()
    
    init_country_alias_test_db()