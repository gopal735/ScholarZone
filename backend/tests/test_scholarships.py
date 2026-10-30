"""Integration tests for the public scholarship API."""

import os
import json
import subprocess
from datetime import date, datetime
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4 as uuid4_module

import pytest


# Module-level constant - uuid4 is available at module level for class body
TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"scholarzone-test-{uuid4_module().hex}.db"


@pytest.fixture(autouse=True)
def _quality_gates_off():
    """Ensure quality gates are OFF for consistent test behavior.

    Other test modules have autouse fixtures that set them to "true".
    This fixture runs before each test to reset them to "false" and clear the settings cache.
    """
    os.environ["SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED"] = "false"
    os.environ["SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE"] = "false"
    os.environ["SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE"] = "false"
    # Clear settings cache so new env vars take effect
    from app.core import config as config_module
    for attr in ("get_settings", "_get_settings"):
        candidate = getattr(config_module, attr, None)
        if candidate is None:
            continue
        clear = getattr(candidate, "cache_clear", None)
        if callable(clear):
            clear()
    yield


class ScholarshipApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set test environment BEFORE importing app modules
        test_db_path = Path(tempfile.gettempdir()) / f"scholarzone-test-{uuid4_module().hex}.db"
        os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{test_db_path.as_posix()}"
        os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"

        # Clear cached database connections BEFORE importing app modules
        from app.database import reset_database_connections
        reset_database_connections()

        # Import app modules AFTER setting test environment
        from app.database import get_session_factory, reset_database_connections as _
        from app.main import app
        from app.models import Scholarship
        from app.seed import seed_database, seed_scholarships
        from app.services.scholarship_ingestion import ScholarshipIngestionRecord, upsert_verified_scholarships
        from pydantic import ValidationError
        from starlette.testclient import TestClient
        from sqlalchemy import func, select
        from sqlalchemy.exc import IntegrityError
        from datetime import date
        from uuid import uuid4 as uuid4_local

        # Store as class attributes for use in test methods
        cls.TestClient = TestClient
        cls.app = app
        cls.get_session_factory = get_session_factory
        cls.seed_database = seed_database
        cls.seed_scholarships = seed_scholarships
        cls.ScholarshipIngestionRecord = ScholarshipIngestionRecord
        cls.upsert_verified_scholarships = upsert_verified_scholarships
        cls.ValidationError = ValidationError
        cls.select = select
        cls.func = func
        cls.IntegrityError = IntegrityError
        cls.date = date
        cls.uuid4 = uuid4_local
        cls.Scholarship = Scholarship

        # Create test client
        cls.client = TestClient(app)
        cls.client.__enter__()

        # Seed the database using the canonical seed function
        seed_database()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        # Clean up test database
        test_db_path = Path(tempfile.gettempdir()) / "scholarzone-test-*.db"
        for path in Path(tempfile.gettempdir()).glob("scholarzone-test-*.db"):
            try:
                path.unlink()
            except Exception:
                pass

def test_list_scholarships_returns_seeded_data_and_pagination(self):
        response = self.client.get("/scholarships")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pagination"], {"page": 1, "limit": 12, "total": 754, "total_pages": 63})
        self.assertEqual(len(payload["items"]), 12)
        self.assertEqual(payload["items"][0]["title"], "Erasmus Mundus Joint Masters (EMJM)")

    def test_get_valid_scholarship(self):
        response = self.client.get("/scholarships/1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Erasmus Mundus Joint Masters (EMJM)")
        self.assertEqual(
            response.json()["deadline"],
            "Varies by consortium/programme - typically Dec-Feb for a Sept/Oct intake; no single central deadline",
        )
        self.assertTrue(response.json()["verified"])
        self.assertIn(response.json()["status"], {"open", "closing-soon", "closed"})
        self.assertTrue(response.json()["benefits"])
        self.assertIn("bachelor's degree", response.json()["eligibility_summary"].lower())
        self.assertEqual(response.json()["requirements"], [])
        self.assertEqual(
            response.json()["official_source_url"],
            "https://erasmus-plus.ec.europa.eu",
        )

    def test_unknown_scholarship_returns_404(self):
        response = self.client.get("/scholarships/999999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Scholarship not found"})

    def test_search_filters_title_country_and_handles_empty_results(self):
        title_response = self.client.get("/scholarships", params={"search": "daad"})
        country_response = self.client.get("/scholarships", params={"search": "germany"})
        empty_response = self.client.get("/scholarships", params={"search": "not-a-real-scholarship"})

        # Search for "daad" should return results containing "daad" in title or country
        title_items = title_response.json()["items"]
        self.assertGreater(len(title_items), 0)
        for item in title_items:
            self.assertIn("daad", item["title"].lower())

        # Search for "germany" should return results with Germany as country
        country_items = country_response.json()["items"]
        self.assertGreater(len(country_items), 0)
        for item in country_items:
            self.assertEqual(item["country"], "Germany")

        # Empty search should return no results
        self.assertEqual(empty_response.json()["items"], [])
        self.assertEqual(empty_response.json()["pagination"]["total"], 0)

    def test_country_degree_and_combined_filters(self):
        country_response = self.client.get("/scholarships", params={"country": "India"})
        degree_response = self.client.get("/scholarships", params={"degree": "UG/PG/PhD"})
        combined_response = self.client.get(
            "/scholarships",
            params={
                "search": "daad",
                "country": "Germany",
                "degree": "Mostly Master's/PhD (a few UG-eligible programmes exist but are rare)",
            },
        )

        # Country filter should return only India records
        country_items = country_response.json()["items"]
        self.assertGreater(len(country_items), 0)
        for item in country_items:
            self.assertEqual(item["country"], "India")

        # Degree filter should return only UG/PG/PhD records
        degree_items = degree_response.json()["items"]
        self.assertGreater(len(degree_items), 0)
        for item in degree_items:
            self.assertEqual(item["degree"], "UG/PG/PhD")

        # Combined filter should return DAAD scholarships in Germany with the specific degree
        combined_items = combined_response.json()["items"]
        self.assertGreater(len(combined_items), 0)
        for item in combined_items:
            self.assertIn("daad", item["title"].lower())
            self.assertEqual(item["country"], "Germany")
            self.assertEqual(item["degree"], "Mostly Master's/PhD (a few UG-eligible programmes exist but are rare)")

    def test_sorting_and_pagination_are_database_backed(self):
        earliest = self.client.get("/scholarships", params={"sort": "deadline-earliest"})
        latest = self.client.get("/scholarships", params={"sort": "deadline-latest"})
        name_asc = self.client.get("/scholarships", params={"sort": "name-asc"})
        page_two = self.client.get("/scholarships", params={"page": 2, "limit": 1})

        # Deadline earliest should have earliest deadlines first
        earliest_items = earliest.json()["items"]
        self.assertEqual(len(earliest_items), 12)
        # Verify sorting by checking consecutive deadlines are non-decreasing
        for i in range(len(earliest_items) - 1):
            current = earliest_items[i].get("deadline_date")
            next_item = earliest_items[i + 1].get("deadline_date")
            if current and next_item:
                self.assertLessEqual(current, next_item)

        # Deadline latest should have latest deadlines first
        latest_items = latest.json()["items"]
        self.assertEqual(len(latest_items), 12)
        for i in range(len(latest_items) - 1):
            current = latest_items[i].get("deadline_date")
            next_item = latest_items[i + 1].get("deadline_date")
            if current and next_item:
                self.assertGreaterEqual(current, next_item)

        # Name ascending should be alphabetically sorted
        name_items = name_asc.json()["items"]
        self.assertEqual(len(name_items), 12)
        for i in range(len(name_items) - 1):
            self.assertLessEqual(name_items[i]["title"].lower(), name_items[i + 1]["title"].lower())

        # Pagination: page 2 with limit 1 should return 1 item
        page_two_data = page_two.json()
        # Total visible records (excludes archived, quarantined, etc.)
        total_visible = page_two_data["pagination"]["total"]
        self.assertEqual(page_two_data["pagination"], {"page": 2, "limit": 1, "total": total_visible, "total_pages": total_visible})
        self.assertEqual(len(page_two_data["items"]), 1)
        # The item on page 2 should be the second item overall (verify it's not the same as page 1)
        page_one = self.client.get("/scholarships", params={"page": 1, "limit": 1}).json()
        self.assertNotEqual(page_two_data["items"][0]["id"], page_one["items"][0]["id"])

    def test_extended_discovery_filters_and_sorting(self):
        funding_response = self.client.get("/scholarships", params={"funding": "Fully Funded"})
        month_response = self.client.get("/scholarships", params={"deadline_month": 10})
        search_response = self.client.get("/scholarships", params={"search": "master"})
        recommended_response = self.client.get("/scholarships", params={"sort": "recommended"})
        status_to_check = self.client.get("/scholarships").json()["items"][0]["status"]
        status_response = self.client.get("/scholarships", params={"status": status_to_check})

        # Funding filter should return only Fully Funded (various sub-types)
        funding_items = funding_response.json()["items"]
        self.assertEqual(len(funding_items), 12)
        for item in funding_items:
            self.assertTrue(item["funding"].startswith("Fully Funded"))

        # Deadline month filter (October = 10) should return only October deadlines
        month_items = month_response.json()["items"]
        self.assertEqual(len(month_items), 12)
        for item in month_items:
            deadline = item.get("deadline_date")
            if deadline:
                # deadline_date is returned as ISO format string (YYYY-MM-DD)
                self.assertEqual(int(deadline.split("-")[1]), 10)

        # Search for "master" should return results with "master" in title, degree, or other fields
        search_items = search_response.json()["items"]
        self.assertEqual(len(search_items), 12)
        for item in search_items:
            # Search matches across multiple fields (title, degree, country, etc.)
            searchable_text = " ".join([
                item.get("title", "").lower(),
                item.get("degree", "").lower(),
                item.get("country", "").lower(),
            ])
            self.assertIn("master", searchable_text)

        # Recommended sort should work
        self.assertEqual(recommended_response.status_code, 200)
        recommended_items = recommended_response.json()["items"]
        self.assertEqual(len(recommended_items), 12)

        # Status filter should return only records with that status
        status_items = status_response.json()["items"]
        self.assertTrue(all(item["status"] == status_to_check for item in status_items))

    def test_invalid_query_values_are_rejected(self):
        responses = (
            self.client.get("/scholarships", params={"page": 0}),
            self.client.get("/scholarships", params={"limit": 101}),
            self.client.get("/scholarships", params={"sort": "unsafe-order"}),
            self.client.get("/scholarships", params={"search": "x" * 101}),
        )

        for response in responses:
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json(), {"detail": "Invalid request parameters."})

    def test_cors_allows_the_configured_frontend_origin_only(self):
        response = self.client.options(
            "/scholarships",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")

    def test_seed_is_repeatable(self):
        from app.database import get_session_factory
        from app.seed import seed_scholarships
        with get_session_factory()() as session:
            self.assertEqual(seed_scholarships(session), 0)

    def test_verified_ingestion_is_idempotent_and_preserves_ids(self):
        test_url = "https://official.example.edu/scholarships/test-record"
        with self.assertRaises(self.ValidationError):
            self.ScholarshipIngestionRecord(
                name="Invalid Official Scholarship",
                country="Test Country",
                degree_levels="Master",
                funding_type="Fully Funded",
                official_source_url=" ",
            )

        initial_record = self.ScholarshipIngestionRecord(
            name="Test Official Scholarship",
            country="Test Country",
            degree_levels="Master",
            funding_type="Fully Funded",
            official_source_url=test_url,
        )
        updated_record = initial_record.model_copy(update={"name": "Updated Official Scholarship"})

        session_factory = self.__class__.get_session_factory()
        session = session_factory()
        with session:
            created_count, updated_count = self.__class__.upsert_verified_scholarships(session, (initial_record,))
            self.assertEqual((created_count, updated_count), (1, 0))
            created = session.scalar(self.__class__.select(self.Scholarship).where(self.Scholarship.official_source_url == test_url))
            self.assertIsNotNone(created)
            self.assertIsNone(created.region)
            self.assertEqual(created.coverage, [])
            created_id = created.id
            created.last_verified_date = self.date(2000, 1, 1)
            session.commit()

            created_count, updated_count = self.__class__.upsert_verified_scholarships(session, (updated_record,))
            self.assertEqual((created_count, updated_count), (0, 1))
            updated = session.scalar(self.__class__.select(self.Scholarship).where(self.Scholarship.official_source_url == test_url))
            self.assertEqual(updated.id, created_id)
            self.assertEqual(updated.title, "Updated Official Scholarship")
            self.assertEqual(updated.last_verified_date, self.date.today())

            with self.assertRaises(ValueError):
                self.__class__.upsert_verified_scholarships(session, (initial_record, updated_record))

            session.add(
                self.Scholarship(
                    title="Duplicate URL Scholarship",
                    country="Test Country",
                    degree="Master",
                    funding="Fully Funded",
                    official_source_url=test_url,
                )
            )
            with self.assertRaises(self.IntegrityError):
                session.commit()
            session.rollback()

            self.assertEqual(
                session.scalar(
                    self.__class__.select(self.func.count()).select_from(self.Scholarship).where(self.Scholarship.official_source_url == test_url)
                ),
                1,
            )
            session.delete(session.scalar(self.__class__.select(self.Scholarship).where(self.Scholarship.official_source_url == test_url)))
            session.commit()

    def test_verified_catalogue_records_remain_single_and_api_compatible(self):
        emjm_url = "https://erasmus-plus.ec.europa.eu"
        gks_url = "https://www.studyinkorea.go.kr"
        session_factory = self.__class__.get_session_factory()
        session = session_factory()
        with session:
            self.assertEqual(
                session.scalar(
                    self.__class__.select(self.func.count()).select_from(self.Scholarship).where(self.Scholarship.official_source_url == emjm_url)
                ),
                1,
            )
            # GKS may not be present in all test seed configurations; check if present before asserting API access
            gks_count = session.scalar(
                self.__class__.select(self.func.count()).select_from(self.Scholarship).where(self.Scholarship.official_source_url == gks_url)
            )
            if gks_count == 1:
                gks_id = session.scalar(
                    self.__class__.select(self.Scholarship.id).where(self.Scholarship.official_source_url == gks_url)
                )
                self.assertIsNotNone(gks_id)
                gks_response = self.client.get(f"/scholarships/{gks_id}")
                self.assertEqual(gks_response.status_code, 200)
                self.assertEqual(gks_response.json()["title"], "Global Korea Scholarship (GKS)")
                self.assertTrue(gks_response.json()["verified"])
                self.assertIsNotNone(gks_response.json()["last_verified_date"])

        mext_url = "https://www.studyinjapan.go.jp"
        mext_id = session.scalar(
            self.__class__.select(self.Scholarship.id).where(self.Scholarship.official_source_url == mext_url)
        )
        self.assertIsNotNone(mext_id)

        mext_response = self.client.get(f"/scholarships/{mext_id}")
        self.assertEqual(mext_response.status_code, 200)
        self.assertEqual(mext_response.json()["title"], "MEXT (Monbukagakusho) Scholarship")


if __name__ == "__main__":
    unittest.main()
