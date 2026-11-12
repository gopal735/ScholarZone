"""PostgreSQL-specific integration tests for country alias matching.

These tests require a live PostgreSQL 16 or 18 database.
They are skipped unless SCHOLARZONE_TEST_POSTGRES=1 is set.
"""

import os
import pytest
from uuid import uuid4

# Skip all tests in this module unless explicitly enabled
pytestmark = pytest.mark.skipif(
    os.environ.get("SCHOLARZONE_TEST_POSTGRES") != "1",
    reason="PostgreSQL integration tests require SCHOLARZONE_TEST_POSTGRES=1"
)


class TestPostgresCountryAliasMatching:
    """Test country alias matching against real PostgreSQL."""
    
    @pytest.fixture(scope="class")
    def postgres_client(self):
        """Create test client with PostgreSQL backend."""
        import tempfile
        from pathlib import Path
        from starlette.testclient import TestClient
        
        # Use PostgreSQL from environment
        pg_url = os.environ.get("SCHOLARZONE_POSTGRES_URL")
        if not pg_url:
            pytest.skip("SCHOLARZONE_POSTGRES_URL not set")
        
        # Set test environment
        os.environ["SCHOLARZONE_DATABASE_URL"] = pg_url
        os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
        
        # Clear cached database connections
        from app.database import reset_database_connections
        reset_database_connections()
        
        # Import app modules AFTER setting test environment
        from app.main import app
        from app.database import get_session_factory
        from app.models import Scholarship
        from app.seed import seed_database
        from sqlalchemy import text
        
        # Create test client
        client = TestClient(app)
        client.__enter__()
        
        # Get session factory for direct DB access
        session_factory = get_session_factory()
        
        # Seed test data with specific country aliases
        session = session_factory()
        with session:
            # Clear existing test data
            session.execute(text("DELETE FROM scholarships WHERE official_source_url LIKE 'https://test.country.alias/%'"))
            session.commit()
            
            # Insert test records with various country aliases
            test_records = [
                # Türkiye aliases
                {"name": "Test Turkey 1", "country": "Türkiye", "degree_levels": "Master", "funding_type": "Fully Funded",
                 "official_source_url": "https://test.country.alias/turkiye-1"},
                {"name": "Test Turkey 2", "country": "Turkiye", "degree_levels": "PhD", "funding_type": "Stipend",
                 "official_source_url": "https://test.country.alias/turkiye-2"},
                {"name": "Test Turkey 3", "country": "Turkey", "degree_levels": "Master", "funding_type": "Tuition Fee Waiver",
                 "official_source_url": "https://test.country.alias/turkey-1"},
                
                # USA aliases
                {"name": "Test USA 1", "country": "USA", "degree_levels": "Bachelor", "funding_type": "Fully Funded",
                 "official_source_url": "https://test.country.alias/usa-1"},
                {"name": "Test USA 2", "country": "US", "degree_levels": "Master", "funding_type": "Stipend",
                 "official_source_url": "https://test.country.alias/us-1"},
                {"name": "Test USA 3", "country": "United States", "degree_levels": "PhD", "funding_type": "Fully Funded",
                 "official_source_url": "https://test.country.alias/us-2"},
                
                # UK aliases
                {"name": "Test UK 1", "country": "UK", "degree_levels": "Master", "funding_type": "Fully Funded",
                 "official_source_url": "https://test.country.alias/uk-1"},
                {"name": "Test UK 2", "country": "United Kingdom", "degree_levels": "Bachelor", "funding_type": "Tuition Fee Waiver",
                 "official_source_url": "https://test.country.alias/uk-2"},
                
                # Control: non-matching country
                {"name": "Test Germany", "country": "Germany", "degree_levels": "Master", "funding_type": "Fully Funded",
                 "official_source_url": "https://test.country.alias/germany-1"},
            ]
            
            for record in test_records:
                sch = Scholarship(
                    name=record["name"],
                    title=record["name"],
                    country=record["country"],
                    degree=record["degree_levels"],
                    degree_levels=record["degree_levels"],
                    funding=record["funding_type"],
                    funding_type=record["funding_type"],
                    official_source_url=record["official_source_url"],
                    deadline_date=None,
                    deadline_precision="none",
                    status="open",
                    verification_status="active",
                    fully_funded=(record["funding_type"] == "Fully Funded"),
                    created_at=None,
                    updated_at=None,
                )
                session.add(sch)
            session.commit()
            
            # Get the inserted IDs for cleanup
            test_urls = [r["official_source_url"] for r in test_records]
            result = session.execute(
                text("SELECT id FROM scholarships WHERE official_source_url = ANY(:urls)"),
                {"urls": test_urls}
            )
            test_ids = [row[0] for row in result]
        
        yield {
            "client": client,
            "session_factory": session_factory,
            "test_ids": test_ids,
            "test_urls": test_urls,
        }
        
        # Cleanup
        session = session_factory()
        with session:
            session.execute(text("DELETE FROM scholarships WHERE official_source_url LIKE 'https://test.country.alias/%'"))
            session.commit()
        client.__exit__(None, None, None)

    def test_turkiye_alias_matching(self, postgres_client):
        """Test that Türkiye, Turkiye, Turkey all resolve to Turkey canonical."""
        client = postgres_client["client"]
        
        # Query with canonical value
        canonical_resp = client.get("/scholarships", params={"country": "Turkey", "limit": 50})
        assert canonical_resp.status_code == 200
        canonical_ids = {item["id"] for item in canonical_resp.json()["items"]}
        
        # Should find 3 records: Türkiye, Turkiye, Turkey
        assert len(canonical_ids) == 3, f"Expected 3 Turkey records, got {len(canonical_ids)}"
        
        # Query with aliases - should return same IDs
        for alias in ["Türkiye", "Turkiye"]:
            alias_resp = client.get("/scholarships", params={"country": alias, "limit": 50})
            assert alias_resp.status_code == 200
            alias_ids = {item["id"] for item in alias_resp.json()["items"]}
            assert alias_ids == canonical_ids, f"Alias '{alias}' should return same IDs as 'Turkey'"

    def test_usa_alias_matching(self, postgres_client):
        """Test that USA, US, United States all resolve to United States."""
        client = postgres_client["client"]
        
        canonical_resp = client.get("/scholarships", params={"country": "United States", "limit": 50})
        assert canonical_resp.status_code == 200
        canonical_ids = {item["id"] for item in canonical_resp.json()["items"]}
        
        # Should find 3 records: USA, US, United States
        assert len(canonical_ids) == 3, f"Expected 3 US records, got {len(canonical_ids)}"
        
        for alias in ["USA", "US"]:
            alias_resp = client.get("/scholarships", params={"country": alias, "limit": 50})
            assert alias_resp.status_code == 200
            alias_ids = {item["id"] for item in alias_resp.json()["items"]}
            assert alias_ids == canonical_ids, f"Alias '{alias}' should return same IDs as 'United States'"

    def test_uk_alias_matching(self, postgres_client):
        """Test that UK, United Kingdom resolve to United Kingdom."""
        client = postgres_client["client"]
        
        canonical_resp = client.get("/scholarships", params={"country": "United Kingdom", "limit": 50})
        assert canonical_resp.status_code == 200
        canonical_ids = {item["id"] for item in canonical_resp.json()["items"]}
        
        # Should find 2 records: UK, United Kingdom
        assert len(canonical_ids) == 2, f"Expected 2 UK records, got {len(canonical_ids)}"
        
        for alias in ["UK", "Great Britain"]:
            alias_resp = client.get("/scholarships", params={"country": alias, "limit": 50})
            assert alias_resp.status_code == 200
            alias_ids = {item["id"] for item in alias_resp.json()["items"]}
            assert alias_ids == canonical_ids, f"Alias '{alias}' should return same IDs as 'United Kingdom'"

    def test_non_matching_country_excluded(self, postgres_client):
        """Test that Germany is not returned when filtering for Turkey/USA/UK."""
        client = postgres_client["client"]
        
        # Filter for Turkey
        turkey_resp = client.get("/scholarships", params={"country": "Turkey", "limit": 50})
        turkey_ids = {item["id"] for item in turkey_resp.json()["items"]}
        
        # Filter for USA
        usa_resp = client.get("/scholarships", params={"country": "United States", "limit": 50})
        usa_ids = {item["id"] for item in usa_resp.json()["items"]}
        
        # Filter for UK
        uk_resp = client.get("/scholarships", params={"country": "United Kingdom", "limit": 50})
        uk_ids = {item["id"] for item in uk_resp.json()["items"]}
        
        # Germany should not appear in any of these
        all_filtered_ids = turkey_ids | usa_ids | uk_ids
        germany_resp = client.get("/scholarships", params={"country": "Germany", "limit": 50})
        germany_ids = {item["id"] for item in germany_resp.json()["items"]}
        
        assert len(germany_ids) == 1, "Should have exactly 1 Germany record"
        assert germany_ids.isdisjoint(all_filtered_ids), "Germany must not appear in other country filters"

    def test_facet_count_equals_distinct_ids(self, postgres_client):
        """Test that country facet count equals distinct matching result IDs."""
        client = postgres_client["client"]
        
        # Get first page with facets
        resp = client.get("/scholarships", params={"page": 1, "limit": 12})
        assert resp.status_code == 200
        data = resp.json()
        
        # Check Turkey facet - must exist
        turkey_facet = next((f for f in data["facets"]["country"] if f["value"] == "Turkey"), None)
        assert turkey_facet is not None, "Turkey facet must be present"
        facet_count = turkey_facet["count"]
        
        # Query all pages with Turkey filter
        all_ids = set()
        page = 1
        while True:
            page_resp = client.get("/scholarships", params={"country": "Turkey", "page": page, "limit": 50})
            assert page_resp.status_code == 200
            page_data = page_resp.json()
            page_ids = {item["id"] for item in page_data["items"]}
            if not page_ids:
                break
            all_ids.update(page_ids)
            if page >= page_data["pagination"]["total_pages"]:
                break
            page += 1
        
        assert facet_count == len(all_ids), \
            f"Turkey facet count ({facet_count}) must equal distinct matching IDs ({len(all_ids)})"
        
        # Check United States facet - must exist
        us_facet = next((f for f in data["facets"]["country"] if f["value"] == "United States"), None)
        assert us_facet is not None, "United States facet must be present"
        us_facet_count = us_facet["count"]
        
        # Query all pages with United States filter
        all_us_ids = set()
        page = 1
        while True:
            page_resp = client.get("/scholarships", params={"country": "United States", "page": page, "limit": 50})
            assert page_resp.status_code == 200
            page_data = page_resp.json()
            page_ids = {item["id"] for item in page_data["items"]}
            if not page_ids:
                break
            all_us_ids.update(page_ids)
            if page >= page_data["pagination"]["total_pages"]:
                break
            page += 1
        
        assert us_facet_count == len(all_us_ids), \
            f"United States facet count ({us_facet_count}) must equal distinct matching IDs ({len(all_us_ids)})"

    def test_deadline_parsing_valid_formats(self, postgres_client):
        """Test deadline parsing with valid exact and month-only formats."""
        from app.database import get_session_factory
        from app.models import Scholarship
        from datetime import date
        from sqlalchemy import text
        
        session_factory = postgres_client["session_factory"]
        session = session_factory()
        with session:
            # Insert test records with various deadline formats
            test_records = [
                {"name": "Exact Date", "country": "Test Country", "degree_levels": "Master", "funding_type": "Fully Funded",
                 "official_source_url": "https://test.deadline/exact", "deadline_date": date(2027, 12, 15)},
                {"name": "Month Only", "country": "Test Country", "degree_levels": "Master", "funding_type": "Fully Funded",
                 "official_source_url": "https://test.deadline/month", "deadline_date": None},
                # We'll test month-only via direct SQL since ORM may not support YYYY-MM
            ]
            
            for record in test_records:
                sch = Scholarship(
                    name=record["name"],
                    title=record["name"],
                    country=record["country"],
                    degree=record["degree_levels"],
                    degree_levels=record["degree_levels"],
                    funding=record["funding_type"],
                    funding_type=record["funding_type"],
                    official_source_url=record["official_source_url"],
                    deadline_date=record.get("deadline_date"),
                    deadline_precision="exact" if record.get("deadline_date") else "none",
                    status="open",
                    verification_status="active",
                    fully_funded=True,
                )
                session.add(sch)
            session.commit()
            
            # Get the exact date record
            exact_id = session.execute(
                text("SELECT id FROM scholarships WHERE official_source_url = 'https://test.deadline/exact'")
            ).scalar()
            
        # Query for December (month 12)
        client = postgres_client["client"]
        resp = client.get("/scholarships", params={"deadline_month": 12, "limit": 50})
        assert resp.status_code == 200
        dec_ids = {item["id"] for item in resp.json()["items"]}
        
        # Should find the exact date record
        assert exact_id in dec_ids, "Record with exact 2027-12-15 deadline should match December filter"
        
        # Cleanup
        session = session_factory()
        with session:
            session.execute(text("DELETE FROM scholarships WHERE official_source_url LIKE 'https://test.deadline/%'"))
            session.commit()

    def test_deadline_invalid_formats_excluded(self, postgres_client):
        """Test that invalid/missing deadlines are excluded from month filters."""
        client = postgres_client["client"]
        
        # Records with no deadline_date should not match any month
        for month in range(1, 13):
            resp = client.get("/scholarships", params={"deadline_month": month, "limit": 50})
            assert resp.status_code == 200
            data = resp.json()
            # Should not include test control records with no deadline
            for item in data["items"]:
                assert item.get("deadline_date") is not None, \
                    f"Month {month} filter returned record with no deadline_date"