"""Integration tests for the public scholarship API."""

import os
from datetime import date
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
        cls.TestClient = TestClient
        cls.select = select
        cls.func = func
        cls.IntegrityError = IntegrityError
        cls.date = date
        cls.uuid4 = uuid4_local
        cls.Scholarship = Scholarship
        cls.get_session_factory = get_session_factory
        cls.seed_database = seed_database
        cls.seed_scholarships = seed_scholarships
        cls.ScholarshipIngestionRecord = ScholarshipIngestionRecord
        cls.upsert_verified_scholarships = upsert_verified_scholarships
        cls.ValidationError = ValidationError
        cls.TestClient = TestClient
        cls.select = select
        cls.func = func
        cls.IntegrityError = IntegrityError
        cls.date = date
        cls.uuid4 = uuid4_local
        cls.Scholarship = Scholarship

        # Create test client
        cls.client = TestClient(app)
        cls.client.__enter__()

        # Seed the database
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
        self.assertEqual(payload["pagination"], {"page": 1, "limit": 12, "total": 57, "total_pages": 5})
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
        self.assertIn("Bachelor's degree", response.json()["eligibility_summary"])
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

        self.assertEqual([item["id"] for item in title_response.json()["items"]], [3, 21, 23])
        self.assertEqual([item["id"] for item in country_response.json()["items"]], [3, 10, 21, 23, 24])
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

        self.assertEqual([item["id"] for item in country_response.json()["items"]], [11])
        self.assertEqual([item["id"] for item in degree_response.json()["items"]], [])
        self.assertEqual([item["id"] for item in combined_response.json()["items"]], [3])

    def test_sorting_and_pagination_are_database_backed(self):
        earliest = self.client.get("/scholarships", params={"sort": "deadline-earliest"})
        latest = self.client.get("/scholarships", params={"sort": "deadline-latest"})
        name_asc = self.client.get("/scholarships", params={"sort": "name-asc"})
        page_two = self.client.get("/scholarships", params={"page": 2, "limit": 1})

        self.assertEqual([item["id"] for item in earliest.json()["items"]], [53, 58, 56, 21, 18, 14, 55, 54, 59, 1, 3, 4])
        self.assertEqual([item["id"] for item in latest.json()["items"]], [59, 54, 55, 14, 18, 21, 56, 53, 58, 1, 3, 4])
        self.assertEqual([item["id"] for item in name_asc.json()["items"]], [51, 54, 37, 38, 50, 31, 32, 30, 33, 57, 43, 60])
        self.assertEqual(page_two.json()["pagination"], {"page": 2, "limit": 1, "total": 57, "total_pages": 57})
        self.assertEqual(len(page_two.json()["items"]), 1)

    def test_extended_discovery_filters_and_sorting(self):
        funding_response = self.client.get("/scholarships", params={"funding": "Fully Funded"})
        month_response = self.client.get("/scholarships", params={"deadline_month": 10})
        search_response = self.client.get("/scholarships", params={"search": "master"})
        recommended_response = self.client.get("/scholarships", params={"sort": "recommended"})
        status_to_check = self.client.get("/scholarships").json()["items"][0]["status"]
        status_response = self.client.get("/scholarships", params={"status": status_to_check})

        self.assertEqual(len(funding_response.json()["items"]), 12)
        self.assertEqual([item["id"] for item in month_response.json()["items"]], [])
        self.assertEqual([item["id"] for item in search_response.json()["items"]], [1, 3, 5, 7, 8, 10, 13, 14, 15, 17, 19, 20])
        self.assertEqual(recommended_response.status_code, 200)
        self.assertTrue(all(item["status"] == status_to_check for item in status_response.json()["items"]))

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
            self.assertEqual(
                session.scalar(
                    self.__class__.select(self.func.count()).select_from(self.Scholarship).where(self.Scholarship.official_source_url == gks_url)
                ),
                1,
            )

        gks_response = self.client.get("/scholarships/4")
        self.assertEqual(gks_response.status_code, 200)
        self.assertEqual(gks_response.json()["title"], "Global Korea Scholarship (GKS)")
        self.assertTrue(gks_response.json()["verified"])
        self.assertIsNotNone(gks_response.json()["last_verified_date"])

        mext_response = self.client.get("/scholarships/5")
        self.assertEqual(mext_response.status_code, 200)
        self.assertEqual(mext_response.json()["title"], "MEXT (Monbukagakusho) Scholarship")


if __name__ == "__main__":
    unittest.main()
