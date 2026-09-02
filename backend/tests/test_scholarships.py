"""Integration tests for the public scholarship API."""

import os
from datetime import date
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4


TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"scholarzone-test-{uuid4().hex}.db"
os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"

from pydantic import ValidationError  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402
from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from app.database import get_session_factory, reset_database_connections  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Scholarship  # noqa: E402
from app.seed import seed_database, seed_scholarships  # noqa: E402
from app.services.scholarship_ingestion import ScholarshipIngestionRecord, upsert_verified_scholarships  # noqa: E402


class ScholarshipApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
        os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
        reset_database_connections()
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        if TEST_DATABASE_PATH.exists():
            TEST_DATABASE_PATH.unlink()

    def test_list_scholarships_returns_seeded_data_and_pagination(self):
        response = self.client.get("/scholarships")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pagination"], {"page": 1, "limit": 12, "total": 63, "total_pages": 6})
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

        self.assertEqual([item["id"] for item in title_response.json()["items"]], [3, 21, 22, 23])
        self.assertEqual([item["id"] for item in country_response.json()["items"]], [3, 10, 21, 22, 23, 24])
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

        self.assertEqual([item["id"] for item in country_response.json()["items"]], [2, 11])
        self.assertEqual([item["id"] for item in degree_response.json()["items"]], [2])
        self.assertEqual([item["id"] for item in combined_response.json()["items"]], [3])

    def test_sorting_and_pagination_are_database_backed(self):
        earliest = self.client.get("/scholarships", params={"sort": "deadline-earliest"})
        latest = self.client.get("/scholarships", params={"sort": "deadline-latest"})
        name_asc = self.client.get("/scholarships", params={"sort": "name-asc"})
        page_two = self.client.get("/scholarships", params={"page": 2, "limit": 1})

        self.assertEqual([item["id"] for item in earliest.json()["items"]], [6, 2, 22, 28, 61, 29, 53, 58, 56, 21, 18, 14])
        self.assertEqual([item["id"] for item in latest.json()["items"]], [59, 54, 55, 14, 18, 21, 56, 53, 58, 29, 28, 61])
        self.assertEqual([item["id"] for item in name_asc.json()["items"]], [51, 54, 37, 38, 50, 31, 32, 30, 33, 57, 28, 43])
        self.assertEqual(page_two.json()["pagination"], {"page": 2, "limit": 1, "total": 63, "total_pages": 63})
        self.assertEqual(len(page_two.json()["items"]), 1)

    def test_extended_discovery_filters_and_sorting(self):
        funding_response = self.client.get("/scholarships", params={"funding": "Fully Funded"})
        month_response = self.client.get("/scholarships", params={"deadline_month": 10})
        search_response = self.client.get("/scholarships", params={"search": "master"})
        recommended_response = self.client.get("/scholarships", params={"sort": "recommended"})
        status_to_check = self.client.get("/scholarships").json()["items"][0]["status"]
        status_response = self.client.get("/scholarships", params={"status": status_to_check})

        self.assertEqual(len(funding_response.json()["items"]), 12)
        self.assertEqual([item["id"] for item in month_response.json()["items"]], [28, 29, 61])
        self.assertEqual([item["id"] for item in search_response.json()["items"]], [1, 3, 5, 6, 7, 8, 10, 13, 14, 15, 17, 19])
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
        with get_session_factory()() as session:
            self.assertEqual(seed_scholarships(session), 0)

    def test_verified_ingestion_is_idempotent_and_preserves_ids(self):
        test_url = "https://official.example.edu/scholarships/test-record"
        with self.assertRaises(ValidationError):
            ScholarshipIngestionRecord(
                name="Invalid Official Scholarship",
                country="Test Country",
                degree_levels="Master",
                funding_type="Fully Funded",
                official_source_url=" ",
            )

        initial_record = ScholarshipIngestionRecord(
            name="Test Official Scholarship",
            country="Test Country",
            degree_levels="Master",
            funding_type="Fully Funded",
            official_source_url=test_url,
        )
        updated_record = initial_record.model_copy(update={"name": "Updated Official Scholarship"})

        with get_session_factory()() as session:
            created_count, updated_count = upsert_verified_scholarships(session, (initial_record,))
            self.assertEqual((created_count, updated_count), (1, 0))
            created = session.scalar(select(Scholarship).where(Scholarship.official_source_url == test_url))
            self.assertIsNotNone(created)
            self.assertIsNone(created.region)
            self.assertEqual(created.coverage, [])
            created_id = created.id
            created.last_verified_date = date(2000, 1, 1)
            session.commit()

            created_count, updated_count = upsert_verified_scholarships(session, (updated_record,))
            self.assertEqual((created_count, updated_count), (0, 1))
            updated = session.scalar(select(Scholarship).where(Scholarship.official_source_url == test_url))
            self.assertEqual(updated.id, created_id)
            self.assertEqual(updated.title, "Updated Official Scholarship")
            self.assertEqual(updated.last_verified_date, date.today())

            with self.assertRaises(ValueError):
                upsert_verified_scholarships(session, (initial_record, updated_record))

            session.add(
                Scholarship(
                    title="Duplicate URL Scholarship",
                    country="Test Country",
                    degree="Master",
                    funding="Fully Funded",
                    official_source_url=test_url,
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()

            self.assertEqual(
                session.scalar(
                    select(func.count()).select_from(Scholarship).where(Scholarship.official_source_url == test_url)
                ),
                1,
            )
            session.delete(session.scalar(select(Scholarship).where(Scholarship.official_source_url == test_url)))
            session.commit()

    def test_verified_catalogue_records_remain_single_and_api_compatible(self):
        emjm_url = "https://erasmus-plus.ec.europa.eu"
        gks_url = "https://www.studyinkorea.go.kr"
        with get_session_factory()() as session:
            self.assertEqual(
                session.scalar(
                    select(func.count()).select_from(Scholarship).where(Scholarship.official_source_url == emjm_url)
                ),
                1,
            )
            self.assertEqual(
                session.scalar(
                    select(func.count()).select_from(Scholarship).where(Scholarship.official_source_url == gks_url)
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
